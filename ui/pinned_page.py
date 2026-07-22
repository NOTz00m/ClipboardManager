from PySide6.QtWidgets import (QFrame, QVBoxLayout, QWidget, QLabel,
                                QScrollArea, QApplication)
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import SearchLineEdit

from ui.clipboard_card import ClipboardCard
from encryption import decrypt_text
from content_detection import detect_language, detect_content_type


class PinnedPage(QFrame):
    # pinned and favorited items view

    def __init__(self, db_manager, fernet, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.fernet = fernet
        self.setObjectName("pinnedPage")
        self._selected_card_id = None
        self._setup_ui()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.load_entries)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Pinned & favorites")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Search bar
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Search pinned...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search)
        layout.addWidget(self.search_bar)

        # Scrollable card list
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(8)

        self.empty_label = QLabel("Pin or favorite an item to keep it close", self.card_container)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #6B7280; padding: 60px 24px;")
        self.empty_label.setVisible(False)
        self.card_layout.addWidget(self.empty_label)

        self.card_layout.addStretch()

        self.scroll_area.setWidget(self.card_container)
        layout.addWidget(self.scroll_area, 1)

    def _on_search(self, text):
        self.search_timer.start()

    def load_entries(self):
        # Reload pinned items and favorited snippets
        for i in reversed(range(self.card_layout.count())):
            item = self.card_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ClipboardCard):
                w = item.widget()
                self.card_layout.removeWidget(w)
                w.deleteLater()

        search_term = self.search_bar.text().strip().lower()
        rendered = 0

        entries = self.db_manager.get_saved_history_entries()
        for entry in entries:
            entry_id, enc_text, timestamp, is_code, pinned, favorite = entry
            if not pinned and not favorite:
                continue

            decrypted_text = decrypt_text(enc_text, self.fernet)
            if search_term and search_term not in decrypted_text.lower():
                continue

            content_type = detect_content_type(decrypted_text)
            language = detect_language(decrypted_text) if is_code else "Text"
            title = self._extract_title(decrypted_text, content_type)
            preview = self._extract_preview(decrypted_text)

            card = ClipboardCard(
                entry_id=entry_id,
                title=title,
                preview_text=preview,
                timestamp=timestamp,
                language=language,
                content_type=content_type,
                is_pinned=bool(pinned),
                is_favorite=bool(favorite),
                show_pin=True,
                show_favorite=True,
                show_edit=False,
                show_copy=True,
                show_delete=True,
                show_timestamp=getattr(self.window(), 'settings', {}).get('show_timestamps', True),
                parent=self.card_container
            )

            card.copyClicked.connect(self._on_copy)
            card.pinClicked.connect(self._on_unpin)
            card.favoriteClicked.connect(self._on_unstar)
            card.deleteClicked.connect(self._on_delete)
            card.cardClicked.connect(self._on_card_click)

            self.card_layout.insertWidget(rendered, card)
            rendered += 1

        snippets = self.db_manager.get_favorite_snippets()
        for snippet in snippets:
            snippet_id, title, enc_text, language, timestamp, favorite = snippet
            if not favorite:
                continue

            decrypted_text = decrypt_text(enc_text, self.fernet)
            if search_term and search_term not in decrypted_text.lower():
                continue

            preview = decrypted_text.strip()
            if len(preview) > 100:
                preview = preview[:97] + "..."

            card = ClipboardCard(
                entry_id=-snippet_id,
                title=title,
                preview_text=preview,
                timestamp=timestamp,
                language=language,
                content_type='code',
                is_pinned=False,
                is_favorite=True,
                show_pin=False,
                show_favorite=True,
                show_edit=False,
                show_copy=True,
                show_delete=True,
                show_timestamp=getattr(self.window(), 'settings', {}).get('show_timestamps', True),
                parent=self.card_container
            )

            card.copyClicked.connect(self._on_copy_snippet)
            card.favoriteClicked.connect(self._on_unstar_snippet)
            card.deleteClicked.connect(self._on_delete_snippet)
            card.cardClicked.connect(self._on_card_click)

            self.card_layout.insertWidget(rendered, card)
            rendered += 1

        self.empty_label.setVisible(rendered == 0)

    def _extract_title(self, text, content_type):
        if content_type == "link":
            first_line = text.strip().split('\n')[0]
            return first_line[:57] + "..." if len(first_line) > 60 else first_line
        lines = text.strip().split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped:
                return stripped[:57] + "..." if len(stripped) > 60 else stripped
        return "Empty entry"

    def _extract_preview(self, text):
        lines = text.strip().split('\n')
        preview_lines = [l.strip() for l in lines[1:4] if l.strip()]
        if preview_lines:
            preview = '  '.join(preview_lines)
            return preview[:97] + "..." if len(preview) > 100 else preview
        text_flat = text.strip()
        return text_flat[:97] + "..." if len(text_flat) > 100 else text_flat

    def _on_copy(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            decrypted = decrypt_text(row[0], self.fernet)
            window = self.window()
            if hasattr(window, "copy_text"):
                window.copy_text(decrypted)
            else:
                QApplication.clipboard().setText(decrypted)

    def _on_copy_snippet(self, neg_snippet_id):
        snippet_id = abs(neg_snippet_id)
        snippet = self.db_manager.get_snippet_by_id(snippet_id)
        if snippet:
            decrypted = decrypt_text(snippet[2], self.fernet)
            window = self.window()
            if hasattr(window, "copy_text"):
                window.copy_text(decrypted)
            else:
                QApplication.clipboard().setText(decrypted)

    def _on_unpin(self, entry_id):
        self.db_manager.update_pin_state(entry_id, 0)
        QTimer.singleShot(0, self.load_entries)

    def _on_unstar(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            self.db_manager.update_favorite_state(entry_id, 0 if row[2] else 1)
        QTimer.singleShot(0, self.load_entries)

    def _on_unstar_snippet(self, neg_snippet_id):
        snippet_id = abs(neg_snippet_id)
        self.db_manager.update_snippet_favorite(snippet_id, 0)
        QTimer.singleShot(0, self.load_entries)

    def _on_delete(self, entry_id):
        self.db_manager.delete_entry_by_id(entry_id)
        QTimer.singleShot(0, self.load_entries)

    def _on_delete_snippet(self, neg_snippet_id):
        snippet_id = abs(neg_snippet_id)
        self.db_manager.delete_snippet_by_id(snippet_id)
        QTimer.singleShot(0, self.load_entries)

    def _on_card_click(self, entry_id):
        self._selected_card_id = entry_id
        for i in range(self.card_layout.count()):
            item = self.card_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ClipboardCard):
                item.widget().setSelected(item.widget().entry_id == entry_id)

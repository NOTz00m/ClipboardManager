from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QWidget,
                                QScrollArea, QLabel, QApplication, QSizePolicy)
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import SearchLineEdit, SegmentedWidget, InfoBar

from ui.clipboard_card import ClipboardCard, EditDialog
from encryption import decrypt_text, encrypt_text
from content_detection import detect_language, detect_content_type, is_code
from encryption import content_fingerprint
import re


class HistoryPage(QFrame):
    # main clipboard history tab

    MAX_SCAN_ITEMS = 2000
    MAX_RENDERED_ITEMS = 250

    def __init__(self, db_manager, fernet, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.fernet = fernet
        self.setObjectName("historyPage")
        self._selected_card_id = None
        self._current_filter = "All Items"
        self._setup_ui()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.load_entries)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Clipboard history")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #6B7280;")
        header.addWidget(self.count_label)
        layout.addLayout(header)

        # Search bar
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Search clipboard...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search)
        layout.addWidget(self.search_bar)

        # Filter row
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)

        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)

        self.filter_segment = SegmentedWidget(self)
        self.filter_segment.setFixedHeight(34)
        self.filter_segment.addItem("all", "All Items")
        self.filter_segment.addItem("code", "Code")
        self.filter_segment.addItem("text", "Text")
        self.filter_segment.addItem("links", "Links")
        self.filter_segment.addItem("favorites", "★ Favorites")
        self.filter_segment.setCurrentItem("all")
        self.filter_segment.currentItemChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_segment)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # Scrollable card list
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(8)

        self.empty_label = QLabel("Your clipboard history will appear here", self.card_container)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #6B7280; padding: 60px 24px;")
        self.empty_label.setVisible(False)
        self.card_layout.addWidget(self.empty_label)

        self.card_layout.addStretch()

        self.scroll_area.setWidget(self.card_container)
        layout.addWidget(self.scroll_area, 1)

    def _on_filter_changed(self, key):
        filter_map = {
            "all": "All Items", "code": "Code", "text": "Text",
            "links": "Links", "favorites": "Favorites"
        }
        self._current_filter = filter_map.get(key, "All Items")
        QTimer.singleShot(0, self.load_entries)

    def _on_search(self, text):
        self.search_timer.start()

    def load_entries(self):
        # Reload entries from DB and rebuild cards
        for i in reversed(range(self.card_layout.count())):
            item = self.card_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ClipboardCard):
                w = item.widget()
                self.card_layout.removeWidget(w)
                w.deleteLater()

        total_entries = self.db_manager.count_history()
        entries = self.db_manager.get_all_entries(limit=self.MAX_SCAN_ITEMS)
        search_term = self.search_bar.text().strip().lower()
        rendered = 0

        date_filter = None
        type_filter = None
        clean_search = search_term

        date_match = re.search(r"date:\s*(\d{4}-\d{2}-\d{2})", search_term, re.IGNORECASE)
        if date_match:
            date_filter = date_match.group(1)
            clean_search = re.sub(r"date:\s*\d{4}-\d{2}-\d{2}", "", clean_search, flags=re.IGNORECASE)

        type_match = re.search(r"type:\s*(code|text)", search_term, re.IGNORECASE)
        if type_match:
            type_filter = type_match.group(1).lower()
            clean_search = re.sub(r"type:\s*(code|text)", "", clean_search, flags=re.IGNORECASE)

        clean_search = clean_search.strip()

        for entry in entries:
            entry_id, enc_text, timestamp, is_code, pinned, favorite = entry

            if self._current_filter == "Favorites" and not favorite:
                continue

            if date_filter and not timestamp.startswith(date_filter):
                continue

            if type_filter:
                if type_filter == "code" and not is_code:
                    continue
                elif type_filter == "text" and is_code:
                    continue

            decrypted_text = decrypt_text(enc_text, self.fernet)

            content_type = detect_content_type(decrypted_text)
            language = detect_language(decrypted_text) if is_code else "Text"

            if self._current_filter == "Code" and content_type != "code":
                continue
            elif self._current_filter == "Text" and content_type != "text":
                continue
            elif self._current_filter == "Links" and content_type != "link":
                continue

            if clean_search and clean_search not in decrypted_text.lower():
                continue

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
                show_edit=True,
                show_copy=True,
                show_delete=True,
                show_save_snippet=is_code,
                show_tag=True,
                show_timestamp=getattr(self.window(), 'settings', {}).get('show_timestamps', True),
                parent=self.card_container
            )

            card.copyClicked.connect(self._on_copy)
            card.pinClicked.connect(self._on_pin)
            card.favoriteClicked.connect(self._on_star)
            card.editClicked.connect(self._on_edit)
            card.deleteClicked.connect(self._on_delete)
            card.saveAsSnippetClicked.connect(self._on_save_snippet)
            card.tagClicked.connect(self._on_tag)
            card.cardClicked.connect(self._on_card_click)

            if entry_id == self._selected_card_id:
                card.setSelected(True)

            self.card_layout.insertWidget(rendered, card)
            rendered += 1
            if rendered >= self.MAX_RENDERED_ITEMS:
                break

        self.empty_label.setVisible(rendered == 0)
        if total_entries > self.MAX_SCAN_ITEMS and (search_term or self._current_filter != "All Items"):
            self.count_label.setText(
                f"{rendered:,} shown · searched newest {self.MAX_SCAN_ITEMS:,} of {total_entries:,}"
            )
        elif total_entries > self.MAX_RENDERED_ITEMS and not search_term and self._current_filter == "All Items":
            self.count_label.setText(f"{total_entries:,} items · showing newest {rendered}")
        elif rendered != total_entries:
            self.count_label.setText(f"{rendered:,} shown · {total_entries:,} total")
        else:
            self.count_label.setText(f"{total_entries:,} item{'s' if total_entries != 1 else ''}")

    def _extract_title(self, text, content_type):
        if content_type == "link":
            first_line = text.strip().split('\n')[0]
            if len(first_line) > 60:
                return first_line[:57] + "..."
            return first_line
        lines = text.strip().split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped:
                if len(stripped) > 60:
                    return stripped[:57] + "..."
                return stripped
        return "Empty entry"

    def _extract_preview(self, text):
        lines = text.strip().split('\n')
        preview_lines = []
        for line in lines[1:4]:
            stripped = line.strip()
            if stripped:
                preview_lines.append(stripped)
        if preview_lines:
            preview = '  '.join(preview_lines)
            if len(preview) > 100:
                return preview[:97] + "..."
            return preview
        elif lines:
            text_flat = text.strip()
            if len(text_flat) > 100:
                return text_flat[:97] + "..."
            return text_flat
        return ""

    def _on_copy(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            decrypted = decrypt_text(row[0], self.fernet)
            window = self.window()
            if hasattr(window, "copy_text"):
                window.copy_text(decrypted)
            else:
                QApplication.clipboard().setText(decrypted)
            InfoBar.success("Copied", "Copied to clipboard!", parent=self, duration=1500)

    def _on_pin(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            new_state = 0 if row[1] else 1
            self.db_manager.update_pin_state(entry_id, new_state)
            QTimer.singleShot(0, self.load_entries)

    def _on_star(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            new_state = 0 if row[2] else 1
            self.db_manager.update_favorite_state(entry_id, new_state)
            QTimer.singleShot(0, self.load_entries)

    def _on_edit(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            decrypted = decrypt_text(row[0], self.fernet)
            dialog = EditDialog(decrypted, self)
            if dialog.exec():
                new_text = dialog.edited_text
                if new_text != decrypted:
                    new_encrypted = encrypt_text(new_text, self.fernet)
                    window = self.window()
                    fingerprint_key = getattr(window, "fingerprint_key", b"clipboard-manager")
                    self.db_manager.update_entry_content(
                        entry_id,
                        new_encrypted,
                        content_fingerprint(new_text, fingerprint_key),
                        is_code(new_text),
                    )
                    QTimer.singleShot(0, self.load_entries)
                    InfoBar.success("Saved", "Entry updated.", parent=self, duration=1500)

    def _on_delete(self, entry_id):
        self.db_manager.delete_entry_by_id(entry_id)
        QTimer.singleShot(0, self.load_entries)

    def _on_save_snippet(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            decrypted = decrypt_text(row[0], self.fernet)
            language = detect_language(decrypted)
            title = self._extract_title(decrypted, "code")
            encrypted = encrypt_text(decrypted, self.fernet)
            import datetime
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.db_manager.add_snippet(title, encrypted, language, ts)
            InfoBar.success("Snippet", "Saved as snippet!", parent=self, duration=1500)

    def _on_tag(self, entry_id):
        from ui.tag_dialog import TagDialog

        dialog = TagDialog(self.db_manager, entry_id, "history", self)
        if dialog.exec():
            InfoBar.success("Tags", "Tags updated.", parent=self, duration=1500)

    def _on_card_click(self, entry_id):
        self._selected_card_id = entry_id
        for i in range(self.card_layout.count()):
            item = self.card_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ClipboardCard):
                item.widget().setSelected(item.widget().entry_id == entry_id)

from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QWidget,
                                QScrollArea, QLabel, QApplication)
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import SearchLineEdit, SegmentedWidget

from ui.clipboard_card import ClipboardCard, EditDialog
from encryption import decrypt_text, encrypt_text
from content_detection import detect_language


class SnippetsPage(QFrame):
    # saved snippets tab

    def __init__(self, db_manager, fernet, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.fernet = fernet
        self.setObjectName("snippetsPage")
        self._current_filter = "All Languages"
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

        title = QLabel("Saved snippets")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Search bar
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Search snippets...")
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
        self.filter_segment.addItem("all", "All Languages")
        self.filter_segment.addItem("js", "JS")
        self.filter_segment.addItem("python", "Python")
        self.filter_segment.addItem("css", "CSS")
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

        self.empty_label = QLabel("Save a code item from history to create a snippet", self.card_container)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #6B7280; padding: 60px 24px;")
        self.empty_label.setVisible(False)
        self.card_layout.addWidget(self.empty_label)

        self.card_layout.addStretch()

        self.scroll_area.setWidget(self.card_container)
        layout.addWidget(self.scroll_area, 1)

    def _on_filter_changed(self, key):
        filter_map = {"all": "All Languages", "js": "JS", "python": "Python", "css": "CSS"}
        self._current_filter = filter_map.get(key, "All Languages")
        QTimer.singleShot(0, self.load_entries)

    def _on_search(self, text):
        self.search_timer.start()

    def load_entries(self):
        # Reload snippets from DB
        for i in reversed(range(self.card_layout.count())):
            item = self.card_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ClipboardCard):
                w = item.widget()
                self.card_layout.removeWidget(w)
                w.deleteLater()

        snippets = self.db_manager.get_all_snippets()
        search_term = self.search_bar.text().strip().lower()
        rendered = 0

        for snippet in snippets:
            snippet_id, title, enc_text, language, timestamp, favorite = snippet

            if self._current_filter != "All Languages":
                if language.lower() != self._current_filter.lower():
                    continue

            decrypted_text = decrypt_text(enc_text, self.fernet)

            if search_term:
                if (search_term not in title.lower() and
                        search_term not in decrypted_text.lower()):
                    continue

            preview = decrypted_text.strip()
            if len(preview) > 100:
                preview = preview[:97] + "..."

            card = ClipboardCard(
                entry_id=snippet_id,
                title=title,
                preview_text=preview,
                timestamp=timestamp,
                language=language,
                content_type='code',
                is_pinned=False,
                is_favorite=bool(favorite),
                show_pin=False,
                show_favorite=True,
                show_edit=True,
                show_copy=True,
                show_delete=True,
                show_save_snippet=False,
                show_tag=True,
                show_timestamp=getattr(self.window(), 'settings', {}).get('show_timestamps', True),
                parent=self.card_container
            )

            card.copyClicked.connect(self._on_copy)
            card.favoriteClicked.connect(self._on_star)
            card.editClicked.connect(self._on_edit)
            card.deleteClicked.connect(self._on_delete)
            card.tagClicked.connect(self._on_tag)
            card.cardClicked.connect(self._on_card_click)

            if snippet_id == self._selected_card_id:
                card.setSelected(True)

            self.card_layout.insertWidget(rendered, card)
            rendered += 1

        self.empty_label.setVisible(rendered == 0)

    def _on_copy(self, snippet_id):
        snippet = self.db_manager.get_snippet_by_id(snippet_id)
        if snippet:
            decrypted = decrypt_text(snippet[2], self.fernet)
            window = self.window()
            if hasattr(window, "copy_text"):
                window.copy_text(decrypted)
            else:
                QApplication.clipboard().setText(decrypted)

    def _on_star(self, snippet_id):
        snippet = self.db_manager.get_snippet_by_id(snippet_id)
        if snippet:
            new_state = 0 if snippet[5] else 1
            self.db_manager.update_snippet_favorite(snippet_id, new_state)
            QTimer.singleShot(0, self.load_entries)

    def _on_edit(self, snippet_id):
        snippet = self.db_manager.get_snippet_by_id(snippet_id)
        if not snippet:
            return
        original = decrypt_text(snippet[2], self.fernet)
        dialog = EditDialog(original, self)
        dialog.setWindowTitle("Edit snippet")
        if dialog.exec() and dialog.edited_text != original:
            updated = dialog.edited_text
            first_line = next((line.strip() for line in updated.splitlines() if line.strip()), "Untitled snippet")
            title = first_line[:57] + "..." if len(first_line) > 60 else first_line
            self.db_manager.update_snippet(
                snippet_id,
                title=title,
                encrypted_text=encrypt_text(updated, self.fernet),
                language=detect_language(updated),
            )
            QTimer.singleShot(0, self.load_entries)

    def _on_delete(self, snippet_id):
        self.db_manager.delete_snippet_by_id(snippet_id)
        QTimer.singleShot(0, self.load_entries)

    def _on_tag(self, snippet_id):
        from ui.tag_dialog import TagDialog

        TagDialog(self.db_manager, snippet_id, "snippet", self).exec()

    def _on_card_click(self, snippet_id):
        self._selected_card_id = snippet_id
        for i in range(self.card_layout.count()):
            item = self.card_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ClipboardCard):
                item.widget().setSelected(item.widget().entry_id == snippet_id)

from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QWidget,
                                QScrollArea, QLabel, QPushButton,
                                QApplication)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from qfluentwidgets import SearchLineEdit, isDarkTheme, PushButton, MessageBox, InfoBar

from ui.clipboard_card import ClipboardCard
from ui.flow_layout import FlowLayout
from encryption import decrypt_text
from content_detection import detect_language, detect_content_type


class TagChip(QPushButton):
    # pill tag chip button

    def __init__(self, tag_id, name, color, count, parent=None):
        super().__init__(f"{name} ({count})", parent)
        self.tag_id = tag_id
        self.tag_color = color
        self._is_active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self.setFont(font)
        self._apply_style()

    def _apply_style(self):
        if self._is_active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.tag_color};
                    color: white;
                    border: 2px solid {self.tag_color};
                    border-radius: 14px;
                    padding: 4px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    opacity: 0.9;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.tag_color};
                    color: white;
                    border: none;
                    border-radius: 14px;
                    padding: 4px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border: 2px solid white;
                }}
            """)

    def setActive(self, active):
        self._is_active = active
        self._apply_style()


class TagsPage(QFrame):
    # tag management and filtered entry view

    def __init__(self, db_manager, fernet, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.fernet = fernet
        self.setObjectName("tagsPage")
        self._selected_tag_id = None
        self._selected_tag_name = None
        self._setup_ui()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.load_entries)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Tags")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Search and tag management
        search_row = QHBoxLayout()
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("Search tags...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_bar, 1)
        self.delete_tag_button = PushButton("Delete selected tag", self)
        self.delete_tag_button.setEnabled(False)
        self.delete_tag_button.clicked.connect(self._delete_selected_tag)
        search_row.addWidget(self.delete_tag_button)
        layout.addLayout(search_row)

        # Tag chips container with flow layout
        self.chips_container = QWidget()
        self.chips_layout = FlowLayout(self.chips_container, margin=0, h_spacing=8, v_spacing=8)
        self.chips_container.setLayout(self.chips_layout)
        layout.addWidget(self.chips_container)

        self.tagged_label = QLabel("")
        tagged_font = self.tagged_label.font()
        tagged_font.setPointSize(10)
        self.tagged_label.setFont(tagged_font)
        if isDarkTheme():
            self.tagged_label.setStyleSheet("color: #9CA3AF; margin-top: 8px;")
        else:
            self.tagged_label.setStyleSheet("color: #6B7280; margin-top: 8px;")
        self.tagged_label.setVisible(False)
        layout.addWidget(self.tagged_label)

        # Scrollable card list
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(8)

        self.empty_label = QLabel("Select a tag to view its items", self.card_container)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #6B7280; padding: 60px 24px;")
        self.card_layout.addWidget(self.empty_label)

        self.card_layout.addStretch()

        self.scroll_area.setWidget(self.card_container)
        layout.addWidget(self.scroll_area, 1)

    def _on_search(self, text):
        self.search_timer.start()

    def load_entries(self):
        self._load_chips()
        if self._selected_tag_id is not None:
            self._load_tagged_items()

    def _load_chips(self):
        self.chips_layout.clear()

        search_term = self.search_bar.text().strip().lower()
        tag_counts = self.db_manager.get_tag_counts()

        for tag_id, name, color, count in tag_counts:
            if search_term and search_term not in name.lower():
                continue

            chip = TagChip(tag_id, name, color, count, self.chips_container)
            chip.setActive(tag_id == self._selected_tag_id)
            chip.clicked.connect(lambda checked, tid=tag_id, tname=name: self._on_chip_clicked(tid, tname))
            self.chips_layout.addWidget(chip)

    def _on_chip_clicked(self, tag_id, tag_name):
        if self._selected_tag_id == tag_id:
            self._selected_tag_id = None
            self._selected_tag_name = None
            self.tagged_label.setVisible(False)
            self.delete_tag_button.setEnabled(False)
            self._clear_cards()
            self.empty_label.setText("Select a tag to view its items")
            self.empty_label.setVisible(True)
        else:
            self._selected_tag_id = tag_id
            self._selected_tag_name = tag_name
            self.tagged_label.setText(f"Tagged: {tag_name}")
            self.tagged_label.setVisible(True)
            self.delete_tag_button.setEnabled(True)
            self._load_tagged_items()

        for i in range(self.chips_layout.count()):
            item = self.chips_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), TagChip):
                item.widget().setActive(item.widget().tag_id == self._selected_tag_id)

    def _load_tagged_items(self):
        self._clear_cards()

        if self._selected_tag_id is None:
            return

        entries = self.db_manager.get_history_entries_by_tag(self._selected_tag_id)
        rendered = 0

        for entry in entries:
            entry_id, enc_text, timestamp, is_code, pinned, favorite = entry

            decrypted_text = decrypt_text(enc_text, self.fernet)
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
                show_pin=False,
                show_favorite=True,
                show_edit=False,
                show_copy=True,
                show_delete=True,
                show_timestamp=getattr(self.window(), 'settings', {}).get('show_timestamps', True),
                parent=self.card_container
            )

            card.copyClicked.connect(self._on_copy)
            card.deleteClicked.connect(self._on_delete)
            card.favoriteClicked.connect(self._on_star)

            self.card_layout.insertWidget(rendered, card)
            rendered += 1

        for snippet_id, title, enc_text, language, timestamp, favorite in self.db_manager.get_snippets_by_tag(self._selected_tag_id):
            decrypted_text = decrypt_text(enc_text, self.fernet)
            preview = self._extract_preview(decrypted_text)
            card = ClipboardCard(
                entry_id=-snippet_id,
                title=title,
                preview_text=preview,
                timestamp=timestamp,
                language=language,
                content_type="code",
                is_pinned=False,
                is_favorite=bool(favorite),
                show_pin=False,
                show_favorite=True,
                show_edit=False,
                show_copy=True,
                show_delete=True,
                show_timestamp=getattr(self.window(), 'settings', {}).get('show_timestamps', True),
                parent=self.card_container,
            )
            card.copyClicked.connect(self._on_copy_snippet)
            card.deleteClicked.connect(self._on_delete_snippet)
            card.favoriteClicked.connect(self._on_star_snippet)
            self.card_layout.insertWidget(rendered, card)
            rendered += 1

        self.empty_label.setText("No items use this tag yet")
        self.empty_label.setVisible(rendered == 0)

    def _clear_cards(self):
        for i in reversed(range(self.card_layout.count())):
            item = self.card_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), ClipboardCard):
                w = item.widget()
                self.card_layout.removeWidget(w)
                w.deleteLater()

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

    def _delete_selected_tag(self):
        if self._selected_tag_id is None:
            return
        dialog = MessageBox(
            "Delete tag",
            f"Delete ‘{self._selected_tag_name}’? Items using it will stay in your history.",
            self,
        )
        if not dialog.exec():
            return
        self.db_manager.delete_tag(self._selected_tag_id)
        self._selected_tag_id = None
        self._selected_tag_name = None
        self.tagged_label.setVisible(False)
        self.delete_tag_button.setEnabled(False)
        self._clear_cards()
        self.empty_label.setText("Select a tag to view its items")
        self.empty_label.setVisible(True)
        self._load_chips()
        InfoBar.success("Tags", "Tag deleted.", parent=self, duration=1500)

    def _on_delete(self, entry_id):
        self.db_manager.delete_entry_by_id(entry_id)
        QTimer.singleShot(0, self.load_entries)

    def _on_copy_snippet(self, negative_snippet_id):
        snippet = self.db_manager.get_snippet_by_id(-negative_snippet_id)
        if snippet:
            decrypted = decrypt_text(snippet[2], self.fernet)
            window = self.window()
            if hasattr(window, "copy_text"):
                window.copy_text(decrypted)
            else:
                QApplication.clipboard().setText(decrypted)

    def _on_delete_snippet(self, negative_snippet_id):
        self.db_manager.delete_snippet_by_id(-negative_snippet_id)
        QTimer.singleShot(0, self.load_entries)

    def _on_star_snippet(self, negative_snippet_id):
        snippet_id = -negative_snippet_id
        snippet = self.db_manager.get_snippet_by_id(snippet_id)
        if snippet:
            self.db_manager.update_snippet_favorite(snippet_id, 0 if snippet[5] else 1)
        QTimer.singleShot(0, self.load_entries)

    def _on_star(self, entry_id):
        entries = self.db_manager.get_all_entries()
        for e in entries:
            if e[0] == entry_id:
                new_state = 0 if e[5] else 1
                self.db_manager.update_favorite_state(entry_id, new_state)
                break
        QTimer.singleShot(0, self.load_entries)

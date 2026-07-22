from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                                QSizePolicy, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor, QFontMetrics, QIcon, QPixmap, QPainter
from qfluentwidgets import (CardWidget, TransparentToolButton, FluentIcon,
                             isDarkTheme, PlainTextEdit, LineEdit)

from utils import get_jetbrains_font, format_relative_time


LANGUAGE_COLORS = {
    'JS':     '#F59E0B',
    'Python': '#3B82F6',
    'PY':     '#3B82F6',
    'CSS':    '#8B5CF6',
    'HTML':   '#EF4444',
    'Java':   '#F97316',
    'C++':    '#00599C',
    'C#':     '#179417',
    'Go':     '#00ADD8',
    'Rust':   '#DEA584',
    'SQL':    '#336791',
    'Shell':  '#4EAA25',
    'PHP':    '#777BB4',
    'JSON':   '#10B981',
    'Text':   '#6B7280',
}

CONTENT_TYPE_COLORS = {
    'code': '#3B82F6',
    'link': '#10B981',
    'text': '#6B7280',
}


class LanguageBadge(QLabel):
    # small pill badge for language/content type

    def __init__(self, label_text, color=None, parent=None):
        super().__init__(label_text, parent)
        if color is None:
            color = LANGUAGE_COLORS.get(label_text, '#6B7280')
        self.badge_color = color
        self.setAlignment(Qt.AlignCenter)

        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        self.setFont(font)

        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(label_text)
        self.setFixedWidth(max(28, text_width + 14))
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {self.badge_color};
                color: white;
                border-radius: 4px;
                padding: 2px 5px;
                font-weight: bold;
                font-size: 9px;
            }}
        """)


def _tinted_icon(fluent_icon, color_hex):
    # tint fluent icons because default ones don't color dynamically
    icon = fluent_icon.icon()
    sizes = icon.availableSizes()
    size = sizes[0] if sizes else QSize(16, 16)
    pixmap = icon.pixmap(size)
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color_hex))
    painter.end()
    return QIcon(pixmap)


class EditDialog(QDialog):
    # quick popup to edit entry text

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Entry")
        self.setMinimumSize(500, 350)
        self.edited_text = text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.editor = PlainTextEdit(self)
        mono_font = get_jetbrains_font(10)
        self.editor.setFont(mono_font)
        self.editor.setPlainText(text)
        layout.addWidget(self.editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        self.edited_text = self.editor.toPlainText()
        self.accept()


class ClipboardCard(CardWidget):
    # card widget for clipboard item in lists

    copyClicked = Signal(int)
    pinClicked = Signal(int)
    editClicked = Signal(int)
    deleteClicked = Signal(int)
    favoriteClicked = Signal(int)
    cardClicked = Signal(int)
    saveAsSnippetClicked = Signal(int)
    tagClicked = Signal(int)

    def __init__(self, entry_id, title, preview_text, timestamp,
                 language='Text', content_type='text',
                 is_pinned=False, is_favorite=False,
                 show_pin=True, show_favorite=True, show_edit=True,
                 show_copy=True, show_delete=True,
                 show_save_snippet=False, show_tag=False,
                 show_timestamp=True,
                 parent=None):
        super().__init__(parent)
        self.entry_id = entry_id
        self._is_selected = False
        self._is_pinned = is_pinned
        self._is_favorite = is_favorite

        self.setFixedHeight(96)
        self.setMinimumWidth(360)
        self.setCursor(Qt.PointingHandCursor)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 8, 10)
        main_layout.setSpacing(10)

        badge_label = language if language != 'Text' else content_type.capitalize()
        badge_color = LANGUAGE_COLORS.get(language, CONTENT_TYPE_COLORS.get(content_type, '#6B7280'))
        self.badge = LanguageBadge(badge_label, badge_color, parent=self)
        main_layout.addWidget(self.badge, 0, Qt.AlignTop)

        center_layout = QVBoxLayout()
        center_layout.setSpacing(4)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(title, self)
        title_font = self.title_label.font()
        title_font.setPointSize(10)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(False)
        self.title_label.setTextInteractionFlags(Qt.NoTextInteraction)
        center_layout.addWidget(self.title_label)

        self.preview_label = QLabel(preview_text, self)
        mono_font = get_jetbrains_font(9)
        self.preview_label.setFont(mono_font)
        self.preview_label.setWordWrap(False)
        self.preview_label.setMaximumHeight(40)
        self.preview_label.setTextInteractionFlags(Qt.NoTextInteraction)
        if isDarkTheme():
            self.preview_label.setStyleSheet("color: #9CA3AF;")
        else:
            self.preview_label.setStyleSheet("color: #6B7280;")
        center_layout.addWidget(self.preview_label)
        center_layout.addStretch()

        main_layout.addLayout(center_layout, 1)

        right_widget = QWidget(self)
        right_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(4)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.time_label = QLabel(format_relative_time(timestamp) if show_timestamp else "", right_widget)
        self.time_label.setVisible(show_timestamp)
        time_font = self.time_label.font()
        time_font.setPointSize(8)
        self.time_label.setFont(time_font)
        if isDarkTheme():
            self.time_label.setStyleSheet("color: #6B7280;")
        else:
            self.time_label.setStyleSheet("color: #9CA3AF;")
        self.time_label.setAlignment(Qt.AlignRight)
        right_layout.addWidget(self.time_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(1)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addStretch()

        self._action_buttons = []

        if show_copy:
            self.copy_btn = TransparentToolButton(FluentIcon.COPY, right_widget)
            self.copy_btn.setFixedSize(30, 30)
            self.copy_btn.setIconSize(QSize(18, 18))
            self.copy_btn.setToolTip("Copy")
            self.copy_btn.clicked.connect(lambda: self.copyClicked.emit(self.entry_id))
            actions_layout.addWidget(self.copy_btn)
            self._action_buttons.append(self.copy_btn)

        if show_pin:
            self.pin_btn = TransparentToolButton(FluentIcon.PIN if not is_pinned else FluentIcon.UNPIN, right_widget)
            self.pin_btn.setFixedSize(30, 30)
            self.pin_btn.setIconSize(QSize(18, 18))
            self.pin_btn.setToolTip("Unpin" if is_pinned else "Pin")
            self.pin_btn.clicked.connect(lambda: self.pinClicked.emit(self.entry_id))
            actions_layout.addWidget(self.pin_btn)
            self._action_buttons.append(self.pin_btn)

        if show_favorite:
            self.fav_btn = TransparentToolButton(FluentIcon.HEART, right_widget)
            self.fav_btn.setFixedSize(30, 30)
            self.fav_btn.setIconSize(QSize(18, 18))
            self.fav_btn.setToolTip("Unfavorite" if is_favorite else "Favorite")
            if is_favorite:
                self.fav_btn.setIcon(_tinted_icon(FluentIcon.HEART, '#EF4444'))
            self.fav_btn.clicked.connect(lambda: self.favoriteClicked.emit(self.entry_id))
            actions_layout.addWidget(self.fav_btn)
            self._action_buttons.append(self.fav_btn)

        if show_edit:
            self.edit_btn = TransparentToolButton(FluentIcon.EDIT, right_widget)
            self.edit_btn.setFixedSize(30, 30)
            self.edit_btn.setIconSize(QSize(18, 18))
            self.edit_btn.setToolTip("Edit")
            self.edit_btn.clicked.connect(lambda: self.editClicked.emit(self.entry_id))
            actions_layout.addWidget(self.edit_btn)
            self._action_buttons.append(self.edit_btn)

        if show_save_snippet:
            self.snippet_btn = TransparentToolButton(FluentIcon.SAVE, right_widget)
            self.snippet_btn.setFixedSize(30, 30)
            self.snippet_btn.setIconSize(QSize(18, 18))
            self.snippet_btn.setToolTip("Save as Snippet")
            self.snippet_btn.clicked.connect(lambda: self.saveAsSnippetClicked.emit(self.entry_id))
            actions_layout.addWidget(self.snippet_btn)
            self._action_buttons.append(self.snippet_btn)

        if show_tag:
            self.tag_btn = TransparentToolButton(FluentIcon.TAG, right_widget)
            self.tag_btn.setFixedSize(30, 30)
            self.tag_btn.setIconSize(QSize(18, 18))
            self.tag_btn.setToolTip("Tag")
            self.tag_btn.clicked.connect(lambda: self.tagClicked.emit(self.entry_id))
            actions_layout.addWidget(self.tag_btn)
            self._action_buttons.append(self.tag_btn)

        if show_delete:
            self.delete_btn = TransparentToolButton(FluentIcon.DELETE, right_widget)
            self.delete_btn.setFixedSize(30, 30)
            self.delete_btn.setIconSize(QSize(18, 18))
            self.delete_btn.setToolTip("Delete")
            self.delete_btn.clicked.connect(lambda: self.deleteClicked.emit(self.entry_id))
            actions_layout.addWidget(self.delete_btn)
            self._action_buttons.append(self.delete_btn)

        right_layout.addLayout(actions_layout)
        right_layout.addStretch()

        right_widget.setMinimumWidth(max(128, len(self._action_buttons) * 31 + 8))

        main_layout.addWidget(right_widget, 0)

        self._apply_border_style()

    def setSelected(self, selected):
        self._is_selected = selected
        self._apply_border_style()

    def _apply_border_style(self):
        if self._is_selected:
            self.setStyleSheet("""
                ClipboardCard {
                    border: 2px solid #0078D4;
                    border-radius: 8px;
                }
            """)
        else:
            if isDarkTheme():
                self.setStyleSheet("""
                    ClipboardCard {
                        border: 1px solid #3D3D3D;
                        border-radius: 8px;
                    }
                """)
            else:
                self.setStyleSheet("""
                    ClipboardCard {
                        border: 1px solid #E0E0E0;
                        border-radius: 8px;
                    }
                """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            for btn in self._action_buttons:
                if btn.underMouse():
                    super().mousePressEvent(event)
                    return
            self.cardClicked.emit(self.entry_id)
        super().mousePressEvent(event)

    def update_pin_state(self, is_pinned):
        self._is_pinned = is_pinned
        if hasattr(self, 'pin_btn'):
            self.pin_btn.setIcon(FluentIcon.UNPIN if is_pinned else FluentIcon.PIN)
            self.pin_btn.setToolTip("Unpin" if is_pinned else "Pin")

    def update_favorite_state(self, is_favorite):
        self._is_favorite = is_favorite
        if hasattr(self, 'fav_btn'):
            if is_favorite:
                self.fav_btn.setIcon(_tinted_icon(FluentIcon.HEART, '#EF4444'))
            else:
                self.fav_btn.setIcon(FluentIcon.HEART.icon())
            self.fav_btn.setToolTip("Unfavorite" if is_favorite else "Favorite")

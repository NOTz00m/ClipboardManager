from PySide6.QtWidgets import QWidget, QLabel, QToolButton, QHBoxLayout
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, Signal
from utils import get_icon_path

class HistoryItemWidget(QWidget):
    clicked = Signal(int)

    def __init__(self, entry_id, text_preview, timestamp, is_code, pinned, favorite, parent=None):
        super().__init__(parent)
        self.entry_id = entry_id
        self.text_preview = text_preview
        self.timestamp = timestamp
        self.is_code = is_code
        self.pinned = pinned
        self.favorite = favorite
        self.setupUI()
        self.setMouseTracking(True)
        self.setMinimumHeight(40)

    def setupUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)

        self.label = QLabel(f"{self.entry_id} - {self.text_preview} ({self.timestamp})")
        layout.addWidget(self.label)
        layout.addStretch()

        self.trash_button = QToolButton()
        trash_icon_path = get_icon_path("trash.png")
        trash_pixmap = QPixmap(trash_icon_path)
        # Scale the icon to 28x28 for better visibility (button is 24x24)
        trash_icon = QIcon(trash_pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.trash_button.setIcon(trash_icon)
        self.trash_button.setToolTip("delete")
        self.trash_button.setFixedSize(24, 24)
        layout.addWidget(self.trash_button)

        self.star_button = QToolButton()
        star_icon = QIcon(get_icon_path("star_active.png") if self.favorite else get_icon_path("star.png"))
        self.star_button.setIcon(star_icon)
        self.star_button.setToolTip("favorite")
        self.star_button.setFixedSize(24, 24)
        layout.addWidget(self.star_button)

        self.pin_button = QToolButton()
        pin_icon = QIcon(get_icon_path("pin_active.png") if self.pinned else get_icon_path("pin.png"))
        self.pin_button.setIcon(pin_icon)
        self.pin_button.setToolTip("pin")
        self.pin_button.setFixedSize(24, 24)
        layout.addWidget(self.pin_button)

        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not (self.trash_button.underMouse() or self.star_button.underMouse() or self.pin_button.underMouse()):
                self.clicked.emit(self.entry_id)
        super().mousePressEvent(event)

    def update_icons(self, pinned, favorite):
        self.pinned = pinned
        self.favorite = favorite
        self.pin_button.setIcon(QIcon(get_icon_path("pin_active.png") if self.pinned else get_icon_path("pin.png")))
        self.star_button.setIcon(QIcon(get_icon_path("star_active.png") if self.favorite else get_icon_path("star.png"))) 
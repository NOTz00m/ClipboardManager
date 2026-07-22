from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QWidget, QFileDialog, QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from qfluentwidgets import (SwitchButton, ComboBox, LineEdit, PushButton,
                             PrimaryPushButton, CardWidget, PasswordLineEdit,
                             BodyLabel, StrongBodyLabel, CaptionLabel,
                             setTheme, Theme, isDarkTheme)
from utils import get_app_font, get_system_theme
import sys
import os
import platform


def add_to_startup():
    if platform.system() == "Windows":
        import winreg
        if getattr(sys, "frozen", False):
            command = f'"{os.path.abspath(sys.executable)}"'
        else:
            command = f'"{os.path.abspath(sys.executable)}" "{os.path.abspath(sys.argv[0])}"'
        reg_key = winreg.HKEY_CURRENT_USER
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_name = "ClipboardManager"
        with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, command)
    elif platform.system() == "Darwin":
        app_path = sys.argv[0]
        os.system(f"osascript -e 'tell application \"System Events\" to make login item at end with properties {{name:\"ClipboardManager\", path:\"{app_path}\", hidden:true}}'")
    elif platform.system() == "Linux":
        app_path = sys.argv[0]
        autostart_dir = os.path.expanduser("~/.config/autostart")
        if not os.path.exists(autostart_dir):
            os.makedirs(autostart_dir)
        desktop_entry = os.path.join(autostart_dir, "clipboardmanager.desktop")
        with open(desktop_entry, "w") as f:
            f.write(f"[Desktop Entry]\nName=ClipboardManager\nExec={app_path}\nType=Application\nX-GNOME-Autostart-enabled=true\n")


def remove_from_startup():
    if platform.system() == "Windows":
        import winreg
        reg_key = winreg.HKEY_CURRENT_USER
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_name = "ClipboardManager"
        try:
            with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, reg_name)
            with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, reg_name)
        except FileNotFoundError:
            pass
    elif platform.system() == "Darwin":
        os.system("osascript -e 'tell application \"System Events\" to delete login item \"ClipboardManager\"'")
    elif platform.system() == "Linux":
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_entry = os.path.join(autostart_dir, "clipboardmanager.desktop")
        if os.path.exists(desktop_entry):
            os.remove(desktop_entry)


class WizardCard(CardWidget):
    # section card for wizard

    def __init__(self, title, subtitle=None, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(10)

        title_label = StrongBodyLabel(title)
        title_font = title_label.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        self._layout.addWidget(title_label)

        if subtitle:
            sub = CaptionLabel(subtitle)
            sub.setStyleSheet("color: #6B7280;")
            sub.setWordWrap(True)
            self._layout.addWidget(sub)

    def addRow(self, label_text, widget):
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        label = BodyLabel(label_text)
        label.setMinimumWidth(180)
        row.addWidget(label)
        row.addWidget(widget, 1)
        self._layout.addWidget(container)
        return container

    def addFullRow(self, widget):
        self._layout.addWidget(widget)


class StartupWizard(QDialog):
    # first run wizard dialog

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clipboard Manager — Setup")
        self.setMinimumSize(520, 580)
        self.resize(560, 640)
        self.app_font = get_app_font(10)
        self.settings = None

        system_theme = get_system_theme()
        if system_theme == "dark":
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QLabel("Welcome to Clipboard Manager")
        header_font = header.font()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        subtitle = CaptionLabel("Let's set up your preferences before getting started.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #6B7280; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        security_card = WizardCard(
            "🔒 Security",
            "Your clipboard data can be encrypted locally so only you can read it."
        )

        self.encryption_switch = SwitchButton()
        self.encryption_switch.setChecked(True)
        security_card.addRow("Encrypt clipboard data", self.encryption_switch)

        self.personal_key_switch = SwitchButton()
        self.personal_key_switch.setChecked(False)
        self.personal_key_switch.checkedChanged.connect(self._on_personal_key_toggled)
        security_card.addRow("Use a personal password", self.personal_key_switch)

        self.password_field = PasswordLineEdit()
        self.password_field.setPlaceholderText("Enter a password...")
        self.password_field.setEnabled(False)
        security_card.addRow("Password", self.password_field)

        layout.addWidget(security_card)

        appearance_card = WizardCard("🎨 Appearance")

        self.theme_combo = ComboBox()
        self.theme_combo.addItems(["System (Default)", "Light", "Dark"])
        self.theme_combo.setCurrentIndex(0)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance_card.addRow("Theme", self.theme_combo)

        self.timestamps_switch = SwitchButton()
        self.timestamps_switch.setChecked(True)
        appearance_card.addRow("Show timestamps", self.timestamps_switch)

        layout.addWidget(appearance_card)

        history_card = WizardCard(
            "📋 History",
            "Choose how long to keep clipboard entries."
        )

        self.history_combo = ComboBox()
        self.history_combo.addItems(["Keep All", "Auto-Delete", "Archive"])
        self.history_combo.setCurrentIndex(0)
        history_card.addRow("History mode", self.history_combo)

        self.threshold_field = LineEdit()
        self.threshold_field.setText("30")
        self.threshold_field.setPlaceholderText("30")
        self.threshold_row = history_card.addRow("Threshold (days)", self.threshold_field)

        self.history_combo.currentIndexChanged.connect(self._on_history_mode_changed)
        self._on_history_mode_changed(0)

        layout.addWidget(history_card)

        system_card = WizardCard("⚙️ System")

        self.startup_switch = SwitchButton()
        self.startup_switch.setChecked(False)
        system_card.addRow("Start at login", self.startup_switch)

        layout.addWidget(system_card)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_btn = PrimaryPushButton("Get Started")
        self.save_btn.setMinimumWidth(180)
        self.save_btn.setMinimumHeight(36)
        self.save_btn.clicked.connect(self._save_settings)
        btn_row.addWidget(self.save_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _on_history_mode_changed(self, index):
        self.threshold_row.setVisible(index != 0)

    def _on_personal_key_toggled(self, checked):
        self.password_field.setEnabled(checked)

    def _on_theme_changed(self, index):
        if index == 2:
            setTheme(Theme.DARK)
        elif index == 1:
            setTheme(Theme.LIGHT)
        else:
            system_theme = get_system_theme()
            setTheme(Theme.DARK if system_theme == "dark" else Theme.LIGHT)

    def _save_settings(self):
        theme_text = self.theme_combo.currentText().lower()
        if "system" in theme_text:
            theme = "system"
        elif "light" in theme_text:
            theme = "light"
        else:
            theme = "dark"

        history_text = self.history_combo.currentText().lower()
        if history_text == "keep all":
            history_management = "keep"
        else:
            history_management = history_text

        self.settings = {
            "encryption_enabled": self.encryption_switch.isChecked(),
            "use_personal_key": self.personal_key_switch.isChecked(),
            "personal_key": self.password_field.text().strip() if self.personal_key_switch.isChecked() else "",
            "theme": theme,
            "show_timestamps": self.timestamps_switch.isChecked(),
            "start_at_startup": self.startup_switch.isChecked(),
            "custom_font_path": "",
            "history_management": history_management,
            "history_threshold_days": self.threshold_field.text().strip(),
        }

        if self.startup_switch.isChecked():
            add_to_startup()
        else:
            remove_from_startup()

        self.accept()

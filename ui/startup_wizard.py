from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QLabel, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QFileDialog, QWidget
from utils import get_app_font, get_system_theme, RAVENS_WING_DARK_STYLE
import sys
import os
import platform

def add_to_startup():
    if platform.system() == "Windows":
        import winreg
        app_path = sys.argv[0]
        reg_key = winreg.HKEY_CURRENT_USER
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_name = "ClipboardManager"
        with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, app_path)
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
            f.write(f"""[Desktop Entry]\nName=ClipboardManager\nExec={app_path}\nType=Application\nX-GNOME-Autostart-enabled=true\n""")

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

class StartupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("initial setup")
        self.app_font = get_app_font(10)
        self.setFont(self.app_font)
        self.setupUI()
        self.settings = None

    def setupUI(self):
        layout = QVBoxLayout()

        self.encryption_checkbox = QCheckBox("enable encryption")
        self.encryption_checkbox.setChecked(True)
        layout.addWidget(self.encryption_checkbox)

        self.personal_key_checkbox = QCheckBox("use personal key/password")
        layout.addWidget(self.personal_key_checkbox)

        self.password_label = QLabel("enter password:")
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.Password)
        self.password_field.setEnabled(False)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_field)

        self.personal_key_checkbox.stateChanged.connect(
            lambda: self.password_field.setEnabled(self.personal_key_checkbox.isChecked())
        )

        theme_label = QLabel("select theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system (default)", "light", "dark"])
        self.theme_combo.setCurrentIndex(0)
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)

        self.theme_combo.currentTextChanged.connect(self.update_theme)

        font_label = QLabel("custom font (optional):")
        self.font_path_field = QLineEdit()
        self.font_browse_button = QPushButton("browse")
        self.font_browse_button.clicked.connect(self.browse_font)
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.font_path_field)
        font_layout.addWidget(self.font_browse_button)
        layout.addWidget(font_label)
        layout.addLayout(font_layout)

        self.timestamps_checkbox = QCheckBox("show timestamps in history")
        self.timestamps_checkbox.setChecked(True)
        layout.addWidget(self.timestamps_checkbox)

        self.startup_checkbox = QCheckBox("start at startup")
        self.startup_checkbox.setChecked(False)
        layout.addWidget(self.startup_checkbox)

        history_mgmt_label = QLabel("history management:")
        self.history_mgmt_combo = QComboBox()
        self.history_mgmt_combo.addItems(["keep all", "auto-delete", "archive"])
        layout.addWidget(history_mgmt_label)
        layout.addWidget(self.history_mgmt_combo)

        threshold_label = QLabel("threshold (days):")
        self.threshold_field = QLineEdit("30")
        layout.addWidget(threshold_label)
        layout.addWidget(self.threshold_field)

        self.save_button = QPushButton("save settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        self.setLayout(layout)
        self.update_theme(self.theme_combo.currentText())

    def browse_font(self):
        font_file, _ = QFileDialog.getOpenFileName(self, "select font file", "", "font files (*.ttf *.otf)")
        if font_file:
            self.font_path_field.setText(font_file)
            new_font = get_app_font(10, {"custom_font_path": font_file})
            self.app_font = new_font
            self.setFont(new_font)
            for widget in self.findChildren(QWidget):
                widget.setFont(new_font)

    def update_theme(self, theme):
        theme_lower = theme.lower()
        if "dark" in theme_lower:
            self.setStyleSheet(RAVENS_WING_DARK_STYLE)
        elif "system" in theme_lower:
            system_theme = get_system_theme()
            if system_theme == "dark":
                self.setStyleSheet(RAVENS_WING_DARK_STYLE)
            else:
                self.setStyleSheet("")
        else:
            self.setStyleSheet("")
        self.setFont(self.app_font)
        for widget in self.findChildren(QWidget):
            widget.setFont(self.app_font)

    def save_settings(self):
        encryption_enabled = self.encryption_checkbox.isChecked()
        use_personal_key = self.personal_key_checkbox.isChecked()
        password = self.password_field.text().strip() if use_personal_key else ""
        theme = self.theme_combo.currentText().lower()
        if "system" in theme:
            theme = "system"
        show_timestamps = self.timestamps_checkbox.isChecked()
        start_at_startup = self.startup_checkbox.isChecked()
        custom_font_path = self.font_path_field.text().strip()
        history_management = self.history_mgmt_combo.currentText().lower()
        if history_management == "keep all":
            history_management = "keep"
        history_threshold_days = self.threshold_field.text().strip()
        self.settings = {
            "encryption_enabled": encryption_enabled,
            "use_personal_key": use_personal_key,
            "personal_key": password,
            "theme": theme,
            "show_timestamps": show_timestamps,
            "start_at_startup": start_at_startup,
            "custom_font_path": custom_font_path,
            "history_management": history_management,
            "history_threshold_days": history_threshold_days
        }
        if start_at_startup:
            add_to_startup()
        else:
            remove_from_startup()
        self.accept() 
import sys
import os
import tempfile
import sqlite3
import datetime
import re
import platform
import json
import base64
import hashlib

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QListWidget, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu, QStyle,
    QDialog, QLabel, QCheckBox, QComboBox, QHBoxLayout
)
from PySide6.QtGui import QAction, QFontDatabase, QFont, QIcon
from PySide6.QtCore import Qt

from cryptography.fernet import Fernet

# --- dummy encryption (for no encryption mode) ---
class DummyFernet:
    def encrypt(self, text_bytes):
        return text_bytes
    def decrypt(self, token):
        return token

# --- global variables? ---
JETBRAINS_FONT = None

# --- helper: load jetbrains mono font (always use JetBrainsMono, we like JetBrainsMono) ---
def get_jetbrains_font(size=10):
    global JETBRAINS_FONT
    if JETBRAINS_FONT is None:
        # Handle packaged environment
        if getattr(sys, 'frozen', False):
            # Running in a PyInstaller bundle
            font_path = os.path.join(sys._MEIPASS, "JetBrainsMono-Regular.ttf")
        else:
            # Running in a normal Python environment
            font_path = "JetBrainsMono-Regular.ttf"

        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print("Failed to load JetBrainsMono font.")
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            JETBRAINS_FONT = QFont(families[0], size)
        else:
            # Fallback to system-installed JetBrainsMono
            JETBRAINS_FONT = QFont("JetBrainsMono", size)
            if JETBRAINS_FONT.family() != "JetBrainsMono":
                # Fallback to a monospace font if JetBrainsMono is not available
                JETBRAINS_FONT = QFont("Monospace", size)
                print("JetBrainsMono not found, falling back to Monospace")
    return JETBRAINS_FONT

# --- settings personal key encryption utilities ---
# uses a unique key stored per user in the app folder (SETTINGS_ENCRYPTION_KEY is set in main)
def encrypt_personal_key(plain_key: str) -> str:
    f = Fernet(SETTINGS_ENCRYPTION_KEY)
    return f.encrypt(plain_key.encode()).decode()

def decrypt_personal_key(enc_key: str) -> str:
    f = Fernet(SETTINGS_ENCRYPTION_KEY)
    try:
        return f.decrypt(enc_key.encode()).decode()
    except Exception:
        return ""

# --- encryption utilities ---
def load_key(key_file):
    # load or generate an encryption key.
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
    return key

def encrypt_text(text, fernet):
    return fernet.encrypt(text.encode())

def decrypt_text(token, fernet):
    try:
        return fernet.decrypt(token).decode()
    except Exception:
        return ""

# --- startup handling ---
def add_to_startup():
    if platform.system() == "Windows":
        import winreg
        app_path = sys.argv[0]
        reg_key = winreg.HKEY_CURRENT_USER
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_name = "ClipboardManager"
        with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, app_path)
    elif platform.system() == "Darwin":  # macOS
        app_path = sys.argv[0]
        os.system(f"osascript -e 'tell application \"System Events\" to make login item at end with properties {{name:\"ClipboardManager\", path:\"{app_path}\", hidden:true}}'")
    elif platform.system() == "Linux":
        app_path = sys.argv[0]
        autostart_dir = os.path.expanduser("~/.config/autostart")
        if not os.path.exists(autostart_dir):
            os.makedirs(autostart_dir)
        desktop_entry = os.path.join(autostart_dir, "clipboardmanager.desktop")
        with open(desktop_entry, "w") as f:
            f.write(f"""[Desktop Entry]
Name=ClipboardManager
Exec={app_path}
Type=Application
X-GNOME-Autostart-enabled=true
            """)

def remove_from_startup():
    if platform.system() == "Windows":
        import winreg
        reg_key = winreg.HKEY_CURRENT_USER
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_name = "ClipboardManager"
        try:
            with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, reg_name)  # Check if the value exists
            # If the value exists, delete it
            with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, reg_name)
        except FileNotFoundError:
            # If the value doesn't exist, do nothing
            pass
    elif platform.system() == "Darwin":
        os.system("osascript -e 'tell application \"System Events\" to delete login item \"ClipboardManager\"'")
    elif platform.system() == "Linux":
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_entry = os.path.join(autostart_dir, "clipboardmanager.desktop")
        if os.path.exists(desktop_entry):
            os.remove(desktop_entry)

# --- code detection heuristic ---
def is_code(text):
    if "\n" in text:
        indicators = [
            # c/c++/c#
            '#include', 'std::', 'printf', 'scanf', 'cout', 'cin', '->', '::',
            'console.writeline', 'using System',
            # python
            'def ', 'class ', 'import ', 'print(', 'lambda ',
            # javascript/typescript
            'function ', 'console.log', 'var ', 'let ', 'const ', '=>',
            # java
            'public ', 'private ', 'protected ', 'system.out.println',
            # rust
            'fn ', 'println!',
            # go
            'func ', 'package ', 'import ', 'package main',
            # php
            '<?php', 'echo ', '->',
            # swift
            'import ', 'func ',
            # additional
            'struct ', 'defmodule '
        ]
        for ind in indicators:
            if ind in text:
                return 1
    return 0

# --- database manager ---
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.create_table()

    def create_table(self):
        c = self.conn.cursor()
        c.execute('''
            create table if not exists history (
                id integer primary key autoincrement,
                text blob,
                timestamp text,
                is_code integer
            )
        ''')
        self.conn.commit()

    def add_entry(self, encrypted_text, timestamp, is_code_flag):
        c = self.conn.cursor()
        c.execute(
            "insert into history (text, timestamp, is_code) values (?, ?, ?)",
            (encrypted_text, timestamp, is_code_flag)
        )
        self.conn.commit()

    def get_all_entries(self):
        c = self.conn.cursor()
        c.execute("select id, text, timestamp, is_code from history order by id desc")
        return c.fetchall()

    def get_entry_by_id(self, entry_id):
        c = self.conn.cursor()
        c.execute("select text from history where id=?", (entry_id,))
        return c.fetchone()

# --- settings manager ---
class SettingsManager:
    @staticmethod
    def load_settings(settings_path):
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            # if using a personal key, decrypt it
            if settings.get("use_personal_key", False) and settings.get("personal_key", ""):
                settings["personal_key"] = decrypt_personal_key(settings["personal_key"])
            return settings
        else:
            return None

    @staticmethod
    def save_settings(settings, settings_path):
        # if using a personal key, encrypt it before saving
        settings_to_save = settings.copy()
        if settings.get("use_personal_key", False) and settings.get("personal_key", ""):
            settings_to_save["personal_key"] = encrypt_personal_key(settings["personal_key"])
        with open(settings_path, 'w') as f:
            json.dump(settings_to_save, f, indent=4)

# --- startup wizard (runs on first launch) ---
class StartupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Initial Setup")
        self.jetbrains_font = get_jetbrains_font(10)
        self.setFont(self.jetbrains_font)
        self.setupUI()
        self.settings = None

    def setupUI(self):
        layout = QVBoxLayout()

        # encryption enabled checkbox
        self.encryption_checkbox = QCheckBox("enable encryption")
        self.encryption_checkbox.setChecked(True)
        layout.addWidget(self.encryption_checkbox)

        # personal key option
        self.personal_key_checkbox = QCheckBox("use personal key/password")
        layout.addWidget(self.personal_key_checkbox)

        # password field (enabled only if personal key is checked)
        self.password_label = QLabel("enter password:")
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.Password)
        self.password_field.setEnabled(False)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_field)

        self.personal_key_checkbox.stateChanged.connect(
            lambda: self.password_field.setEnabled(self.personal_key_checkbox.isChecked())
        )

        # theme selection
        theme_label = QLabel("select theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)
        self.theme_combo.currentTextChanged.connect(self.update_theme)

        # toggle timestamps
        self.timestamps_checkbox = QCheckBox("show timestamps in history")
        self.timestamps_checkbox.setChecked(True)
        layout.addWidget(self.timestamps_checkbox)

        # start at startup checkbox
        self.startup_checkbox = QCheckBox("start at startup")
        layout.addWidget(self.startup_checkbox)

        # save button
        self.save_button = QPushButton("save settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        self.setLayout(layout)
        self.update_theme(self.theme_combo.currentText())

    def update_theme(self, theme):
        if theme.lower() == "dark":
            self.setStyleSheet("background-color: #2d2d2d; color: #ffffff;")
        else:
            self.setStyleSheet("")
        # always reapply jetbrains mono font
        self.setFont(self.jetbrains_font)
        for widget in self.findChildren(QWidget):
            widget.setFont(self.jetbrains_font)

    def save_settings(self):
        encryption_enabled = self.encryption_checkbox.isChecked()
        use_personal_key = self.personal_key_checkbox.isChecked()
        password = self.password_field.text().strip() if use_personal_key else ""
        theme = self.theme_combo.currentText().lower()
        show_timestamps = self.timestamps_checkbox.isChecked()
        start_at_startup = self.startup_checkbox.isChecked()
        self.settings = {
            "encryption_enabled": encryption_enabled,
            "use_personal_key": use_personal_key,
            "personal_key": password,  # will be encrypted when saving settings.
            "theme": theme,
            "show_timestamps": show_timestamps,
            "start_at_startup": start_at_startup
        }

        if start_at_startup:
            add_to_startup()
        else:
            remove_from_startup()

        self.accept()

# --- settings dialog (accessible from tray menu) ---
class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.jetbrains_font = get_jetbrains_font(10)
        self.setFont(self.jetbrains_font)
        self.current_settings = current_settings.copy()
        self.setupUI()

    def setupUI(self):
        layout = QVBoxLayout()

        self.encryption_checkbox = QCheckBox("enable encryption")
        self.encryption_checkbox.setChecked(self.current_settings.get("encryption_enabled", True))
        layout.addWidget(self.encryption_checkbox)

        self.personal_key_checkbox = QCheckBox("use personal key/password")
        self.personal_key_checkbox.setChecked(self.current_settings.get("use_personal_key", False))
        layout.addWidget(self.personal_key_checkbox)

        self.password_label = QLabel("enter password:")
        self.password_field = QLineEdit()
        self.password_field.setEchoMode(QLineEdit.Password)
        self.password_field.setText(self.current_settings.get("personal_key", ""))
        self.password_field.setEnabled(self.personal_key_checkbox.isChecked())
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_field)

        self.personal_key_checkbox.stateChanged.connect(
            lambda: self.password_field.setEnabled(self.personal_key_checkbox.isChecked())
        )

        theme_label = QLabel("select theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        current_theme = self.current_settings.get("theme", "light").capitalize()
        index = self.theme_combo.findText(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)

        self.timestamps_checkbox = QCheckBox("show timestamps in history")
        self.timestamps_checkbox.setChecked(self.current_settings.get("show_timestamps", True))
        layout.addWidget(self.timestamps_checkbox)

        self.startup_checkbox = QCheckBox("start at startup")
        layout.addWidget(self.startup_checkbox)

        self.save_button = QPushButton("save settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def save_settings(self):
        encryption_enabled = self.encryption_checkbox.isChecked()
        use_personal_key = self.personal_key_checkbox.isChecked()
        password = self.password_field.text().strip() if use_personal_key else ""
        theme = self.theme_combo.currentText().lower()
        show_timestamps = self.timestamps_checkbox.isChecked()
        start_at_startup = self.startup_checkbox.isChecked()
        self.current_settings.update({
            "encryption_enabled": encryption_enabled,
            "use_personal_key": use_personal_key,
            "personal_key": password,
            "theme": theme,
            "show_timestamps": show_timestamps,
            "start_at_startup": start_at_startup
        })

        if start_at_startup:
            add_to_startup()
        else:
            remove_from_startup()

        self.accept()

# --- main gui application ---
class ClipboardManager(QMainWindow):
    def __init__(self, db_manager, fernet, settings, app_dir):
        super().__init__()
        self.jetbrains_font = get_jetbrains_font(10)
        self.setFont(self.jetbrains_font)
        self.db_manager = db_manager
        self.fernet = fernet
        self.settings = settings
        self.app_dir = app_dir
        self._allow_exit = False  # flag to allow proper exit

        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.last_clipboard_text = ""

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Clipboard Manager")
        self.setGeometry(100, 100, 600, 400)
        self.jetbrains_font = get_jetbrains_font(10)
        self.setFont(self.jetbrains_font)

        # apply theme
        if self.settings.get("theme", "light") == "dark":
            self.setStyleSheet("background-color: #2d2d2d; color: #ffffff;")
        else:
            self.setStyleSheet("")

        # main widget layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("search clipboard history... (use '*' as wildcard, e.g. [code])")
        self.search_bar.textChanged.connect(self.on_search)
        layout.addWidget(self.search_bar)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_click)
        layout.addWidget(self.list_widget)

        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)
        layout.addWidget(self.detail_view)

        # button to copy the selected snippet back to clipboard
        self.copy_button = QPushButton("Copy to clipboard")
        self.copy_button.clicked.connect(self.copy_selected)
        layout.addWidget(self.copy_button)

        central_widget.setLayout(layout)

        self.load_history()

        # setup system tray icon for background operation
        script_dir = os.path.dirname(os.path.realpath(__file__))

        # Handle both development and PyInstaller-packaged environments
        if getattr(sys, 'frozen', False):
            # running in a PyInstaller bundle
            clipboard_icon_path = os.path.join(sys._MEIPASS, "clipboard.png")
        else:
            # running in a normal Python environment
            clipboard_icon_path = os.path.join(script_dir, "clipboard.png")

        if os.path.exists(clipboard_icon_path):
            icon = QIcon(clipboard_icon_path)
        else:
            # fallback
            icon = self.style().standardIcon(QStyle.SP_FileIcon)
            print("clipboard.png not found, falling back to default icon")

        # set up the system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icon)
        tray_menu = QMenu()

        restore_action = QAction("restore", self)
        restore_action.triggered.connect(self.show)
        tray_menu.addAction(restore_action)

        settings_action = QAction("settings", self)
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addAction(settings_action)

        exit_action = QAction("exit", self)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def closeEvent(self, event):
        # override close event to hide window (minimize to tray) unless exit is allowed
        if self._allow_exit:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def exit_app(self):
        # allow exit and quit the application
        self._allow_exit = True
        self.close()
        QApplication.quit()

    def on_tray_icon_activated(self, reason):
        # on double click, show the window
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def on_clipboard_change(self):
        text = self.clipboard.text()
        if text and text != self.last_clipboard_text:
            self.last_clipboard_text = text
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
            code_flag = is_code(text)
            encrypted_text = encrypt_text(text, self.fernet)
            self.db_manager.add_entry(encrypted_text, timestamp, code_flag)
            self.load_history()

    def load_history(self):
        self.list_widget.clear()
        entries = self.db_manager.get_all_entries()
        show_timestamps = self.settings.get("show_timestamps", True)
        for entry in entries:
            decrypted_text = decrypt_text(entry[1], self.fernet)
            preview = decrypted_text[:50] + "..." if len(decrypted_text) > 50 else decrypted_text
            code_indicator = "[code] " if entry[3] else ""
            if show_timestamps:
                item_text = f"{entry[0]} - {code_indicator}{preview} ({entry[2]})"
            else:
                item_text = f"{entry[0]} - {code_indicator}{preview}"
            self.list_widget.addItem(item_text)

    def on_search(self, search_term):
        self.list_widget.clear()
        entries = self.db_manager.get_all_entries()
        show_timestamps = self.settings.get("show_timestamps", True)
        # if search term is exactly "[code]", filter for code-only entries
        if search_term.strip().lower() == "[code]":
            for entry in entries:
                if entry[3]:
                    decrypted_text = decrypt_text(entry[1], self.fernet)
                    preview = decrypted_text[:50] + "..." if len(decrypted_text) > 50 else decrypted_text
                    item_text = f"{entry[0]} - [code] {preview} ({entry[2]})" if show_timestamps else f"{entry[0]} - [code] {preview}"
                    self.list_widget.addItem(item_text)
            return
        try:
            pattern = re.compile(search_term.replace('*', '.*'), re.IGNORECASE)
        except Exception:
            pattern = None
        for entry in entries:
            decrypted_text = decrypt_text(entry[1], self.fernet)
            if pattern and pattern.search(decrypted_text):
                preview = decrypted_text[:50] + "..." if len(decrypted_text) > 50 else decrypted_text
                code_indicator = "[code] " if entry[3] else ""
                item_text = f"{entry[0]} - {code_indicator}{preview} ({entry[2]})" if show_timestamps else f"{entry[0]} - {code_indicator}{preview}"
                self.list_widget.addItem(item_text)

    def on_item_click(self, item):
        item_text = item.text()
        entry_id = int(item_text.split(" - ")[0])
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            decrypted_text = decrypt_text(row[0], self.fernet)
            self.detail_view.setPlainText(decrypted_text)

    def copy_selected(self):
        clipboard_text = self.detail_view.toPlainText()
        if clipboard_text:
            self.clipboard.setText(clipboard_text)

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            self.settings.update(dialog.current_settings)
            settings_path = os.path.join(self.app_dir, "settings.json")
            SettingsManager.save_settings(self.settings, settings_path)
            if self.settings.get("theme", "light") == "dark":
                self.setStyleSheet("background-color: #2d2d2d; color: #ffffff;")
            else:
                self.setStyleSheet("")
            self.setFont(self.jetbrains_font)
            self.load_history()

# --- main execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    home_dir = os.path.expanduser("~")
    app_dir = os.path.join(home_dir, "ClipboardManager")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)

    temp_folder = temp_folder = tempfile.gettempdir()
    db_path = os.path.join(app_dir, "clipboard_manager.db")
    key_file = os.path.join(app_dir, "clipboard_manager.key")
    settings_file = os.path.join(app_dir, "settings.json")
    settings_key_file = os.path.join(temp_folder, "settings_key.key")

    if os.path.exists(settings_key_file):
        with open(settings_key_file, 'rb') as f:
            SETTINGS_ENCRYPTION_KEY = f.read()
    else:
        SETTINGS_ENCRYPTION_KEY = Fernet.generate_key()
        with open(settings_key_file, 'wb') as f:
            f.write(SETTINGS_ENCRYPTION_KEY)

    settings = SettingsManager.load_settings(settings_file)
    if settings is None:
        wizard = StartupWizard()
        if wizard.exec() == QDialog.Accepted:
            settings = wizard.settings
            SettingsManager.save_settings(settings, settings_file)
        else:
            sys.exit(0)

    if settings.get("encryption_enabled", True):
        if settings.get("use_personal_key", False) and settings.get("personal_key", ""):
            password = settings.get("personal_key")
            derived_key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
            fernet = Fernet(derived_key)
        else:
            key = load_key(key_file)
            fernet = Fernet(key)
    else:
        fernet = DummyFernet()

    db_manager = DatabaseManager(db_path)
    window = ClipboardManager(db_manager, fernet, settings, app_dir)
    window.show()
    sys.exit(app.exec())

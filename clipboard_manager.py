# region --- imports ---
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
import subprocess

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu, QStyle,
    QDialog, QLabel, QCheckBox, QComboBox, QHBoxLayout, QFileDialog, QToolButton, QTabWidget
)
from PySide6.QtGui import QAction, QFontDatabase, QFont, QIcon
from PySide6.QtCore import Qt, Signal

from cryptography.fernet import Fernet

# --- dummy encryption (for no encryption mode) ---
class DummyFernet:
    def encrypt(self, text_bytes):
        return text_bytes

    def decrypt(self, token):
        return token

# --- global dark style (raven's wing palette, with lighter text) ---
RAVENS_WING_DARK_STYLE = """
QWidget {
    background-color: #2c2f33;
    color: #d0d0d0;
}
QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QPushButton, QToolButton {
    border: 1px solid #23272a;
    border-radius: 8px;
    padding: 6px;
    background-color: #2c2f33;
    color: #d0d0d0;
}
QPushButton {
    background-color: #7289da;
}
QPushButton:hover {
    background-color: #677bc4;
}
"""

# region --- global vars/helpers ---
JETBRAINS_FONT = None

def get_icon_path(icon_name):
    # return the full path for the given icon based on packaging
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, icon_name)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name)

# --- load jetbrains font helper ---
def get_jetbrains_font(size=10):
    global JETBRAINS_FONT
    if JETBRAINS_FONT is None:
        # handle packaged environment
        if getattr(sys, 'frozen', False):
            font_path = os.path.join(sys._MEIPASS, "JetBrainsMono-Regular.ttf")
        else:
            font_path = "JetBrainsMono-Regular.ttf"
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print("failed to load jetbrainsmono font.")
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            JETBRAINS_FONT = QFont(families[0], size)
        else:
            JETBRAINS_FONT = QFont("JetBrainsMono", size)
            if JETBRAINS_FONT.family() != "JetBrainsMono":
                JETBRAINS_FONT = QFont("Monospace", size)
                print("jetbrainsmono not found, falling back to monospace")
    return JETBRAINS_FONT

# --- load app font helper ---
def get_app_font(size=10, settings=None):
    # use custom font if provided in settings
    custom_font_path = settings.get("custom_font_path") if settings else None
    if custom_font_path and os.path.exists(custom_font_path):
        font_id = QFontDatabase.addApplicationFont(custom_font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return QFont(families[0], size)
    return get_jetbrains_font(size)

# region --- system theme detection ---
def get_system_theme():
    # determine system theme based on os settings
    if platform.system() == "Windows":
        try:
            import winreg
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(reg_key, "AppsUseLightTheme")
            winreg.CloseKey(reg_key)
            return "light" if value == 1 else "dark"
        except Exception:
            return "light"
    elif platform.system() == "Darwin":
        try:
            result = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                    capture_output=True, text=True)
            if "Dark" in result.stdout:
                return "dark"
            else:
                return "light"
        except Exception:
            return "light"
    elif platform.system() == "Linux":
        gtk_theme = os.environ.get("GTK_THEME", "").lower()
        if "dark" in gtk_theme:
            return "dark"
        try:
            result = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                                    capture_output=True, text=True)
            theme_name = result.stdout.strip().strip("'").lower()
            if "dark" in theme_name:
                return "dark"
        except Exception:
            pass
        return "light"
    else:
        return "light"

# region --- settings personal key encryption utilities ---
def encrypt_personal_key(plain_key: str) -> str:
    f = Fernet(SETTINGS_ENCRYPTION_KEY)
    return f.encrypt(plain_key.encode()).decode()

def decrypt_personal_key(enc_key: str) -> str:
    f = Fernet(SETTINGS_ENCRYPTION_KEY)
    try:
        return f.decrypt(enc_key.encode()).decode()
    except Exception:
        return ""

# region --- encryption utilities ---
def load_key(key_file):
    # load key from file or generate a new one
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

# region --- startup handling ---
def add_to_startup():
    # add app to system startup based on os
    if platform.system() == "Windows":
        import winreg
        app_path = sys.argv[0]
        reg_key = winreg.HKEY_CURRENT_USER
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_name = "ClipboardManager"
        with winreg.OpenKey(reg_key, reg_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, app_path)
    elif platform.system() == "Darwin":  # macos
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

# region --- code detection ---
def is_code(text):
    # simple heuristic to detect if text is code
    if "\n" not in text:
        return 0
    patterns = [
        r'\b(?:def|class|import|from|return|if|elif|else|for|while|try|except|with|lambda)\b',
        r'#include\s*[<"].+[>"]',
        r'\b(?:public|private|protected|static|void|int|float|double|String|bool|boolean)\b',
        r'\b(?:console\.log|System\.out\.println|printf|scanf|std::)\b',
        r'\b(?:function|var|let|const|=>)\b',
        r'<\?php',
        r'\b(?:fn|println!|struct|defmodule)\b'
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            return 1
    return 0

# region --- database manager ---
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
                is_code integer,
                pinned integer default 0,
                favorite integer default 0
            )
        ''')
        self.conn.commit()

    def add_entry(self, encrypted_text, timestamp, is_code_flag):
        c = self.conn.cursor()
        # when adding new entry, pinned and favorite default to 0.
        c.execute(
            "insert into history (text, timestamp, is_code, pinned, favorite) values (?, ?, ?, 0, 0)",
            (encrypted_text, timestamp, is_code_flag)
        )
        self.conn.commit()

    def get_all_entries(self):
        c = self.conn.cursor()
        # order so that pinned entries appear at the top.
        c.execute("select id, text, timestamp, is_code, pinned, favorite from history order by pinned desc, id desc")
        return c.fetchall()

    def get_entry_by_id(self, entry_id):
        c = self.conn.cursor()
        c.execute("select text, pinned, favorite from history where id=?", (entry_id,))
        return c.fetchone()

    def update_pin_state(self, entry_id, new_state):
        c = self.conn.cursor()
        c.execute("update history set pinned = ? where id = ?", (new_state, entry_id))
        self.conn.commit()

    def update_favorite_state(self, entry_id, new_state):
        c = self.conn.cursor()
        c.execute("update history set favorite = ? where id = ?", (new_state, entry_id))
        self.conn.commit()

    def delete_entries_older_than(self, cutoff_timestamp):
        c = self.conn.cursor()
        c.execute("delete from history where timestamp < ?", (cutoff_timestamp,))
        self.conn.commit()

    def delete_entry_by_id(self, entry_id):
        c = self.conn.cursor()
        c.execute("delete from history where id = ?", (entry_id,))
        self.conn.commit()

# region --- archive manager ---
class ArchiveDatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.create_table()

    def create_table(self):
        c = self.conn.cursor()
        c.execute('''
            create table if not exists archive_history (
                id integer primary key autoincrement,
                text blob,
                timestamp text,
                is_code integer,
                pinned integer default 0,
                favorite integer default 0
            )
        ''')
        self.conn.commit()

    def add_entry(self, entry):
        c = self.conn.cursor()
        c.execute(
            "insert into archive_history (text, timestamp, is_code, pinned, favorite) values (?, ?, ?, ?, ?)",
            (entry[1], entry[2], entry[3], entry[4], entry[5])
        )
        self.conn.commit()

# region --- history management helper ---
def manage_history(db_manager, settings, app_dir):
    # manage history based on settings
    mode = settings.get("history_management", "keep")  # "keep", "auto-delete", "archive"
    try:
        threshold_days = int(settings.get("history_threshold_days", "30"))
    except ValueError:
        threshold_days = 30
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=threshold_days)).strftime("%Y-%m-%d %H:%M:%S")
    if mode == "auto-delete":
        db_manager.delete_entries_older_than(cutoff)
    elif mode == "archive":
        archive_db_path = os.path.join(app_dir, "clipboard_manager_archive.db")
        archive_db_manager = ArchiveDatabaseManager(archive_db_path)
        # for simplicity, get all entries older than cutoff and archive them.
        # (todo: add a method to get those entries as needed.)
        entries = db_manager.get_all_entries()
        for entry in entries:
            if entry[2] < cutoff:
                archive_db_manager.add_entry(entry)
                db_manager.delete_entry_by_id(entry[0])

# region --- settings manager ---
class SettingsManager:
    @staticmethod
    def load_settings(settings_path):
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            if settings.get("use_personal_key", False) and settings.get("personal_key", ""):
                settings["personal_key"] = decrypt_personal_key(settings["personal_key"])
            return settings
        else:
            return None

    @staticmethod
    def save_settings(settings, settings_path):
        settings_to_save = settings.copy()
        if settings.get("use_personal_key", False) and settings.get("personal_key", ""):
            settings_to_save["personal_key"] = encrypt_personal_key(settings["personal_key"])
        with open(settings_path, 'w') as f:
            json.dump(settings_to_save, f, indent=4)

# region --- custom history list item widget ---
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
        self.trash_button.setIcon(QIcon(get_icon_path("trash.png")))
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
            # emit signal if click is not on any button
            if not (self.trash_button.underMouse() or self.star_button.underMouse() or self.pin_button.underMouse()):
                self.clicked.emit(self.entry_id)
        super().mousePressEvent(event)

    def update_icons(self, pinned, favorite):
        self.pinned = pinned
        self.favorite = favorite
        self.pin_button.setIcon(QIcon(get_icon_path("pin_active.png") if self.pinned else get_icon_path("pin.png")))
        self.star_button.setIcon(QIcon(get_icon_path("star_active.png") if self.favorite else get_icon_path("star.png")))

# region --- startup wizard ---
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

# region --- settings tray dialog ---
class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("settings")
        self.current_settings = current_settings.copy()
        self.app_font = get_app_font(10, self.current_settings)
        self.setFont(self.app_font)
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
        self.theme_combo.addItems(["system (default)", "light", "dark"])
        self.theme_combo.setCurrentIndex(0)
        current_theme = self.current_settings.get("theme", "system")
        if current_theme == "light":
            self.theme_combo.setCurrentIndex(1)
        elif current_theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)

        font_label = QLabel("custom font (optional):")
        self.font_path_field = QLineEdit()
        self.font_path_field.setText(self.current_settings.get("custom_font_path", ""))
        self.font_browse_button = QPushButton("browse")
        self.font_browse_button.clicked.connect(self.browse_font)
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.font_path_field)
        font_layout.addWidget(self.font_browse_button)
        layout.addWidget(font_label)
        layout.addLayout(font_layout)

        self.timestamps_checkbox = QCheckBox("show timestamps in history")
        self.timestamps_checkbox.setChecked(self.current_settings.get("show_timestamps", True))
        layout.addWidget(self.timestamps_checkbox)

        self.startup_checkbox = QCheckBox("start at startup")
        self.startup_checkbox.setChecked(self.current_settings.get("start_at_startup", False))
        layout.addWidget(self.startup_checkbox)

        history_mgmt_label = QLabel("history management:")
        self.history_mgmt_combo = QComboBox()
        self.history_mgmt_combo.addItems(["keep all", "auto-delete", "archive"])
        current_history = self.current_settings.get("history_management", "keep").lower()
        if current_history == "keep":
            self.history_mgmt_combo.setCurrentIndex(0)
        elif current_history == "auto-delete":
            self.history_mgmt_combo.setCurrentIndex(1)
        elif current_history == "archive":
            self.history_mgmt_combo.setCurrentIndex(2)
        layout.addWidget(history_mgmt_label)
        layout.addWidget(self.history_mgmt_combo)

        threshold_label = QLabel("threshold (days):")
        self.threshold_field = QLineEdit(self.current_settings.get("history_threshold_days", "30"))
        layout.addWidget(threshold_label)
        layout.addWidget(self.threshold_field)

        self.save_button = QPushButton("save settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def browse_font(self):
        font_file, _ = QFileDialog.getOpenFileName(self, "select font file", "", "font files (*.ttf *.otf)")
        if font_file:
            self.font_path_field.setText(font_file)
            new_font = get_app_font(10, {"custom_font_path": font_file})
            self.app_font = new_font
            self.setFont(new_font)
            for widget in self.findChildren(QWidget):
                widget.setFont(new_font)

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
        self.current_settings.update({
            "encryption_enabled": encryption_enabled,
            "use_personal_key": use_personal_key,
            "personal_key": password,
            "theme": theme,
            "show_timestamps": show_timestamps,
            "start_at_startup": start_at_startup,
            "custom_font_path": custom_font_path,
            "history_management": history_management,
            "history_threshold_days": history_threshold_days
        })
        if start_at_startup:
            add_to_startup()
        else:
            remove_from_startup()
        self.accept()

# region --- main gui application ---
class ClipboardManager(QMainWindow):
    def __init__(self, db_manager, fernet, settings, app_dir):
        super().__init__()
        self.settings = settings
        self.app_font = get_app_font(10, self.settings)
        self.setFont(self.app_font)
        self.db_manager = db_manager
        self.fernet = fernet
        self.app_dir = app_dir
        self._allow_exit = False

        self.tab_widget = QTabWidget()
        self.all_list = QListWidget()
        self.fav_list = QListWidget()
        self.tab_widget.addTab(self.all_list, "all")
        self.tab_widget.addTab(self.fav_list, "favorites")
        
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.last_clipboard_text = ""

        self.initUI()

    def initUI(self):
        self.setWindowTitle("clipboard manager")
        self.setGeometry(100, 100, 600, 400)
        self.setFont(self.app_font)
        theme = self.settings.get("theme", "light")
        if "dark" in theme:
            self.setStyleSheet(RAVENS_WING_DARK_STYLE)
        elif "system" in theme:
            system_theme = get_system_theme()
            if system_theme == "dark":
                self.setStyleSheet(RAVENS_WING_DARK_STYLE)
            else:
                self.setStyleSheet("")
        else:
            self.setStyleSheet("")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("search clipboard history... (filters: date:yyyy-mm-dd, type:code/text)")
        self.search_bar.textChanged.connect(self.on_search)
        layout.addWidget(self.search_bar)

        layout.addWidget(self.tab_widget)

        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)
        layout.addWidget(self.detail_view)

        self.copy_button = QPushButton("copy to clipboard")
        self.copy_button.clicked.connect(self.copy_selected)
        layout.addWidget(self.copy_button)

        central_widget.setLayout(layout)
        self.load_history()

        script_dir = os.path.dirname(os.path.realpath(__file__))
        if getattr(sys, 'frozen', False):
            clipboard_icon_path = os.path.join(sys._MEIPASS, "clipboard.png")
        else:
            clipboard_icon_path = os.path.join(script_dir, "clipboard.png")
        if os.path.exists(clipboard_icon_path):
            icon = QIcon(clipboard_icon_path)
        else:
            icon = self.style().standardIcon(QStyle.SP_FileIcon)
            print("clipboard.png not found, falling back to default icon")
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
        if self._allow_exit:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def exit_app(self):
        self._allow_exit = True
        self.close()
        QApplication.quit()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def on_clipboard_change(self):
        text = self.clipboard.text()
        if text and text != self.last_clipboard_text:
            self.last_clipboard_text = text
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            code_flag = is_code(text)
            encrypted_text = encrypt_text(text, self.fernet)
            self.db_manager.add_entry(encrypted_text, timestamp, code_flag)
            self.load_history()

    def load_history(self):
        self.all_list.clear()
        self.fav_list.clear()
        entries = self.db_manager.get_all_entries()
        for entry in entries:
            # entry: (id, text, timestamp, is_code, pinned, favorite)
            decrypted_text = decrypt_text(entry[1], self.fernet)
            preview = decrypted_text if len(decrypted_text) <= 50 else decrypted_text[:50] + "..."
            item_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
            item_widget.clicked.connect(self.load_detail)
            item_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
            item_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
            item_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.all_list.addItem(list_item)
            self.all_list.setItemWidget(list_item, item_widget)
            if entry[5]:
                fav_item = QListWidgetItem()
                fav_item.setSizeHint(item_widget.sizeHint())
                fav_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
                fav_widget.clicked.connect(self.load_detail)
                fav_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
                fav_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
                fav_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
                self.fav_list.addItem(fav_item)
                self.fav_list.setItemWidget(fav_item, fav_widget)

    def load_detail(self, entry_id):
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            decrypted_text = decrypt_text(row[0], self.fernet)
            self.detail_view.setPlainText(decrypted_text)

    def delete_entry(self, entry_id):
        self.db_manager.delete_entry_by_id(entry_id)
        self.load_history()

    def favorite_entry(self, entry_id):
        # toggle favorite state
        row = self.db_manager.get_entry_by_id(entry_id)
        if row:
            current_state = row[2] if len(row) >= 3 else 0  # row: (text, pinned, favorite)
            # get favorite state from loaded entries
            entries = self.db_manager.get_all_entries()
            fav_state = 0
            for e in entries:
                if e[0] == entry_id:
                    fav_state = e[5]
                    break
            new_state = 0 if fav_state else 1
            self.db_manager.update_favorite_state(entry_id, new_state)
            self.load_history()

    def pin_entry(self, entry_id):
        # toggle pinned state
        entries = self.db_manager.get_all_entries()
        pin_state = 0
        for e in entries:
            if e[0] == entry_id:
                pin_state = e[4]
                break
        new_state = 0 if pin_state else 1
        self.db_manager.update_pin_state(entry_id, new_state)
        self.load_history()

    def on_search(self, search_term):
        self.all_list.clear()
        self.fav_list.clear()
        entries = self.db_manager.get_all_entries()
        date_filter = None
        type_filter = None
        date_match = re.search(r"date:\s*(\d{4}-\d{2}-\d{2})", search_term, re.IGNORECASE)
        if date_match:
            date_filter = date_match.group(1)
            search_term = re.sub(r"date:\s*\d{4}-\d{2}-\d{2}", "", search_term, flags=re.IGNORECASE)
        type_match = re.search(r"type:\s*(code|text)", search_term, re.IGNORECASE)
        if type_match:
            type_filter = type_match.group(1).lower()
            search_term = re.sub(r"type:\s*(code|text)", "", search_term, flags=re.IGNORECASE)
        search_term = search_term.strip().lower()
        for entry in entries:
            if date_filter and not entry[2].startswith(date_filter):
                continue
            if type_filter:
                if type_filter == "code" and not entry[3]:
                    continue
                elif type_filter == "text" and entry[3]:
                    continue
            decrypted_text = decrypt_text(entry[1], self.fernet)
            if search_term and search_term not in decrypted_text.lower():
                continue
            preview = decrypted_text if len(decrypted_text) <= 50 else decrypted_text[:50] + "..."
            item_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
            item_widget.clicked.connect(self.load_detail)
            item_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
            item_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
            item_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.all_list.addItem(list_item)
            self.all_list.setItemWidget(list_item, item_widget)
            if entry[5]:
                fav_item = QListWidgetItem()
                fav_item.setSizeHint(item_widget.sizeHint())
                fav_widget = HistoryItemWidget(entry[0], preview, entry[2], entry[3], entry[4], entry[5])
                fav_widget.clicked.connect(self.load_detail)
                fav_widget.trash_button.clicked.connect(lambda checked, eid=entry[0]: self.delete_entry(eid))
                fav_widget.star_button.clicked.connect(lambda checked, eid=entry[0]: self.favorite_entry(eid))
                fav_widget.pin_button.clicked.connect(lambda checked, eid=entry[0]: self.pin_entry(eid))
                self.fav_list.addItem(fav_item)
                self.fav_list.setItemWidget(fav_item, fav_widget)

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
            theme = self.settings.get("theme", "light")
            if "dark" in theme:
                self.setStyleSheet(RAVENS_WING_DARK_STYLE)
            elif "system" in theme:
                system_theme = get_system_theme()
                if system_theme == "dark":
                    self.setStyleSheet(RAVENS_WING_DARK_STYLE)
                else:
                    self.setStyleSheet("")
            else:
                self.setStyleSheet("")
            self.app_font = get_app_font(10, self.settings)
            self.setFont(self.app_font)
            self.load_history()

# region --- main execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    home_dir = os.path.expanduser("~")
    app_dir = os.path.join(home_dir, "ClipboardManager")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    temp_folder = tempfile.gettempdir()
    db_path = os.path.join(app_dir, "clipboard_manager.db")
    key_file = os.path.join(temp_folder, "clipboard_manager.key")
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
    manage_history(db_manager, settings, app_dir)
    window = ClipboardManager(db_manager, fernet, settings, app_dir)
    window.show()
    sys.exit(app.exec())

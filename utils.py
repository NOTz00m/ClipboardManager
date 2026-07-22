import sys
import os
import platform
import subprocess
import re
from PySide6.QtGui import QFontDatabase, QFont

RAVENS_WING_DARK_STYLE = """
QWidget {
    background-color: #23272e;
    color: #e0e0e0;
    font-family: 'JetBrains Mono', 'JetBrainsMono', 'Monospace', 'Consolas', 'Courier New', monospace;
    font-size: 10pt;
}

QScrollBar:vertical {
    border: none;
    background: #2b2f37;
    width: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #4d5562;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #5865f2;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #2b2f37;
    height: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #4d5562;
    min-width: 30px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #5865f2;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QPushButton, QToolButton {
    border: 1px solid #181a1b;
    border-radius: 8px;
    padding: 6px;
    background-color: #23272e;
    color: #e0e0e0;
    font-family: 'JetBrains Mono', 'JetBrainsMono', 'Monospace', 'Consolas', 'Courier New', monospace;
    font-size: 10pt;
}

QListWidget::item:hover {
    background-color: #2b2f37;
    border: none;
}

QListWidget::item:selected {
    background-color: #5865f2;
    color: #ffffff;
    border: none;
}

QPushButton {
    background-color: #5865f2;
    color: #fff;
    font-size: 10pt;
}

QPushButton:hover {
    background-color: #4752c4;
}

QToolTip {
    background-color: #181a1b;
    color: #e0e0e0;
    border: 1px solid #5865f2;
    font-size: 10pt;
}

QTabWidget::pane {
    border: 1px solid #181a1b;
    background: #23272e;
}

QTabBar::tab {
    background: #181a1b;
    color: #e0e0e0;
    border: 1px solid #23272e;
    border-bottom: none;
    padding: 6px 18px 6px 18px;
    min-width: 80px;
    font-family: 'JetBrains Mono', 'JetBrainsMono', 'Monospace', 'Consolas', 'Courier New', monospace;
    font-size: 10pt;
}

QTabBar::tab:selected, QTabBar::tab:hover {
    background: #5865f2;
    color: #fff;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}
"""

JETBRAINS_FONT = None


def get_icon_path(icon_name):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, icon_name)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name)


def get_jetbrains_font(size=10):
    global JETBRAINS_FONT
    if JETBRAINS_FONT is None:
        if getattr(sys, 'frozen', False):
            font_path = os.path.join(sys._MEIPASS, "JetBrainsMono-Regular.ttf")
        else:
            font_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "JetBrainsMono-Regular.ttf",
            )
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print("failed to load jetbrainsmono font.")
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            JETBRAINS_FONT = QFont(families[0], size)
        else:
            JETBRAINS_FONT = QFont("JetBrains Mono", size)
            if JETBRAINS_FONT.family() not in ["JetBrains Mono", "JetBrainsMono"]:
                JETBRAINS_FONT = QFont("Monospace", size)
                print("jetbrainsmono not found, falling back to monospace")
    return JETBRAINS_FONT


def get_app_font(size=10, settings=None):
    custom_font_path = settings.get("custom_font_path") if settings else None
    if custom_font_path and os.path.exists(custom_font_path):
        font_id = QFontDatabase.addApplicationFont(custom_font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return QFont(families[0], size)
    return get_jetbrains_font(size)


def get_system_theme():
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


def format_relative_time(timestamp_str):
    # format timestamp into human readable relative string
    try:
        from datetime import datetime
        ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        diff = now - ts
        seconds = int(diff.total_seconds())
        if seconds < 0:
            return "just now"
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        if months < 12:
            return f"{months}mo ago"
        years = days // 365
        return f"{years}y ago"
    except Exception:
        return timestamp_str


from content_detection import (
    detect_content_type as detect_content_type,
    detect_language as detect_language,
    is_code as is_code,
)

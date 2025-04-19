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
            font_path = "JetBrainsMono-Regular.ttf"
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

####### below was made with help from chatgpt, i wasn't sure how to do it myself

def is_code(text):
    if not text or "\n" not in text:
        return 0

    # Common programming language keywords and patterns
    patterns = {
        'python': [
            r'\b(?:def|class|import|from|return|if|elif|else|for|while|try|except|with|lambda|async|await|raise|pass|break|continue|yield|global|nonlocal)\b',
            r'#.*$',  # Python comments
            r'"""[\s\S]*?"""',  # Python docstrings
            r"'''[\s\S]*?'''",  # Python docstrings
            r'\b(?:True|False|None)\b',  # Python constants
            r'@\w+',  # Python decorators
        ],
        'javascript': [
            r'\b(?:function|var|let|const|=>|return|if|else|for|while|try|catch|throw|class|extends|new|this|super|import|export|default)\b',
            r'//.*$',  # JS single-line comments
            r'/\*[\s\S]*?\*/',  # JS multi-line comments
            r'\b(?:true|false|null|undefined)\b',  # JS constants
            r'`[\s\S]*?`',  # Template literals
        ],
        'java': [
            r'\b(?:public|private|protected|static|void|int|float|double|String|boolean|class|interface|extends|implements|new|this|super|import|package)\b',
            r'//.*$',  # Java single-line comments
            r'/\*[\s\S]*?\*/',  # Java multi-line comments
            r'@\w+',  # Java annotations
        ],
        'cpp': [
            r'#include\s*[<"].+[>"]',
            r'\b(?:class|struct|namespace|template|public|private|protected|virtual|inline|const|static|extern|typedef|using|enum|union)\b',
            r'//.*$',  # C++ single-line comments
            r'/\*[\s\S]*?\*/',  # C++ multi-line comments
            r'::\w+',  # Scope resolution
        ],
        'php': [
            r'<\?php',
            r'\b(?:function|class|namespace|use|public|private|protected|static|const|echo|print|return|if|else|for|while|foreach|try|catch|throw)\b',
            r'//.*$',  # PHP single-line comments
            r'#.*$',  # PHP alternative comments
            r'/\*[\s\S]*?\*/',  # PHP multi-line comments
        ],
        'ruby': [
            r'\b(?:def|class|module|require|include|attr_accessor|attr_reader|attr_writer|private|public|protected|return|if|else|elsif|unless|case|when|while|until|for|begin|rescue|ensure|yield|super|self)\b',
            r'#.*$',  # Ruby comments
            r':\w+',  # Ruby symbols
        ],
        'rust': [
            r'\b(?:fn|let|mut|pub|struct|enum|trait|impl|mod|use|crate|extern|static|const|type|unsafe|async|await|return|if|else|match|loop|while|for|break|continue|move)\b',
            r'//.*$',  # Rust single-line comments
            r'/\*[\s\S]*?\*/',  # Rust multi-line comments
            r'![\w!]+',  # Rust macros
        ],
        'go': [
            r'\b(?:func|type|struct|interface|import|package|const|var|map|chan|go|defer|return|if|else|for|range|switch|case|default|select|break|continue|fallthrough|goto)\b',
            r'//.*$',  # Go single-line comments
            r'/\*[\s\S]*?\*/',  # Go multi-line comments
        ],
        'sql': [
            r'\b(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|GROUP BY|ORDER BY|HAVING|UNION|CREATE|ALTER|DROP|TABLE|INDEX|VIEW|TRIGGER|PROCEDURE|FUNCTION)\b',
            r'--.*$',  # SQL single-line comments
            r'/\*[\s\S]*?\*/',  # SQL multi-line comments
        ],
        'html': [
            r'<[^>]+>',  # HTML tags
            r'<!DOCTYPE\s+html>',
            r'<!--[\s\S]*?-->',  # HTML comments
        ],
        'css': [
            r'{[^}]*}',  # CSS rules
            r'@media\s+[^{]+{',
            r'@keyframes\s+\w+\s*{',
            r'/\*[\s\S]*?\*/',  # CSS comments
        ],
        'shell': [
            r'^\s*\$\s*',  # Shell commands
            r'\b(?:if|then|else|fi|for|while|do|done|case|esac|function|export|source|alias|cd|ls|grep|sed|awk|cat|echo|mkdir|rm|cp|mv)\b',
            r'#.*$',  # Shell comments
        ],
    }

    # Additional heuristics
    code_indicators = [
        r'[{}]',  # Braces
        r'[;]',   # Semicolons
        r'[=+\-*/%&|^<>!]=?',  # Operators
        r'\b\d+\b',  # Numbers
        r'["\']',  # Quotes
        r'\b(?:true|false|null|undefined)\b',  # Common constants
        r'\b(?:if|else|for|while|return|function|class)\b',  # Common keywords
    ]

    # Check for language-specific patterns
    for language, language_patterns in patterns.items():
        for pattern in language_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return 1

    # Check for general code indicators
    indicator_count = 0
    for indicator in code_indicators:
        if re.search(indicator, text):
            indicator_count += 1

    # If we have multiple code indicators, it's likely code
    if indicator_count >= 3:
        return 1

    # Check for indentation patterns (common in code)
    lines = text.split('\n')
    indented_lines = sum(1 for line in lines if line.startswith(('    ', '\t')))
    if indented_lines / len(lines) > 0.3:  # If more than 30% of lines are indented
        return 1

    return 0 
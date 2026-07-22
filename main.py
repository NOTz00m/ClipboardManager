import sys
import os

# SHUT UP QT QPA MIME WARNINGS
os.environ["QT_LOGGING_RULES"] = "qt.qpa.mime.warning=false;qt.qpa.mime*=false"

import tempfile
import base64
import hashlib
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtCore import QLockFile, qInstallMessageHandler
from PySide6.QtGui import QIcon
from cryptography.fernet import Fernet
from database import DatabaseManager, manage_history
from encryption import (DummyFernet, content_fingerprint, decrypt_text,
                        decrypt_text_strict, derive_key, encrypt_text,
                        generate_salt, load_key)
from settings import SettingsManager
from ui.startup_wizard import StartupWizard
from ui.fluent_window import ClipboardManagerWindow
from qfluentwidgets import setTheme, Theme
from utils import get_app_font, get_system_theme


def _qt_message_handler(mode, context, message):
    # filter out qt clipboard spam
    if "qt.qpa.mime" in message or "Retrying to obtain clipboard" in message:
        return
    sys.__stderr__.write(f"{message}\n")


def main():
    qInstallMessageHandler(_qt_message_handler)

    # Windows taskbar icon fix (don't group under generic python.exe)
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ClipboardManager.App.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Clipboard Manager")
    app.setOrganizationName("ClipboardManager")
    app.setQuitOnLastWindowClosed(False)
    home_dir = os.path.expanduser("~")
    app_dir = os.path.join(home_dir, "ClipboardManager")
    os.makedirs(app_dir, exist_ok=True)

    # prevent double instance chaos
    instance_lock = QLockFile(os.path.join(app_dir, "clipboard_manager.lock"))
    instance_lock.setStaleLockTime(30_000)
    if not instance_lock.tryLock(100):
        QMessageBox.information(
            None,
            "Clipboard Manager is already running",
            "The app is already active. Use its tray icon or global shortcut to show it.",
        )
        return 0

    resource_dir = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    app_icon_path = os.path.join(resource_dir, "clipboard.png")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))

    temp_folder = tempfile.gettempdir()
    db_path = os.path.join(app_dir, "clipboard_manager.db")
    key_file = os.path.join(app_dir, "clipboard_manager.key")
    settings_file = os.path.join(app_dir, "settings.json")
    settings_key_file = os.path.join(app_dir, "settings_key.key")

    settings_encryption_key = load_key(
        settings_key_file,
        legacy_paths=[os.path.join(temp_folder, "settings_key.key")],
    )

    settings = SettingsManager.load_settings(settings_file, settings_encryption_key)
    if settings is None:
        wizard = StartupWizard()
        if wizard.exec() == QDialog.Accepted:
            settings = wizard.settings
            SettingsManager.save_settings(settings, settings_file, settings_encryption_key)
        else:
            sys.exit(0)

    theme = settings.get("theme", "system")
    if theme == "dark":
        setTheme(Theme.DARK)
    elif theme == "light":
        setTheme(Theme.LIGHT)
    else:
        system_theme = get_system_theme()
        if system_theme == "dark":
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)

    app.setFont(get_app_font(10, settings))

    migrate_legacy_personal_key = False
    if settings.get("encryption_enabled", True):
        if settings.get("use_personal_key", False) and settings.get("personal_key", ""):
            password = settings.get("personal_key")
            salt_b64 = settings.get("encryption_salt", "")
            if salt_b64:
                salt = base64.b64decode(salt_b64)
                derived_key = derive_key(password, salt, settings.get("encryption_mode", "normal"))
            else:
                derived_key = base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())
                migrate_legacy_personal_key = True
            fernet = Fernet(derived_key)
        else:
            key = load_key(
                key_file,
                legacy_paths=[os.path.join(temp_folder, "clipboard_manager.key")],
            )
            fernet = Fernet(key)
    else:
        fernet = DummyFernet()

    db_manager = DatabaseManager(db_path)
    if migrate_legacy_personal_key:
        new_salt = generate_salt()
        new_fernet = Fernet(derive_key(settings["personal_key"], new_salt, "normal"))
        try:
            db_manager.reencrypt_payloads(
                lambda token: encrypt_text(decrypt_text_strict(token, fernet), new_fernet)
            )
        except Exception as exc:
            db_manager.close()
            QMessageBox.critical(
                None,
                "Clipboard history could not be unlocked",
                "The personal password does not match the existing history. "
                "No data was changed. Check the password stored in settings.json.\n\n"
                f"Details: {exc}",
            )
            return 1
        settings["encryption_salt"] = base64.b64encode(new_salt).decode()
        settings["encryption_mode"] = "normal"
        SettingsManager.save_settings(settings, settings_file, settings_encryption_key)
        fernet = new_fernet

    db_manager.reconcile_content_hashes(
        lambda token: decrypt_text(token, fernet),
        lambda text: content_fingerprint(text, settings_encryption_key),
    )
    manage_history(db_manager, settings, app_dir)
    window = ClipboardManagerWindow(
        db_manager,
        fernet,
        settings,
        app_dir,
        fingerprint_key=settings_encryption_key,
        settings_encryption_key=settings_encryption_key,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

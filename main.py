import sys
import os
import tempfile
import base64
import hashlib
from PySide6.QtWidgets import QApplication, QDialog
from cryptography.fernet import Fernet
from database import DatabaseManager, manage_history
from encryption import DummyFernet, load_key
from settings import SettingsManager
from ui.startup_wizard import StartupWizard
from ui.main_window import ClipboardManager

def main():
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

    # load or generate the settings encryption key
    if os.path.exists(settings_key_file):
        with open(settings_key_file, 'rb') as f:
            SETTINGS_ENCRYPTION_KEY = f.read()
    else:
        SETTINGS_ENCRYPTION_KEY = Fernet.generate_key()
        with open(settings_key_file, 'wb') as f:
            f.write(SETTINGS_ENCRYPTION_KEY)

    # load settings, or run the startup wizard if not present
    settings = SettingsManager.load_settings(settings_file, SETTINGS_ENCRYPTION_KEY)
    if settings is None:
        wizard = StartupWizard()
        if wizard.exec() == QDialog.Accepted:
            settings = wizard.settings
            SettingsManager.save_settings(settings, settings_file, SETTINGS_ENCRYPTION_KEY)
        else:
            sys.exit(0)

    # setup encryption
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

if __name__ == "__main__":
    main() 
import os
import json
from cryptography.fernet import Fernet


DEFAULT_SETTINGS = {
    "encryption_enabled": True,
    "use_personal_key": False,
    "personal_key": "",
    "encryption_salt": "",
    "encryption_mode": "normal",
    "theme": "system",
    "show_timestamps": True,
    "start_at_startup": False,
    "global_shortcut": "ctrl+alt+v",
    "custom_font_path": "",
    "history_management": "keep",
    "history_threshold_days": "30",
    "gdrive_enabled": False,
    "gdrive_token": "",
}

def encrypt_personal_key(plain_key: str, settings_encryption_key: bytes) -> str:
    f = Fernet(settings_encryption_key)
    return "enc:v1:" + f.encrypt(plain_key.encode()).decode()

def decrypt_personal_key(enc_key: str, settings_encryption_key: bytes) -> str:
    f = Fernet(settings_encryption_key)
    token = enc_key.removeprefix("enc:v1:")
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        return ""

class SettingsManager:
    @staticmethod
    def load_settings(settings_path, settings_encryption_key=None):
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
            except (OSError, json.JSONDecodeError):
                return None
            settings = DEFAULT_SETTINGS.copy()
            if isinstance(loaded, dict):
                settings.update(loaded)
            personal_key = settings.get("personal_key", "")
            if settings.get("use_personal_key", False) and personal_key and settings_encryption_key:
                # A short-lived bug saved this field as plaintext. Prefixed
                # values and legacy Fernet tokens are decrypted; other values
                # are retained as the user's plaintext password and migrated
                # on the next save.
                if personal_key.startswith("enc:v1:") or personal_key.startswith("gAAAAA"):
                    settings["personal_key"] = decrypt_personal_key(personal_key, settings_encryption_key)
            return settings
        else:
            return None

    @staticmethod
    def save_settings(settings, settings_path, settings_encryption_key=None):
        settings_to_save = DEFAULT_SETTINGS.copy()
        settings_to_save.update(settings)
        if settings.get("use_personal_key", False) and settings.get("personal_key", "") and settings_encryption_key:
            settings_to_save["personal_key"] = encrypt_personal_key(settings["personal_key"], settings_encryption_key)
        os.makedirs(os.path.dirname(os.path.abspath(settings_path)), exist_ok=True)
        temp_path = f"{settings_path}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(settings_to_save, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, settings_path)

    @staticmethod
    def unlink_gdrive(settings, settings_path, settings_encryption_key=None):
        settings['gdrive_enabled'] = False
        settings['gdrive_token'] = ""
        SettingsManager.save_settings(settings, settings_path, settings_encryption_key)

# google Drive sync stubs (to be implemented in sync module)
def upload_to_gdrive(local_path, token):
    pass

def download_from_gdrive(local_path, token):
    pass

def delete_gdrive_data(token):
    pass 

import os
import json
from cryptography.fernet import Fernet

def encrypt_personal_key(plain_key: str, settings_encryption_key: bytes) -> str:
    f = Fernet(settings_encryption_key)
    return f.encrypt(plain_key.encode()).decode()

def decrypt_personal_key(enc_key: str, settings_encryption_key: bytes) -> str:
    f = Fernet(settings_encryption_key)
    try:
        return f.decrypt(enc_key.encode()).decode()
    except Exception:
        return ""

class SettingsManager:
    @staticmethod
    def load_settings(settings_path, settings_encryption_key=None):
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            if settings.get("use_personal_key", False) and settings.get("personal_key", "") and settings_encryption_key:
                settings["personal_key"] = decrypt_personal_key(settings["personal_key"], settings_encryption_key)
            # set defaults for new Google Drive sync fields
            settings.setdefault('gdrive_enabled', False)
            settings.setdefault('gdrive_token', "")
            return settings
        else:
            return None

    @staticmethod
    def save_settings(settings, settings_path, settings_encryption_key=None):
        settings_to_save = settings.copy()
        if settings.get("use_personal_key", False) and settings.get("personal_key", "") and settings_encryption_key:
            settings_to_save["personal_key"] = encrypt_personal_key(settings["personal_key"], settings_encryption_key)
        with open(settings_path, 'w') as f:
            json.dump(settings_to_save, f, indent=4)

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
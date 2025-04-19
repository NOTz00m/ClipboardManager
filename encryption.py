import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import secrets

ENCRYPTION_VERSION = 2  # 1 = old, 2 = PBKDF2+salt
PBKDF2_ITERATIONS_NORMAL = 200_000
PBKDF2_ITERATIONS_HARD = 600_000
SALT_SIZE = 16

class DummyFernet:
    def encrypt(self, text_bytes):
        return text_bytes

    def decrypt(self, token):
        return token

def generate_salt():
    return secrets.token_bytes(SALT_SIZE)

def derive_key(password: str, salt: bytes, mode: str = 'normal') -> bytes:
    iterations = PBKDF2_ITERATIONS_NORMAL if mode == 'normal' else PBKDF2_ITERATIONS_HARD
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def encrypt_text(text, fernet, version=ENCRYPTION_VERSION, salt=None, mode='normal'):
    # versioned encryption: v2 = PBKDF2+salt, v1 = legacy
    if version == 2 and salt is not None:
        token = fernet.encrypt(text.encode())
        # store version, mode, and salt as prefix: v2:mode:salt:token
        return f"v2:{mode}:{base64.b64encode(salt).decode()}:{token.decode()}".encode()
    else:
        return fernet.encrypt(text.encode())

def decrypt_text(token, fernet, password=None):
    # detect version
    if isinstance(token, bytes):
        token = token.decode(errors='ignore')
    if token.startswith("v2:"):
        try:
            _, mode, salt_b64, real_token = token.split(":", 3)
            salt = base64.b64decode(salt_b64)
            if password is None:
                raise ValueError("Password required for v2 decryption")
            key = derive_key(password, salt, mode)
            f = Fernet(key)
            return f.decrypt(real_token.encode()).decode()
        except Exception:
            return ""
    else:
        try:
            return fernet.decrypt(token.encode() if isinstance(token, str) else token).decode()
        except Exception:
            return ""

def load_key(key_file):
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
    return key

def reencrypt_all_data(db_manager, old_password, new_password, settings, mode='normal'):
    # v2 encryption
    entries = db_manager.get_all_entries()
    new_salt = generate_salt()
    new_key = derive_key(new_password, new_salt, mode)
    new_fernet = Fernet(new_key)
    for entry in entries:
        entry_id, enc_text, timestamp, is_code, pinned, favorite = entry
        # decrypt with old password (auto-detect mode)
        plain = decrypt_text(enc_text, None, old_password)
        if plain:
            new_enc = encrypt_text(plain, new_fernet, version=2, salt=new_salt, mode=mode)
            db_manager.update_entry_text(entry_id, new_enc)
    # update salt and mode in settings
    settings['encryption_salt'] = base64.b64encode(new_salt).decode()
    settings['encryption_mode'] = mode

def get_encryption_mode(settings):
    return settings.get('encryption_mode', 'normal') 
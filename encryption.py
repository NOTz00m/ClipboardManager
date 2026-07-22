import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import secrets
import hmac

ENCRYPTION_VERSION = 2
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
    if version == 2 and salt is not None:
        token = fernet.encrypt(text.encode())
        return f"v2:{mode}:{base64.b64encode(salt).decode()}:{token.decode()}".encode()
    else:
        return fernet.encrypt(text.encode())


def decrypt_text_strict(token, fernet, password=None):
    # decrypt payload or throw if format/key is broken
    if isinstance(token, bytes):
        token = token.decode(errors='ignore')
    if token.startswith("v2:"):
        _, mode, salt_b64, real_token = token.split(":", 3)
        if fernet is not None:
            return fernet.decrypt(real_token.encode()).decode()
        if password is None:
            raise ValueError("Password required for v2 decryption")
        salt = base64.b64decode(salt_b64)
        key = derive_key(password, salt, mode)
        return Fernet(key).decrypt(real_token.encode()).decode()
    return fernet.decrypt(token.encode() if isinstance(token, str) else token).decode()


def decrypt_text(token, fernet, password=None):
    # quiet fallback for UI reads
    try:
        return decrypt_text_strict(token, fernet, password)
    except Exception:
        return ""


def load_key(key_file, legacy_paths=None):
    # load encryption key or migrate from legacy temp path if needed
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            key = f.read()
    else:
        key = None
        for legacy_path in legacy_paths or ():
            if legacy_path and os.path.exists(legacy_path):
                with open(legacy_path, 'rb') as f:
                    candidate = f.read()
                try:
                    Fernet(candidate)
                    key = candidate
                    break
                except (TypeError, ValueError):
                    continue
        if key is None:
            key = Fernet.generate_key()
        os.makedirs(os.path.dirname(os.path.abspath(key_file)), exist_ok=True)
        temp_path = f"{key_file}.tmp"
        with open(temp_path, 'wb') as f:
            f.write(key)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, key_file)
    return key


def content_fingerprint(text: str, secret: bytes) -> str:
    # hmac sha256 fingerprint for deduplication
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hmac.new(secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def reencrypt_all_data(db_manager, old_password, new_password, settings, mode='normal'):
    entries = db_manager.get_all_entries()
    new_salt = generate_salt()
    new_key = derive_key(new_password, new_salt, mode)
    new_fernet = Fernet(new_key)
    for entry in entries:
        entry_id, enc_text, timestamp, is_code, pinned, favorite = entry
        plain = decrypt_text(enc_text, None, old_password)
        if plain:
            new_enc = encrypt_text(plain, new_fernet, version=2, salt=new_salt, mode=mode)
            db_manager.update_entry_text(entry_id, new_enc)
    settings['encryption_salt'] = base64.b64encode(new_salt).decode()
    settings['encryption_mode'] = mode


def get_encryption_mode(settings):
    return settings.get('encryption_mode', 'normal')

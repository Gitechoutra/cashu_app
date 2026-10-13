"""Authenticated field encryption (Fernet = AES-128-CBC + HMAC-SHA256) for
provider access tokens. The key comes from DATA_ENCRYPTION_KEY — generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet():
    key = current_app.config.get('DATA_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError('DATA_ENCRYPTION_KEY is not configured.')
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext):
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode('utf-8')).decode('ascii')


def decrypt(ciphertext):
    if ciphertext is None:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode('ascii')).decode('utf-8')
    except InvalidToken as e:
        raise RuntimeError('Stored token could not be decrypted (key rotated?).') from e

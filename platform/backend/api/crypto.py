import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _derive_fernet_key_from_secret(secret: str) -> bytes:
    # Fernet requires a 32-byte key, urlsafe-base64-encoded (44 chars).
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    key = os.getenv("KEYSTONE_FERNET_KEY", "").strip()
    if key:
        return Fernet(key.encode("utf-8"))
    return Fernet(_derive_fernet_key_from_secret(settings.SECRET_KEY))


def encrypt_str(value: str) -> str:
    if not value:
        return ""
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_str(token: str) -> str:
    if not token:
        return ""
    try:
        return get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # If the secret changes or legacy plaintext exists, avoid exploding reads.
        # Treat as plaintext and let next save re-encrypt.
        return token



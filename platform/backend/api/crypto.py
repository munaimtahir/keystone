"""
Encryption utilities for Keystone.

Provides Fernet-based encryption for sensitive data like GitHub PATs.
See docs/SECURITY_MODEL.md - GitHub tokens stored server-side (encrypted).
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _derive_fernet_key_from_secret(secret: str) -> bytes:
    """Derive a Fernet key from Django's SECRET_KEY."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    """Get a Fernet instance for encryption/decryption."""
    key = os.getenv("KEYSTONE_FERNET_KEY", "").strip()
    if key:
        return Fernet(key.encode("utf-8"))
    return Fernet(_derive_fernet_key_from_secret(settings.SECRET_KEY))


def encrypt_str(value: str) -> str:
    """Encrypt a plaintext string."""
    if not value:
        return ""
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_str(token: str) -> str:
    """Decrypt a ciphertext string. Returns original if decryption fails."""
    if not token:
        return ""
    try:
        return get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # If decryption fails (e.g., key changed), return as-is
        return token

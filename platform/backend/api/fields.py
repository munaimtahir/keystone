"""
Custom Django model fields for Keystone.
"""
from django.db import models

from .crypto import decrypt_str, encrypt_str


class EncryptedTextField(models.TextField):
    """
    A TextField that stores encrypted ciphertext in the database
    but exposes plaintext to Python code.
    
    Uses Fernet encryption derived from DJANGO_SECRET_KEY or KEYSTONE_FERNET_KEY.
    See docs/SECURITY_MODEL.md for security requirements.
    """

    def from_db_value(self, value, expression, connection):
        """Decrypt value when reading from database."""
        if value is None:
            return value
        return decrypt_str(value)

    def to_python(self, value):
        """Convert value to Python (decrypt if needed)."""
        if value is None or value == "":
            return value
        return decrypt_str(value)

    def get_prep_value(self, value):
        """Encrypt value before saving to database."""
        value = super().get_prep_value(value)
        if not value:
            return ""
        return encrypt_str(value)

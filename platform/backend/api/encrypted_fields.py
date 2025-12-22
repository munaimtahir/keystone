from django.db import models

from .crypto import decrypt_str, encrypt_str


class EncryptedTextField(models.TextField):
    """
    Stores encrypted ciphertext in DB, exposes plaintext in Python.

    This is intentionally simple (single-tenant VM) and uses a Fernet key derived
    from DJANGO_SECRET_KEY unless KEYSTONE_FERNET_KEY is provided.
    """

    def from_db_value(self, value, expression, connection):  # noqa: ARG002
        if value is None:
            return value
        return decrypt_str(value)

    def to_python(self, value):
        if value is None or value == "":
            return value
        # If value already looks like plaintext (e.g., assigned in code),
        # decrypt_str will return it unchanged if it isn't valid ciphertext.
        return decrypt_str(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value:
            return ""
        return encrypt_str(value)



"""
Enkripsi payload antar-agen menggunakan Fernet (AES-128-CBC + HMAC-SHA256).
Kunci dibaca dari environment variable MEDIFLOW_ENCRYPTION_KEY.

Generate kunci baru:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
from cryptography.fernet import Fernet, InvalidToken

_DEFAULT_ENCRYPTION_KEY = os.environ.get("MEDIFLOW_ENCRYPTION_KEY") or Fernet.generate_key().decode()


def _get_fernet() -> Fernet:
    key = os.environ.get("MEDIFLOW_ENCRYPTION_KEY")
    if not key:
        key = _DEFAULT_ENCRYPTION_KEY
        os.environ["MEDIFLOW_ENCRYPTION_KEY"] = key
    return Fernet(key.encode())


def encrypt_payload(plaintext: str) -> str:
    """Enkripsi string payload, kembalikan ciphertext sebagai string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_payload(ciphertext: str) -> str:
    """Dekripsi ciphertext, kembalikan plaintext. Raise ValueError jika token tidak valid."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Payload antar-agen tidak valid atau telah dimanipulasi.") from exc

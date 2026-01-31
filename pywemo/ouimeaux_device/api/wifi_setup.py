"""Cryptography helpers for WiFi setup."""

import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def encrypt_password(password: str, key: str, salt: str, iv: str) -> str:
    """Encrypt the WiFi password."""
    password_bytes = password.encode("utf-8")
    key_bytes = key.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    iv_bytes = iv.encode("utf-8")

    # Derive the Key. Logic: MD5(key + salt)
    # MD5 is no longer considered secure, but it's the algorithm used for WeMo.
    hasher = hashes.Hash(hashes.MD5(), backend=default_backend())  # noqa: S303
    hasher.update(key_bytes + salt_bytes)
    derived_key = hasher.finalize()[:16]

    # Setup Cipher (AES-128-CBC)
    cipher = Cipher(
        algorithms.AES(derived_key),
        modes.CBC(iv_bytes),
        backend=default_backend(),
    )
    encryptor = cipher.encryptor()

    # Handle Padding (PKCS7)
    # AES is a block cipher; data must be a multiple of 16 bytes.
    pad_len = 16 - (len(password_bytes) % 16)
    padded_data = password_bytes + bytes([pad_len] * pad_len)

    # Encrypt
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

    # Encode to Base64
    return base64.b64encode(encrypted_data).decode()

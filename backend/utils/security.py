"""Security helpers for authentication flows."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from backend.exceptions import AppError

# bcrypt solo acepta hasta 72 bytes. Pre-hasheamos siempre con SHA-256 para que
# la entrada a bcrypt sea 64 caracteres (hex) y no dependamos de passlib.
def _normalize_for_bcrypt(value: str) -> str:
    """Normaliza el valor a 64 caracteres (SHA-256 hex) antes de bcrypt."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_string(value: str) -> str:
    """Hash a string value using bcrypt.

    Args:
        value: Plain-text value to hash.

    Returns:
        str: Secure bcrypt hash.

    Raises:
        ValueError: If the input string is empty or blank.
    """
    if not value or not value.strip():
        raise ValueError("Cannot hash an empty string.")

    normalized = _normalize_for_bcrypt(value)
    hashed = bcrypt.hashpw(
        normalized.encode("utf-8"),
        bcrypt.gensalt(),
    )
    return hashed.decode("utf-8")


def verify_string(value: str, hashed_value: str) -> bool:
    """Verify a plain-text string against a stored hash.

    Args:
        value: Plain-text value to verify.
        hashed_value: Stored bcrypt hash (string).

    Returns:
        bool: True when the value matches the hash.
    """
    normalized = _normalize_for_bcrypt(value)
    return bcrypt.checkpw(
        normalized.encode("utf-8"),
        hashed_value.encode("utf-8"),
    )


def hash_token(value: str) -> str:
    """Return a deterministic hash for opaque session tokens."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_token(value: str, hashed_value: str) -> bool:
    """Compare an opaque token against its stored hash."""

    return hmac.compare_digest(hash_token(value), hashed_value)


def generate_opaque_token() -> str:
    """Generate a URL-safe token for session cookies."""

    return secrets.token_urlsafe(48)


def encrypt_secret(value: str, secret_key: str) -> str:
    """Encrypt a secret value for database storage."""

    normalized = value.strip()
    if not normalized:
        raise ValueError("Cannot encrypt an empty secret.")

    return _get_fernet(secret_key).encrypt(normalized.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str, secret_key: str) -> str:
    """Decrypt a previously encrypted secret."""

    normalized = value.strip()
    if not normalized:
        raise AppError(
            "El secreto almacenado es invalido.",
            err_code="INVALID_ENCRYPTED_SECRET",
            status_code=500,
        )

    try:
        return _get_fernet(secret_key).decrypt(normalized.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            "No se pudo descifrar el secreto almacenado.",
            err_code="SECRET_DECRYPTION_FAILED",
            status_code=500,
        ) from exc


@lru_cache(maxsize=8)
def _get_fernet(secret_key: str) -> Fernet:
    """Build a Fernet cipher from an arbitrary application secret."""

    normalized = secret_key.strip()
    if not normalized:
        raise ValueError("Secret key is required for encryption.")

    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

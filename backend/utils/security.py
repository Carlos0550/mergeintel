"""Security helpers for authentication flows."""

from __future__ import annotations

import hashlib

import bcrypt

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

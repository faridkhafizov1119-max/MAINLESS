"""Хеширование паролей и оценка их надёжности."""
from __future__ import annotations

import hashlib
import hmac
import os
import re

PBKDF2_ITERATIONS = 180_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, saved_hash: str, saved_salt: str) -> bool:
    try:
        calculated, _ = hash_password(password, bytes.fromhex(saved_salt))
        return hmac.compare_digest(calculated, saved_hash)
    except (ValueError, TypeError):
        return False


def password_strength(password: str) -> tuple[float, str]:
    """Возвращает (доля 0..1, подпись). Пустой пароль -> (0, '')."""
    if not password:
        return 0.0, ""
    score = 0
    score += len(password) >= 6
    score += len(password) >= 10
    score += bool(re.search(r"[a-zа-я]", password) and re.search(r"[A-ZА-Я]", password))
    score += bool(re.search(r"\d", password))
    score += bool(re.search(r"[^\w\s]", password))
    ratio = max(score, 1) / 5
    if ratio <= 0.4:
        return ratio, "Слабый"
    if ratio <= 0.6:
        return ratio, "Средний"
    return ratio, "Надёжный"

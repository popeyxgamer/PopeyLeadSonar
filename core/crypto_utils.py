# -*- coding: utf-8 -*-
"""
Szyfrowanie danych wrażliwych (hasło do Gmaila) przechowywanych w bazie danych.
"""
from typing import Optional

from .config import logger, get_crypto_key_path

try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "Biblioteka 'cryptography' nie jest zainstalowana - hasła będą przechowywane "
        "jawnym tekstem! Zainstaluj: pip install cryptography"
    )


def get_crypto_key(profile: Optional[str] = None) -> bytes:
    """
    Zwraca klucz szyfrowania dla danego profilu (lub aktywnego, jeśli nie podano),
    tworząc go jeśli nie istnieje.

    Uwaga: wcześniej ta funkcja zawsze brała klucz AKTYWNEGO profilu, ignorując
    parametr `profile` przekazywany przez wywołujących (np. get_setting/set_setting
    w database.py). Powodowało to szyfrowanie/odszyfrowywanie złym kluczem, gdy
    operacja dotyczyła profilu innego niż aktualnie aktywny.
    """
    if not CRYPTO_AVAILABLE:
        return b""

    key_path = get_crypto_key_path(profile)
    if key_path.exists():
        return key_path.read_bytes()

    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    try:
        key_path.chmod(0o600)
    except (NotImplementedError, OSError):
        pass
    return key


def encrypt_text(text: str, profile: Optional[str] = None) -> str:
    if not CRYPTO_AVAILABLE or not text:
        return text
    key = get_crypto_key(profile)
    if not key:
        return text
    return Fernet(key).encrypt(text.encode()).decode()


def decrypt_text(encrypted: str, profile: Optional[str] = None) -> str:
    if not CRYPTO_AVAILABLE or not encrypted:
        return encrypted
    key = get_crypto_key(profile)
    if not key:
        return encrypted
    try:
        return Fernet(key).decrypt(encrypted.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as e:
        logger.debug("Nie udało się odszyfrować wartości: %s", e)
        return encrypted
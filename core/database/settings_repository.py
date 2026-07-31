# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

from ..config import logger
from ..crypto_utils import decrypt_text, encrypt_text
from .connection import get_connection_context

ENCRYPTED_SETTINGS = {"gmail_password"}


def get_setting(key: str, default: str = "", profile: Optional[str] = None) -> str:
    with get_connection_context(profile) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    return decrypt_text(row[0], profile) if key in ENCRYPTED_SETTINGS else row[0]


def set_setting(key: str, value: str, profile: Optional[str] = None) -> None:
    if key in ENCRYPTED_SETTINGS:
        value = encrypt_text(value, profile)
    with get_connection_context(profile) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


def add_to_blacklist(email: str, reason: str = "manual", profile: Optional[str] = None) -> bool:
    if not email:
        return False
    try:
        normalized_email = email.strip().lower()
        with get_connection_context(profile) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO blacklist (email, reason, added_at) VALUES (?, ?, ?)",
                (normalized_email, reason, datetime.now().isoformat())
            )
        return True
    except sqlite3.Error as e:
        logger.error("Błąd dodawania do blacklist %s: %s", email, e)
        return False


def is_blacklisted(email: str, profile: Optional[str] = None) -> bool:
    if not email:
        return False
    with get_connection_context(profile) as conn:
        row = conn.execute("SELECT 1 FROM blacklist WHERE email=?", (email.strip().lower(),)).fetchone()
    return row is not None


def get_blacklist(profile: Optional[str] = None) -> List[Tuple[str, str, str]]:
    with get_connection_context(profile) as conn:
        return conn.execute("SELECT email, reason, added_at FROM blacklist ORDER BY added_at DESC").fetchall()


def remove_from_blacklist(email: str, profile: Optional[str] = None) -> bool:
    with get_connection_context(profile) as conn:
        conn.execute("DELETE FROM blacklist WHERE email=?", (email.strip().lower(),))
    return True

# -*- coding: utf-8 -*-
import sqlite3
from typing import Dict, List, Optional

from ..config import logger
from ..crypto_utils import decrypt_text, encrypt_text
from .connection import get_connection_context


def save_smtp_accounts(accounts: List[Dict], profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute("DELETE FROM smtp_accounts")
        for acc in accounts:
            conn.execute(
                "INSERT INTO smtp_accounts (user, password, host, port, enabled, warmup_only, is_main) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (acc.get("user", ""), encrypt_text(acc.get("password", ""), profile),
                 acc.get("host", "smtp-relay.gmail.com"), acc.get("port", 587),
                 1 if acc.get("enabled", True) else 0,
                 1 if acc.get("warmup_only", False) else 0,
                 1 if acc.get("is_main", False) else 0)
            )


def get_smtp_accounts(profile: Optional[str] = None) -> List[Dict]:
    with get_connection_context(profile) as conn:
        rows = conn.execute("SELECT id, user, password, host, port, enabled, warmup_only, is_main FROM smtp_accounts").fetchall()
    return [{
        "id": r[0], "user": r[1], "password": decrypt_text(r[2], profile),
        "host": r[3], "port": r[4], "enabled": bool(r[5]), "warmup_only": bool(r[6]),
        "is_main": bool(r[7])
    } for r in rows]


def set_main_account(email: str, profile: Optional[str] = None) -> bool:
    try:
        with get_connection_context(profile) as conn:
            conn.execute("UPDATE smtp_accounts SET is_main = 0")
            conn.execute("UPDATE smtp_accounts SET is_main = 1 WHERE user = ?", (email.strip(),))
        return True
    except sqlite3.Error as e:
        logger.error("Błąd ustawiania głównego konta %s: %s", email, e)
        return False

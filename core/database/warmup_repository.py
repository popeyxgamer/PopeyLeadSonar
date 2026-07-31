# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from .connection import get_connection_context


def get_warmup_targets(profile: Optional[str] = None) -> List[Dict]:
    with get_connection_context(profile) as conn:
        rows = conn.execute("SELECT id, email, name FROM warmup_targets ORDER BY added_at DESC").fetchall()
    return [{"id": r[0], "email": r[1], "name": r[2]} for r in rows]


def add_warmup_target(email: str, name: str = "", profile: Optional[str] = None) -> bool:
    try:
        with get_connection_context(profile) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO warmup_targets (email, name, added_at) VALUES (?, ?, ?)",
                (email.strip().lower(), name, datetime.now().isoformat())
            )
        return True
    except sqlite3.Error:
        return False


def delete_warmup_target(target_id: int, profile: Optional[str] = None):
    with get_connection_context(profile) as conn:
        conn.execute("DELETE FROM warmup_targets WHERE id=?", (target_id,))

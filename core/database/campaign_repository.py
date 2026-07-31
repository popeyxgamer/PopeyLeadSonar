# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from ..config import logger
from .connection import get_connection_context


def log_wysylka(lead_id: int, email: str, temat: str, tresc: str,
                status: str, blad: str = "", profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute(
            """INSERT INTO wysylki (lead_id, email, temat, tresc, status, data_wyslania, blad)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (lead_id, email, temat, tresc, status, datetime.now().isoformat(), blad)
        )


def count_sent_today(profile: Optional[str] = None) -> int:
    dzis = datetime.now().date().isoformat()
    with get_connection_context(profile) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM wysylki WHERE date(data_wyslania)=? AND status='wysłano'",
            (dzis,)
        ).fetchone()
    return row[0] if row else 0


def count_warmup_today(profile: Optional[str] = None) -> int:
    dzis = datetime.now().date().isoformat()
    with get_connection_context(profile) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM wysylki WHERE date(data_wyslania)=? AND status='warmup'",
            (dzis,)
        ).fetchone()
    return row[0] if row else 0


def count_sent_last_hour(profile: Optional[str] = None) -> int:
    godzina_temu = (datetime.now() - timedelta(hours=1)).isoformat()
    with get_connection_context(profile) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM wysylki WHERE data_wyslania > ? AND status='wysłano'",
            (godzina_temu,)
        ).fetchone()
    return row[0] if row else 0


def get_searched_combos(profile: Optional[str] = None) -> Set[Tuple[str, str]]:
    with get_connection_context(profile) as conn:
        rows = conn.execute("SELECT query, location FROM searched_combos").fetchall()
    return {(row[0], row[1]) for row in rows}


def mark_combo_searched(query: str, location: str, profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO searched_combos (query, location, searched_at) VALUES (?, ?, ?)",
            (query, location, datetime.now().isoformat())
        )


def clear_searched_combos(profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute("DELETE FROM searched_combos")


def get_profile_names(profile: Optional[str] = None) -> List[str]:
    with get_connection_context(profile) as conn:
        rows = conn.execute("SELECT name FROM profiles ORDER BY name").fetchall()
    return [r[0] for r in rows]


def get_profile(name: str, profile: Optional[str] = None) -> Optional[Dict[str, str]]:
    with get_connection_context(profile) as conn:
        row = conn.execute(
            "SELECT name, queries, locations, template, subject FROM profiles WHERE name=?",
            (name,)
        ).fetchone()
    if not row:
        return None
    return {"name": row[0], "queries": row[1], "locations": row[2], "template": row[3], "subject": row[4]}


def save_profile(name: str, queries: str, locations: str, template: str, subject: str,
                 profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute(
            """INSERT INTO profiles (name, queries, locations, template, subject)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                   queries=excluded.queries, locations=excluded.locations,
                   template=excluded.template, subject=excluded.subject""",
            (name, queries, locations, template, subject)
        )


def delete_profile_from_db(name: str, profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute("DELETE FROM profiles WHERE name=?", (name,))


def get_history(limit: int = 200, profile: Optional[str] = None) -> List[Tuple]:
    with get_connection_context(profile) as conn:
        return conn.execute(
            "SELECT data_wyslania, email, status, temat, blad FROM wysylki "
            "ORDER BY data_wyslania DESC LIMIT ?",
            (limit,)
        ).fetchall()


def clear_old_logs(days: int = 30, profile: Optional[str] = None) -> int:
    limit = (datetime.now() - timedelta(days=days)).isoformat()
    with get_connection_context(profile) as conn:
        cur = conn.execute("DELETE FROM wysylki WHERE data_wyslania < ?", (limit,))
        return cur.rowcount

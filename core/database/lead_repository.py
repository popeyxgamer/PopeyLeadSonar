# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from ..config import logger
from .connection import get_connection_context

LEADS_SUMMARY_COLUMNS = ("id", "firma", "email", "adres", "typ", "status", "wyslano")


def add_lead(firma: str, email: str, adres: str = "", telefon: str = "",
             website: str = "", typ: str = "", kontakt: str = "",
             lead_score: int = -1, lead_score_reason: str = "",
             linkedin: str = "",
             profile: Optional[str] = None) -> Optional[int]:
    try:
        with get_connection_context(profile) as conn:
            c = conn.cursor()
            if c.execute("SELECT id FROM leads WHERE email=?", (email,)).fetchone():
                return None
            c.execute(
                """INSERT INTO leads
                   (firma, kontakt, email, adres, telefon, website, linkedin, typ, status, source, lead_score, lead_score_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'nowy', 'wyszukiwarka', ?, ?)""",
                (firma, kontakt, email, adres, telefon, website, linkedin, typ, lead_score, lead_score_reason)
            )
            return c.lastrowid
    except sqlite3.Error as e:
        logger.error("Nie udało się dodać leada %s: %s", email, e)
        return None


def get_leads(status: Optional[str] = None, profile: Optional[str] = None) -> List[Tuple]:
    query = ("SELECT id, firma, kontakt, email, adres, telefon, website, typ, status, wyslano "
             "FROM leads")
    params = []
    if status:
        query += " WHERE status=?"
        params = [status]
    query += " ORDER BY id"
    with get_connection_context(profile) as conn:
        return conn.execute(query, params).fetchall()


def get_leads_summary(status: Optional[str] = None, search: str = "",
                      limit: Optional[int] = None, offset: int = 0,
                      profile: Optional[str] = None) -> List[Tuple]:
    query = "SELECT id, firma, email, adres, typ, status, wyslano FROM leads"
    conditions = []
    params = []
    if status:
        conditions.append("status=?")
        params.append(status)
    if search:
        conditions.append("(LOWER(firma) LIKE ? OR LOWER(email) LIKE ?)")
        like = f"%{search.lower()}%"
        params.extend([like, like])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC"

    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    with get_connection_context(profile) as conn:
        return conn.execute(query, params).fetchall()


def count_leads(status: Optional[str] = None, search: str = "",
                 profile: Optional[str] = None) -> int:
    query = "SELECT COUNT(*) FROM leads"
    conditions = []
    params = []
    if status:
        conditions.append("status=?")
        params.append(status)
    if search:
        conditions.append("(LOWER(firma) LIKE ? OR LOWER(email) LIKE ?)")
        like = f"%{search.lower()}%"
        params.extend([like, like])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    with get_connection_context(profile) as conn:
        row = conn.execute(query, params).fetchone()
    return row[0] if row else 0


def get_lead_by_id(lead_id: int, profile: Optional[str] = None) -> Optional[Tuple]:
    with get_connection_context(profile) as conn:
        return conn.execute(
            "SELECT id, firma, kontakt, email, adres, telefon, lead_score, website FROM leads WHERE id=?",
            (lead_id,)
        ).fetchone()


def update_lead_score(lead_id: int, score: int, reason: str = "", profile: Optional[str] = None) -> bool:
    try:
        with get_connection_context(profile) as conn:
            conn.execute(
                "UPDATE leads SET lead_score=?, lead_score_reason=? WHERE id=?",
                (score, reason, lead_id)
            )
        return True
    except sqlite3.Error as e:
        logger.error("Błąd aktualizacji scoru leada %s: %s", lead_id, e)
        return False


def get_leads_by_score(min_score: int = 0, max_score: int = 100,
                       profile: Optional[str] = None) -> List[Tuple]:
    with get_connection_context(profile) as conn:
        return conn.execute(
            "SELECT id, firma, email, lead_score FROM leads WHERE lead_score >= ? AND lead_score <= ? ORDER BY lead_score DESC",
            (min_score, max_score)
        ).fetchall()


def delete_sent_leads(profile: Optional[str] = None) -> int:
    with get_connection_context(profile) as conn:
        cur = conn.execute("DELETE FROM leads WHERE status='wysłano'")
        return cur.rowcount


def get_wyslano_emails(profile: Optional[str] = None) -> Set[str]:
    with get_connection_context(profile) as conn:
        rows = conn.execute("SELECT email FROM wyslano").fetchall()
    return {r[0] for r in rows}


def get_excluded_emails(profile: Optional[str] = None) -> Set[str]:
    excluded = set()
    with get_connection_context(profile) as conn:
        # 1. Wyslane
        rows = conn.execute("SELECT email FROM wyslano").fetchall()
        excluded.update(r[0] for r in rows)

        # 2. Błędne, Odpowiedzieli, Rezygnacja
        rows = conn.execute("SELECT email FROM leads WHERE status IN ('błędny', 'responded', 'rezygnacja')").fetchall()
        excluded.update(r[0] for r in rows)

        # 3. Blacklist
        rows = conn.execute("SELECT email FROM blacklist").fetchall()
        excluded.update(r[0] for r in rows)

    return excluded


def mark_sent(email: str, profile: Optional[str] = None) -> None:
    now = datetime.now().isoformat()
    with get_connection_context(profile) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO wyslano (email, data_wyslania) VALUES (?, ?)", (email, now)
        )
        conn.execute(
            "UPDATE leads SET status='wysłano', wyslano=? WHERE email=?", (now, email)
        )


def mark_invalid(email: str, profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute(
            "UPDATE leads SET status='błędny' WHERE email=?", (email.strip().lower(),)
        )


def get_unscored_leads(profile: Optional[str] = None) -> List[Tuple]:
    with get_connection_context(profile) as conn:
        return conn.execute(
            "SELECT id, firma, email, website FROM leads WHERE lead_score = -1 AND status = 'nowy' ORDER BY id"
        ).fetchall()


def get_scanned_domains(max_age_days: int = 30, profile: Optional[str] = None) -> Dict[str, Optional[str]]:
    cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    with get_connection_context(profile) as conn:
        rows = conn.execute(
            "SELECT domain, email FROM scanned_domains WHERE checked_at > ?", (cutoff,)
        ).fetchall()
    return {domain: email for domain, email in rows}


def mark_domains_scanned(results: Dict[str, Optional[str]], profile: Optional[str] = None) -> None:
    if not results:
        return
    now = datetime.now().isoformat()
    with get_connection_context(profile) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO scanned_domains (domain, email, checked_at) VALUES (?, ?, ?)",
            [(domain, email, now) for domain, email in results.items()]
        )

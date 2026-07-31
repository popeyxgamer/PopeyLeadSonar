# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .connection import get_connection_context


def get_sequences(profile: Optional[str] = None) -> List[Dict]:
    with get_connection_context(profile) as conn:
        rows = conn.execute("SELECT id, name, created_at FROM sequences ORDER BY name").fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]


def get_sequence(seq_id: int, profile: Optional[str] = None) -> Optional[Dict]:
    with get_connection_context(profile) as conn:
        row = conn.execute("SELECT id, name, created_at FROM sequences WHERE id=?", (seq_id,)).fetchone()
        if not row:
            return None
        steps = conn.execute(
            "SELECT id, step_number, delay_days, subject, template FROM sequence_steps "
            "WHERE sequence_id=? ORDER BY step_number", (seq_id,)
        ).fetchall()
    return {
        "id": row[0], "name": row[1], "created_at": row[2],
        "steps": [{"id": s[0], "step": s[1], "delay": s[2], "subject": s[3], "template": s[4]} for s in steps]
    }


def add_sequence(name: str, steps: List[Dict], profile: Optional[str] = None) -> int:
    with get_connection_context(profile) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO sequences (name, created_at) VALUES (?, ?)", (name, datetime.now().isoformat()))
        seq_id = c.lastrowid
        for i, step in enumerate(steps):
            c.execute(
                "INSERT INTO sequence_steps (sequence_id, step_number, delay_days, subject, template) "
                "VALUES (?, ?, ?, ?, ?)",
                (seq_id, i+1, step.get("delay", 0), step.get("subject", ""), step.get("template", ""))
            )
        return seq_id


def delete_sequence(seq_id: int, profile: Optional[str] = None):
    with get_connection_context(profile) as conn:
        conn.execute("DELETE FROM sequences WHERE id=?", (seq_id,))


def start_lead_sequence(lead_id: int, seq_id: int, profile: Optional[str] = None):
    now = datetime.now().isoformat()
    with get_connection_context(profile) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO lead_sequences (lead_id, sequence_id, current_step, next_run_at, status) "
            "VALUES (?, ?, 1, ?, 'active')",
            (lead_id, seq_id, now)
        )


def get_pending_sequence_steps(profile: Optional[str] = None) -> List[Tuple]:
    now = datetime.now().isoformat()
    query = """
        SELECT ls.lead_id, ls.sequence_id, ls.current_step, ss.subject, ss.template, l.email, l.firma
        FROM lead_sequences ls
        JOIN sequence_steps ss ON ls.sequence_id = ss.sequence_id AND ls.current_step = ss.step_number
        JOIN leads l ON ls.lead_id = l.id
        WHERE ls.status = 'active' AND ls.next_run_at <= ?
    """
    with get_connection_context(profile) as conn:
        return conn.execute(query, (now,)).fetchall()


def mark_step_done(lead_id: int, seq_id: int, next_delay_days: Optional[int], profile: Optional[str] = None):
    if next_delay_days is None:
        status = 'finished'
        next_run = None
    else:
        status = 'active'
        next_run = (datetime.now() + timedelta(days=next_delay_days)).isoformat()

    with get_connection_context(profile) as conn:
        conn.execute(
            "UPDATE lead_sequences SET current_step = current_step + 1, next_run_at = ?, status = ? "
            "WHERE lead_id = ? AND sequence_id = ?",
            (next_run, status, lead_id, seq_id)
        )


def mark_as_responded(email: str, profile: Optional[str] = None):
    with get_connection_context(profile) as conn:
        email_clean = email.strip().lower()
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE lead_sequences SET status = 'responded' "
            "WHERE lead_id IN (SELECT id FROM leads WHERE email = ?) AND status = 'active'",
            (email_clean,)
        )
        conn.execute(
            "UPDATE leads SET status = 'responded', data_odpowiedzi = ? WHERE email = ?",
            (now, email_clean)
        )

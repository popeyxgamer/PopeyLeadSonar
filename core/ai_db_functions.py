# -*- coding: utf-8 -*-
"""AI Database Functions - dołączyć do core/database.py na koniec"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from . import database as db


def save_ai_suggestion(feature: str, email: str, input_text: str, suggestion: str, provider: str = "unknown", lead_id: Optional[int] = None, profile: Optional[str] = None) -> None:
    """Zapisz sugestię AI w bazie."""
    with db.get_connection_context(profile) as conn:
        conn.execute("INSERT INTO ai_suggestions (feature, lead_id, email, input_text, suggestion, provider, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (feature, lead_id, email, input_text, suggestion, provider, datetime.now().isoformat()))


def get_ai_suggestions(feature: Optional[str] = None, email: Optional[str] = None, limit: int = 10, profile: Optional[str] = None) -> list:
    """Pobierz sugestie AI."""
    query = "SELECT id, feature, email, suggestion, provider, created_at FROM ai_suggestions"
    conditions = []
    params = []
    if feature:
        conditions.append("feature=?")
        params.append(feature)
    if email:
        conditions.append("email=?")
        params.append(email)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with db.get_connection_context(profile) as conn:
        return conn.execute(query, params).fetchall()


def save_lead_score(email: str, score: int, is_spam: int, reason: str = "", lead_id: Optional[int] = None, profile: Optional[str] = None) -> None:
    """Zapisz ocenę leadу z AI."""
    with db.get_connection_context(profile) as conn:
        conn.execute("INSERT INTO ai_lead_scores (lead_id, email, score, is_spam, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)", (lead_id, email, score, is_spam, reason, datetime.now().isoformat()))


def get_lead_score(email: str, profile: Optional[str] = None) -> Optional[tuple]:
    """Pobierz ostatnią ocenę leadу."""
    with db.get_connection_context(profile) as conn:
        return conn.execute("SELECT score, is_spam, reason FROM ai_lead_scores WHERE email=? ORDER BY created_at DESC LIMIT 1", (email,)).fetchone()


def mark_suggestion_used(suggestion_id: int, profile: Optional[str] = None) -> None:
    """Oznacz sugestię jako użytą."""
    with db.get_connection_context(profile) as conn:
        conn.execute("UPDATE ai_suggestions SET used=1 WHERE id=?", (suggestion_id,))


def create_ab_test(name: str, variant_a: str, variant_b: str, metric: str = "opens", profile: Optional[str] = None) -> int:
    """Utwórz A/B test."""
    with db.get_connection_context(profile) as conn:
        cur = conn.execute("INSERT INTO ai_ab_tests (name, variant_a, variant_b, metric, created_at) VALUES (?, ?, ?, ?, ?)", (name, variant_a, variant_b, metric, datetime.now().isoformat()))
        return cur.lastrowid


def log_ab_test_result(test_id: int, variant: str, result: int, profile: Optional[str] = None) -> None:
    """Zaloguj wynik A/B testu."""
    if variant == "A":
        query = "UPDATE ai_ab_tests SET result_a = result_a + ? WHERE id=?"
    else:
        query = "UPDATE ai_ab_tests SET result_b = result_b + ? WHERE id=?"
    with db.get_connection_context(profile) as conn:
        conn.execute(query, (result, test_id))


def finish_ab_test(test_id: int, winner: str, profile: Optional[str] = None) -> None:
    """Zakończ A/B test."""
    with db.get_connection_context(profile) as conn:
        conn.execute("UPDATE ai_ab_tests SET winner=?, finished_at=? WHERE id=?", (winner, datetime.now().isoformat(), test_id))


def get_ab_tests(limit: int = 10, profile: Optional[str] = None) -> list:
    """Pobierz A/B testy."""
    with db.get_connection_context(profile) as conn:
        return conn.execute("SELECT id, name, variant_a, variant_b, result_a, result_b, winner, created_at FROM ai_ab_tests ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()

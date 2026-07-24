# -*- coding: utf-8 -*-
"""
Funkcje bazodanowe dla funkcji AI (sugestie, A/B testy, scoring leadów).

UWAGA: ten moduł wcześniej definiował te same funkcje bezpośrednio, ale bez
importu `Optional` (błąd NameError przy imporcie) i z SQL-em tworzącym
tabele schowanym w komentarzu (nigdy się nie wykonywał, więc tabele
ai_suggestions / ai_ab_tests / ai_lead_scores nigdy nie powstawały).

Prawidłowa, działająca implementacja tych funkcji żyje w
`core/ai_db_functions.py`, a CREATE TABLE dla powyższych tabel zostało
przeniesione do `init_db_for_profile()` w `core/database.py`. Ten plik jest
teraz cienkim re-eksportem, żeby istniejące importy (`from core.ai_database
import ...`) nadal działały.
"""
from .ai_db_functions import (
    save_ai_suggestion,
    get_ai_suggestions,
    mark_suggestion_used,
    save_lead_score,
    get_lead_score,
    create_ab_test,
    log_ab_test_result,
    finish_ab_test,
    get_ab_tests,
)

__all__ = [
    "save_ai_suggestion",
    "get_ai_suggestions",
    "mark_suggestion_used",
    "save_lead_score",
    "get_lead_score",
    "create_ab_test",
    "log_ab_test_result",
    "finish_ab_test",
    "get_ab_tests",
]

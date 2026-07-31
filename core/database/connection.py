# -*- coding: utf-8 -*-
import sqlite3
import threading
from contextlib import contextmanager
from typing import Dict, Iterator, Optional

from ..config import (
    get_db_path, get_active_profile, logger,
    DEFAULT_PROFILE_NAME,
)

# Pula połączeń – klucz: nazwa profilu, wartość: połączenie
_connections: Dict[str, sqlite3.Connection] = {}
# Chroni _connections przed równoczesnym dostępem z wielu wątków naraz
_connections_lock = threading.Lock()


def get_connection(profile: Optional[str] = None) -> sqlite3.Connection:
    """
    Zwraca połączenie SQLite dla danego profilu.
    Tworzy nowe połączenie, jeśli nie istnieje w puli.
    """
    if profile is None:
        profile = get_active_profile() or DEFAULT_PROFILE_NAME

    with _connections_lock:
        if profile in _connections:
            try:
                _connections[profile].execute("SELECT 1").fetchone()
                return _connections[profile]
            except (sqlite3.Error, sqlite3.ProgrammingError, OSError) as e:
                logger.debug("Nieaktywne połączenie %s: %s", profile, e)
                del _connections[profile]

        db_path = get_db_path(profile)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA encoding='UTF-8'")
        conn.row_factory = sqlite3.Row
        _connections[profile] = conn
        return conn


@contextmanager
def get_connection_context(profile: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """Menedżer kontekstu – zwraca połączenie z puli, ale NIE zamyka go."""
    conn = get_connection(profile)
    with _connections_lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def close_all_connections() -> None:
    """Zamyka wszystkie połączenia w puli."""
    global _connections
    with _connections_lock:
        for profile, conn in _connections.items():
            try:
                conn.close()
            except Exception:
                pass
        _connections.clear()
    logger.debug("Zamknięto wszystkie połączenia do bazy.")


def init_db_for_profile(profile: Optional[str] = None) -> None:
    """Tworzy tabele i indeksy dla danego profilu (jeśli nie istnieją)."""
    if profile is None:
        profile = get_active_profile() or DEFAULT_PROFILE_NAME

    with get_connection_context(profile) as conn:
        c = conn.cursor()
        c.execute("PRAGMA encoding='UTF-8'")
        c.execute('''CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firma TEXT,
            kontakt TEXT,
            email TEXT UNIQUE,
            adres TEXT,
            telefon TEXT,
            website TEXT,
            linkedin TEXT,
            typ TEXT,
            status TEXT DEFAULT 'nowy',
            wyslano TEXT,
            odpowiedz TEXT,
            data_odpowiedzi TEXT,
            source TEXT,
            lead_score INTEGER DEFAULT -1,
            lead_score_reason TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS wysylki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            email TEXT,
            temat TEXT,
            tresc TEXT,
            status TEXT,
            data_wyslania TEXT,
            blad TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS wyslano (
            email TEXT PRIMARY KEY,
            data_wyslania TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS scanned_domains (
            domain TEXT PRIMARY KEY,
            email TEXT,
            checked_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS searched_combos (
            query TEXT,
            location TEXT,
            searched_at TEXT,
            PRIMARY KEY (query, location)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS profiles (
            name TEXT PRIMARY KEY,
            queries TEXT,
            locations TEXT,
            template TEXT,
            subject TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS blacklist (
            email TEXT PRIMARY KEY,
            reason TEXT,
            added_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS smtp_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            password TEXT,
            host TEXT,
            port INTEGER,
            enabled INTEGER DEFAULT 1,
            warmup_only INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS ai_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature TEXT,
            lead_id INTEGER,
            email TEXT,
            input_text TEXT,
            suggestion TEXT,
            provider TEXT,
            created_at TEXT,
            used INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS ai_ab_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            variant_a TEXT,
            variant_b TEXT,
            metric TEXT,
            result_a INTEGER DEFAULT 0,
            result_b INTEGER DEFAULT 0,
            winner TEXT,
            created_at TEXT,
            finished_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS ai_lead_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            email TEXT,
            score INTEGER,
            is_spam INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS sequence_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sequence_id INTEGER,
            step_number INTEGER,
            delay_days INTEGER,
            subject TEXT,
            template TEXT,
            FOREIGN KEY(sequence_id) REFERENCES sequences(id) ON DELETE CASCADE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS lead_sequences (
            lead_id INTEGER,
            sequence_id INTEGER,
            current_step INTEGER DEFAULT 1,
            next_run_at TEXT,
            status TEXT DEFAULT 'active',
            PRIMARY KEY(lead_id, sequence_id),
            FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY(sequence_id) REFERENCES sequences(id) ON DELETE CASCADE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS warmup_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            added_at TEXT
        )''')

        c.execute("CREATE INDEX IF NOT EXISTS idx_ai_suggestions_email ON ai_suggestions(email)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ai_suggestions_feature ON ai_suggestions(feature)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ai_lead_scores_email ON ai_lead_scores(email)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ai_ab_tests_created ON ai_ab_tests(created_at)")

        try:
            c.execute("SELECT lead_score FROM leads LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE leads ADD COLUMN lead_score INTEGER DEFAULT -1")
            c.execute("ALTER TABLE leads ADD COLUMN lead_score_reason TEXT")
            logger.info("Dodano kolumny lead_score i lead_score_reason do tabeli leads.")

        c.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(lead_score)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wysylki_data ON wysylki(data_wyslania)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wysylki_status_data ON wysylki(status, data_wyslania)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_scanned_domains_checked ON scanned_domains(checked_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_email ON blacklist(email)")

        try:
            c.execute("SELECT linkedin FROM leads LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE leads ADD COLUMN linkedin TEXT")
            logger.info("Dodano kolumnę linkedin do tabeli leads.")

        try:
            c.execute("SELECT data_odpowiedzi FROM leads LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE leads ADD COLUMN data_odpowiedzi TEXT")
            logger.info("Dodano kolumnę data_odpowiedzi do tabeli leads.")

        try:
            c.execute("SELECT warmup_only FROM smtp_accounts LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE smtp_accounts ADD COLUMN warmup_only INTEGER DEFAULT 0")
            logger.info("Dodano kolumnę warmup_only do tabeli smtp_accounts.")

        try:
            c.execute("SELECT is_main FROM smtp_accounts LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE smtp_accounts ADD COLUMN is_main INTEGER DEFAULT 0")
            logger.info("Dodano kolumnę is_main do tabeli smtp_accounts.")

        if c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
            from ..default_profile import (
                DEFAULT_LOCATIONS, DEFAULT_PROFILE_NAME as DEFAULT_PROFILE_NAME_TEXT,
                DEFAULT_QUERIES, DEFAULT_SUBJECT, DEFAULT_TEMPLATE,
            )
            c.execute(
                "INSERT INTO profiles (name, queries, locations, template, subject) VALUES (?, ?, ?, ?, ?)",
                (DEFAULT_PROFILE_NAME_TEXT, DEFAULT_QUERIES, DEFAULT_LOCATIONS, DEFAULT_TEMPLATE, DEFAULT_SUBJECT)
            )

    logger.info("Baza danych dla profilu '%s' zainicjowana.", profile)

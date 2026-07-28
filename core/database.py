# -*- coding: utf-8 -*-
"""
Warstwa dostępu do bazy danych (SQLite) – z obsługą wielu profili.
"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple

from .config import (
    get_db_path, get_active_profile, logger,
    setup_profile_logging, DEFAULT_PROFILE_NAME,
)
from .crypto_utils import decrypt_text, encrypt_text

ENCRYPTED_SETTINGS = {"gmail_password"}
LEADS_SUMMARY_COLUMNS = ("id", "firma", "email", "adres", "typ", "status", "wyslano")

# Pula połączeń – klucz: nazwa profilu, wartość: połączenie
_connections: Dict[str, sqlite3.Connection] = {}
# Chroni _connections przed równoczesnym dostępem z wielu wątków naraz
# (SearchWorker/SendWorker/AutoPilotWorker działają każdy w swoim QThread i
# wszystkie wołają get_connection() na tym samym słowniku - bez blokady
# jeden wątek mógł usunąć wpis w trakcie gdy inny go właśnie odczytywał,
# co dawało losowy KeyError: '<nazwa_profilu>').
_connections_lock = threading.Lock()


def get_connection(profile: Optional[str] = None) -> sqlite3.Connection:
    """
    Zwraca połączenie SQLite dla danego profilu.
    Tworzy nowe połączenie, jeśli nie istnieje w puli.
    """
    if profile is None:
        profile = get_active_profile() or DEFAULT_PROFILE_NAME

    with _connections_lock:
        # Jeśli połączenie już istnieje i jest otwarte – zwróć je
        if profile in _connections:
            try:
                # Sprawdź, czy połączenie jest aktywne (z timeoutem)
                _connections[profile].execute("SELECT 1").fetchone()
                return _connections[profile]
            except (sqlite3.Error, sqlite3.ProgrammingError, OSError) as e:
                # Połączenie jest nieaktywne – usuń z puli
                logger.debug("Nieaktywne połączenie %s: %s", profile, e)
                del _connections[profile]

        # Utwórz nowe połączenie. check_same_thread=False, bo to samo połączenie
        # jest współdzielone między wątkami GUI i wątkami roboczymi (QThread) -
        # dostęp jest serializowany przez _connections_lock / commit-y są krótkie,
        # więc bezpiecznie jest używać jednego połączenia z wielu wątków.
        db_path = get_db_path(profile)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA encoding='UTF-8'")
        conn.row_factory = sqlite3.Row
        _connections[profile] = conn
        return conn


@contextmanager
def get_connection_context(profile: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """Menedżer kontekstu – zwraca połączenie z puli, ale NIE zamyka go (bo jest współdzielone)."""
    conn = get_connection(profile)
    with _connections_lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def close_all_connections() -> None:
    """Zamyka wszystkie połączenia w puli (przy przełączaniu profilu)."""
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

        # New tables for Sequences
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

        # Warm-up targets table
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

        # Dodaj kolumny do istniejące tabeli leads (jeśli nie istnieją) - PRZED indeksami!
        try:
            c.execute("SELECT lead_score FROM leads LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE leads ADD COLUMN lead_score INTEGER DEFAULT -1")
            c.execute("ALTER TABLE leads ADD COLUMN lead_score_reason TEXT")
            logger.info("Dodano kolumny lead_score i lead_score_reason do tabeli leads.")

        # Teraz tworzymy indeksy
        c.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(lead_score)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wysylki_data ON wysylki(data_wyslania)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wysylki_status_data ON wysylki(status, data_wyslania)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_scanned_domains_checked ON scanned_domains(checked_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_email ON blacklist(email)")

        # Migrations for existing tables
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

        # Domyślny profil przykładowy – tylko jeśli tabela profili jest pusta
        if c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
            from .default_profile import (
                DEFAULT_LOCATIONS, DEFAULT_PROFILE_NAME as DEFAULT_PROFILE_NAME_TEXT,
                DEFAULT_QUERIES, DEFAULT_SUBJECT, DEFAULT_TEMPLATE,
            )
            c.execute(
                "INSERT INTO profiles (name, queries, locations, template, subject) VALUES (?, ?, ?, ?, ?)",
                (DEFAULT_PROFILE_NAME_TEXT, DEFAULT_QUERIES, DEFAULT_LOCATIONS, DEFAULT_TEMPLATE, DEFAULT_SUBJECT)
            )

    logger.info("Baza danych dla profilu '%s' zainicjowana.", profile)


# ------------------------------------------------------------------
# Ustawienia (w bazie, nie w pliku JSON – dla kompatybilności wstecznej)
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Leady – wszystkie funkcje korzystają z domyślnego profilu (aktualnego)
# ------------------------------------------------------------------
def add_lead(firma: str, email: str, adres: str = "", telefon: str = "",
             website: str = "", typ: str = "", kontakt: str = "",
             lead_score: int = -1, lead_score_reason: str = "",
             linkedin: str = "",
             profile: Optional[str] = None) -> Optional[int]:
    """Dodaje leada. Zwraca ID nowo dodanego rekordu, albo None jeśli e-mail
    już istnieje w bazie lub wystąpił błąd."""
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
    params: Sequence = ()
    if status:
        query += " WHERE status=?"
        params = (status,)
    query += " ORDER BY id"
    with get_connection_context(profile) as conn:
        return conn.execute(query, params).fetchall()


def get_leads_summary(status: Optional[str] = None, search: str = "",
                      limit: Optional[int] = None, offset: int = 0,
                      profile: Optional[str] = None) -> List[Tuple]:
    query = "SELECT id, firma, email, adres, typ, status, wyslano FROM leads"
    conditions = []
    params: List = []
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
    params: List = []
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
    """Aktualizuje scoring leadу (0-100, -1 = nie oceniany)."""
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
    """Zwraca leady w danym zakresie scoru."""
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
    """
    Zwraca zbiór adresów e-mail, do których NIE należy wysyłać wiadomości:
    - adresy z tabeli wyslano
    - leady o statusie 'błędny'
    - leady o statusie 'responded'
    - adresy z czarnej listy (blacklist)
    """
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
    """Oznacza lead jako błędny, aby nie próbować wysyłki ponownie."""
    with get_connection_context(profile) as conn:
        conn.execute(
            "UPDATE leads SET status='błędny' WHERE email=?", (email.strip().lower(),)
        )


def get_unscored_leads(profile: Optional[str] = None) -> List[Tuple]:
    """Zwraca leady bez scoru (lead_score = -1) do AI oceniania."""
    with get_connection_context(profile) as conn:
        return conn.execute(
            "SELECT id, firma, email, website FROM leads WHERE lead_score = -1 AND status = 'nowy' ORDER BY id"
        ).fetchall()


def log_wysylka(lead_id: int, email: str, temat: str, tresc: str,
                status: str, blad: str = "", profile: Optional[str] = None) -> None:
    with get_connection_context(profile) as conn:
        conn.execute(
            """INSERT INTO wysylki (lead_id, email, temat, tresc, status, data_wyslania, blad)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (lead_id, email, temat, tresc, status, datetime.now().isoformat(), blad)
        )


# ------------------------------------------------------------------
# Limity
# ------------------------------------------------------------------
def count_sent_today(profile: Optional[str] = None) -> int:
    dzis = datetime.now().date().isoformat()
    with get_connection_context(profile) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM wysylki WHERE date(data_wyslania)=? AND status='wysłano'",
            (dzis,)
        ).fetchone()
    return row[0]


def count_warmup_today(profile: Optional[str] = None) -> int:
    dzis = datetime.now().date().isoformat()
    with get_connection_context(profile) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM wysylki WHERE date(data_wyslania)=? AND status='warmup'",
            (dzis,)
        ).fetchone()
    return row[0]


def count_sent_last_hour(profile: Optional[str] = None) -> int:
    godzina_temu = (datetime.now() - timedelta(hours=1)).isoformat()
    with get_connection_context(profile) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM wysylki WHERE data_wyslania > ? AND status='wysłano'",
            (godzina_temu,)
        ).fetchone()
    return row[0]


# ------------------------------------------------------------------
# Cache domen
# ------------------------------------------------------------------
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


def get_searched_combos(profile: Optional[str] = None) -> Set[Tuple[str, str]]:
    """Zwraca zbiór (kategoria, lokalizacja) już przeszukanych w tym profilu -
    pozwala kolejnemu wyszukiwaniu pominąć to, co już zostało sprawdzone,
    zamiast zaczynać od pierwszej kategorii za każdym razem."""
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
    """Czyści historię przeszukanych kombinacji - użyj, żeby przeszukać wszystko od nowa."""
    with get_connection_context(profile) as conn:
        conn.execute("DELETE FROM searched_combos")


# ------------------------------------------------------------------
# Profile (wewnętrzne – kategorie/lokalizacje/szablon)
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Historia
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Blacklist
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Konta SMTP do rotacji i przełączania
# ------------------------------------------------------------------
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
    """Ustawia wybrane konto jako główne (is_main=1) i odznacza pozostałe."""
    try:
        with get_connection_context(profile) as conn:
            # Najpierw odznacz wszystkie
            conn.execute("UPDATE smtp_accounts SET is_main = 0")
            # Ustaw wybrane
            conn.execute("UPDATE smtp_accounts SET is_main = 1 WHERE user = ?", (email.strip(),))
        return True
    except sqlite3.Error as e:
        logger.error("Błąd ustawiania głównego konta %s: %s", email, e)
        return False

# ------------------------------------------------------------------
# Sekwencje (Sequences)
# ------------------------------------------------------------------
def get_sequences(profile: Optional[str] = None) -> List[Dict]:
    with get_connection_context(profile) as conn:
        rows = conn.execute("SELECT id, name, created_at FROM sequences ORDER BY name").fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]

def get_sequence(seq_id: int, profile: Optional[str] = None) -> Optional[Dict]:
    with get_connection_context(profile) as conn:
        row = conn.execute("SELECT id, name, created_at FROM sequences WHERE id=?", (seq_id,)).fetchone()
        if not row: return None
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
    """Zapisuje start sekwencji dla leada. Pierwszy krok wysyłany jest 'od razu' przez workera."""
    now = datetime.now().isoformat()
    with get_connection_context(profile) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO lead_sequences (lead_id, sequence_id, current_step, next_run_at, status) "
            "VALUES (?, ?, 1, ?, 'active')",
            (lead_id, seq_id, now)
        )

def get_pending_sequence_steps(profile: Optional[str] = None) -> List[Tuple]:
    """Zwraca leady i kroki sekwencji, które powinny być wysłane teraz."""
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
        # Koniec sekwencji
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
    """Zatrzymuje wszystkie aktywne sekwencje dla danego adresu e-mail i aktualizuje status leada."""
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

# ------------------------------------------------------------------
# Warm-up Targets
# ------------------------------------------------------------------
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

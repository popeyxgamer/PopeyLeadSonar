# -*- coding: utf-8 -*-
"""
Centralna konfiguracja aplikacji – z obsługą wielu profili.
Każdy profil ma własny folder z bazą, logami i ustawieniami.
"""
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from cryptography.hazmat.primitives import hashes

# ------------------------------------------------------------------
# Ścieżki GŁÓWNE (niezależne od profilu)
# ------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

PROFILES_DIR = BASE_DIR / "profiles"
PROFILES_INDEX_FILE = BASE_DIR / "profiles_index.json"

# Domyślna nazwa profilu (pierwsze uruchomienie / fallback)
DEFAULT_PROFILE_NAME = "default"

# ------------------------------------------------------------------
# Zarządzanie aktywnym profilem (stan w pamięci)
# ------------------------------------------------------------------
_active_profile: Optional[str] = None


def set_active_profile(name: str) -> None:
    """Ustawia aktywny profil (zmienia kontekst ścieżek)."""
    global _active_profile
    if name and not get_profile_path(name).exists():
        raise ValueError(f"Profil '{name}' nie istnieje.")
    _active_profile = name
    # Zapisz ostatni użyty profil do pliku (żeby przy restarcie wczytać)
    try:
        with open(BASE_DIR / "last_profile.txt", "w", encoding="utf-8") as f:
            f.write(name)
    except OSError:
        pass


def get_active_profile() -> Optional[str]:
    """Zwraca nazwę aktywnego profilu lub None."""
    return _active_profile


def load_last_profile() -> Optional[str]:
    """Wczytuje ostatnio używany profil z pliku."""
    try:
        with open(BASE_DIR / "last_profile.txt", "r", encoding="utf-8") as f:
            name = f.read().strip()
            if name and get_profile_path(name).exists():
                return name
    except (OSError, FileNotFoundError):
        pass
    return None


# ------------------------------------------------------------------
# Ścieżki ZALEŻNE od profilu
# ------------------------------------------------------------------
def get_profile_path(name: Optional[str] = None) -> Path:
    """Zwraca ścieżkę do folderu profilu."""
    if name is None:
        name = get_active_profile() or DEFAULT_PROFILE_NAME
    return PROFILES_DIR / name


def get_db_path(profile: Optional[str] = None) -> Path:
    return get_profile_path(profile) / "campaign_data.db"


def get_log_path(profile: Optional[str] = None) -> Path:
    return get_profile_path(profile) / "app.log"


def get_crypto_key_path(profile: Optional[str] = None) -> Path:
    return get_profile_path(profile) / "crypto.key"


def get_settings_path(profile: Optional[str] = None) -> Path:
    return get_profile_path(profile) / "settings.json"


def get_blacklist_path(profile: Optional[str] = None) -> Path:
    return get_profile_path(profile) / "blacklist.txt"  # opcjonalnie


# ------------------------------------------------------------------
# Operacje na profilach (lista, tworzenie, usuwanie)
# ------------------------------------------------------------------
def list_profiles() -> List[str]:
    """Zwraca listę nazw istniejących profili (foldery w PROFILES_DIR)."""
    if not PROFILES_DIR.exists():
        return []
    return [p.name for p in PROFILES_DIR.iterdir() if p.is_dir() and (p / "campaign_data.db").exists()]


def profile_exists(name: str) -> bool:
    return get_profile_path(name).exists() and (get_profile_path(name) / "campaign_data.db").exists()


def create_profile(name: str, copy_from: Optional[str] = None) -> bool:
    """
    Tworzy nowy profil (folder + pusta baza + domyślne ustawienia).
    Jeśli copy_from podane – kopiuje bazę i ustawienia z istniejącego profilu.
    Zwraca True jeśli sukces.
    """
    if profile_exists(name):
        return False

    new_path = get_profile_path(name)
    new_path.mkdir(parents=True, exist_ok=True)

    # Jeśli kopiujemy z innego profilu
    if copy_from and profile_exists(copy_from):
        src_path = get_profile_path(copy_from)
        # Kopiuj bazę
        shutil.copy2(src_path / "campaign_data.db", new_path / "campaign_data.db")
        # Kopiuj klucz (jeśli istnieje)
        if (src_path / "crypto.key").exists():
            shutil.copy2(src_path / "crypto.key", new_path / "crypto.key")
        # Kopiuj ustawienia (jeśli istnieją)
        if (src_path / "settings.json").exists():
            shutil.copy2(src_path / "settings.json", new_path / "settings.json")
        # Kopiuj blacklistę (jeśli istnieje)
        if (src_path / "blacklist.txt").exists():
            shutil.copy2(src_path / "blacklist.txt", new_path / "blacklist.txt")
    else:
        # Tworzymy pustą bazę – będzie zainicjowana przy pierwszym użyciu
        from core.database import init_db_for_profile
        init_db_for_profile(name)  # funkcja z database.py (ETAP 2)

        # Domyślne ustawienia
        default_settings = {
            "gmail_user": "",
            "gmail_password": "",
            "smtp_host": "smtp-relay.gmail.com",
            "smtp_port": 587,
            "dzienny_limit": 9500,
            "custom_send_delay": 3.0,
            "custom_session_cap": 250,
            "proxy_enabled": False,
            "proxy_list": "",
            "html_enabled": False,
            "mx_verify_enabled": True,
            "smime_enabled": True,
            "attachments": "",
            "account_rotation_enabled": False,
            "rotation_max_per_account": 1000,
            "imap_enabled": False,
            "imap_server": "imap.gmail.com",
            "imap_user": "",
            "imap_password": "",
            "ai_scoring_enabled": False,
            "ai_scoring_threshold": 50,
            "ai_scoring_model": "gpt-3.5-turbo",
            "last_queries": "",
            "last_locations": "",
            "last_template": "",
            "last_subject": "",
        }
        save_profile_settings(name, default_settings)

        # Tworzymy domyślny profil przykładowy w bazie (przy pierwszym uruchomieniu)
        # To będzie zrobione w init_db_for_profile

    # Zapisz indeks (listę profili) – opcjonalnie
    update_profiles_index()

    return True


def delete_profile(name: str) -> bool:
    """Usuwa profil (folder i wszystkie pliki)."""
    if name == DEFAULT_PROFILE_NAME:
        # Nie pozwalamy usunąć domyślnego profilu
        return False
    if not profile_exists(name):
        return False
    import shutil
    shutil.rmtree(get_profile_path(name))
    update_profiles_index()
    return True


def update_profiles_index() -> None:
    """Zapisuje listę profili do pliku indeksu (dla szybkiego dostępu)."""
    profiles = list_profiles()
    try:
        with open(PROFILES_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump({"profiles": profiles, "updated": datetime.now().isoformat()}, f, indent=2)
    except OSError:
        pass


def load_profiles_index() -> List[str]:
    """Wczytuje listę profili z pliku indeksu (jeśli istnieje)."""
    if not PROFILES_INDEX_FILE.exists():
        return list_profiles()  # fallback – skanowanie folderu
    try:
        with open(PROFILES_INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("profiles", [])
    except (OSError, json.JSONDecodeError):
        return list_profiles()


# ------------------------------------------------------------------
# Ustawienia profilu (zapis/odczyt w pliku settings.json)
# ------------------------------------------------------------------
def load_profile_settings(profile: Optional[str] = None) -> Dict[str, Any]:
    """Ładuje ustawienia profilu z pliku JSON."""
    path = get_settings_path(profile)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_profile_settings(profile: Optional[str], settings: Dict[str, Any]) -> None:
    """Zapisuje ustawienia profilu do pliku JSON."""
    path = get_settings_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_profile_setting(key: str, default: Any = None, profile: Optional[str] = None) -> Any:
    """Pobiera pojedyncze ustawienie z profilu."""
    settings = load_profile_settings(profile)
    return settings.get(key, default)


def set_profile_setting(key: str, value: Any, profile: Optional[str] = None) -> None:
    """Zapisuje pojedyncze ustawienie w profilu."""
    settings = load_profile_settings(profile)
    settings[key] = value
    save_profile_settings(profile, settings)


# ------------------------------------------------------------------
# Stałe konfiguracyjne (NIEZALEŻNE od profilu)
# ------------------------------------------------------------------
# Sieć / scraping
REQUEST_TIMEOUT = 5
MAX_ASYNC_CONCURRENT = 12
ASYNC_GLOBAL_TIMEOUT = 45
MAX_HTML_SIZE = 500_000
SEARCH_DELAY_RANGE = (2, 4)
DOMAIN_CACHE_MAX_AGE_DAYS = 30

# SMTP (domyślne)
SMTP_RELAY_HOST = "smtp-relay.gmail.com"
SMTP_RELAY_PORT = 587
SMTP_FALLBACK_HOST = "smtp.gmail.com"
SMTP_FALLBACK_PORT = 587
SMTP_TIMEOUT = 30

# Tempo
SEND_FIXED_DELAY = 0.7
GMAIL_FREE_SEND_DELAY = 4.0

# Limity
SESSION_CAP_ABS_MAX = 10_000
SESSION_CAP_OPTIONS = [2_000, 5_000, 9_500, 10_000]
SESSION_HARD_CAP = 9_500
GMAIL_FREE_SESSION_CAP_ABS_MAX = 500
GMAIL_FREE_SESSION_CAP_OPTIONS = [200, 500]
GMAIL_FREE_SESSION_CAP_DEFAULT = 200
CUSTOM_SEND_DELAY_DEFAULT = 3.0
CUSTOM_SEND_DELAY_MIN = 1.0
CUSTOM_SESSION_CAP_DEFAULT = 250
CUSTOM_SESSION_CAP_MAX = 5_000

SMTP_TEMP_FAIL_CODES = (421, 450)
SMTP_TEMP_FAIL_PAUSE = 60

DEFAULT_DAILY_LIMIT = SESSION_HARD_CAP

# Nowe ustawienia (globalne)
BLACKLIST_AUTO_ADD_BOUNCE = True
BLACKLIST_AUTO_ADD_UNSUBSCRIBE = True
IMAP_SERVER = "imap.gmail.com"
IMAP_CHECK_INTERVAL = 300
SMIME_ENABLED_DEFAULT = False
SMIME_CERT_VALIDITY_DAYS = 365
SMIME_DIGEST_ALGORITHM = hashes.SHA256
ACCOUNT_ROTATION_ENABLED_DEFAULT = False
ACCOUNT_ROTATION_MAX_PER_ACCOUNT = 1000
HTML_EMAIL_ENABLED_DEFAULT = False
HTML_EMAIL_FALLBACK_TO_TEXT = True

# Domeny ignorowane (portale itp.) – bez zmian
IGNORED_DOMAINS = [
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "pinterest.", "tiktok.com", "twitter.com", "x.com",
    "google.", "bing.com", "wikipedia.org", "wikimedia.org",
    "gelbeseiten.de", "dasoertliche.de", "11880.com", "meinestadt.de",
    "cylex.de", "stadtbranchenbuch.com", "firmenwissen.de",
    "unternehmensregister.de", "wlw.de", "europages.", "kompass.com",
    "branchenbuch.", "firmendb.de",
    "lieferando.de", "wolt.com", "ubereats.com", "opentable.",
    "quandoo.", "resengo.com", "thefork.", "booking.com", "hrs.de",
    "hrs.com", "expedia.", "holidaycheck.de", "tripadvisor.",
    "yelp.", "trustpilot.com", "kununu.com", "indeed.com", "stepstone.de",
    "xing.com", "provenexpert.com", "golocal.de",
    "t-online.de", "focus.de", "welt.de", "spiegel.de", "sueddeutsche.de",
    "faz.net", "zeit.de", "stern.de", "handelsblatt.de", "n-tv.de",
    "tagesspiegel.de", "berliner-zeitung.de", "morgenpost.de", "bz-berlin.de",
    "rbb24.de", "stroeer.de",
    "visitberlin.de", "berlin.de", "stadtentwicklung.berlin.de",
    "top10berlin.de",
]
PORTAL_DOMAIN_KEYWORDS = [
    "top10", "ratgeber", "bewertung", "bewertungsportal", "vergleich",
    "verzeichnis", "branchenbuch", "stadtplan", "stadtfuehrer", "guide",
]
PORTAL_TITLE_KEYWORDS = [
    "top 10", "top10", "die besten", "bestenliste", "ratgeber", "tipps &",
    "tipps und", " news", "magazin", "vergleich", "rangliste", "übersicht",
    "was tun in", "sehenswürdigkeiten",
]
EMAIL_BLACKLIST = [
    "example.com", "noreply", "no-reply", "segmenter",
    ".js", ".css", "wix.com", "jimdo.com",
]

# Autodetekcja SMTP
SMTP_PROVIDERS = {
    "gmail.com": ("smtp.gmail.com", 587),
    "googlemail.com": ("smtp.gmail.com", 587),
    "outlook.com": ("smtp.office365.com", 587),
    "hotmail.com": ("smtp.office365.com", 587),
    "live.com": ("smtp.office365.com", 587),
    "live.pl": ("smtp.office365.com", 587),
    "outlook.pl": ("smtp.office365.com", 587),
    "wp.pl": ("smtp.wp.pl", 587),
    "onet.pl": ("smtp.onet.pl", 587),
    "o2.pl": ("smtp.o2.pl", 587),
    "interia.pl": ("smtp.interia.pl", 587),
    "gazeta.pl": ("smtp.gazeta.pl", 587),
    "yahoo.com": ("smtp.mail.yahoo.com", 587),
    "yahoo.pl": ("smtp.mail.yahoo.com", 587),
    "icloud.com": ("smtp.mail.me.com", 587),
    "mac.com": ("smtp.mail.me.com", 587),
    "me.com": ("smtp.mail.me.com", 587),
    "mail.com": ("smtp.mail.com", 587),
    "email.com": ("smtp.mail.com", 587),
    "protonmail.com": ("smtp.protonmail.ch", 587),
    "proton.me": ("smtp.protonmail.ch", 587),
    "web.de": ("smtp.web.de", 587),
    "gmx.de": ("smtp.gmx.de", 587),
    "gmx.net": ("smtp.gmx.net", 587),
    "t-online.de": ("smtp.t-online.de", 587),
    "freenet.de": ("smtp.freenet.de", 587),
    "seznam.cz": ("smtp.seznam.cz", 587),
    "zoho.com": ("smtp.zoho.com", 587),
    "yandex.com": ("smtp.yandex.com", 587),
    "yandex.ru": ("smtp.yandex.ru", 587),
    "aol.com": ("smtp.aol.com", 587),
}


def guess_smtp(email: str) -> Optional[tuple[str, int]]:
    if not email or '@' not in email:
        return None
    domain = email.split('@')[1].lower()
    return SMTP_PROVIDERS.get(domain)


# ------------------------------------------------------------------
# Logowanie – dynamiczna ścieżka logu
# ------------------------------------------------------------------
def setup_profile_logging(profile: Optional[str] = None) -> logging.Logger:
    """Konfiguruje logger dla danego profilu (plik w folderze profilu)."""
    logger = logging.getLogger("leadgen")
    # Usuń stare handlery, żeby nie dublować
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    try:
        log_path = get_log_path(profile)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Nie można utworzyć pliku logu dla profilu %s", profile)

    return logger


# Domyślny logger (do czasu ustawienia profilu)
logger = setup_profile_logging(None)


# ------------------------------------------------------------------
# Funkcje pomocnicze (zgodność z poprzednim API)
# ------------------------------------------------------------------
def get_send_delay(host: str, custom_delay: Optional[float] = None) -> float:
    if host == SMTP_RELAY_HOST:
        return SEND_FIXED_DELAY
    if host == SMTP_FALLBACK_HOST:
        return GMAIL_FREE_SEND_DELAY
    if custom_delay is not None:
        return max(float(custom_delay), CUSTOM_SEND_DELAY_MIN)
    return CUSTOM_SEND_DELAY_DEFAULT


def get_abs_session_cap(host: str, custom_cap: Optional[int] = None) -> int:
    if host == SMTP_RELAY_HOST:
        return SESSION_CAP_ABS_MAX
    if host == SMTP_FALLBACK_HOST:
        return GMAIL_FREE_SESSION_CAP_ABS_MAX
    if custom_cap is not None:
        return min(int(custom_cap), CUSTOM_SESSION_CAP_MAX)
    return CUSTOM_SESSION_CAP_DEFAULT


# -*- coding: utf-8 -*-
"""
Menadżer profili – operacje na profilach (tworzenie, usuwanie, przełączanie)
z integracją z bazą danych i ustawieniami.
"""
import shutil
from typing import Optional, List, Dict, Any

from .config import (
    PROFILES_DIR, DEFAULT_PROFILE_NAME, get_profile_path, get_active_profile,
    set_active_profile, get_db_path, get_log_path, get_crypto_key_path,
    get_settings_path, list_profiles, profile_exists, create_profile,
    delete_profile, load_profile_settings, save_profile_settings,
    get_profile_setting, set_profile_setting, logger,
    setup_profile_logging, update_profiles_index,
)
from .database import init_db_for_profile, close_all_connections


def migrate_old_account_to_db(profile: str) -> None:
    """Migruje dane konta z pliku settings.json do bazy danych, jeśli go tam nie ma."""
    from .database import get_smtp_accounts, save_smtp_accounts

    # Pobierz stare dane z pliku
    settings = load_profile_settings(profile)
    old_user = settings.get("gmail_user")
    old_pass = settings.get("gmail_password")

    if not old_user or not old_pass:
        return

    # Sprawdź czy ten konkretny użytkownik jest już w bazie
    existing_accounts = get_smtp_accounts(profile)
    if any(a['user'].lower() == old_user.lower() for a in existing_accounts):
        return

    logger.info("Migracja brakującego konta %s do bazy danych dla profilu %s", old_user, profile)

    # Jeśli to pierwsze konto w bazie, ustaw je jako główne
    is_main = len(existing_accounts) == 0

    new_acc = {
        "user": old_user,
        "password": old_pass,
        "host": settings.get("smtp_host", "smtp.gmail.com"),
        "port": settings.get("smtp_port", 587),
        "enabled": True,
        "warmup_only": False,
        "is_main": is_main
    }

    # Pobieramy obecne konta i dodajemy nowe
    updated_list = existing_accounts + [new_acc]
    save_smtp_accounts(updated_list, profile)


def switch_profile(name: str) -> bool:
    """Przełącza aktywny profil – zamyka stare połączenia, inicjuje nowy."""
    if not profile_exists(name):
        if name == DEFAULT_PROFILE_NAME:
            create_profile(name)
        else:
            logger.error("Profil '%s' nie istnieje", name)
            return False

    close_all_connections()
    set_active_profile(name)
    init_db_for_profile(name)

    # URUCHOM MIGRACJĘ
    migrate_old_account_to_db(name)

    from .config import setup_profile_logging as setup_log
    new_logger = setup_log(name)

    new_logger.info("Przełączono na profil: %s", name)
    return True


def get_current_profile_settings() -> Dict[str, Any]:
    profile = get_active_profile()
    if not profile:
        return {}

    settings = load_profile_settings(profile)

    # Próba nadpisania głównym kontem z bazy (obsługa wielu kont)
    from .database import get_smtp_accounts
    accounts = get_smtp_accounts(profile)
    main_acc = next((a for a in accounts if a.get("is_main")), None)

    if main_acc:
        settings["gmail_user"] = main_acc["user"]
        settings["gmail_password"] = main_acc["password"]
        settings["smtp_host"] = main_acc["host"]
        settings["smtp_port"] = main_acc["port"]

    return settings


def update_current_profile_settings(settings: Dict[str, Any]) -> None:
    profile = get_active_profile()
    if not profile:
        return
    save_profile_settings(profile, settings)


def get_current_profile_name() -> Optional[str]:
    return get_active_profile()


def get_all_profiles() -> List[str]:
    return list_profiles()


COMPANY_INFO_KEYS = (
    "company_name", "company_address", "company_phone",
    "company_email", "company_website", "company_offer_description",
)


def get_company_info() -> Dict[str, str]:
    """
    Zwraca dane firmy (nazwa/adres/telefon/e-mail/strona) zapisane w ustawieniach
    aktywnego profilu - używane do podstawienia zmiennych {company_name},
    {company_address}, {company_phone}, {company_email}, {company_website}
    w szablonie wiadomości (stopka). Brakujące pola zwracane jako "".
    """
    settings = get_current_profile_settings()
    return {key: settings.get(key, "") for key in COMPANY_INFO_KEYS}


def create_new_profile(name: str, copy_from: Optional[str] = None) -> bool:
    if profile_exists(name):
        logger.warning("Profil '%s' już istnieje", name)
        return False
    if not create_profile(name, copy_from):
        return False
    return switch_profile(name)


def delete_profile_by_name(name: str) -> bool:
    if name == DEFAULT_PROFILE_NAME:
        logger.warning("Nie można usunąć domyślnego profilu")
        return False
    if not profile_exists(name):
        return False
    if get_active_profile() == name:
        switch_profile(DEFAULT_PROFILE_NAME)
    return delete_profile(name)


def copy_profile(source: str, destination: str) -> bool:
    if not profile_exists(source):
        logger.error("Profil źródłowy '%s' nie istnieje", source)
        return False
    if profile_exists(destination):
        logger.error("Profil docelowy '%s' już istnieje", destination)
        return False
    src_path = get_profile_path(source)
    dst_path = get_profile_path(destination)
    shutil.copytree(src_path, dst_path)
    update_profiles_index()
    logger.info("Skopiowano profil '%s' -> '%s'", source, destination)
    return True
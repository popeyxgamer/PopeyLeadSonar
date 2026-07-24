#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skrypt migracyjny – przenosi istniejące dane do systemu wieloprofilowego.
Tworzy profil 'default' i kopiuje do niego:
- campaign_data.db
- crypto.key
- app.log
- ustawienia z pliku (jeśli istnieją)

Uruchom raz przed pierwszym uruchomieniem nowej wersji.
"""
import os
import shutil
import json
import sys
from pathlib import Path

# Ścieżki
BASE_DIR = Path(__file__).resolve().parent
PROFILES_DIR = BASE_DIR / "profiles"
DEFAULT_PROFILE_DIR = PROFILES_DIR / "default"

# Stare pliki (w głównym katalogu)
OLD_DB = BASE_DIR / "campaign_data.db"
OLD_KEY = BASE_DIR / "crypto.key"
OLD_LOG = BASE_DIR / "app.log"
OLD_SETTINGS = BASE_DIR / "settings.json"  # opcjonalnie, jeśli istniał

# Nowe ścieżki
NEW_DB = DEFAULT_PROFILE_DIR / "campaign_data.db"
NEW_KEY = DEFAULT_PROFILE_DIR / "crypto.key"
NEW_LOG = DEFAULT_PROFILE_DIR / "app.log"
NEW_SETTINGS = DEFAULT_PROFILE_DIR / "settings.json"
NEW_INDEX = BASE_DIR / "profiles_index.json"


def migrate():
    print("🔄 Rozpoczynam migrację do systemu wieloprofilowego...")

    # 1. Utwórz folder profili
    PROFILES_DIR.mkdir(exist_ok=True)

    # 2. Utwórz folder dla domyślnego profilu
    DEFAULT_PROFILE_DIR.mkdir(exist_ok=True)

    # 3. Kopiuj bazę danych
    if OLD_DB.exists():
        print(f"   Kopiuję bazę: {OLD_DB} -> {NEW_DB}")
        shutil.copy2(OLD_DB, NEW_DB)
    else:
        print("   ⚠️ Brak pliku campaign_data.db – tworzę nową pustą bazę.")
        # Baza zostanie utworzona przy pierwszym uruchomieniu

    # 4. Kopiuj klucz szyfrowania
    if OLD_KEY.exists():
        print(f"   Kopiuję klucz: {OLD_KEY} -> {NEW_KEY}")
        shutil.copy2(OLD_KEY, NEW_KEY)

    # 5. Kopiuj log (jeśli istnieje)
    if OLD_LOG.exists():
        print(f"   Kopiuję log: {OLD_LOG} -> {NEW_LOG}")
        shutil.copy2(OLD_LOG, NEW_LOG)

    # 6. Kopiuj ustawienia (jeśli istnieją) – np. z poprzedniego systemu
    if OLD_SETTINGS.exists():
        print(f"   Kopiuję ustawienia: {OLD_SETTINGS} -> {NEW_SETTINGS}")
        shutil.copy2(OLD_SETTINGS, NEW_SETTINGS)
    else:
        # Tworzę domyślne ustawienia
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
            "mx_verify_enabled": False,
            "smime_enabled": False,
            "attachments": "",
            "account_rotation_enabled": False,
            "rotation_max_per_account": 1000,
            "imap_enabled": False,
            "imap_server": "imap.gmail.com",
            "imap_user": "",
            "imap_password": "",
        }
        with open(NEW_SETTINGS, "w", encoding="utf-8") as f:
            json.dump(default_settings, f, indent=2, ensure_ascii=False)
        print("   ✅ Utworzono domyślne ustawienia.")

    # 7. Zapisz indeks profili
    with open(NEW_INDEX, "w", encoding="utf-8") as f:
        json.dump({"profiles": ["default"], "updated": "migrated"}, f, indent=2)

    # 8. Zapisz ostatni użyty profil
    with open(BASE_DIR / "last_profile.txt", "w", encoding="utf-8") as f:
        f.write("default")

    print("✅ Migracja zakończona pomyślnie!")
    print("   Stare pliki pozostawiono (możesz je usunąć ręcznie po weryfikacji).")
    print("   Teraz możesz uruchomić aplikację w nowej wersji.")


if __name__ == "__main__":
    migrate()
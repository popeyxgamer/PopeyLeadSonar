# -*- coding: utf-8 -*-
"""
Prosty system wielojęzyczności (PL / EN / DE) dla interfejsu użytkownika.
Wczytuje tłumaczenia z plików JSON w katalogu locales/.
"""
import json
from pathlib import Path
from typing import Optional, Dict
from core.config import BASE_DIR

SUPPORTED_LANGUAGES = ["pl", "en", "de"]
LANGUAGE_NAMES = {"pl": "Polski", "en": "English", "de": "Deutsch"}
LANGUAGE_FLAGS = {"pl": "🇵🇱", "en": "🇬🇧", "de": "🇩🇪"}

_LANG_FILE = BASE_DIR / "app_language.txt"
_LOCALES_DIR = BASE_DIR / "locales"
_current_language = "pl"
_translations_cache: Dict[str, str] = {}

def get_language() -> str:
    """Zwraca kod aktualnie ustawionego języka."""
    return _current_language

def _load_translations(code: str):
    """Wczytuje plik JSON z tłumaczeniami dla danego języka."""
    global _translations_cache
    file_path = _LOCALES_DIR / f"{code}.json"
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                _translations_cache = json.load(f)
        except Exception as e:
            print(f"Error loading translation file {file_path}: {e}")
            _translations_cache = {}
    else:
        # Jeśli nie ma pliku, czyścimy cache (np. dla języka bazowego PL)
        _translations_cache = {}

def set_language(code: str, persist: bool = True) -> None:
    """Ustawia język aplikacji i ładuje odpowiednie tłumaczenia."""
    global _current_language
    if code not in SUPPORTED_LANGUAGES:
        return
    _current_language = code
    _load_translations(code)
    if persist:
        try:
            _LANG_FILE.write_text(code, encoding="utf-8")
        except OSError:
            pass

def load_language_from_disk() -> str:
    """Wczytuje preferencje języka z dysku i ładuje tłumaczenia."""
    global _current_language
    try:
        code = _LANG_FILE.read_text(encoding="utf-8").strip()
        if code in SUPPORTED_LANGUAGES:
            _current_language = code
    except (OSError, FileNotFoundError):
        pass

    _load_translations(_current_language)
    return _current_language

def restart_app() -> None:
    """Restartuje cały proces aplikacji, żeby nowy język był widoczny od razu."""
    import os
    import sys

    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.closeAllWindows()
    except Exception:
        pass

    python = sys.executable
    os.execv(python, [python] + sys.argv)

def tr(text: str) -> str:
    """Tłumaczy dany tekst na aktualny język lub zwraca oryginał."""
    if not text:
        return text
    return _translations_cache.get(text, text)

# Inicjalizacja przy pierwszym imporcie modułu
load_language_from_disk()

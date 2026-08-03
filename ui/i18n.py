# -*- coding: utf-8 -*-
"""
Prosty system wielojęzyczności (PL / EN / DE) dla interfejsu użytkownika.
Wczytuje tłumaczenia z plików JSON w katalogu locales/.
"""
import json
import sys
from pathlib import Path
from typing import Optional, Dict
from core.config import BASE_DIR

SUPPORTED_LANGUAGES = ["pl", "en", "de"]
LANGUAGE_NAMES = {"pl": "Polski", "en": "English", "de": "Deutsch"}
LANGUAGE_FLAGS = {"pl": "🇵🇱", "en": "🇬🇧", "de": "🇩🇪"}

def get_resource_path(relative_path):
    """Pobiera ścieżkę do zasobów (działa dla .py i .exe)"""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return BASE_DIR / relative_path

_LANG_FILE = BASE_DIR / "app_language.txt"
_LOCALES_DIR = get_resource_path("locales")
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
    """Bezpiecznie restartuje aplikację, działając poprawnie również w wersji EXE."""
    import os
    import sys
    import subprocess

    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.closeAllWindows()
    except Exception:
        pass

    # Pobieramy ścieżkę do wykonywalnego pliku (skryptu lub EXE)
    executable = sys.executable
    args = sys.argv[:]

    # Jeśli działamy jako EXE, sys.executable to ścieżka do naszego pliku .exe
    # Używamy Popen, aby odseparować procesy i uniknąć błędów z folderem _MEIPASS
    subprocess.Popen([executable] + args)

    # Kończymy bieżący proces
    os._exit(0)

def tr(text: str) -> str:
    """Tłumaczy dany tekst na aktualny język lub zwraca oryginał."""
    if not text:
        return text
    return _translations_cache.get(text, text)

# Inicjalizacja przy pierwszym imporcie modułu
load_language_from_disk()

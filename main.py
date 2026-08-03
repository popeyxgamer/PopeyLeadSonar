#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KOMPLETNY SYSTEM – HYBRYDOWE WYSZUKIWANIE FIRM + WYSYŁKA EMAILI
=================================================================
Punkt wejścia aplikacji.
"""
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt

# Ustaw ścieżki przed importem core
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

def get_resource_path(relative_path):
    """Pobiera ścieżkę do zasobów (działa dla .py i .exe)"""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(relative_path)

ASSETS_DIR = get_resource_path("assets")
ICON_PATH = ASSETS_DIR / "icon.ico"
SPLASH_PATH = ASSETS_DIR / "splash.png"

from core.database import init_db_for_profile
from core.profile_manager import switch_profile, get_all_profiles
from core.config import logger, get_active_profile, DEFAULT_PROFILE_NAME, PROFILES_DIR, APP_DATA_DIR
from ui.i18n import load_language_from_disk
from ui.main_window import MainWindow


def main() -> int:
    # Utwórz folder danych i profili
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(exist_ok=True)

    # Sprawdź, czy istnieje profil "default" – jeśli nie, utwórz
    if "default" not in get_all_profiles():
        from core.profile_manager import create_new_profile
        create_new_profile("default")

    # Przełącz na ostatni profil (lub default)
    last_profile = None
    try:
        with open(APP_DATA_DIR / "last_profile.txt", "r", encoding="utf-8") as f:
            last_profile = f.read().strip()
    except (OSError, FileNotFoundError):
        pass

    if not last_profile or last_profile not in get_all_profiles():
        last_profile = "default"
        logger.warning("Profil '%s' nie znaleziony, używam domyślnego", last_profile or "")

    switch_profile(last_profile)

    # Wczytaj zapisany wcześniej język interfejsu (globalny, niezależny od profilu)
    load_language_from_disk()

    app = QApplication(sys.argv)
    app.setApplicationName("PopeyLeadSonar")
    app.setApplicationDisplayName("PopeyLeadSonar")

    # Ikona aplikacji (taskbar, pasek tytułu, plik .exe po spakowaniu)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    # Splash screen z logo PopeyLeadSonar przy starcie
    splash = None
    if SPLASH_PATH.exists():
        pixmap = QPixmap(str(SPLASH_PATH))
        pixmap = pixmap.scaledToWidth(420, Qt.SmoothTransformation)
        splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
        splash.setWindowFlag(Qt.FramelessWindowHint)
        splash.show()
        app.processEvents()

    window = MainWindow()
    if ICON_PATH.exists():
        window.setWindowIcon(QIcon(str(ICON_PATH)))

    if splash is not None:
        splash.finish(window)

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
# -*- coding: utf-8 -*-
"""
Magistrala sygnałów (Signal Bus) - centralny punkt komunikacji między
modułami aplikacji (Core <-> UI). Pozwala na reaktywne odświeżanie
interfejsu bez bezpośrednich zależności między widokami.
"""
from PySide6.QtCore import QObject, Signal

class SignalBus(QObject):
    """Globalna magistrala sygnałów."""

    # --- Zdarzenia bazy danych ---
    lead_added = Signal(dict)       # Nowy lead dodany do bazy
    leads_changed = Signal()        # Zmiana w bazie leadów (import/usuwanie)

    # --- Zdarzenia wysyłki ---
    email_sent = Signal(dict)       # Mail wysłany pomyślnie
    email_error = Signal(str, str)  # Błąd wysyłki (email, błąd)

    # --- Zdarzenia kampanii ---
    search_started = Signal()
    search_finished = Signal(int)   # Liczba znalezionych

    # Autopilot / AI Auto Send counters
    # (found, sent, errors) lub (processed, sent, skipped, errors)
    autopilot_counters = Signal(int, int, int)
    ai_auto_counters = Signal(int, int, int, int)

    # --- Zdarzenia systemowe ---
    profile_changed = Signal(str)   # Nazwa nowego profilu (globalny)
    internal_profile_loaded = Signal(dict) # Dane profilu kampanii
    settings_saved = Signal()       # Ustawienia zapisane
    language_changed = Signal(str)  # Kod języka

    # --- Powiadomienia UI ---
    show_message = Signal(str, str) # title, message (Toast)

# Singleton magistrali
bus = SignalBus()

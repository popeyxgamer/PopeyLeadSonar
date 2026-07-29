# -*- coding: utf-8 -*-
"""Zmodernizowane główne okno aplikacji PopeyLeadSonar v2.0"""
import os
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QMessageBox, QToolBar, QComboBox, QLabel, QPushButton, QInputDialog, QSizePolicy
)

from core import database as db
from core.signal_bus import bus
from core.profile_manager import (
    get_all_profiles, get_current_profile_name, switch_profile,
    create_new_profile, delete_profile_by_name, copy_profile, get_profile_path,
    get_current_profile_settings
)
from ui.sidebar import Sidebar
from ui.widgets.animated_stack import AnimatedStackedWidget
from ui.views.dashboard_view import DashboardView
from ui.views.leads_view import LeadsView
from ui.views.campaign_view import CampaignView
from ui.views.sequences_view import SequencesView
from ui.views.warmup_view import WarmupView
from ui.views.sending_view import SendingView
from ui.views.inbox_view import InboxView
from ui.views.history_view import HistoryView
from ui.views.ai_lab_view import AILabView
from ui.views.settings_view import SettingsView
from ui.styles import DARK_STYLESHEET, DEFAULT_PROFILE_NAME, COLOR_BG, COLOR_BORDER, COLOR_ACCENT, COLOR_ERROR, COLOR_SECONDARY
from ui.i18n import tr
from core.config import logger
from core.workers import SequenceWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PopeyLeadSonar v2.0')
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(DARK_STYLESHEET)

        self.seq_worker = None

        # 1. Główny układ
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 2. Pasek boczny
        self.sidebar = Sidebar(self)
        self.main_layout.addWidget(self.sidebar)

        # 3. Kontener na widoki
        self.content_stack = AnimatedStackedWidget()
        self.main_layout.addWidget(self.content_stack, stretch=1)

        # Inicjalizacja wszystkich widoków
        self.views = {
            0: DashboardView(),
            1: CampaignView(),
            2: SequencesView(),
            3: WarmupView(),
            4: SendingView(),
            5: LeadsView(),
            6: InboxView(),
            7: HistoryView(),
            8: AILabView(),
            9: SettingsView()
        }

        for idx in sorted(self.views.keys()):
            self.content_stack.addWidget(self.views[idx])

        # Nawigacja
        self.sidebar.indexChanged.connect(self.content_stack.setCurrentIndex)

        # Profile i Toolbar
        self._create_toolbar()
        self._setup_bus_connections()

        # Inicjalizacja
        active = self._refresh_profile_list()
        self._refresh_account_list()

        if active:
            # Wymuszamy odświeżenie wszystkich widoków informacją o aktualnym profilu
            QTimer.singleShot(100, lambda: bus.profile_changed.emit(active))

        # Wymuszenie odświeżenia Dashboardu na starcie
        QTimer.singleShot(500, lambda: self.content_stack.setCurrentIndex(0))
        QTimer.singleShot(600, lambda: self.views[0].refresh_stats())

    def _setup_bus_connections(self):
        bus.profile_changed.connect(self._on_profile_changed)
        bus.profile_changed.connect(self._refresh_account_list)
        bus.show_message.connect(self._show_toast)

        # Inicjalizacja workera sekwencji dla domyślnego profilu
        self._restart_sequence_worker()

    def _restart_sequence_worker(self):
        if self.seq_worker:
            self.seq_worker.stop()
            self.seq_worker.wait()

        s = get_current_profile_settings()
        if s.get("gmail_user") and s.get("gmail_password"):
            self.seq_worker = SequenceWorker(
                s["gmail_user"], s["gmail_password"],
                s.get("smtp_host", "smtp.gmail.com"), s.get("smtp_port", 587)
            )
            self.seq_worker.status.connect(lambda msg: self.statusBar().showMessage(msg, 3000))
            self.seq_worker.start()
            logger.info("SequenceWorker started for %s", s["gmail_user"])

    def _show_toast(self, title, message):
        self.statusBar().showMessage(f"[{title}] {message}", 6000)

    def _create_toolbar(self):
        toolbar = QToolBar("Profile")
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"QToolBar {{ background-color: {COLOR_BG}; border-bottom: 1px solid {COLOR_BORDER}; padding: 5px; }}")
        self.addToolBar(toolbar)

        # Sekcja Profilu
        label = QLabel(tr('  📁 Profil:  '))
        label.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: bold;")
        toolbar.addWidget(label)

        self.profile_selector = QComboBox()
        self.profile_selector.setMinimumWidth(200)
        self.profile_selector.currentTextChanged.connect(self._on_profile_selector_changed)
        toolbar.addWidget(self.profile_selector)

        toolbar.addSeparator()

        # Sekcja Konta
        label_acc = QLabel(tr('  📧 Konto:  '))
        label_acc.setStyleSheet(f"color: {COLOR_SECONDARY}; font-weight: bold;")
        toolbar.addWidget(label_acc)

        self.account_selector = QComboBox()
        self.account_selector.setMinimumWidth(250)
        self.account_selector.currentIndexChanged.connect(self._on_account_selector_changed)
        toolbar.addWidget(self.account_selector)

        toolbar.addSeparator()

        btn_new = QPushButton(tr('  ➕ Nowy  '))
        btn_new.clicked.connect(self._create_new_profile_dialog)
        toolbar.addWidget(btn_new)

        btn_copy = QPushButton(tr('  📋 Kopiuj  '))
        btn_copy.clicked.connect(self._copy_current_profile)
        toolbar.addWidget(btn_copy)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        btn_delete = QPushButton(tr('  🗑 Usuń Profil  '))
        btn_delete.setObjectName("danger")
        btn_delete.setStyleSheet(f"QPushButton#danger {{ background-color: transparent; color: {COLOR_ERROR}; border: 1px solid {COLOR_ERROR}; }} QPushButton#danger:hover {{ background-color: {COLOR_ERROR}; color: white; }}")
        btn_delete.clicked.connect(self._delete_current_profile)
        toolbar.addWidget(btn_delete)

    def _refresh_profile_list(self):
        profiles = get_all_profiles()
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        self.profile_selector.addItems(profiles)
        active = get_current_profile_name()
        if active:
            self.profile_selector.setCurrentText(active)
            self.sidebar.set_active_profile(active)
        self.profile_selector.blockSignals(False)
        return active

    def _refresh_account_list(self, _profile_name=None):
        """Odświeża listę kont w toolbarze."""
        self.account_selector.blockSignals(True)
        self.account_selector.clear()

        accounts = db.get_smtp_accounts()
        if not accounts:
            self.account_selector.addItem(tr("-- Brak kont SMTP --"), None)
        else:
            main_idx = 0
            for i, acc in enumerate(accounts):
                text = acc["user"]
                if acc.get("warmup_only"): text += f" [{tr('Tylko do rozgrzewania')}]"
                if not acc.get("enabled", True): text += f" [{tr('WYŁĄCZONE')}]"

                self.account_selector.addItem(text, acc["user"])
                if acc.get("is_main"): main_idx = i

            self.account_selector.setCurrentIndex(main_idx)

        self.account_selector.blockSignals(False)

    def _on_account_selector_changed(self, index):
        email = self.account_selector.currentData()
        if not email: return

        if db.set_main_account(email):
            logger.info("MainWindow: Zmieniono główne konto na %s", email)
            # Powiadamiamy wszystkie widoki, że "ustawienia profilu" (czyli też konto) się zmieniły
            bus.profile_changed.emit(get_current_profile_name())

    def _on_profile_selector_changed(self, name):
        if not name or name == get_current_profile_name(): return

        # Zatrzymujemy aktywne procesy przy zmianie profilu
        self._stop_all_workers()

        if switch_profile(name):
            logger.info("MainWindow: Przełączono profil na %s", name)
            self.sidebar.set_active_profile(name)
            bus.profile_changed.emit(name) # To wyzwoli load_settings we wszystkich widokach

    def _stop_all_workers(self, wait=False):
        """Zatrzymuje wszystkich workerów we wszystkich widokach."""
        for view in self.views.values():
            for attr in ['worker', 'search_worker', 'send_worker', 'body_worker', 'action_worker', 'batch_worker']:
                if hasattr(view, attr):
                    w = getattr(view, attr)
                    if w and w.isRunning():
                        w.stop()
                        if wait:
                            w.wait(2000) # Czekaj maks 2 sekundy

        if self.seq_worker and self.seq_worker.isRunning():
            self.seq_worker.stop()
            if wait:
                self.seq_worker.wait(2000)

    def closeEvent(self, event):
        """Obsługa zamykania aplikacji - upewniamy się, że wątki kończą pracę."""
        self.statusBar().showMessage(tr("Zamykanie aplikacji..."), 5000)
        self._stop_all_workers(wait=True)
        db.close_all_connections()
        event.accept()

    def _on_profile_changed(self, name):
        self.setWindowTitle(f"PopeyLeadSonar v2.0 – 🎯 {name}")
        self._restart_sequence_worker()

    def _create_new_profile_dialog(self):
        name, ok = QInputDialog.getText(self, tr('Nowy profil'), tr('Podaj nazwę profilu:'))
        if ok and name.strip():
            if create_new_profile(name.strip()):
                self._refresh_profile_list()

    def _copy_current_profile(self):
        curr = get_current_profile_name()
        name, ok = QInputDialog.getText(self, tr('Kopiuj profil'), tr('Nowa nazwa:'))
        if ok and name.strip():
            if copy_profile(curr, name.strip()):
                self._refresh_profile_list()

    def _delete_current_profile(self):
        current = get_current_profile_name()
        if current == DEFAULT_PROFILE_NAME:
            QMessageBox.warning(self, tr('Błąd'), tr('Nie można usunąć domyślnego profilu.'))
            return

        if QMessageBox.question(self, tr('Potwierdzenie'), tr("Usuwamy profile '{}'?").format(current)) == QMessageBox.Yes:
            if delete_profile_by_name(current):
                self._refresh_profile_list()

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
    create_new_profile, delete_profile_by_name, copy_profile, get_profile_path
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
from ui.styles import DARK_STYLESHEET, DEFAULT_PROFILE_NAME, COLOR_BG, COLOR_BORDER, COLOR_ACCENT, COLOR_ERROR
from ui.i18n import tr
from core.config import logger, get_current_profile_settings
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
        self._refresh_profile_list()

        # Wymuszenie odświeżenia Dashboardu na starcie
        QTimer.singleShot(500, lambda: self.content_stack.setCurrentIndex(0))
        QTimer.singleShot(600, lambda: self.views[0].refresh_stats())

    def _setup_bus_connections(self):
        bus.profile_changed.connect(self._on_profile_changed)
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

        label = QLabel(tr('  📁 Profil:  '))
        label.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: bold;")
        toolbar.addWidget(label)

        self.profile_selector = QComboBox()
        self.profile_selector.setMinimumWidth(220)
        self.profile_selector.currentTextChanged.connect(self._on_profile_selector_changed)
        toolbar.addWidget(self.profile_selector)

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

    def _on_profile_selector_changed(self, name):
        if not name or name == get_current_profile_name(): return

        # Zatrzymujemy aktywne procesy przy zmianie profilu
        self._stop_all_workers()

        if switch_profile(name):
            logger.info("MainWindow: Przełączono profil na %s", name)
            self.sidebar.set_active_profile(name)
            bus.profile_changed.emit(name) # To wyzwoli load_settings we wszystkich widokach

    def _stop_all_workers(self):
        """Zatrzymuje wszystkich workerów we wszystkich widokach."""
        for view in self.views.values():
            if hasattr(view, 'worker') and view.worker: view.worker.stop()
            if hasattr(view, 'search_worker') and view.search_worker: view.search_worker.stop()
            if hasattr(view, 'send_worker') and view.send_worker: view.send_worker.stop()

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

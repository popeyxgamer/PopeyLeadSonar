# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QProgressBar, QListWidget, QGroupBox, QSpinBox,
    QCheckBox, QMessageBox, QScrollArea, QListWidgetItem, QWidget, QComboBox, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from ui.views.base_view import BaseView
from ui.i18n import tr
from ui.styles import COLOR_SENT_LIST_ALT, DEFAULT_QUERIES, DEFAULT_LOCATIONS
from core import database as db
from core.workers import SearchWorker, AutoPilotWorker
from core.profile_manager import (
    get_current_profile_settings, update_current_profile_settings, get_company_info
)
from core.email_sender import test_gmail_connection
from core.config import (
    logger, SMTP_RELAY_HOST, SMTP_RELAY_PORT, SESSION_HARD_CAP,
    CUSTOM_SEND_DELAY_DEFAULT, CUSTOM_SESSION_CAP_DEFAULT
)
from core.signal_bus import bus
from core.account_rotator import SMTPAccountRotator

class CampaignView(BaseView):
    def setup_ui(self):
        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setStyleSheet("border: none; background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)

        header = QLabel(tr("Kampania i Wyszukiwanie"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        layout.addWidget(header)

        # 1. Profile Kampanii (wewnętrzne)
        prof_group = QGroupBox(tr("👤 Profile kampanii (kategorie + lokalizacje)"))
        prof_lay = QHBoxLayout(prof_group)
        self.prof_combo = QComboBox()
        self.prof_combo.setMinimumWidth(200)
        prof_lay.addWidget(self.prof_combo, stretch=1)

        btn_load = QPushButton(tr("📂 Wczytaj"))
        btn_load.clicked.connect(self._load_internal_profile)
        prof_lay.addWidget(btn_load)

        btn_overwrite = QPushButton(tr("💾 Nadpisz"))
        btn_overwrite.clicked.connect(self._overwrite_internal_profile)
        prof_lay.addWidget(btn_overwrite)

        btn_save = QPushButton(tr("💾 Zapisz jako..."))
        btn_save.clicked.connect(self._save_internal_profile)
        prof_lay.addWidget(btn_save)

        btn_del = QPushButton(tr("🗑 Usuń"))
        btn_del.clicked.connect(self._delete_internal_profile)
        prof_lay.addWidget(btn_del)
        layout.addWidget(prof_group)

        # 2. Parametry wyszukiwania
        search_group = QGroupBox(tr("🔍 Parametry wyszukiwania"))
        search_layout = QVBoxLayout(search_group)

        search_layout.addWidget(QLabel(tr('Branże / Kategorie (jedna na linię):')))
        self.queries_edit = QTextEdit()
        self.queries_edit.setMaximumHeight(100)
        self.queries_edit.setPlainText(DEFAULT_QUERIES)
        search_layout.addWidget(self.queries_edit)

        search_layout.addWidget(QLabel(tr('Lokalizacje (jedna na linię):')))
        self.locations_edit = QTextEdit()
        self.locations_edit.setMaximumHeight(100)
        self.locations_edit.setPlainText(DEFAULT_LOCATIONS)
        search_layout.addWidget(self.locations_edit)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Limit:')))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(3, 100); self.limit_spin.setValue(15)
        row.addWidget(self.limit_spin)

        row.addWidget(QLabel(tr('Czas (min):')))
        self.czas_spin = QSpinBox()
        self.czas_spin.setRange(0, 300); self.czas_spin.setValue(60)
        row.addWidget(self.czas_spin)

        self.force_research_check = QCheckBox(tr('Nowa sesja'))
        row.addWidget(self.force_research_check)

        self.ai_scoring_check = QCheckBox(tr('🤖 AI Lead Scoring'))
        row.addWidget(self.ai_scoring_check)
        row.addStretch()
        search_layout.addLayout(row)
        layout.addWidget(search_group)

        # 3. Akcje
        btn_row = QHBoxLayout()
        self.search_btn = QPushButton(tr('🔍 ROZPOCZNIJ SZUKANIE'))
        self.search_btn.setStyleSheet("background: #2b5e2b; font-weight: bold; padding: 12px;")
        self.search_btn.clicked.connect(self.start_search)
        btn_row.addWidget(self.search_btn)

        self.autopilot_btn = QPushButton(tr('🤖 AUTOPILOT (Szukaj + Wysyłaj)'))
        self.autopilot_btn.setStyleSheet("background: #5e2b8b; font-weight: bold; padding: 12px;")
        self.autopilot_btn.clicked.connect(self.start_autopilot)
        btn_row.addWidget(self.autopilot_btn)

        self.stop_btn = QPushButton(tr('⏹️ STOP'))
        self.stop_btn.setStyleSheet("background: #8b0000; font-weight: bold;")
        self.stop_btn.clicked.connect(self.stop_worker)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

        # 4. Status i Postęp
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        status_row = QHBoxLayout()
        self.status_label = QLabel(tr('Gotowy'))
        status_row.addWidget(self.status_label, stretch=1)

        self.counters_label = QLabel(tr('Znaleziono: 0 | Wysłano: 0'))
        self.counters_label.setStyleSheet("font-weight: bold; color: #a6e3a1;")
        status_row.addWidget(self.counters_label)
        layout.addLayout(status_row)

        # 5. Podgląd wyników
        layout.addWidget(QLabel(tr('📋 Firmy znalezione w bieżącej sesji:')))
        self.results_list = QListWidget()
        layout.addWidget(self.results_list)

        container.setWidget(content)
        self.layout.addWidget(container)

        self.worker = None
        self.found_leads = []
        self._refresh_internal_profiles()

    def setup_signals(self):
        bus.profile_changed.connect(self._on_profile_changed)

    def _on_profile_changed(self, name):
        self._refresh_internal_profiles()

        # Load last internal profile
        last_int = db.get_setting("last_profile", "")
        if last_int and last_int in db.get_profile_names():
            self.prof_combo.setCurrentText(last_int)
            self._load_internal_profile(silent=True)

        self.results_list.clear()
        self.found_leads = []
        self.counters_label.setText(tr('Znaleziono: 0 | Wysłano: 0'))
        self.status_label.setText(tr("Gotowy (Profil: {})").format(name))

    def _refresh_internal_profiles(self):
        self.prof_combo.clear()
        self.prof_combo.addItems(db.get_profile_names())

    def _load_internal_profile(self, silent=False):
        name = self.prof_combo.currentText()
        if not name: return
        p = db.get_profile(name)
        if p:
            self.queries_edit.setPlainText(p.get("queries", ""))
            self.locations_edit.setPlainText(p.get("locations", ""))
            db.set_setting("last_profile", name)
            bus.internal_profile_loaded.emit(p)
            if not silent: bus.show_message.emit("Kampania", tr("Wczytano profil: {}").format(name))

    def _save_internal_profile(self):
        name, ok = QInputDialog.getText(self, tr("Zapisz profil"), tr("Nazwa profilu:"))
        if ok and name:
            db.save_profile(name, self.queries_edit.toPlainText(), self.locations_edit.toPlainText(), "", "")
            self._refresh_internal_profiles()
            self.prof_combo.setCurrentText(name)
            db.set_setting("last_profile", name)

    def _overwrite_internal_profile(self):
        name = self.prof_combo.currentText()
        if not name: return
        if QMessageBox.question(self, tr("Nadpisz"), tr("Nadpisać profil '{}'?").format(name)) == QMessageBox.Yes:
            db.save_profile(name, self.queries_edit.toPlainText(), self.locations_edit.toPlainText(), "", "")
            bus.show_message.emit("Kampania", tr("Profil zaktualizowany"))

    def _delete_internal_profile(self):
        name = self.prof_combo.currentText()
        if not name: return
        if QMessageBox.question(self, tr("Usuń"), tr("Usunąć profil '{}'?").format(name)) == QMessageBox.Yes:
            db.delete_profile_from_db(name)
            self._refresh_internal_profiles()

    def start_search(self):
        q, l = self._get_params()
        if not q or not l: return

        settings = get_current_profile_settings()
        proxies = []
        if settings.get("proxy_enabled"):
            raw = settings.get("proxy_list", "")
            proxies = [p.strip() for p in raw.splitlines() if p.strip()]

        self._prep_ui()
        self.worker = SearchWorker(
            q, l, self.limit_spin.value(), self.czas_spin.value(), proxies,
            ai_scoring=self.ai_scoring_check.isChecked(),
            force_research=self.force_research_check.isChecked()
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.live_result.connect(self.on_live_result)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def start_autopilot(self):
        q, l = self._get_params()
        if not q or not l: return

        settings = get_current_profile_settings()
        user, pwd = settings.get("gmail_user"), settings.get("gmail_password")
        if not user or not pwd:
            QMessageBox.warning(self, tr("Błąd"), tr("Skonfiguruj SMTP w Ustawieniach!")); return

        proxies = []
        if settings.get("proxy_enabled"):
            raw = settings.get("proxy_list", "")
            proxies = [p.strip() for p in raw.splitlines() if p.strip()]

        self._prep_ui()

        # Setup rotator if enabled
        rotator = None
        if settings.get("account_rotation_enabled"):
            accs = db.get_smtp_accounts()
            if accs: rotator = SMTPAccountRotator(accs)

        self.worker = AutoPilotWorker(
            q, l, self.limit_spin.value(),
            settings.get("last_template", ""), settings.get("last_subject", ""),
            user, pwd, settings.get("smtp_host", SMTP_RELAY_HOST), settings.get("smtp_port", 587),
            settings.get("dzienny_limit", SESSION_HARD_CAP),
            html=settings.get("html_enabled", False),
            verify_mx=settings.get("mx_verify_enabled", False),
            smime_sign=settings.get("smime_enabled", False),
            rotator=rotator, use_account_rotation=(rotator is not None),
            proxies=proxies
        )
        self.worker.status.connect(self.status_label.setText)
        self.worker.counters.connect(lambda f, s, e: self.counters_label.setText(f"Znaleziono: {f} | Wysłano: {s} | Błędy: {e}"))
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def _get_params(self):
        q = [x.strip() for x in self.queries_edit.toPlainText().splitlines() if x.strip()]
        l = [x.strip() for x in self.locations_edit.toPlainText().splitlines() if x.strip()]
        if not q or not l: bus.show_message.emit("Błąd", tr("Wpisz kategorie i miasta!")); return None, None
        return q, l

    def _prep_ui(self):
        self.search_btn.setEnabled(False)
        self.autopilot_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.results_list.clear()
        self.found_leads = []

    def stop_worker(self):
        if self.worker: self.worker.stop()

    def on_live_result(self, lead):
        self.found_leads.append(lead)
        self.counters_label.setText(f"Znaleziono: {len(self.found_leads)}")
        self.results_list.addItem(f"{lead.get('name')} | {lead.get('email')}")

        # Auto save to db
        db.add_lead(
            lead.get('name', ''), lead.get('email', ''), lead.get('address', ''),
            '', lead.get('website', ''), lead.get('category', ''),
            linkedin=lead.get('linkedin', '')
        )
        bus.leads_changed.emit()

    def on_finished(self):
        self.search_btn.setEnabled(True)
        self.autopilot_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        bus.show_message.emit("Kampania", tr("Zadanie zakończone!"))

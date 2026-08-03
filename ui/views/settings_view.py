# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QGroupBox, QPushButton,
    QMessageBox, QScrollArea, QCheckBox, QSpinBox, QWidget, QLabel,
    QTabWidget, QComboBox, QDoubleSpinBox, QListWidget, QFileDialog, QTextEdit, QListWidgetItem
)
from PySide6.QtCore import Qt
from ui.views.base_view import BaseView
from ui.i18n import tr, SUPPORTED_LANGUAGES, LANGUAGE_NAMES, LANGUAGE_FLAGS, get_language, set_language, restart_app
from core.profile_manager import (
    get_current_profile_settings, update_current_profile_settings, get_company_info
)
from core.email_sender import test_gmail_connection
from core.config import (
    SMTP_RELAY_HOST, SMTP_RELAY_PORT, SMTP_FALLBACK_HOST, SMTP_FALLBACK_PORT,
    CUSTOM_SEND_DELAY_DEFAULT, CUSTOM_SEND_DELAY_MIN, CUSTOM_SESSION_CAP_DEFAULT,
    CUSTOM_SESSION_CAP_MAX, GMAIL_FREE_SESSION_CAP_DEFAULT, GMAIL_FREE_SESSION_CAP_OPTIONS,
    SESSION_CAP_OPTIONS, SESSION_HARD_CAP, get_send_delay, guess_smtp, VERSION
)
from core.updater import check_for_updates
from core.signal_bus import bus
from core import database as db
from core.bounce_imap import BounceMonitor
from core.blacklist_import import import_blacklist_from_file

class SettingsView(BaseView):
    def setup_ui(self):
        header = QLabel(tr("Konfiguracja Systemu"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        self.layout.addWidget(header)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # 1. Podstawowe
        self.basic_tab = QWidget()
        self._setup_basic_tab()
        self.tabs.addTab(self.basic_tab, tr("🟢 Podstawowe"))

        # 2. Zaawansowane
        self.adv_tab = QWidget()
        self._setup_adv_tab()
        self.tabs.addTab(self.adv_tab, tr("⚙️ Zaawansowane"))

        # 3. Blacklist
        self.bl_tab = QWidget()
        self._setup_bl_tab()
        self.tabs.addTab(self.bl_tab, tr("🚫 Blacklist"))

        # 4. Aktualizacje
        self.update_tab = QWidget()
        self._setup_update_tab()
        self.tabs.addTab(self.update_tab, tr("🚀 Aktualizacje"))

        # Save & Test row
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton(tr("💾 ZAPISZ WSZYSTKIE USTAWIENIA"))
        self.btn_save.setStyleSheet("background: #4a9eff; font-weight: bold; padding: 12px;")
        self.btn_save.clicked.connect(self.save_settings)
        btn_row.addWidget(self.btn_save, stretch=2)

        self.btn_test = QPushButton(tr("🔍 Testuj SMTP"))
        self.btn_test.clicked.connect(self.test_connection)
        btn_row.addWidget(self.btn_test, stretch=1)

        self.layout.addLayout(btn_row)

        self.bounce_monitor = None
        self.accounts_data = []
        self.load_settings()

    def _setup_basic_tab(self):
        lay = QVBoxLayout(self.basic_tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QVBoxLayout(content)

        # Language
        lang_group = QGroupBox(tr("🌐 Język aplikacji"))
        lang_form = QHBoxLayout(lang_group)
        self.language_combo = QComboBox()
        for code in SUPPORTED_LANGUAGES:
            self.language_combo.addItem(f"{LANGUAGE_FLAGS[code]} {LANGUAGE_NAMES[code]}", code)
        lang_form.addWidget(QLabel(tr("Język interfejsu:")))
        lang_form.addWidget(self.language_combo)
        lang_form.addStretch()
        form.addWidget(lang_group)

        # Gmail (Teraz jako wybór z listy)
        gmail_group = QGroupBox(tr("🔐 Aktywne konto wysyłkowe"))
        gmail_form = QFormLayout(gmail_group)

        self.active_account_combo = QComboBox()
        self.active_account_combo.currentIndexChanged.connect(self._on_active_account_selection_changed)
        gmail_form.addRow(tr('Wybierz konto:'), self.active_account_combo)

        self.gmail_user = QLineEdit()
        self.gmail_user.setReadOnly(True)
        self.gmail_user.setStyleSheet("background-color: #242437; color: #888;")
        gmail_form.addRow(tr('Adres Gmail:'), self.gmail_user)

        self.gmail_pass = QLineEdit()
        self.gmail_pass.setReadOnly(True)
        self.gmail_pass.setEchoMode(QLineEdit.Password)
        self.gmail_pass.setStyleSheet("background-color: #242437; color: #888;")
        gmail_form.addRow(tr('Hasło aplikacji:'), self.gmail_pass)

        hint_acc = QLabel(tr("ℹ️ Kontami zarządzasz w zakładce 'Zaawansowane'."))
        hint_acc.setStyleSheet("color: #888; font-size: 11px;")
        gmail_form.addRow(hint_acc)

        form.addWidget(gmail_group)

        # Company
        company_group = QGroupBox(tr("🏢 Dane firmy (do stopki)"))
        company_form = QFormLayout(company_group)
        self.company_name = QLineEdit()
        company_form.addRow(tr('Nazwa firmy:'), self.company_name)
        self.company_address = QLineEdit()
        company_form.addRow(tr('Adres:'), self.company_address)
        self.company_phone = QLineEdit()
        company_form.addRow(tr('Telefon:'), self.company_phone)
        self.company_email = QLineEdit()
        company_form.addRow(tr('E-mail firmy:'), self.company_email)
        self.company_website = QLineEdit()
        company_form.addRow(tr('Strona WWW:'), self.company_website)
        self.company_offer = QLineEdit()
        company_form.addRow(tr('Czym się zajmujemy (AI):'), self.company_offer)
        form.addWidget(company_group)

        # Limits
        limit_group = QGroupBox(tr("📊 Limity wysyłki"))
        limit_form = QFormLayout(limit_group)
        self.dzienny_limit = QComboBox()
        limit_form.addRow(tr('Limit sesji:'), self.dzienny_limit)
        self.limit_pace_hint = QLabel()
        self.limit_pace_hint.setStyleSheet("color: #888; font-size: 11px;")
        limit_form.addRow(self.limit_pace_hint)
        form.addWidget(limit_group)

        form.addStretch()
        scroll.setWidget(content)
        lay.addWidget(scroll)

    def _setup_adv_tab(self):
        lay = QVBoxLayout(self.adv_tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QVBoxLayout(content)

        # SMTP Server
        smtp_group = QGroupBox(tr("🌐 Serwer SMTP"))
        smtp_form = QFormLayout(smtp_group)
        self.smtp_mode = QComboBox()
        self.smtp_mode.addItems(["Google Workspace Relay", "Zwykły Gmail", "Inny dostawca"])
        self.smtp_mode.currentIndexChanged.connect(self._apply_smtp_mode)
        smtp_form.addRow(tr('Tryb:'), self.smtp_mode)
        self.smtp_host = QLineEdit()
        smtp_form.addRow(tr('Host:'), self.smtp_host)
        self.smtp_port = QLineEdit()
        smtp_form.addRow(tr('Port:'), self.smtp_port)

        self.custom_delay_spin = QDoubleSpinBox()
        self.custom_delay_spin.setRange(CUSTOM_SEND_DELAY_MIN, 30.0)
        self.custom_delay_spin.setSuffix(" s/msg")
        smtp_form.addRow(tr('Własne tempo:'), self.custom_delay_spin)

        self.custom_cap_spin = QSpinBox()
        self.custom_cap_spin.setRange(10, CUSTOM_SESSION_CAP_MAX)
        smtp_form.addRow(tr('Własny limit:'), self.custom_cap_spin)
        form.addWidget(smtp_group)

        # Rotation
        rot_group = QGroupBox(tr("🔄 Rotacja kont SMTP"))
        rot_lay = QVBoxLayout(rot_group)
        self.rotation_enabled = QCheckBox(tr("Włącz rotację kont"))
        rot_lay.addWidget(self.rotation_enabled)

        self.accounts_list = QListWidget()
        self.accounts_list.setMaximumHeight(100)
        rot_lay.addWidget(self.accounts_list)

        btn_rot_row = QHBoxLayout()
        self.btn_add_acc = QPushButton(tr("➕ Dodaj konto"))
        self.btn_add_acc.clicked.connect(self._show_add_account_dialog)
        btn_rot_row.addWidget(self.btn_add_acc)

        self.btn_toggle_acc = QPushButton(tr("Włącz/Wyłącz zaznaczone"))
        self.btn_toggle_acc.clicked.connect(self._toggle_account)
        btn_rot_row.addWidget(self.btn_toggle_acc)

        self.btn_del_acc = QPushButton(tr("🗑 Usuń zaznaczone"))
        self.btn_del_acc.clicked.connect(self._remove_account)
        btn_rot_row.addWidget(self.btn_del_acc)
        rot_lay.addLayout(btn_rot_row)
        form.addWidget(rot_group)

        # IMAP
        imap_group = QGroupBox(tr("📨 Monitorowanie zwrotów (IMAP)"))
        imap_form = QFormLayout(imap_group)
        self.imap_enabled = QCheckBox(tr("Włącz monitorowanie"))
        imap_form.addRow(self.imap_enabled)
        self.imap_server = QLineEdit()
        imap_form.addRow(tr("Serwer IMAP:"), self.imap_server)
        self.imap_user = QLineEdit()
        imap_form.addRow(tr("Użytkownik:"), self.imap_user)
        self.imap_pass = QLineEdit()
        self.imap_pass.setEchoMode(QLineEdit.Password)
        imap_form.addRow(tr("Hasło IMAP:"), self.imap_pass)
        form.addWidget(imap_group)

        # S/MIME
        smime_group = QGroupBox(tr("🔏 S/MIME (podpis cyfrowy)"))
        smime_lay = QVBoxLayout(smime_group)
        self.smime_enabled = QCheckBox(tr("Włącz podpisywanie S/MIME"))
        smime_lay.addWidget(self.smime_enabled)
        self.btn_gen_smime = QPushButton(tr("🔄 Wygeneruj nowy certyfikat"))
        self.btn_gen_smime.clicked.connect(self._generate_smime)
        smime_lay.addWidget(self.btn_gen_smime)
        form.addWidget(smime_group)

        # Proxy
        proxy_group = QGroupBox(tr("🌐 Proxy (wyszukiwanie)"))
        proxy_lay = QVBoxLayout(proxy_group)
        self.proxy_enabled = QCheckBox(tr("Włącz proxy"))
        proxy_lay.addWidget(self.proxy_enabled)
        self.proxy_list = QTextEdit()
        self.proxy_list.setMaximumHeight(80)
        self.proxy_list.setPlaceholderText("http://user:pass@host:port")
        proxy_lay.addWidget(self.proxy_list)
        form.addWidget(proxy_group)

        form.addStretch()
        scroll.setWidget(content)
        lay.addWidget(scroll)

    def _setup_update_tab(self):
        lay = QVBoxLayout(self.update_tab)

        group = QGroupBox(tr("Informacje o wersji"))
        form = QFormLayout(group)

        ver_label = QLabel(f"<b>{VERSION}</b>")
        ver_label.setStyleSheet("font-size: 16px; color: #4a9eff;")
        form.addRow(tr("Aktualna wersja:"), ver_label)

        status_label = QLabel(tr("Aplikacja jest aktualna."))
        status_label.setStyleSheet("color: #888;")
        form.addRow(tr("Status:"), status_label)

        lay.addWidget(group)

        self.btn_check_update = QPushButton(tr("🔄 Sprawdź dostępność aktualizacji"))
        self.btn_check_update.setStyleSheet("padding: 10px; font-weight: bold;")
        self.btn_check_update.clicked.connect(lambda: check_for_updates(self, silent=False))
        lay.addWidget(self.btn_check_update)

        hint = QLabel(tr("ℹ️ Program automatycznie sprawdza aktualizacje przy każdym uruchomieniu."))
        hint.setStyleSheet("color: #888; font-size: 11px; margin-top: 10px;")
        lay.addWidget(hint)

        lay.addStretch()

    def _setup_bl_tab(self):
        lay = QVBoxLayout(self.bl_tab)
        self.bl_list = QListWidget()
        lay.addWidget(self.bl_list)

        btn_row = QHBoxLayout()
        self.btn_bl_refresh = QPushButton(tr("🔄 Odśwież"))
        self.btn_bl_refresh.clicked.connect(self.refresh_blacklist)
        btn_row.addWidget(self.btn_bl_refresh)

        self.btn_bl_del = QPushButton(tr("🗑 Usuń zaznaczone"))
        self.btn_bl_del.clicked.connect(self._remove_from_blacklist)
        btn_row.addWidget(self.btn_bl_del)

        self.btn_bl_import = QPushButton(tr("📥 Importuj z pliku"))
        self.btn_bl_import.clicked.connect(self._import_blacklist)
        btn_row.addWidget(self.btn_bl_import)
        lay.addLayout(btn_row)

    def setup_signals(self):
        bus.profile_changed.connect(self.load_settings)

    def load_settings(self):
        settings = get_current_profile_settings()

        # Język
        idx = SUPPORTED_LANGUAGES.index(get_language()) if get_language() in SUPPORTED_LANGUAGES else 0
        self.language_combo.setCurrentIndex(idx)

        # Konta (do dropdownu w zakładce Podstawowe)
        self.accounts_data = db.get_smtp_accounts()
        self.active_account_combo.blockSignals(True)
        self.active_account_combo.clear()

        main_idx = -1
        for i, acc in enumerate(self.accounts_data):
            self.active_account_combo.addItem(acc["user"], acc["user"])
            if acc.get("is_main"): main_idx = i

        if main_idx >= 0:
            self.active_account_combo.setCurrentIndex(main_idx)
            # Wyświetl dane aktualnego konta
            acc = self.accounts_data[main_idx]
            self.gmail_user.setText(acc["user"])
            self.gmail_pass.setText(acc["password"])
        else:
            self.gmail_user.setText(tr("-- brak --"))
            self.gmail_pass.setText("")

        self.active_account_combo.blockSignals(False)

        # Firma
        self.company_name.setText(settings.get("company_name", ""))
        self.company_address.setText(settings.get("company_address", ""))
        self.company_phone.setText(settings.get("company_phone", ""))
        self.company_email.setText(settings.get("company_email", ""))
        self.company_website.setText(settings.get("company_website", ""))
        self.company_offer.setText(settings.get("company_offer_description", ""))

        # SMTP Server logic
        saved_host = settings.get("smtp_host", SMTP_RELAY_HOST)
        if saved_host == SMTP_RELAY_HOST: mode = 0
        elif saved_host == SMTP_FALLBACK_HOST: mode = 1
        else: mode = 2

        self.smtp_mode.setCurrentIndex(mode)
        self.smtp_host.setText(saved_host)
        self.smtp_port.setText(str(settings.get("smtp_port", 587)))
        self.custom_delay_spin.setValue(settings.get("custom_send_delay", 3.0))
        self.custom_cap_spin.setValue(settings.get("custom_session_cap", 250))

        self._populate_session_cap_options(mode, settings.get("dzienny_limit"))

        # Rotation
        self.rotation_enabled.setChecked(settings.get("account_rotation_enabled", False))
        self.accounts_data = db.get_smtp_accounts()
        self.accounts_list.clear()
        for acc in self.accounts_data:
            text = f"{acc['user']} @ {acc['host']}"
            if acc.get("warmup_only"):
                text += f" [{tr('Tylko do rozgrzewania')}]"

            if not acc.get("enabled", True):
                text += f" -- {tr('WYŁĄCZONE')} --"

            item = QListWidgetItem(text)
            if not acc.get("enabled", True):
                item.setForeground(Qt.gray)
            self.accounts_list.addItem(item)

        # IMAP
        self.imap_enabled.setChecked(settings.get("imap_enabled", False))
        self.imap_server.setText(settings.get("imap_server", "imap.gmail.com"))
        self.imap_user.setText(settings.get("imap_user", ""))
        self.imap_pass.setText(settings.get("imap_password", ""))

        # S/MIME
        self.smime_enabled.setChecked(settings.get("smime_enabled", False))

        # Proxy
        self.proxy_enabled.setChecked(settings.get("proxy_enabled", False))
        self.proxy_list.setPlainText(settings.get("proxy_list", ""))

        self.refresh_blacklist()

    def save_settings(self):
        settings = get_current_profile_settings()

        # Język
        new_lang = self.language_combo.currentData()
        language_changed = new_lang != get_language()
        if language_changed:
            set_language(new_lang)

        settings.update({
            "company_name": self.company_name.text().strip(),
            "company_address": self.company_address.text().strip(),
            "company_phone": self.company_phone.text().strip(),
            "company_email": self.company_email.text().strip(),
            "company_website": self.company_website.text().strip(),
            "company_offer_description": self.company_offer.text().strip(),
            "smtp_host": self.smtp_host.text().strip(),
            "smtp_port": int(self.smtp_port.text()) if self.smtp_port.text().isdigit() else 587,
            "custom_send_delay": self.custom_delay_spin.value(),
            "custom_session_cap": self.custom_cap_spin.value(),
            "dzienny_limit": self.dzienny_limit.currentData(),
            "account_rotation_enabled": self.rotation_enabled.isChecked(),
            "imap_enabled": self.imap_enabled.isChecked(),
            "imap_server": self.imap_server.text().strip(),
            "imap_user": self.imap_user.text().strip(),
            "imap_password": self.imap_pass.text(),
            "smime_enabled": self.smime_enabled.isChecked(),
            "proxy_enabled": self.proxy_enabled.isChecked(),
            "proxy_list": self.proxy_list.toPlainText().strip(),
        })

        update_current_profile_settings(settings)
        db.save_smtp_accounts(self.accounts_data)

        # Ustaw aktywne konto jako główne w bazie danych
        email = self.active_account_combo.currentData()
        if email:
            db.set_main_account(email)

        # Bounce monitor refresh
        if settings["imap_enabled"] and settings["imap_user"] and settings["imap_password"]:
            if not self.bounce_monitor or not self.bounce_monitor.is_alive():
                self.bounce_monitor = BounceMonitor(
                    settings["imap_user"], settings["imap_password"], settings["imap_server"],
                    on_bounce=lambda addr: (db.add_to_blacklist(addr, "bounce"), self.refresh_blacklist())
                )
                self.bounce_monitor.start()

        bus.settings_saved.emit()

        if language_changed:
            # Restart natychmiast po zapisaniu - nie próbujemy przebudowywać
            # całego GUI "na żywo", to zbyt ryzykowne w tak dużym interfejsie.
            self._confirm_and_restart_for_language()
        else:
            bus.show_message.emit(tr("Sukces"), tr("Ustawienia zostały zapisane!"))

    def _confirm_and_restart_for_language(self):
        reply = QMessageBox.question(
            self,
            tr("Zrestartować teraz?"),
            tr("Język został zmieniony. Aby zastosować zmiany, aplikacja musi zostać zrestartowana teraz."),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            restart_app()
        else:
            bus.show_message.emit(tr("Sukces"), tr("Ustawienia zostały zapisane!"))

    def _on_active_account_selection_changed(self, idx):
        if idx >= 0 and idx < len(self.accounts_data):
            acc = self.accounts_data[idx]
            self.gmail_user.setText(acc["user"])
            self.gmail_pass.setText(acc["password"])

            # W opcjach zaawansowanych ustaw host i port (informacyjnie)
            self.smtp_host.setText(acc["host"])
            self.smtp_port.setText(str(acc["port"]))

    def _apply_smtp_mode(self, idx):
        if idx == 0:
            self.smtp_host.setText(SMTP_RELAY_HOST)
            self.smtp_port.setText(str(SMTP_RELAY_PORT))
        elif idx == 1:
            self.smtp_host.setText(SMTP_FALLBACK_HOST)
            self.smtp_port.setText(str(SMTP_FALLBACK_PORT))
        self._populate_session_cap_options(idx)

    def _populate_session_cap_options(self, mode, preselect=None):
        self.dzienny_limit.clear()
        if mode == 0:
            for v in SESSION_CAP_OPTIONS: self.dzienny_limit.addItem(f"{v} / sesję", v)
            delay = get_send_delay(SMTP_RELAY_HOST)
        elif mode == 1:
            for v in GMAIL_FREE_SESSION_CAP_OPTIONS: self.dzienny_limit.addItem(f"{v} / sesję", v)
            delay = get_send_delay(SMTP_FALLBACK_HOST)
        else:
            v = self.custom_cap_spin.value()
            self.dzienny_limit.addItem(f"{v} / sesję", v)
            delay = self.custom_delay_spin.value()

        self.limit_pace_hint.setText(f"Tempo: {delay:g} s/wiadomość.")
        idx = self.dzienny_limit.findData(preselect)
        if idx >= 0: self.dzienny_limit.setCurrentIndex(idx)

    def _generate_smime(self):
        from core.smime import generate_smime_cert
        try:
            p12, finger = generate_smime_cert()
            bus.show_message.emit("S/MIME", tr("Certyfikat wygenerowany!\nFingerprint: {}").format(finger))
        except Exception as e:
            bus.show_message.emit("S/MIME Błąd", str(e))

    def test_connection(self):
        user = self.gmail_user.text().strip()
        pwd = self.gmail_pass.text()
        host = self.smtp_host.text().strip()
        port = int(self.smtp_port.text()) if self.smtp_port.text().isdigit() else 587

        ok, msg = test_gmail_connection(user, pwd, host, port)
        if ok: bus.show_message.emit("SMTP", tr("Połączenie działa!"))
        else: bus.show_message.emit("SMTP Błąd", msg)

    def _show_add_account_dialog(self):
        from PySide6.QtWidgets import QDialog, QFormLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Dodaj konto SMTP"))
        lay = QFormLayout(dlg)
        email = QLineEdit()
        lay.addRow(tr("Email:"), email)
        pwd = QLineEdit(); pwd.setEchoMode(QLineEdit.Password)
        lay.addRow(tr("Hasło:"), pwd)
        host = QLineEdit(); host.setPlaceholderText("smtp.example.com")
        lay.addRow(tr("Host:"), host)
        port = QLineEdit("587")
        lay.addRow(tr("Port:"), port)

        warmup_only = QCheckBox(tr("Tylko do rozgrzewania (pomijaj w kampaniach)"))
        warmup_only.setToolTip(tr("Konto oznaczone jako 'Tylko do rozgrzewania' będzie używane przez silnik Warm-up, ale zostanie całkowicie pominięte przy wysyłaniu ofert w kampaniach."))
        lay.addRow(warmup_only)

        btn = QPushButton(tr("Dodaj"))
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)

        if dlg.exec():
            acc = {
                "user": email.text(),
                "password": pwd.text(),
                "host": host.text() or "smtp.gmail.com",
                "port": int(port.text()) if port.text().isdigit() else 587,
                "enabled": True,
                "warmup_only": warmup_only.isChecked()
            }
            self.accounts_data.append(acc)
            text = f"{acc['user']} @ {acc['host']}"
            if acc["warmup_only"]:
                text += f" [{tr('Tylko do rozgrzewania')}]"

            item = QListWidgetItem(text)
            self.accounts_list.addItem(item)

    def _toggle_account(self):
        idx = self.accounts_list.currentRow()
        if idx >= 0:
            acc = self.accounts_data[idx]
            acc["enabled"] = not acc.get("enabled", True)

            # Odśwież widok listy
            self.accounts_list.clear()
            for a in self.accounts_data:
                text = f"{a['user']} @ {a['host']}"
                if a.get("warmup_only"): text += f" [{tr('Tylko do rozgrzewania')}]"
                if not a.get("enabled", True): text += f" -- {tr('WYŁĄCZONE')} --"
                item = QListWidgetItem(text)
                if not a.get("enabled", True): item.setForeground(Qt.gray)
                self.accounts_list.addItem(item)

            self.accounts_list.setCurrentRow(idx)

    def _remove_account(self):
        idx = self.accounts_list.currentRow()
        if idx >= 0:
            self.accounts_list.takeItem(idx)
            del self.accounts_data[idx]

    def refresh_blacklist(self):
        self.bl_list.clear()
        for email, reason, added in db.get_blacklist():
            self.bl_list.addItem(f"{email} ({reason}) [{added[:10]}]")

    def _remove_from_blacklist(self):
        items = self.bl_list.selectedItems()
        for item in items:
            email = item.text().split()[0]
            db.remove_from_blacklist(email)
        self.refresh_blacklist()

    def _import_blacklist(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Import czarnej listy"), "", "TXT/CSV (*.txt *.csv)")
        if path:
            count = import_blacklist_from_file(path)
            self.refresh_blacklist()
            bus.show_message.emit("Blacklist", tr("Zaimportowano {} adresów.").format(count))

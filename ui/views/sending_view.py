# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QProgressBar, QListWidget, QGroupBox, QCheckBox,
    QMessageBox, QScrollArea, QListWidgetItem, QSpinBox, QWidget, QComboBox, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from ui.views.base_view import BaseView
from ui.i18n import tr
from ui.styles import COLOR_SENT_LIST, DEFAULT_TEMPLATE, DEFAULT_SUBJECT
from core import database as db
from core.workers import SendWorker, AIAutoSendWorker
from core.profile_manager import get_current_profile_settings, get_company_info
from core.email_sender import test_gmail_connection
from core.config import (
    SMTP_RELAY_HOST, SMTP_RELAY_PORT, SESSION_HARD_CAP,
    CUSTOM_SEND_DELAY_DEFAULT, CUSTOM_SESSION_CAP_DEFAULT
)
from core.signal_bus import bus
from core.account_rotator import SMTPAccountRotator

class SendingView(BaseView):
    def setup_ui(self):
        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setStyleSheet("border: none; background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)

        header = QLabel(tr("Wysyłka i Personalizacja"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        layout.addWidget(header)

        # 1. AI Auto-Send (The "Magic" button)
        ai_group = QGroupBox(tr("🤖 AI Auto-Send (Auto-personalizacja i wysyłka)"))
        ai_group.setStyleSheet("QGroupBox { border: 2px solid #5e2b8b; }")
        ai_lay = QVBoxLayout(ai_group)

        ai_hint = QLabel(tr("Pobiera treść strony WWW każdego leada, ocenia dopasowanie i pisze unikalny mail."))
        ai_hint.setStyleSheet("color: #a6adc8; font-size: 11px;"); ai_lay.addWidget(ai_hint)

        ai_row = QHBoxLayout()
        ai_row.addWidget(QLabel(tr("Język:")))
        self.ai_lang = QComboBox()
        self.ai_lang.addItems(["Auto", "Polski", "Niemiecki", "Angielski"])
        ai_row.addWidget(self.ai_lang)

        ai_row.addWidget(QLabel(tr("Próg AI:")))
        self.ai_threshold = QSpinBox(); self.ai_threshold.setRange(0, 100); self.ai_threshold.setValue(50); self.ai_threshold.setSuffix("%")
        ai_row.addWidget(self.ai_threshold)

        self.btn_ai_start = QPushButton(tr("🤖 START AI AUTO-SEND"))
        self.btn_ai_start.setStyleSheet("background: #5e2b8b; font-weight: bold; padding: 10px;")
        self.btn_ai_start.clicked.connect(self.start_ai_auto_send)
        ai_row.addWidget(self.btn_ai_start, stretch=1)
        ai_lay.addLayout(ai_row)
        layout.addWidget(ai_group)

        # 2. Edytor Szablonu (Tradycyjny)
        tmpl_group = QGroupBox(tr("📝 Szablon wiadomości"))
        tmpl_lay = QVBoxLayout(tmpl_group)
        self.szablon_edit = QTextEdit(); self.szablon_edit.setMinimumHeight(150); self.szablon_edit.setPlainText(DEFAULT_TEMPLATE)
        tmpl_lay.addWidget(self.szablon_edit)

        row_subj = QHBoxLayout()
        row_subj.addWidget(QLabel(tr('Temat:')))
        self.temat_edit = QLineEdit(DEFAULT_SUBJECT); row_subj.addWidget(self.temat_edit)

        btn_preview = QPushButton(tr("👁 Podgląd"))
        btn_preview.clicked.connect(self._show_preview)
        row_subj.addWidget(btn_preview)

        btn_save_tmpl = QPushButton(tr("💾 Zapisz szablon"))
        btn_save_tmpl.clicked.connect(self._save_template_to_profile)
        btn_save_tmpl.setStyleSheet("background-color: #3d3d3d;")
        row_subj.addWidget(btn_save_tmpl)

        btn_wiz_tmpl = QPushButton(tr("🚀 Kreator Szablonu (AI)"))
        btn_wiz_tmpl.clicked.connect(self._open_template_wizard)
        btn_wiz_tmpl.setStyleSheet("background-color: #5e2b8b; font-weight: bold;")
        row_subj.addWidget(btn_wiz_tmpl)

        tmpl_lay.addLayout(row_subj)
        layout.addWidget(tmpl_group)

        # 3. Opcje & Filtry
        opt_group = QGroupBox(tr("⚙️ Opcje wysyłki"))
        opt_lay = QHBoxLayout(opt_group)
        self.dry_run = QCheckBox(tr("🎬 Dry-run")); opt_lay.addWidget(self.dry_run)
        self.html_check = QCheckBox(tr("HTML")); opt_lay.addWidget(self.html_check)
        self.mx_check = QCheckBox(tr("MX")); self.mx_check.setChecked(True); opt_lay.addWidget(self.mx_check)
        self.smime_check = QCheckBox(tr("S/MIME")); self.smime_check.setChecked(True); opt_lay.addWidget(self.smime_check)

        opt_lay.addStretch()
        opt_lay.addWidget(QLabel(tr("Min Score:")))
        self.min_score = QSpinBox(); self.min_score.setRange(-1, 100); self.min_score.setValue(0)
        opt_lay.addWidget(self.min_score)

        opt_lay.addStretch()
        opt_lay.addWidget(QLabel(tr("Uruchom sekwencję:")))
        self.seq_combo = QComboBox()
        self.seq_combo.addItem(tr("-- Wybierz (lub wyślij pojedynczo) --"), None)
        opt_lay.addWidget(self.seq_combo)

        self.btn_start_seq = QPushButton(tr("🚀 START SEKWENCJI"))
        self.btn_start_seq.setStyleSheet("background-color: #4a9eff; font-weight: bold;")
        self.btn_start_seq.clicked.connect(self._start_sequence_for_leads)
        opt_lay.addWidget(self.btn_start_seq)

        layout.addWidget(opt_group)

        # 4. Lista Odbiorców
        list_group = QGroupBox(tr("👥 Odbiorcy"))
        list_lay = QVBoxLayout(list_group)
        self.send_list = QListWidget(); self.send_list.setSelectionMode(QListWidget.MultiSelection); self.send_list.setMinimumHeight(150)
        list_lay.addWidget(self.send_list)

        btn_row = QHBoxLayout()
        btn_sel_all = QPushButton(tr("Zaznacz wszystkie")); btn_sel_all.clicked.connect(self.send_list.selectAll); btn_row.addWidget(btn_sel_all)
        btn_sel_new = QPushButton(tr("Tylko nowe")); btn_sel_new.clicked.connect(self.select_new_only); btn_row.addWidget(btn_sel_new)
        list_lay.addLayout(btn_row)
        layout.addWidget(list_group)

        # 5. Kontrola
        ctrl_group = QGroupBox(tr("🚀 Start wysyłki"))
        ctrl_lay = QVBoxLayout(ctrl_group)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel(tr("Ilość odbiorców:")))
        self.send_count_spin = QSpinBox()
        self.send_count_spin.setRange(1, 10000)
        self.send_count_spin.setValue(100)
        qty_row.addWidget(self.send_count_spin)

        self.btn_send_qty = QPushButton(tr("📤 Wyślij określoną ilość"))
        self.btn_send_qty.setStyleSheet("background: #2b5e2b; font-weight: bold;")
        self.btn_send_qty.clicked.connect(lambda: self.start_manual_send(limit=self.send_count_spin.value()))
        qty_row.addWidget(self.btn_send_qty)

        self.btn_send_all = QPushButton(tr("📤 Wyślij do WSZYSTKICH"))
        self.btn_send_all.setStyleSheet("background: #8b5e2b; font-weight: bold;")
        self.btn_send_all.clicked.connect(lambda: self.start_manual_send(limit=99999))
        qty_row.addWidget(self.btn_send_all)
        ctrl_lay.addLayout(qty_row)

        self.btn_stop = QPushButton(tr("⏹️ STOP"))
        self.btn_stop.setStyleSheet("background: #8b0000; font-weight: bold;"); self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_worker)
        ctrl_lay.addWidget(self.btn_stop)
        layout.addWidget(ctrl_group)

        self.progress_bar = QProgressBar(); layout.addWidget(self.progress_bar)
        self.status_label = QLabel(tr("Gotowy")); layout.addWidget(self.status_label)

        container.setWidget(content); self.layout.addWidget(container)
        self.worker = None
        self.refresh_send_list()

    def setup_signals(self):
        bus.leads_changed.connect(self.refresh_send_list)
        bus.profile_changed.connect(self._on_profile_changed)
        bus.internal_profile_loaded.connect(self._on_internal_profile_loaded)
        self._refresh_sequences()

    def _refresh_sequences(self):
        curr = self.seq_combo.currentData()
        self.seq_combo.clear()
        self.seq_combo.addItem(tr("-- Wybierz (lub wyślij pojedynczo) --"), None)
        seqs = db.get_sequences()
        for s in seqs:
            self.seq_combo.addItem(s["name"], s["id"])

        idx = self.seq_combo.findData(curr)
        if idx >= 0: self.seq_combo.setCurrentIndex(idx)

    def _on_internal_profile_loaded(self, p):
        if p.get("template"): self.szablon_edit.setPlainText(p["template"])
        if p.get("subject"): self.temat_edit.setText(p["subject"])

    def _on_profile_changed(self, name):
        settings = get_current_profile_settings()
        self.szablon_edit.setPlainText(settings.get("last_template", DEFAULT_TEMPLATE))
        self.temat_edit.setText(settings.get("last_subject", DEFAULT_SUBJECT))

        # Odśwież stan opcji wysyłki
        self.mx_check.setChecked(settings.get("mx_verify_enabled", True))
        self.smime_check.setChecked(settings.get("smime_enabled", True))
        self.html_check.setChecked(settings.get("html_enabled", False))

        self.refresh_send_list()
        self.status_label.setText(tr("Profil: {}").format(name))

    def refresh_send_list(self):
        self.send_list.clear()
        leads = db.get_leads()
        wyslane = db.get_wyslano_emails()
        for l in leads:
            text = f"{l[1]} | {l[3]}"
            already = l[8] == 'wysłano' or l[3] in wyslane
            if already: text += " ✅"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, {"id": l[0], "email": l[3]})
            if already: item.setBackground(QColor(*COLOR_SENT_LIST))
            self.send_list.addItem(item)

    def select_new_only(self):
        self.send_list.clearSelection()
        wyslane = db.get_wyslano_emails()
        for i in range(self.send_list.count()):
            item = self.send_list.item(i); data = item.data(Qt.UserRole)
            if data and data.get('email') not in wyslane: item.setSelected(True)

    def start_manual_send(self, limit=None):
        # 1. Pobierz wszystkie leady, do których jeszcze nie wysłano wiadomości
        wyslane = db.get_wyslano_emails()
        leads_to_send_data = []

        for i in range(self.send_list.count()):
            item = self.send_list.item(i)
            data = item.data(Qt.UserRole)
            if data and data.get('email') not in wyslane:
                leads_to_send_data.append(data)

        if not leads_to_send_data:
            QMessageBox.information(self, tr("Info"), tr("Brak nowych leadów do wysyłki!"))
            return

        # Zastosuj limit jeśli podano
        if limit and limit < len(leads_to_send_data):
            leads_to_send_data = leads_to_send_data[:limit]

        settings = get_current_profile_settings()
        user, pwd = settings.get("gmail_user"), settings.get("gmail_password")
        if not user or not pwd:
            QMessageBox.warning(self, tr("Błąd"), tr("Skonfiguruj pocztę w Ustawieniach!"))
            return

        leads = []
        for s in leads_to_send_data:
            row = db.get_lead_by_id(s['id'])
            if row:
                leads.append({'id': row[0], 'firma': row[1] or '', 'kontakt': row[2] or '', 'email': row[3] or ''})

        if not leads: return

        self.btn_send_qty.setEnabled(False); self.btn_send_all.setEnabled(False); self.btn_stop.setEnabled(True)
        self.worker = SendWorker(
            leads, self.szablon_edit.toPlainText(), self.temat_edit.text(),
            user, pwd, settings.get("smtp_host", SMTP_RELAY_HOST), 587,
            html=self.html_check.isChecked(),
            verify_mx=self.mx_check.isChecked(),
            smime_sign=self.smime_check.isChecked(),
            dry_run=self.dry_run.isChecked()
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def start_ai_auto_send(self):
        selected = [self.send_list.item(i).data(Qt.UserRole) for i in range(self.send_list.count()) if self.send_list.item(i).isSelected()]
        if not selected: return

        settings = get_current_profile_settings()
        user, pwd = settings.get("gmail_user"), settings.get("gmail_password")
        if not user or not pwd: return

        leads = []
        for s in selected:
            row = db.get_lead_by_id(s['id'])
            if row: leads.append({'id': row[0], 'firma': row[1], 'email': row[3], 'website': row[7]})

        self.btn_ai_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.worker = AIAutoSendWorker(
            leads, user, pwd, settings.get("smtp_host", SMTP_RELAY_HOST), 587,
            ai_scoring_threshold=self.ai_threshold.value(),
            email_language=self.ai_lang.currentText().lower(),
            html=self.html_check.isChecked(),
            verify_mx=self.mx_check.isChecked(),
            smime_sign=self.smime_check.isChecked(),
            dry_run=self.dry_run.isChecked()
        )
        self.worker.status.connect(self.status_label.setText)
        self.worker.counters.connect(lambda p, s, k, e: self.status_label.setText(f"Wysłano: {s} | Pominięto: {k} | Błędy: {e}"))
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def _start_sequence_for_leads(self):
        seq_id = self.seq_combo.currentData()
        if not seq_id:
            bus.show_message.emit(tr("Błąd"), tr("Wybierz sekwencję z listy!")); return

        selected = [self.send_list.item(i).data(Qt.UserRole) for i in range(self.send_list.count()) if self.send_list.item(i).isSelected()]
        if not selected:
            bus.show_message.emit(tr("Błąd"), tr("Zaznacz odbiorców na liście!")); return

        # Confirm
        count = len(selected)
        seq_name = self.seq_combo.currentText()
        if QMessageBox.question(self, tr("Start Sekwencji"),
                               tr("Uruchomić sekwencję '{}' dla {} leadów?").format(seq_name, count)) == QMessageBox.No:
            return

        for s in selected:
            db.start_lead_sequence(s['id'], seq_id)

        bus.show_message.emit(tr("Sukces"), tr("Sekwencja uruchomiona dla {} leadów. Worker tła zajmie się resztą.").format(count))
        self.refresh_send_list()

    def stop_worker(self):
        if self.worker: self.worker.stop()

    def on_finished(self):
        self.btn_send_qty.setEnabled(True); self.btn_send_all.setEnabled(True);
        self.btn_ai_start.setEnabled(True); self.btn_stop.setEnabled(False)
        bus.leads_changed.emit()
        bus.show_message.emit("Wysyłka", tr("Zakończono!"))

    def _save_template_to_profile(self):
        name = db.get_setting("last_profile", "")
        if not name:
            bus.show_message.emit("Błąd", tr("Najpierw wczytaj lub zapisz profil w zakładce Kampania"))
            return

        # We need current categories/locations too to avoid overwriting them with empty strings
        p = db.get_profile(name)
        if p:
            db.save_profile(name, p["queries"], p["locations"], self.szablon_edit.toPlainText(), self.temat_edit.text())
            bus.show_message.emit("Sukces", tr("Szablon zapisany w profilu '{}'").format(name))

    def _open_template_wizard(self):
        """Otwiera kreator szablonu AI."""
        from ui.widgets.template_wizard import TemplateWizard
        wiz = TemplateWizard(self)
        if wiz.exec_():
            result = wiz.property("final_ai_result")
            if result:
                self.szablon_edit.setPlainText(result)
                bus.show_message.emit("AI", tr("Szablon wklejony do zakładki Wysyłka!"))

    def _show_preview(self):
        """Wyświetla podgląd wiadomości z podstawionymi zmiennymi i spintaxem."""
        try:
            from core.workers import SendWorker

            # 1. Przygotuj dane do podstawienia
            leads = db.get_leads()
            if leads:
                l = leads[0]
                dane = {
                    'id': str(l[0]), 'firma': l[1] or '', 'kontakt': l[2] or '',
                    'email': l[3] or '', 'adres': l[4] or '', 'telefon': l[5] or '',
                    'website': l[6] or '', 'company_name': l[1] or '' # fallback
                }
            else:
                # Dane testowe jeśli baza jest pusta
                dane = {
                    'firma': 'Przykładowa Firma Sp. z o.o.', 'kontakt': 'Jan Kowalski',
                    'email': 'kontakt@przykladowa.pl', 'adres': 'Ul. Wiejska 1, Warszawa',
                    'telefon': '123-456-789', 'id': '1', 'website': 'www.przyklad.pl'
                }

            # Dodaj dane firmy z profilu
            company_info = get_company_info()
            dane.update(company_info)

            # 2. Przetwórz szablon i temat
            szablon_raw = self.szablon_edit.toPlainText()
            temat_raw = self.temat_edit.text()

            # Podstaw zmienne i rozwiąż spintax
            tresc = SendWorker.resolve_spintax(SendWorker.parse_zmienne(szablon_raw, dane))
            temat = SendWorker.resolve_spintax(SendWorker.parse_zmienne(temat_raw, dane))

            # 3. Wyświetl okno podglądu
            dlg = QDialog(self)
            dlg.setWindowTitle(tr("Podgląd wiadomości"))
            dlg.resize(700, 500)
            lay = QVBoxLayout(dlg)

            header_temat = QLabel(tr("Temat:"))
            header_temat.setStyleSheet("font-weight: bold; color: #4a9eff;")
            lay.addWidget(header_temat)

            temat_display = QLineEdit()
            temat_display.setText(temat)
            temat_display.setReadOnly(True)
            lay.addWidget(temat_display)

            header_tresc = QLabel(tr("Treść:"))
            header_tresc.setStyleSheet("font-weight: bold; color: #4a9eff;")
            lay.addWidget(header_tresc)

            text_display = QTextEdit()
            text_display.setReadOnly(True)
            text_display.setPlainText(tresc)
            lay.addWidget(text_display)

            btn_close = QPushButton(tr("Zamknij"))
            btn_close.clicked.connect(dlg.accept)
            lay.addWidget(btn_close)

            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, tr("Błąd"), f"Nie udało się otworzyć podglądu:\n{str(e)}")

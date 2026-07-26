# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QListWidget, QScrollArea, QMessageBox,
    QDialog, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt
from ui.views.base_view import BaseView
from ui.i18n import tr
from core.workers import InboxFetchWorker, MessageFullWorker, MessageActionWorker
from core.profile_manager import get_current_profile_settings, get_company_info
from core.mailbox_reader import guess_imap_server, guess_trash_folder, is_relay_account
from core.ai_features import ReplyGenerator
from core.signal_bus import bus
from core import database as db
from core.email_sender import wyslij_email

class InboxView(BaseView):
    def setup_ui(self):
        header = QLabel(tr("Skrzynka Odbiorcza"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        self.layout.addWidget(header)

        # Toolbar
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Konto:')))
        self.account_combo = QComboBox()
        row.addWidget(self.account_combo, stretch=1)

        btn_refresh = QPushButton(tr('🔄 Odśwież'))
        btn_refresh.clicked.connect(self.refresh_inbox)
        row.addWidget(btn_refresh)

        self.btn_ai_reply = QPushButton(tr('🤖 Odpowiedz z AI'))
        self.btn_ai_reply.setStyleSheet("background-color: #5e2b8b; font-weight: bold;")
        self.btn_ai_reply.clicked.connect(self._reply_with_ai)
        row.addWidget(self.btn_ai_reply)

        self.btn_del = QPushButton(tr('🗑 Usuń'))
        self.btn_del.clicked.connect(self._delete_message)
        row.addWidget(self.btn_del)
        self.layout.addLayout(row)

        # Layout: Split Table and View
        content_layout = QHBoxLayout()

        # Table
        self.inbox_table = QTableWidget()
        self.inbox_table.setColumnCount(3)
        self.inbox_table.setHorizontalHeaderLabels([tr('Od'), tr('Temat'), tr('Data')])
        self.inbox_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.inbox_table.itemSelectionChanged.connect(self.on_message_selected)
        content_layout.addWidget(self.inbox_table, stretch=2)

        # Right: View
        right_panel = QVBoxLayout()
        self.body_view = QTextEdit()
        self.body_view.setReadOnly(True)
        self.body_view.setStyleSheet("background-color: #1e1e1e; border: 1px solid #333;")
        right_panel.addWidget(QLabel(tr("Treść wiadomości:")))
        right_panel.addWidget(self.body_view)

        content_layout.addLayout(right_panel, stretch=3)
        self.layout.addLayout(content_layout)

        self.worker = None
        self.messages = []
        self.refresh_accounts()

    def setup_signals(self):
        bus.profile_changed.connect(self.refresh_accounts)

    def refresh_accounts(self):
        """Inteligentnie buduje listę kont, które mogą posiadać skrzynkę odbiorczą."""
        self.account_combo.clear()
        added_emails = set()

        settings = get_current_profile_settings()

        # 1. Priorytet: Konto z ustawień IMAP (jeśli włączone)
        if settings.get("imap_enabled") and settings.get("imap_user"):
            email = settings["imap_user"]
            self.account_combo.addItem(f"📥 {email} ({tr('Monitorowanie')})", email)
            added_emails.add(email.lower())

        # 2. Konto firmowe (często używane jako adres zwrotny przy relayu)
        company_email = settings.get("company_email")
        if company_email and company_email.lower() not in added_emails:
            if not is_relay_account(company_email):
                self.account_combo.addItem(f"🏢 {company_email} ({tr('E-mail firmy')})", company_email)
                added_emails.add(company_email.lower())

        # 3. Główne konto wysyłkowe (jeśli nie jest relayem)
        main_user = settings.get("gmail_user")
        if main_user and main_user.lower() not in added_emails:
            if not is_relay_account(main_user):
                self.account_combo.addItem(f"👤 {main_user} ({tr('Główne')})", main_user)
                added_emails.add(main_user.lower())

        # 4. Konta z rotacji (filtrowane)
        accs = db.get_smtp_accounts()
        for a in accs:
            email = a.get("user")
            if email and email.lower() not in added_emails:
                if not is_relay_account(email):
                    self.account_combo.addItem(f"🔄 {email} ({tr('Rotacja')})", email)
                    added_emails.add(email.lower())

    def _get_creds_for_email(self, email):
        """Przeszukuje wszystkie ustawienia, aby znaleźć hasło i serwer dla danego maila."""
        if not email: return None, None, None

        settings = get_current_profile_settings()

        # Jeśli to mail z sekcji IMAP
        if email.lower() == settings.get("imap_user", "").lower():
            return settings.get("imap_password"), settings.get("imap_server", "imap.gmail.com"), email

        # Jeśli to główne konto
        if email.lower() == settings.get("gmail_user", "").lower():
            return settings.get("gmail_password"), guess_imap_server(email), email

        # Przeszukaj rotację
        accs = db.get_smtp_accounts()
        for a in accs:
            if a["user"].lower() == email.lower():
                return a.get("password"), guess_imap_server(email), email

        # Fallback: jeśli to mail firmy, spróbuj użyć głównego hasła (częsty przypadek)
        if email.lower() == settings.get("company_email", "").lower():
            return settings.get("gmail_password"), guess_imap_server(email), email

        return None, None, None

    def refresh_inbox(self):
        email = self.account_combo.currentData()
        if not email: return

        pwd, server, user = self._get_creds_for_email(email)

        if not pwd:
            self.body_view.setPlainText(tr("Błąd: Brak hasła dla tego konta. Upewnij się, że jest skonfigurowane."))
            return

        self.body_view.setPlainText(tr("Pobieranie wiadomości..."))
        self.worker = InboxFetchWorker(user, pwd, server)
        self.worker.finished_ok.connect(self.on_inbox_fetched)
        self.worker.finished_error.connect(lambda err: self.body_view.setPlainText(f"Błąd logowania: {err}"))
        self.worker.start()

    def on_inbox_fetched(self, messages):
        self.messages = messages
        self.inbox_table.setRowCount(len(messages))
        for i, m in enumerate(messages):
            self.inbox_table.setItem(i, 0, QTableWidgetItem(m.sender))
            self.inbox_table.setItem(i, 1, QTableWidgetItem(m.subject))
            self.inbox_table.setItem(i, 2, QTableWidgetItem(m.date))
        self.inbox_table.resizeColumnsToContents()
        self.body_view.setPlainText(tr("Wczytano {} wiadomości. Wybierz maila z listy.").format(len(messages)))

    def on_message_selected(self):
        rows = self.inbox_table.selectionModel().selectedRows()
        if not rows: return
        idx = rows[0].row(); msg = self.messages[idx]

        email = self.account_combo.currentData()
        pwd, server, user = self._get_creds_for_email(email)

        if not pwd:
            self.body_view.setPlainText(tr("Błąd: Nie znaleziono hasła dla tego konta."))
            return

        self.body_view.setPlainText(tr("Wczytywanie treści..."))
        self.body_worker = MessageFullWorker(user, pwd, server, msg.uid)
        self.body_worker.finished_ok.connect(lambda full: self.body_view.setText(full.body))
        self.body_worker.finished_error.connect(lambda err: self.body_view.setPlainText(f"Błąd: {err}"))
        self.body_worker.start()

    def _delete_message(self):
        rows = self.inbox_table.selectionModel().selectedRows()
        if not rows: return
        idx = rows[0].row(); msg = self.messages[idx]

        if QMessageBox.question(self, tr("Usuń"), tr("Usunąć tę wiadomość?")) == QMessageBox.No: return

        email = self.account_combo.currentData()
        pwd, server, user = self._get_creds_for_email(email)

        if not pwd: return

        self.action_worker = MessageActionWorker("delete", user, pwd, server, msg.uid, "INBOX")
        self.action_worker.finished_ok.connect(self.refresh_inbox)
        self.action_worker.start()

    def _reply_with_ai(self):
        rows = self.inbox_table.selectionModel().selectedRows()
        if not rows:
            bus.show_message.emit("Błąd", tr("Wybierz najpierw wiadomość!")); return

        idx = rows[0].row(); msg = self.messages[idx]
        original_body = self.body_view.toPlainText()

        settings = get_current_profile_settings()
        offer = settings.get("company_offer_description", "")

        # Generate reply proposal
        self.btn_ai_reply.setEnabled(False)
        self.status_label = QLabel(tr("AI generuje odpowiedź...")) # Temporary label if needed, but let's just use bus
        bus.show_message.emit("AI", tr("Generuję propozycję odpowiedzi..."))

        reply_text = ReplyGenerator.generate_reply(original_body, offer)
        self.btn_ai_reply.setEnabled(True)

        if not reply_text:
            bus.show_message.emit("Błąd", tr("AI nie mogło wygenerować odpowiedzi. Sprawdź konfigurację.")); return

        # Show Dialog
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("🤖 Propozycja odpowiedzi AI"))
        dlg.resize(600, 500)
        lay = QVBoxLayout(dlg)

        lay.addWidget(QLabel(tr("Propozycja AI (możesz edytować):")))
        edit = QTextEdit()
        edit.setPlainText(reply_text)
        lay.addWidget(edit)

        btn_send = QPushButton(tr("📤 Wyślij odpowiedź"))
        btn_send.setStyleSheet("background-color: #2b5e2b; font-weight: bold; padding: 10px;")
        lay.addWidget(btn_send)

        email_account = self.account_combo.currentData()

        def _do_send():
            pwd, server, user = self._get_creds_for_email(email_account)

            if not pwd:
                bus.show_message.emit("Błąd", tr("Nie znaleziono hasła SMTP dla tego konta."))
                return

            ok, message, _ = wyslij_email(
                msg.sender, f"Re: {msg.subject}", edit.toPlainText(),
                user, pwd, settings.get("smtp_host", "smtp.gmail.com")
            )
            if ok:
                bus.show_message.emit("Sukces", tr("Odpowiedź wysłana!")); dlg.accept()
            else:
                bus.show_message.emit("Błąd", tr("Nie udało się wysłać: {}").format(message))

        btn_send.clicked.connect(_do_send)
        dlg.exec()

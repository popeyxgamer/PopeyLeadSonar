# -*- coding: utf-8 -*-
"""
Kreator "Szybki start" - prowadzi nowego użytkownika krok po kroku od zera
do pierwszej wysyłki: poczta -> dane firmy -> czego szukamy -> gotowe.

W przeciwieństwie do ProfileWizard (który tworzy NOWY profil), ten kreator
uzupełnia ustawienia BIEŻĄCEGO, aktywnego profilu - to ten sam mechanizm,
z którego korzysta zakładka Ustawienia (core.profile_manager.
get_current_profile_settings / update_current_profile_settings), więc
wszystko co tu wpiszesz pojawi się od razu w Ustawieniach i na odwrót.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QWizard, QWizardPage, QFormLayout, QMessageBox,
)

from core.config import SMTP_RELAY_HOST, SMTP_RELAY_PORT
from core.email_sender import test_gmail_connection
from core.profile_manager import get_current_profile_settings, update_current_profile_settings
from core.default_profile import DEFAULT_QUERIES, DEFAULT_LOCATIONS
from ui.i18n import tr


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("👋 Witaj! Skonfigurujmy Twoją pierwszą wysyłkę")
        layout = QVBoxLayout(self)
        text = QLabel(
            tr('Ten kreator przeprowadzi Cię przez 3 proste kroki:\n\n  1️⃣  Podłączenie Twojej skrzynki Gmail\n  2️⃣  Dane Twojej firmy (pojawią się w stopce wiadomości)\n  3️⃣  Kogo szukamy (branża i lokalizacja)\n\nZajmie to około 2 minut. Wszystko można potem zmienić w zakładce ⚙️ Ustawienia.')
        )
        text.setWordWrap(True)
        layout.addWidget(text)


class GmailPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("📧 Krok 1: Twoja skrzynka pocztowa")
        layout = QVBoxLayout(self)

        hint = QLabel(
            tr('Potrzebujemy adresu Gmail i tzw. „hasła aplikacji” (nie zwykłego hasła do konta!). Hasło aplikacji wygenerujesz na stronie:\nmyaccount.google.com → Bezpieczeństwo → Hasła aplikacji.')
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(hint)

        form = QFormLayout()
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText(tr('twoj.adres@gmail.com'))
        form.addRow(tr('Adres Gmail:'), self.email_edit)

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText(tr('hasło aplikacji (16 znaków)'))
        form.addRow(tr('Hasło aplikacji:'), self.pass_edit)
        layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_test = QPushButton(tr('🔍 Testuj połączenie'))
        btn_test.clicked.connect(self._test_connection)
        layout.addWidget(btn_test)

        self.registerField("gmail_user*", self.email_edit)
        self.registerField("gmail_password*", self.pass_edit)

    def _test_connection(self):
        user = self.email_edit.text().strip()
        password = self.pass_edit.text().strip()
        if not user or not password:
            QMessageBox.warning(self, tr('Błąd'), tr('Wpisz adres i hasło aplikacji!'))
            return
        self.status_label.setText(tr('⏳ Sprawdzam połączenie...'))
        ok, msg = test_gmail_connection(user, password, SMTP_RELAY_HOST, SMTP_RELAY_PORT)
        if ok:
            self.status_label.setText(tr('✅ Połączenie działa!'))
            self.status_label.setStyleSheet("color: #a6e3a1;")
        else:
            self.status_label.setText(f"❌ Nie można połączyć: {msg}")
            self.status_label.setStyleSheet("color: #f38ba8;")


class CompanyPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("🏢 Krok 2: Dane Twojej firmy")
        layout = QVBoxLayout(self)

        hint = QLabel(
            tr('Te dane pojawią się automatycznie w stopce każdej wysyłanej wiadomości - nie musisz ich wpisywać ręcznie w szablonie.')
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(hint)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr('np. Twoja Firma Sp. z o.o.'))
        form.addRow(tr('Nazwa firmy:'), self.name_edit)
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText(tr('np. Ul. Przykładowa 1, 00-001 Miasto'))
        form.addRow(tr('Adres:'), self.address_edit)
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText(tr('np. +48 123 456 789'))
        form.addRow(tr('Telefon:'), self.phone_edit)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText(tr('np. kontakt@twojafirma.pl'))
        form.addRow(tr('E-mail firmy:'), self.email_edit)
        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText(tr('np. https://twojafirma.pl'))
        form.addRow(tr('Strona WWW:'), self.website_edit)
        layout.addLayout(form)

        self.registerField("company_name", self.name_edit)
        self.registerField("company_address", self.address_edit)
        self.registerField("company_phone", self.phone_edit)
        self.registerField("company_email", self.email_edit)
        self.registerField("company_website", self.website_edit)


class SearchPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("🔍 Krok 3: Kogo szukamy?")
        layout = QVBoxLayout(self)

        hint = QLabel(
            tr('Wpisz branże (jedna na linię) i miejscowości, w których mają się znajdować firmy. Zostawiliśmy przykładowe wartości - możesz je od razu zmienić na swoje.')
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(hint)

        row = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.addWidget(QLabel(tr('Branże / kategorie:')))
        self.queries_edit = QTextEdit()
        self.queries_edit.setPlainText(DEFAULT_QUERIES)
        col1.addWidget(self.queries_edit)
        row.addLayout(col1)

        col2 = QVBoxLayout()
        col2.addWidget(QLabel(tr('Miejscowości:')))
        self.locations_edit = QTextEdit()
        self.locations_edit.setPlainText(DEFAULT_LOCATIONS)
        col2.addWidget(self.locations_edit)
        row.addLayout(col2)

        layout.addLayout(row)

        self.registerField("last_queries*", self.queries_edit, "plainText", self.queries_edit.textChanged)
        self.registerField("last_locations*", self.locations_edit, "plainText", self.locations_edit.textChanged)


class FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("🎉 Gotowe!")
        layout = QVBoxLayout(self)
        text = QLabel(
            tr('Wszystko zapisane. Po zamknięciu kreatora:\n\n  • Przejdź do zakładki 🔍 Wyszukiwanie i kliknij „Szukaj”, żeby znaleźć pierwsze firmy\n  • Potem w zakładce 📤 Wysyłka sprawdź podgląd wiadomości\n  • Gdy wszystko wygląda dobrze - wyślij!\n\nW każdej chwili możesz wrócić do tego kreatora albo poprawić cokolwiek ręcznie w zakładce ⚙️ Ustawienia.')
        )
        text.setWordWrap(True)
        layout.addWidget(text)


class QuickStartWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('🚀 Szybki start'))
        self.setWizardStyle(QWizard.ModernStyle)
        self.resize(650, 500)

        # Wstępnie wypełnij polami z aktualnych ustawień profilu (jeśli coś już jest)
        settings = get_current_profile_settings()

        self.addPage(WelcomePage())

        gmail_page = GmailPage()
        gmail_page.email_edit.setText(settings.get("gmail_user", ""))
        gmail_page.pass_edit.setText(settings.get("gmail_password", ""))
        self.addPage(gmail_page)

        company_page = CompanyPage()
        company_page.name_edit.setText(settings.get("company_name", ""))
        company_page.address_edit.setText(settings.get("company_address", ""))
        company_page.phone_edit.setText(settings.get("company_phone", ""))
        company_page.email_edit.setText(settings.get("company_email", ""))
        company_page.website_edit.setText(settings.get("company_website", ""))
        self.addPage(company_page)

        search_page = SearchPage()
        if settings.get("last_queries"):
            search_page.queries_edit.setPlainText(settings["last_queries"])
        if settings.get("last_locations"):
            search_page.locations_edit.setPlainText(settings["last_locations"])
        self.addPage(search_page)

        self.addPage(FinishPage())

    def accept(self):
        self._save_all()
        super().accept()

    def _save_all(self):
        settings = get_current_profile_settings()
        settings.update({
            "gmail_user": self.field("gmail_user") or "",
            "gmail_password": self.field("gmail_password") or "",
            "company_name": self.field("company_name") or "",
            "company_address": self.field("company_address") or "",
            "company_phone": self.field("company_phone") or "",
            "company_email": self.field("company_email") or "",
            "company_website": self.field("company_website") or "",
            "last_queries": self.field("last_queries") or "",
            "last_locations": self.field("last_locations") or "",
        })
        update_current_profile_settings(settings)

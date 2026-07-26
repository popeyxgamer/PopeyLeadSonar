# -*- coding: utf-8 -*-
"""
Kreator nowego profilu – uproszczone tworzenie kampanii krok po kroku.
"""
import traceback
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QPushButton, QWizard, QWizardPage,
    QFormLayout, QGroupBox, QMessageBox, QFileDialog, QSpinBox,
    QListWidget, QListWidgetItem, QSplitter, QWidget, QScrollArea,
)
from PySide6.QtGui import QFont

from core.profile_manager import create_new_profile, get_all_profiles, switch_profile
from core.config import (
    SMTP_RELAY_HOST, SMTP_RELAY_PORT, SMTP_FALLBACK_HOST, SMTP_FALLBACK_PORT,
    guess_smtp,
)
from core.database import save_profile
from ui.styles import (
    DEFAULT_LOCATIONS, DEFAULT_PROFILE_NAME, DEFAULT_QUERIES,
    DEFAULT_SUBJECT, DEFAULT_TEMPLATE,
)
from ui.i18n import tr


class ProfileWizard(QWizard):
    """Kreator tworzenia nowego profilu kampanii."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('🎯 Kreator nowego profilu'))
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)

        # Strony
        self.setPage(1, CompanyPage(self))
        self.setPage(2, CategoriesLocationsPage(self))
        self.setPage(3, TemplatePage(self))
        self.setPage(4, SubjectOptionsPage(self))
        self.setPage(5, SmtpPage(self))

        self.setStartId(1)

        # Przyciski
        self.setButtonText(QWizard.FinishButton, "✅ Utwórz profil")
        self.setButtonText(QWizard.NextButton, "Dalej →")
        self.setButtonText(QWizard.BackButton, "← Wstecz")
        self.setButtonText(QWizard.CancelButton, "Anuluj")

    def accept(self):
        """Nadpisana metoda – wykonuje logikę tworzenia profilu przed zamknięciem."""
        # Sprawdź, czy wszystkie strony są walidowane
        for page_id in [1, 2, 3, 4, 5]:
            page = self.page(page_id)
            if not page.validatePage():
                return  # nie zamykaj kreatora

        # Pobierz dane ze wszystkich stron
        data = {}
        for page_id in [1, 2, 3, 4, 5]:
            page = self.page(page_id)
            if hasattr(page, 'get_data'):
                data.update(page.get_data())

        # Walidacja nazwy profilu
        profile_name = data.get('profile_name', '').strip()
        if not profile_name:
            QMessageBox.warning(self, tr('Błąd'), tr('Nazwa profilu nie może być pusta.'))
            return
        if profile_name in get_all_profiles():
            QMessageBox.warning(self, tr('Błąd'), f"Profil '{profile_name}' już istnieje.")
            return

        # Walidacja SMTP
        smtp_user = data.get('smtp_user', '').strip()
        smtp_pass = data.get('smtp_password', '').strip()
        if not smtp_user or not smtp_pass:
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź dane logowania SMTP (e-mail i hasło).'))
            return

        # Tworzenie profilu
        try:
            # 1. Utwórz profil (pusta baza)
            if not create_new_profile(profile_name):
                QMessageBox.warning(self, tr('Błąd'), tr('Nie udało się utworzyć profilu.'))
                return

            # 2. Zapisz dane profilu (kategorie, lokalizacje, szablon, temat) w bazie
            internal_name = data.get('internal_profile_name', 'Domyślny')
            save_profile(
                internal_name,
                data.get('queries', DEFAULT_QUERIES),
                data.get('locations', DEFAULT_LOCATIONS),
                data.get('template', DEFAULT_TEMPLATE),
                data.get('subject', DEFAULT_SUBJECT),
                profile=profile_name
            )

            # 3. Zapisz ustawienia SMTP i inne w settings.json
            from core.profile_manager import update_current_profile_settings
            settings = {
                'gmail_user': smtp_user,
                'gmail_password': smtp_pass,
                'smtp_host': data.get('smtp_host', SMTP_RELAY_HOST),
                'smtp_port': data.get('smtp_port', SMTP_RELAY_PORT),
                'dzienny_limit': data.get('daily_limit', 9500),
                'custom_send_delay': data.get('custom_delay', 3.0),
                'custom_session_cap': data.get('custom_cap', 250),
                'html_enabled': data.get('html_enabled', False),
                'mx_verify_enabled': data.get('mx_enabled', True),
                'smime_enabled': data.get('smime_enabled', True),
                'attachments': data.get('attachments', ''),
                'account_rotation_enabled': False,
                'rotation_max_per_account': 1000,
                'proxy_enabled': False,
                'proxy_list': '',
                'imap_enabled': False,
                'imap_server': 'imap.gmail.com',
                'imap_user': '',
                'imap_password': '',
                'company_name': data.get('company_name', ''),
                'company_address': data.get('company_address', ''),
                'company_phone': data.get('company_phone', ''),
                'company_email': data.get('company_email', ''),
                'company_website': data.get('company_website', ''),
            }
            update_current_profile_settings(settings)

            # 4. Przełącz na nowy profil
            if not switch_profile(profile_name):
                QMessageBox.warning(self, tr('Błąd'), tr('Nie udało się przełączyć na nowy profil.'))
                return

            QMessageBox.information(
                self, tr('✅ Sukces'),
                f"Profil '{profile_name}' został utworzony!\n\n"
                f"Możesz teraz rozpocząć wyszukiwanie leadów.\n"
                f"Folder profilu: profiles/{profile_name}/"
            )

            # Zamknij kreator z sukcesem
            super().accept()

        except Exception as e:
            error_msg = traceback.format_exc()
            QMessageBox.critical(
                self, tr('❌ Błąd'),
                f"Nie udało się utworzyć profilu:\n\n{str(e)}\n\n"
                f"Szczegóły:\n{error_msg[:500]}"
            )
            # Nie zamykaj kreatora – użytkownik może spróbować ponownie


# ------------------------------------------------------------------
# KROK 1 – Dane profilu i firmy
# ------------------------------------------------------------------
class CompanyPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("🏢 Dane profilu i firmy")
        self.setSubTitle("Podaj nazwę profilu oraz dane Twojej firmy – będą używane w szablonie wiadomości.")

        layout = QVBoxLayout()

        # Profil
        grp = QGroupBox(tr("Nazwa profilu (np. 'Kampania Restauracje')"))
        form = QFormLayout(grp)
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText(tr('np. MojaKampania'))
        form.addRow(tr('Nazwa profilu:'), self.profile_name)
        layout.addWidget(grp)

        # Dane firmy
        grp2 = QGroupBox(tr('Dane Twojej firmy (będą użyte w stopce)'))
        form2 = QFormLayout(grp2)
        self.company_name = QLineEdit()
        self.company_name.setPlaceholderText(tr('np. Twoja Firma Sp. z o.o.'))
        form2.addRow(tr('Nazwa firmy:'), self.company_name)

        self.company_address = QLineEdit()
        self.company_address.setPlaceholderText(tr('np. Ul. Przykładowa 1, 00-001 Miasto'))
        form2.addRow(tr('Adres:'), self.company_address)

        self.company_phone = QLineEdit()
        self.company_phone.setPlaceholderText(tr('np. +48 123 456 789'))
        form2.addRow(tr('Telefon:'), self.company_phone)

        self.company_email = QLineEdit()
        self.company_email.setPlaceholderText(tr('np. kontakt@twojafirma.pl'))
        form2.addRow(tr('E-mail firmy:'), self.company_email)

        self.company_website = QLineEdit()
        self.company_website.setPlaceholderText(tr('np. https://twojafirma.pl'))
        form2.addRow(tr('Strona WWW:'), self.company_website)

        layout.addWidget(grp2)
        self.setLayout(layout)

    def get_data(self):
        return {
            'profile_name': self.profile_name.text().strip(),
            'company_name': self.company_name.text().strip(),
            'company_address': self.company_address.text().strip(),
            'company_phone': self.company_phone.text().strip(),
            'company_email': self.company_email.text().strip(),
            'company_website': self.company_website.text().strip(),
        }

    def validatePage(self):
        if not self.profile_name.text().strip():
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź nazwę profilu.'))
            return False
        return True


# ------------------------------------------------------------------
# KROK 2 – Kategorie i lokalizacje
# ------------------------------------------------------------------
class CategoriesLocationsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("📍 Kategorie i lokalizacje")
        self.setSubTitle("Wybierz branże (kategorie) oraz miasta, w których chcesz szukać firm.")

        layout = QVBoxLayout()

        # Kategorie
        grp = QGroupBox(tr('Kategorie (jedna na linię)'))
        grp_layout = QVBoxLayout(grp)
        self.queries_edit = QTextEdit()
        self.queries_edit.setPlainText(DEFAULT_QUERIES)
        grp_layout.addWidget(self.queries_edit)

        btn_fill_cat = QPushButton(tr('📋 Wypełnij przykładowymi kategoriami'))
        btn_fill_cat.clicked.connect(lambda: self.queries_edit.setPlainText(DEFAULT_QUERIES))
        grp_layout.addWidget(btn_fill_cat)
        layout.addWidget(grp)

        # Lokalizacje
        grp2 = QGroupBox(tr('Lokalizacje (jedna na linię)'))
        grp2_layout = QVBoxLayout(grp2)
        self.locations_edit = QTextEdit()
        self.locations_edit.setPlainText(DEFAULT_LOCATIONS)
        grp2_layout.addWidget(self.locations_edit)

        btn_fill_loc = QPushButton(tr('📋 Wypełnij przykładowymi lokalizacjami'))
        btn_fill_loc.clicked.connect(lambda: self.locations_edit.setPlainText(DEFAULT_LOCATIONS))
        grp2_layout.addWidget(btn_fill_loc)
        layout.addWidget(grp2)

        self.setLayout(layout)

    def get_data(self):
        return {
            'queries': self.queries_edit.toPlainText(),
            'locations': self.locations_edit.toPlainText(),
        }

    def validatePage(self):
        if not self.queries_edit.toPlainText().strip():
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź przynajmniej jedną kategorię.'))
            return False
        if not self.locations_edit.toPlainText().strip():
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź przynajmniej jedną lokalizację.'))
            return False
        return True


# ------------------------------------------------------------------
# KROK 3 – Szablon wiadomości
# ------------------------------------------------------------------
class TemplatePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("📝 Szablon wiadomości")
        self.setSubTitle("Przygotuj treść wiadomości. Możesz wybrać gotowy szablon lub dostosować własny.")

        layout = QVBoxLayout()

        # Wybór gotowego szablonu
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Gotowy szablon:')))
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "Standardowy (przykładowy)",
            "Profesjonalny (dłuższy)",
            "Krótki (zwięzły)",
            "Stanley Maler (München)",
            "Własny"
        ])
        self.template_combo.currentTextChanged.connect(self._load_template)
        row.addWidget(self.template_combo)
        row.addStretch()
        layout.addLayout(row)

        # Edycja szablonu
        self.template_edit = QTextEdit()
        self.template_edit.setPlainText(DEFAULT_TEMPLATE)
        self.template_edit.setMinimumHeight(200)
        layout.addWidget(self.template_edit)

        # Podgląd
        btn_preview = QPushButton(tr('👁 Podgląd (z przykładowymi danymi)'))
        btn_preview.clicked.connect(self._preview)
        layout.addWidget(btn_preview)

        # Informacja o zmiennych
        info = QLabel(
            tr('Dostępne zmienne: {firma}, {kontakt}, {email}, {adres}, {telefon}, {id}, {company_name}, {company_address}, {company_phone}, {company_website}\nMieszacz treści: {{wariant 1|wariant 2|wariant 3}}')
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(info)

        self.setLayout(layout)

    def _load_template(self, name):
        templates = {
            "Standardowy (przykładowy)": DEFAULT_TEMPLATE,
            "Profesjonalny (dłuższy)": """{{Szanowni Państwo|Drogi Zespole|Witajcie}} {firma},

Jesteśmy firmą {company_name} specjalizującą się w {uslugi}. 
Chcielibyśmy przedstawić naszą ofertę, która może być dla Państwa interesująca.

Nasze usługi obejmują:
• Usługa 1
• Usługa 2
• Usługa 3

Zapraszamy do kontaktu: {company_phone} lub {company_email}.

Z poważaniem,
{company_name}""",
            "Krótki (zwięzły)": """Witam {firma},

Jesteśmy {company_name} i oferujemy {uslugi}. 
Czy są Państwo zainteresowani współpracą?

Pozdrawiam,
{company_name}""",
            "Stanley Maler (München)": """{{Sehr geehrte Damen und Herren der {firma}|Guten Tag, liebes Team der {firma}|Hallo werte Kolleginnen und Kollegen von {firma}|Sehr geehrte Geschäftsleitung der {firma}}},

{{als regionaler Dienstleister in München und Umgebung|als zuverlässiger Handwerksbetrieb aus München|als erfahrenes Maler- und Sanierungsunternehmen aus der Region München}} unterstützen wir {{Immobilienverwaltungen, Bauunternehmen und Gewerbekunden|Eigentümer, Hausverwaltungen und Baufirmen|Immobilieneigentümer und gewerbliche Kunden}} bei der {{professionellen Instandhaltung, Sanierung und Pflege|fachgerechten Renovierung, Modernisierung und Werterhaltung|hochwertigen Instandsetzung und optischen Aufwertung}} ihrer Objekte.

{{Da Sie in der entsprechenden Branche tätig sind|Da wir Sie als potenziellen Partner in Ihrer Branche sehen|Da Ihre Tätigkeit einen Bezug zu unseren Leistungen hat}}, möchten wir anfragen, {{ob Sie derzeit oder bei zukünftigen Projekten Bedarf an unseren Dienstleistungen haben|ob wir Sie bei kommenden Bau- oder Renovierungsvorhaben unterstützen dürfen|ob Sie Interesse an einer Zusammenarbeit mit uns haben}}. Zu unserem Leistungsspektrum gehören:

{{• Professionelle Maler-, Lackier- und Spachtelarbeiten|• Hochwertige Maler- und Lackierarbeiten, Innen- und Außenputz|• Komplette Innenrenovierung, Fassadenarbeiten und Spachteltechniken}}
{{• Büroreinigung und Praxisreinigung|• Gründliche Büro- und Praxisreinigung, Treppenhausreinigung|• Verlässliche Unterhaltsreinigung für Gewerbe- und Praxisräume}}

{{Falls Sie Interesse an einer Zusammenarbeit oder der Aufnahme in Ihren Handwerker- und Dienstleisterpool haben|Bei Interesse an einer langfristigen Kooperation|Wenn Sie unsere Leistungen in Ihren Dienstleisterpool aufnehmen möchten}}, würden wir uns {{über eine kurze Rückmeldung z. B. mit Angabe der Telefonnummer des zuständigen Ansprechpartners freuen|über Ihre Kontaktdaten für einen unverbindlichen Austausch freuen|über eine kurze Nachricht mit Ihrem Wunschtermin freuen}}. {{Alternativ können Sie uns auch gerne direkt telefonisch kontaktieren|Sie erreichen uns auch telefonisch unter der Nummer unten|Gerne können Sie auch direkt anrufen}} Tel.: {{015510657291|+49 155 1065 7291|0155 1065 7291}}.

{{Falls kein Bedarf an einer Kontaktaufnahme besteht, ignorieren Sie diese E-Mail bitte – Sie werden keine weiteren Nachrichten von uns erhalten.|Sollten Sie kein Interesse haben, betrachten Sie diese E-Mail bitte als gegenstandslos.|Wenn Sie derzeit keinen Bedarf haben, können Sie diese Nachricht einfach ignorieren.}}

{{Mit freundlichen Grüßen|Mit besten Grüßen|Hochachtungsvoll}}

{company_name}
Inhaber: Daniel Stosio
{company_address}
{company_phone}
Web: {company_website}"""
        }
        if name in templates:
            self.template_edit.setPlainText(templates[name])
        # Dla "Własny" – nie zmieniaj

    def _preview(self):
        try:
            from core.workers import SendWorker
            from core.profile_manager import get_company_info

            # Dane testowe dla podglądu w kreatorze
            dane = {
                'firma': 'Przykładowa Firma Sp. z o.o.',
                'kontakt': 'Jan Kowalski',
                'email': 'kontakt@przykladowa.pl',
                'adres': 'Ul. Przykładowa 1, 00-001 Miasto',
                'telefon': '+48 123 456 789',
                'id': '12345',
                'uslugi': 'nasze usługi',
            }

            # Spróbuj pobrać dane firmy z pól kreatora (jeśli wypełnione)
            # Przeszukujemy strony kreatora w poszukiwaniu danych
            wiz = self.wizard()
            if wiz:
                for page_id in wiz.pageIds():
                    page = wiz.page(page_id)
                    if hasattr(page, 'get_data'):
                        dane.update(page.get_data())

            text_raw = self.template_edit.toPlainText()

            # Używamy standardowej logiki podstawiania i mieszania
            text = SendWorker.resolve_spintax(SendWorker.parse_zmienne(text_raw, dane))

            QMessageBox.information(self, tr('👁 Podgląd'), text[:4000] + ("..." if len(text) > 4000 else ""))
        except Exception as e:
            QMessageBox.critical(self, tr("Błąd"), f"Nie udało się otworzyć podglądu:\n{str(e)}")

    def get_data(self):
        return {
            'template': self.template_edit.toPlainText(),
        }

    def validatePage(self):
        if not self.template_edit.toPlainText().strip():
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź treść wiadomości.'))
            return False
        return True


# ------------------------------------------------------------------
# KROK 4 – Temat i opcje
# ------------------------------------------------------------------
class SubjectOptionsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("📌 Temat i opcje wysyłki")
        self.setSubTitle("Wprowadź temat wiadomości i wybierz dodatkowe opcje.")

        layout = QVBoxLayout()

        # Temat
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText(DEFAULT_SUBJECT)
        self.subject_edit.setText(DEFAULT_SUBJECT)
        layout.addWidget(QLabel(tr('Temat wiadomości:')))
        layout.addWidget(self.subject_edit)

        # Opcje
        grp = QGroupBox(tr('Opcje wysyłki'))
        grp_layout = QVBoxLayout(grp)

        self.html_check = QCheckBox(tr('HTML (jeśli treść zawiera znaczniki HTML)'))
        grp_layout.addWidget(self.html_check)

        self.mx_check = QCheckBox(tr('Sprawdzaj MX (odrzuca nieistniejące domeny)'))
        self.mx_check.setChecked(True)
        grp_layout.addWidget(self.mx_check)

        self.smime_check = QCheckBox(tr('Podpis S/MIME (wymaga wygenerowanego certyfikatu)'))
        self.smime_check.setChecked(True)
        grp_layout.addWidget(self.smime_check)

        self.attachments_edit = QLineEdit()
        self.attachments_edit.setPlaceholderText(tr('ścieżka/do/pliku1.pdf, ścieżka/do/pliku2.jpg'))
        grp_layout.addWidget(QLabel(tr('Załączniki (oddzielone przecinkami, możesz użyć zmiennych):')))
        grp_layout.addWidget(self.attachments_edit)

        layout.addWidget(grp)

        self.setLayout(layout)

    def get_data(self):
        return {
            'subject': self.subject_edit.text().strip(),
            'html_enabled': self.html_check.isChecked(),
            'mx_enabled': self.mx_check.isChecked(),
            'smime_enabled': self.smime_check.isChecked(),
            'attachments': self.attachments_edit.text().strip(),
        }

    def validatePage(self):
        if not self.subject_edit.text().strip():
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź temat wiadomości.'))
            return False
        return True


# ------------------------------------------------------------------
# KROK 5 – SMTP
# ------------------------------------------------------------------
class SmtpPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("📧 Konfiguracja SMTP")
        self.setSubTitle("Podaj dane konta e-mail, z którego będą wysyłane wiadomości.")

        layout = QVBoxLayout()

        # Dane logowania
        grp = QGroupBox(tr('Dane konta e-mail'))
        form = QFormLayout(grp)

        self.smtp_user = QLineEdit()
        self.smtp_user.setPlaceholderText(tr('sprzedaz@twojafirma.pl'))
        self.smtp_user.editingFinished.connect(self._auto_fill)
        form.addRow(tr('Adres e-mail nadawcy:'), self.smtp_user)

        self.smtp_password = QLineEdit()
        self.smtp_password.setPlaceholderText(tr('hasło aplikacji lub hasło'))
        self.smtp_password.setEchoMode(QLineEdit.Password)
        form.addRow(tr('Hasło:'), self.smtp_password)

        layout.addWidget(grp)

        # Tryb SMTP
        grp2 = QGroupBox(tr('Serwer SMTP'))
        form2 = QFormLayout(grp2)

        self.smtp_mode = QComboBox()
        self.smtp_mode.addItems([
            "Google Workspace SMTP Relay (wysoki wolumen)",
            "Zwykły Gmail SMTP (limit ok. 500/dobę)",
            "Inny dostawca (wpisz ręcznie host/port)"
        ])
        self.smtp_mode.currentIndexChanged.connect(self._on_mode_changed)
        form2.addRow(tr('Tryb:'), self.smtp_mode)

        self.smtp_host = QLineEdit()
        self.smtp_host.setPlaceholderText(tr('smtp-relay.gmail.com'))
        form2.addRow(tr('Host:'), self.smtp_host)

        self.smtp_port = QLineEdit()
        self.smtp_port.setPlaceholderText(tr('587'))
        form2.addRow(tr('Port:'), self.smtp_port)

        layout.addWidget(grp2)

        # Test połączenia
        btn_test = QPushButton(tr('🔍 Test połączenia'))
        btn_test.clicked.connect(self._test_connection)
        layout.addWidget(btn_test)

        # Limity
        grp3 = QGroupBox(tr('Limity wysyłki'))
        form3 = QFormLayout(grp3)
        self.daily_limit = QComboBox()
        self.daily_limit.addItems(["2000", "5000", "9500", "10000"])
        self.daily_limit.setCurrentIndex(2)
        form3.addRow(tr('Limit sesji:'), self.daily_limit)

        self.custom_delay = QLineEdit()
        self.custom_delay.setPlaceholderText(tr('3.0'))
        self.custom_delay.setText(tr('3.0'))
        form3.addRow(tr("Własne tempo (s/wiadomość) – dla 'Inny dostawca':"), self.custom_delay)

        layout.addWidget(grp3)

        self.setLayout(layout)

    def _auto_fill(self):
        email = self.smtp_user.text().strip()
        if email and '@' in email:
            guessed = guess_smtp(email)
            if guessed:
                host, port = guessed
                self.smtp_host.setText(host)
                self.smtp_port.setText(str(port))
                if host == SMTP_RELAY_HOST:
                    self.smtp_mode.setCurrentIndex(0)
                elif host == SMTP_FALLBACK_HOST:
                    self.smtp_mode.setCurrentIndex(1)
                else:
                    self.smtp_mode.setCurrentIndex(2)

    def _on_mode_changed(self, idx):
        if idx == 0:
            self.smtp_host.setText(SMTP_RELAY_HOST)
            self.smtp_port.setText(str(SMTP_RELAY_PORT))
        elif idx == 1:
            self.smtp_host.setText(SMTP_FALLBACK_HOST)
            self.smtp_port.setText(str(SMTP_FALLBACK_PORT))
        # idx 2 pozostawiam wpisane ręcznie

    def _test_connection(self):
        from core.email_sender import test_gmail_connection
        user = self.smtp_user.text().strip()
        password = self.smtp_password.text().strip()
        host = self.smtp_host.text().strip() or SMTP_RELAY_HOST
        try:
            port = int(self.smtp_port.text().strip())
        except ValueError:
            port = SMTP_RELAY_PORT
        if not user or not password:
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź adres e-mail i hasło.'))
            return
        ok, msg = test_gmail_connection(user, password, host, port)
        if ok:
            QMessageBox.information(self, tr('✅ OK'), tr('Połączenie działa!'))
        else:
            QMessageBox.warning(self, tr('❌ Błąd'), f"Nie można połączyć:\n{msg}")

    def get_data(self):
        return {
            'smtp_user': self.smtp_user.text().strip(),
            'smtp_password': self.smtp_password.text(),
            'smtp_host': self.smtp_host.text().strip() or SMTP_RELAY_HOST,
            'smtp_port': int(self.smtp_port.text().strip()) if self.smtp_port.text().strip().isdigit() else SMTP_RELAY_PORT,
            'daily_limit': int(self.daily_limit.currentText()),
            'custom_delay': float(self.custom_delay.text()) if self.custom_delay.text().replace('.', '').isdigit() else 3.0,
            'custom_cap': int(self.daily_limit.currentText()),
        }

    def validatePage(self):
        if not self.smtp_user.text().strip():
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź adres e-mail nadawcy.'))
            return False
        if not self.smtp_password.text():
            QMessageBox.warning(self, tr('Błąd'), tr('Wprowadź hasło do konta e-mail.'))
            return False
        return True
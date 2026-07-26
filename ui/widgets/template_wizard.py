# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QLabel, QTextEdit,
    QPushButton, QApplication, QMessageBox
)
from PySide6.QtCore import Qt
from ui.i18n import tr
from core.profile_manager import get_company_info

class IntroPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(tr("KROK 1: Twoja wiadomość"))
        self.setSubTitle(tr("Wpisz tutaj surową treść wiadomości (bez stopki). Na jej podstawie AI stworzy profesjonalny szablon z mieszaczem."))

        layout = QVBoxLayout(self)

        self.reminder = QLabel(tr("⚠️ Pamiętaj o uzupełnieniu danych firmy w zakładce Ustawienia! Dzięki temu AI lepiej dopasuje treść wiadomości."))
        self.reminder.setWordWrap(True)
        self.reminder.setStyleSheet("color: #fab387; font-weight: bold; border: 1px solid #fab387; padding: 10px; border-radius: 5px; margin-bottom: 10px;")
        layout.addWidget(self.reminder)

        self.user_msg_edit = QTextEdit()
        self.user_msg_edit.setPlaceholderText("np. Dzień dobry, chcialbym zaprosić Państwa do współpracy...")
        # Ważne: QTextEdit nie odświeża automatycznie stanu przycisku "Dalej"
        self.user_msg_edit.textChanged.connect(self.completeChanged)
        layout.addWidget(self.user_msg_edit)

    def isComplete(self):
        # Przycisk "Dalej" będzie aktywny tylko gdy wpisano tekst
        return bool(self.user_msg_edit.toPlainText().strip())

    def validatePage(self):
        # Zapisujemy ręcznie do pola, żeby było dostępne w PromptPage
        self.wizard().setProperty("user_msg_content", self.user_msg_edit.toPlainText())
        return True

class PromptPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(tr("KROK 2: Prompt dla AI"))
        self.setSubTitle(tr("Skopiuj poniższy prompt i wklej go do darmowego czatu AI (np. Gemini lub ChatGPT)."))

        layout = QVBoxLayout(self)

        self.prompt_display = QTextEdit()
        self.prompt_display.setReadOnly(True)
        self.prompt_display.setStyleSheet("background-color: #1e1e1e; color: #a6e3a1; font-family: monospace;")
        layout.addWidget(self.prompt_display)

        btn_copy = QPushButton(tr("📋 Kopiuj prompt do schowka"))
        btn_copy.setStyleSheet("background-color: #4a9eff; font-weight: bold; padding: 10px;")
        btn_copy.clicked.connect(self._copy_prompt)
        layout.addWidget(btn_copy)

        info = QLabel(tr("Instrukcja:") + "\n" + tr("1. Skopiuj prompt przyciskiem powyżej.\n2. Otwórz Gemini lub ChatGPT w przeglądarce.\n3. Wklej prompt i wyślij.\n4. AI wygeneruje gotowy szablon z mieszaczem ({{|}})."))
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; margin-top: 10px;")
        layout.addWidget(info)

    def initializePage(self):
        # Pobieramy treść zapisaną w validatePage poprzedniego kroku
        user_msg = self.wizard().property("user_msg_content") or ""
        company = get_company_info()

        # Ostrzeżenie jeśli brakuje kluczowych danych
        if not company.get("company_name") or not company.get("company_offer_description"):
            self.prompt_display.setStyleSheet("background-color: #1e1e1e; color: #f38ba8; font-family: monospace; border: 2px solid #f38ba8;")
        else:
            self.prompt_display.setStyleSheet("background-color: #1e1e1e; color: #a6e3a1; font-family: monospace;")

        prompt_tmpl = tr("AI_PROMPT_TEMPLATE")
        prompt = prompt_tmpl.format(
            user_msg=user_msg,
            company_name=company.get("company_name", "Moja Firma"),
            company_offer=company.get("company_offer_description", "nasza oferta"),
            company_website=company.get("company_website", "brak")
        )
        self.prompt_display.setPlainText(prompt)

    def _copy_prompt(self):
        QApplication.clipboard().setText(self.prompt_display.toPlainText())
        QMessageBox.information(self, tr("Sukces"), tr("Prompt skopiowany do schowka!"))

class ResultPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(tr("KROK 3: Wklej wynik z AI"))
        self.setSubTitle(tr("Wklej tutaj treść zwróconą przez AI. Program automatycznie wyczyści ją ze zbędnych tagów i zaktualizuje Twój szablon."))

        layout = QVBoxLayout(self)
        self.result_edit = QTextEdit()
        self.result_edit.setPlaceholderText(tr("Wklej wynik z AI..."))
        self.result_edit.textChanged.connect(self.completeChanged)
        layout.addWidget(self.result_edit)

    def isComplete(self):
        return bool(self.result_edit.toPlainText().strip())

    def validatePage(self):
        text = self.result_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, tr("Błąd"), tr("Wynik z AI nie może być pusty."))
            return False

        # --- PANCERNY SANITIZER ---
        # 1. Usuwamy tagi markdownowe (```) i wyciągamy tylko blok kodu jeśli istnieje
        if "```" in text:
            import re
            code_blocks = re.findall(r'```(?:[a-zA-Z]*)\n?(.*?)\n?```', text, re.DOTALL)
            if code_blocks:
                text = "\n\n".join(code_blocks).strip()
            else:
                # Fallback: po prostu usuń linie zaczynające się od ```
                text = "\n".join([line for line in text.splitlines() if not line.strip().startswith("```")]).strip()

        # 2. Naprawiamy nadmiarowe klamerki (częsty błąd darmowego AI)
        import re
        # Zastąp 3 lub więcej { na dokładnie 2 (dla spintaxu)
        text = re.sub(r'\{{3,}', '{{', text)
        # Zastąp 3 lub więcej } na dokładnie 2
        text = re.sub(r'\}{3,}', '}}', text)

        # 3. Usuwamy typowe wstępy AI
        if "Hier jest" in text or "Oto Twój" in text or "Your template" in text:
            # Jeśli tekst zawiera spintax, spróbujmy wyciąć wszystko przed pierwszym {{
            first_brace = text.find("{{")
            if first_brace > 10: # tylko jeśli jest jakiś znaczny wstęp
                text = text[first_brace:].strip()

        self.result_edit.setPlainText(text)
        # Zapisujemy do właściwości wizarda, aby odebrać w SendingView
        self.wizard().setProperty("final_ai_result", text)
        return True

class TemplateWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Kreator Szablonu AI"))
        self.resize(800, 600)

        self.addPage(IntroPage(self))
        self.addPage(PromptPage(self))
        self.addPage(ResultPage(self))

        self.setButtonText(QWizard.NextButton, tr("Dalej →"))
        self.setButtonText(QWizard.BackButton, tr("← Wstecz"))
        self.setButtonText(QWizard.FinishButton, tr("Zakończ i wstaw"))
        self.setButtonText(QWizard.CancelButton, tr("Anuluj"))

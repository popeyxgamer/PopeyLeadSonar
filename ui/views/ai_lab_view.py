# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QTabWidget, QWidget, QComboBox, QListWidget,
    QProgressBar, QTableWidget, QTableWidgetItem, QScrollArea, QGroupBox, QFormLayout, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from ui.views.base_view import BaseView
from ui.i18n import tr
from core.ai_features import (
    TemplateGenerator, SubjectLineOptimizer, LeadPersonalizer,
    LeadScorer, ResponseAnalyzer, SendTimingOptimizer, ABTestingEngine
)
from core.ai_providers import (
    ai_manager, OpenAIProvider, GeminiProvider, OllamaProvider,
    LMStudioProvider, DeepSeekLaudeProvider
)
from core.ai_workers import AIWorker, BatchAIWorker
from core.signal_bus import bus
from core import database as db
from core.config import logger

class AILabView(BaseView):
    def setup_ui(self):
        header = QLabel(tr("Laboratorium AI"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        self.layout.addWidget(header)

        # 1. Konfiguracja AI (na górze, widoczna zawsze lub w pierwszej zakładce)
        self._setup_config_group()

        # 2. Zakładki narzędzi
        self.ai_tabs = QTabWidget()
        self.layout.addWidget(self.ai_tabs)

        # Tab: Scoring
        self.tab_scoring = QWidget()
        self._setup_scoring_tab()
        self.ai_tabs.addTab(self.tab_scoring, tr("⭐ Ocena leadów"))

        # Tab: Szablony
        self.tab_templates = QWidget()
        self._setup_templates_tab()
        self.ai_tabs.addTab(self.tab_templates, tr("✉️ Szablony"))

        # Tab: Tematy
        self.tab_subjects = QWidget()
        self._setup_subjects_tab()
        self.ai_tabs.addTab(self.tab_subjects, tr("📝 Tematy"))

        # Tab: Analiza
        self.tab_analysis = QWidget()
        self._setup_analysis_tab()
        self.ai_tabs.addTab(self.tab_analysis, tr("📨 Analiza & Timing"))

        # Tab: A/B Testing
        self.tab_ab = QWidget()
        self._setup_ab_tab()
        self.ai_tabs.addTab(self.tab_ab, tr("🔀 Testy A/B"))

        self.status_label = QLabel(tr("Status: Gotowy"))
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        self.layout.addWidget(self.status_label)

        self.worker = AIWorker()
        self.worker.progress.connect(self.status_label.setText)
        self.worker.result.connect(self._on_worker_result)
        self.worker.finished.connect(lambda: self.status_label.setText(tr("Zadanie zakończone")))

        self.batch_worker = None
        self._load_ai_config()

    def setup_signals(self):
        bus.profile_changed.connect(self._on_profile_changed)

    def _on_profile_changed(self, name):
        self._load_ai_config()
        self.scoring_table.setRowCount(0)
        self.status_label.setText(tr("Profil zmieniony: {}").format(name))

    def _setup_config_group(self):
        group = QGroupBox(tr("⚙️ Konfiguracja dostawcy AI"))
        lay = QVBoxLayout(group)

        row_prov = QHBoxLayout()
        row_prov.addWidget(QLabel(tr("Provider:")))
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems(["OpenAI (ChatGPT)", "Google Gemini", "Ollama (Local)", "LM Studio (Local)", "DeepSeekLaude (Local)"])
        self.ai_provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        row_prov.addWidget(self.ai_provider_combo)

        btn_test = QPushButton(tr("Test połączenia"))
        btn_test.clicked.connect(self._test_ai_connection)
        row_prov.addWidget(btn_test)

        btn_save = QPushButton(tr("Zapisz konfigurację AI"))
        btn_save.clicked.connect(self._save_ai_config)
        btn_save.setStyleSheet("background-color: #3d3d3d;")
        row_prov.addWidget(btn_save)
        lay.addLayout(row_prov)

        # Dynamic config widgets
        self.cfg_stack = QWidget()
        self.cfg_layout = QVBoxLayout(self.cfg_stack)

        # OpenAI
        self.pane_openai = QWidget()
        f_o = QFormLayout(self.pane_openai)
        self.ai_openai_key = QLineEdit(); self.ai_openai_key.setEchoMode(QLineEdit.Password)
        f_o.addRow("API Key:", self.ai_openai_key)
        self.ai_openai_model = QComboBox(); self.ai_openai_model.addItems(["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"])
        f_o.addRow("Model:", self.ai_openai_model)
        self.cfg_layout.addWidget(self.pane_openai)

        # Gemini
        self.pane_gemini = QWidget()
        f_g = QFormLayout(self.pane_gemini)
        self.ai_gemini_key = QLineEdit(); self.ai_gemini_key.setEchoMode(QLineEdit.Password)
        f_g.addRow("API Key:", self.ai_gemini_key)
        self.cfg_layout.addWidget(self.pane_gemini)

        # Ollama
        self.pane_ollama = QWidget()
        f_ol = QFormLayout(self.pane_ollama)
        self.ai_ollama_url = QLineEdit("http://localhost:11434")
        f_ol.addRow("URL:", self.ai_ollama_url)
        self.ai_ollama_model = QLineEdit("llama3")
        f_ol.addRow("Model:", self.ai_ollama_model)
        self.cfg_layout.addWidget(self.pane_ollama)

        lay.addWidget(self.cfg_stack)
        self.layout.addWidget(group)

    def _setup_scoring_tab(self):
        lay = QVBoxLayout(self.tab_scoring)
        lay.addWidget(QLabel(tr("Seryjne ocenianie jakości leadów")))

        btn_row = QHBoxLayout()
        self.btn_score_all = QPushButton(tr("Oceń WSZYSTKIE nowe leady"))
        self.btn_score_all.clicked.connect(self._run_batch_scoring)
        btn_row.addWidget(self.btn_score_all)

        self.btn_score_stop = QPushButton(tr("STOP"))
        self.btn_score_stop.setEnabled(False)
        btn_row.addWidget(self.btn_score_stop)
        lay.addLayout(btn_row)

        self.scoring_progress = QProgressBar()
        lay.addWidget(self.scoring_progress)

        self.scoring_table = QTableWidget()
        self.scoring_table.setColumnCount(4)
        self.scoring_table.setHorizontalHeaderLabels([tr("Email"), tr("Score"), tr("Spam?"), tr("Powód")])
        lay.addWidget(self.scoring_table)

    def _setup_templates_tab(self):
        lay = QVBoxLayout(self.tab_templates)
        form = QFormLayout()
        self.industry_input = QLineEdit()
        form.addRow(tr("Branża:"), self.industry_input)
        self.product_input = QLineEdit()
        form.addRow(tr("Produkt:"), self.product_input)
        lay.addLayout(form)

        self.btn_gen_tmpl = QPushButton(tr("Generuj szablony"))
        self.btn_gen_tmpl.clicked.connect(self._generate_templates)
        lay.addWidget(self.btn_gen_tmpl)

        self.templates_output = QTextEdit()
        lay.addWidget(self.templates_output)

    def _setup_subjects_tab(self):
        lay = QVBoxLayout(self.tab_subjects)
        self.subj_topic = QLineEdit()
        lay.addWidget(QLabel(tr("Temat kampanii:")))
        lay.addWidget(self.subj_topic)
        self.btn_gen_subj = QPushButton(tr("Generuj warianty tematów"))
        self.btn_gen_subj.clicked.connect(self._generate_subjects)
        lay.addWidget(self.btn_gen_subj)
        self.subj_list = QListWidget()
        lay.addWidget(self.subj_list)

    def _setup_analysis_tab(self):
        lay = QVBoxLayout(self.tab_analysis)
        lay.addWidget(QLabel(tr("Analiza odpowiedzi & Timing")))

        self.resp_input = QTextEdit()
        self.resp_input.setPlaceholderText(tr("Wklej treść otrzymanej odpowiedzi..."))
        self.resp_input.setMaximumHeight(100)
        lay.addWidget(self.resp_input)

        btn_anal = QPushButton(tr("Analizuj sentyment i intencję"))
        btn_anal.clicked.connect(self._analyze_response)
        lay.addWidget(btn_anal)

        lay.addWidget(QLabel(tr("Optymalizacja czasu wysyłki (Timing):")))
        row_t = QHBoxLayout()
        self.timing_industry = QLineEdit(); self.timing_industry.setPlaceholderText("Branża")
        row_t.addWidget(self.timing_industry)
        btn_time = QPushButton(tr("Oblicz najlepszy czas"))
        btn_time.clicked.connect(self._get_timing)
        row_t.addWidget(btn_time)
        lay.addLayout(row_t)

        self.anal_output = QTextEdit(); self.anal_output.setReadOnly(True)
        lay.addWidget(self.anal_output)

    def _setup_ab_tab(self):
        lay = QVBoxLayout(self.tab_ab)
        lay.addWidget(QLabel(tr("Generator wariantów A/B")))

        self.ab_original = QTextEdit()
        self.ab_original.setPlaceholderText(tr("Wklej oryginał (temat lub treść)..."))
        self.ab_original.setMaximumHeight(100)
        lay.addWidget(self.ab_original)

        btn_ab = QPushButton(tr("Generuj 2 alternatywne warianty"))
        btn_ab.clicked.connect(self._generate_ab)
        lay.addWidget(btn_ab)

        self.ab_output = QTextEdit(); self.ab_output.setReadOnly(True)
        lay.addWidget(self.ab_output)

    # Logic
    def _on_provider_changed(self, idx):
        self.pane_openai.setVisible(idx == 0)
        self.pane_gemini.setVisible(idx == 1)
        self.pane_ollama.setVisible(idx >= 2)

    def _load_ai_config(self):
        prov = db.get_setting("ai_provider", "openai")
        idx_map = {"openai": 0, "gemini": 1, "ollama": 2, "lmstudio": 3, "deepseeklaude": 4}
        self.ai_provider_combo.setCurrentIndex(idx_map.get(prov, 0))

        self.ai_openai_key.setText(db.get_setting("ai_openai_key", ""))
        self.ai_gemini_key.setText(db.get_setting("ai_gemini_key", ""))
        self.ai_ollama_url.setText(db.get_setting("ai_ollama_url", "http://localhost:11434"))
        self.ai_ollama_model.setText(db.get_setting("ai_ollama_model", "llama3"))

        self._on_provider_changed(self.ai_provider_combo.currentIndex())
        self._activate_provider(prov)

    def _save_ai_config(self):
        idx = self.ai_provider_combo.currentIndex()
        prov_id = ["openai", "gemini", "ollama", "lmstudio", "deepseeklaude"][idx]

        db.set_setting("ai_provider", prov_id)
        db.set_setting("ai_openai_key", self.ai_openai_key.text())
        db.set_setting("ai_gemini_key", self.ai_gemini_key.text())
        db.set_setting("ai_ollama_url", self.ai_ollama_url.text())
        db.set_setting("ai_ollama_model", self.ai_ollama_model.text())

        self._activate_provider(prov_id)
        bus.show_message.emit("AI", tr("Konfiguracja zapisana!"))

    def _activate_provider(self, prov_id):
        try:
            if prov_id == "openai":
                p = OpenAIProvider(self.ai_openai_key.text(), self.ai_openai_model.currentText())
            elif prov_id == "gemini":
                p = GeminiProvider(self.ai_gemini_key.text())
            elif prov_id == "ollama":
                p = OllamaProvider(self.ai_ollama_url.text(), self.ai_ollama_model.text())
            else: return

            ai_manager.register_provider(prov_id, p)
            ai_manager.set_active_provider(prov_id)
        except Exception as e:
            logger.error("Błąd aktywacji AI: %s", e)

    def _test_ai_connection(self):
        p = ai_manager.get_active_provider()
        if not p: return
        self.status_label.setText(tr("Testowanie..."))
        if p.check_connection():
            bus.show_message.emit("AI", tr("Połączenie z {} działa!").format(p.name))
        else:
            bus.show_message.emit("AI Błąd", tr("Nie można połączyć z {}").format(p.name))

    def _run_batch_scoring(self):
        leads = db.get_unscored_leads()
        if not leads: return

        leads_data = [{"id": r[0], "firma": r[1], "email": r[2], "website": r[3]} for r in leads]
        self.batch_worker = BatchAIWorker(leads_data, "score")
        self.batch_worker.progress.connect(lambda c, t: self.scoring_progress.setValue(int(c*100/t)))
        self.batch_worker.lead_result.connect(self._on_scoring_result)
        self.batch_worker.start()
        self.btn_score_all.setEnabled(False)

    def _on_scoring_result(self, email, result):
        if result.get("type") == "score" and result.get("data"):
            d = result["data"]
            row = self.scoring_table.rowCount()
            self.scoring_table.insertRow(row)
            self.scoring_table.setItem(row, 0, QTableWidgetItem(email))
            self.scoring_table.setItem(row, 1, QTableWidgetItem(str(d.get("score", 0))))
            self.scoring_table.setItem(row, 2, QTableWidgetItem("TAK" if d.get("is_spam") else "NIE"))
            self.scoring_table.setItem(row, 3, QTableWidgetItem(d.get("reason", "")[:50]))
            db.update_lead_score(0, d.get("score", 0), d.get("reason", "")) # Simplified ID handling

    def _generate_templates(self):
        self.worker.add_task("generate_templates",
                           industry=self.industry_input.text(),
                           product=self.product_input.text())
        self.worker.start()

    def _generate_subjects(self):
        self.worker.add_task("generate_subject_lines",
                           topic=self.subj_topic.text(),
                           industry="general")
        self.worker.start()

    def _analyze_response(self):
        self.worker.add_task("analyze_response",
                           email_body=self.resp_input.toPlainText())
        self.worker.start()

    def _get_timing(self):
        self.worker.add_task("get_send_timing",
                           industry=self.timing_industry.text(),
                           region="PL")
        self.worker.start()

    def _generate_ab(self):
        self.worker.add_task("generate_ab_variants",
                           content_type="email",
                           original=self.ab_original.toPlainText())
        self.worker.start()

    def _on_worker_result(self, res):
        t = res.get("type")
        d = res.get("data", {})

        if t == "generate_templates":
            if d.get("templates"):
                self.templates_output.setPlainText("\n\n---\n\n".join(d["templates"]))
        elif t == "generate_subject_lines":
            if d.get("variants"):
                self.subj_list.clear(); self.subj_list.addItems(d["variants"])
        elif t == "analyze_response":
            self.anal_output.setPlainText(str(d.get("analysis", "")))
        elif t == "get_send_timing":
            self.anal_output.setPlainText(str(d.get("timing", "")))
        elif t == "generate_ab_variants":
            if d.get("variants"):
                self.ab_output.setPlainText("\n\n---\n\n".join(d["variants"]))

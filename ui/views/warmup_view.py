# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QListWidget, QGroupBox, QSpinBox,
    QCheckBox, QMessageBox, QScrollArea, QWidget, QInputDialog, QListWidgetItem
)
from PySide6.QtCore import Qt
from ui.views.base_view import BaseView
from ui.i18n import tr
from core.profile_manager import get_current_profile_settings
from core.workers import WarmupWorker
from core.signal_bus import bus
from core import database as db

class WarmupView(BaseView):
    def setup_ui(self):
        header = QLabel(tr("Email Warm-up (Rozgrzewanie skrzynek)"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        self.layout.addWidget(header)

        main_lay = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # --- LEFT: Config ---
        intro = QLabel(tr(
            "Rozgrzewanie polega na wysyłaniu małych ilości maili do zaufanych adresów, "
            "aby zbudować reputację Twojej domeny. System wykorzystuje Twoje konta SMTP."
        ))
        intro.setWordWrap(True); intro.setStyleSheet("color: #888;"); left_col.addWidget(intro)

        status_group = QGroupBox(tr("Status Rozgrzewania"))
        status_lay = QVBoxLayout(status_group)
        self.status_label = QLabel(tr("Status: Nieaktywny"))
        status_lay.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        status_lay.addWidget(self.progress_bar)
        left_col.addWidget(status_group)

        cfg_group = QGroupBox(tr("Konfiguracja"))
        cfg_lay = QVBoxLayout(cfg_group)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(tr("Dzienny przyrost:")))
        self.increase_spin = QSpinBox(); self.increase_spin.setRange(1, 10); self.increase_spin.setValue(2)
        row1.addWidget(self.increase_spin)
        row1.addWidget(QLabel(tr("Maks/dzień:")))
        self.max_spin = QSpinBox(); self.max_spin.setRange(10, 200); self.max_spin.setValue(50)
        row1.addWidget(self.max_spin)
        cfg_lay.addLayout(row1)
        self.auto_reply = QCheckBox(tr("Auto-odpowiedzi (wymaga IMAP)"))
        self.auto_reply.setChecked(True)
        cfg_lay.addWidget(self.auto_reply)
        left_col.addWidget(cfg_group)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton(tr("🚀 URUCHOM WARM-UP"))
        self.btn_start.setStyleSheet("background-color: #2b5e2b; font-weight: bold; padding: 12px;")
        self.btn_start.clicked.connect(self._start_warmup)
        btn_row.addWidget(self.btn_start)
        self.btn_stop = QPushButton(tr("⏹️ STOP"))
        self.btn_stop.setStyleSheet("background-color: #8b0000; font-weight: bold;")
        self.btn_stop.clicked.connect(self._stop_warmup); self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_stop)
        left_col.addLayout(btn_row)
        left_col.addStretch()

        # --- RIGHT: Targets ---
        targets_group = QGroupBox(tr("🎯 Zaufane adresy odbiorcze (Twoje inne maile)"))
        targets_lay = QVBoxLayout(targets_group)
        self.targets_list = QListWidget()
        targets_lay.addWidget(self.targets_list)

        t_btn_row = QHBoxLayout()
        self.btn_add_target = QPushButton(tr("➕ Dodaj adres"))
        self.btn_add_target.clicked.connect(self._add_target)
        t_btn_row.addWidget(self.btn_add_target)
        self.btn_del_target = QPushButton(tr("🗑 Usuń"))
        self.btn_del_target.clicked.connect(self._remove_target)
        t_btn_row.addWidget(self.btn_del_target)
        targets_lay.addLayout(t_btn_row)
        right_col.addWidget(targets_group)

        main_lay.addLayout(left_col, 1)
        main_lay.addLayout(right_col, 1)
        self.layout.addLayout(main_lay)

        self.worker = None
        self.refresh_data()

    def setup_signals(self):
        bus.profile_changed.connect(self.refresh_data)

    def refresh_data(self):
        self.targets_list.clear()
        for t in db.get_warmup_targets():
            item = QListWidgetItem(t["email"])
            item.setData(Qt.UserRole, t["id"])
            self.targets_list.addItem(item)

    def _add_target(self):
        email, ok = QInputDialog.getText(self, tr("Dodaj cel"), tr("Adres e-mail:"))
        if ok and email:
            if db.add_warmup_target(email): self.refresh_data()

    def _remove_target(self):
        idx = self.targets_list.currentRow()
        if idx >= 0:
            tid = self.targets_list.item(idx).data(Qt.UserRole)
            db.delete_warmup_target(tid); self.refresh_data()

    def _start_warmup(self):
        self.worker = WarmupWorker(self.increase_spin.value(), self.max_spin.value(), self.auto_reply.isChecked())
        self.worker.status.connect(self.status_label.setText)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.start()
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        bus.show_message.emit("Warm-up", tr("Silnik rozgrzewania aktywny."))

    def _stop_warmup(self):
        if self.worker: self.worker.stop()
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)
        self.status_label.setText(tr("Status: Zatrzymany"))

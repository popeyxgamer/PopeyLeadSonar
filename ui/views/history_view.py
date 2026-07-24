# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from ui.views.base_view import BaseView
from ui.i18n import tr
from ui.styles import COLOR_OK, COLOR_ERROR
from core import database as db
from core.signal_bus import bus

class HistoryView(BaseView):
    def setup_ui(self):
        header = QLabel(tr("Historia i Logi Wysyłki"))
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        self.layout.addWidget(header)

        # Toolbar
        row = QHBoxLayout()
        btn_refresh = QPushButton(tr('🔄 Odśwież logi'))
        btn_refresh.clicked.connect(self.refresh_history)
        row.addWidget(btn_refresh)

        btn_clear = QPushButton(tr('🗑 Wyczyść stare logi (>30 dni)'))
        btn_clear.clicked.connect(self.clear_old_logs)
        row.addWidget(btn_clear)

        row.addStretch()
        self.layout.addLayout(row)

        # Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            tr('Data'), tr('Email'), tr('Status'), tr('Temat'), tr('Błąd')
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.layout.addWidget(self.history_table)

        self.refresh_history()

    def setup_signals(self):
        bus.email_sent.connect(self.refresh_history)
        bus.profile_changed.connect(self.refresh_history)

    def refresh_history(self):
        rows = db.get_history(limit=500)
        self.history_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val else "")
                if j == 2: # Status column
                    if val == 'wysłano':
                        item.setBackground(QColor(*COLOR_OK))
                    elif val == 'błąd':
                        item.setBackground(QColor(*COLOR_ERROR))
                self.history_table.setItem(i, j, item)

    def clear_old_logs(self):
        reply = QMessageBox.question(
            self, tr('Potwierdzenie'), tr('Usunąć logi starsze niż 30 dni?'),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            removed = db.clear_old_logs(days=30)
            self.refresh_history()
            QMessageBox.information(self, tr('OK'), f"Usunięto {removed} wpisów.")

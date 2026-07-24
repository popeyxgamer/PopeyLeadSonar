# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QMovie
from ui.views.base_view import BaseView
from ui.i18n import tr
from core import database as db
from core.signal_bus import bus
from core.config import logger
from ui.styles import COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_SECONDARY, COLOR_BG, COLOR_BORDER, COLOR_SURFACE

from datetime import datetime, timedelta

# Matplotlib setup
try:
    import matplotlib
    # Dla PySide6 zalecanym backendem jest 'qtagg' lub 'QtAgg'
    try:
        matplotlib.use('qtagg')
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    except Exception:
        matplotlib.use('Qt5Agg')
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

class StatCard(QFrame):
    def __init__(self, title, value, color="#89b4fa"):
        super().__init__()
        self.setObjectName("StatCard")
        self.setMinimumSize(180, 110)
        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 16px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: bold; text-transform: uppercase;")

        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 900;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def update_value(self, value):
        self.value_label.setText(str(value))

class DashboardView(BaseView):
    def setup_ui(self):
        # 1. Header
        header = QLabel(tr("Pulpit Sterowniczy"))
        header.setStyleSheet("font-size: 26px; font-weight: 900; color: #cdd6f4;")
        self.layout.addWidget(header)
        self.layout.addSpacing(10)

        # 2. Stats Row
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(20)

        self.card_total = StatCard(tr("WSZYSTKIE LEADY"), 0, COLOR_ACCENT)
        self.card_sent = StatCard(tr("WYSŁANO"), 0, COLOR_SUCCESS)
        self.card_resp = StatCard(tr("ODPOWIEDZI"), 0, COLOR_WARNING)
        self.card_conv = StatCard(tr("KONWERSJA"), "0%", COLOR_SECONDARY)

        self.stats_row.addWidget(self.card_total)
        self.stats_row.addWidget(self.card_sent)
        self.stats_row.addWidget(self.card_resp)
        self.stats_row.addWidget(self.card_conv)

        self.layout.addLayout(self.stats_row)
        self.layout.addSpacing(20)

        # 3. Chart
        self.chart_frame = QFrame()
        self.chart_frame.setStyleSheet(f"background-color: #1e1e2e; border: 1px solid #313244; border-radius: 20px;")
        self.chart_lay = QVBoxLayout(self.chart_frame)
        self.layout.addWidget(self.chart_frame, stretch=1)

        # 4. Donation Footer
        self.donate_row = QHBoxLayout()
        self.donate_row.addStretch()

        self.donate_card = QFrame()
        self.donate_card.setStyleSheet("background-color: #313244; border-radius: 15px; border: 1px solid #45475a;")
        self.donate_card.setFixedHeight(80)
        d_lay = QHBoxLayout(self.donate_card)
        d_lay.setContentsMargins(15, 5, 15, 5)

        self.money_label = QLabel("$")
        self.money_label.setStyleSheet("font-size: 40px; font-weight: 900; color: #a6e3a1; margin-right: 10px;")
        d_lay.addWidget(self.money_label)

        d_info = QVBoxLayout()
        d_title = QLabel(tr("Wsparcie projektu"))
        d_title.setStyleSheet("font-weight: bold; color: #cba6f7; font-size: 14px;")
        d_info.addWidget(d_title)

        self.btn_donate = QPushButton(tr("Kliknij, aby wesprzeć projekt na Tipply"))
        self.btn_donate.setStyleSheet("background: transparent; color: #89b4fa; text-decoration: underline; border: none; font-weight: normal; text-align: left;")
        self.btn_donate.setCursor(Qt.PointingHandCursor)
        self.btn_donate.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://tipply.pl/@Papajgejmer")))
        d_info.addWidget(self.btn_donate)
        d_lay.addLayout(d_info)

        self.donate_row.addWidget(self.donate_card)
        self.donate_row.addStretch()
        self.layout.addLayout(self.donate_row)

        self.canvas = None

    def setup_signals(self):
        bus.leads_changed.connect(self.refresh_stats)
        bus.email_sent.connect(self.refresh_stats)
        bus.profile_changed.connect(self.refresh_stats)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(300, self.refresh_stats)

    def refresh_stats(self):
        try:
            total = db.count_leads()
            sent = db.count_leads(status='wysłano')
            resp = db.count_leads(status='responded')
            conv = (resp / sent * 100) if sent > 0 else 0

            self.card_total.update_value(total)
            self.card_sent.update_value(sent)
            self.card_resp.update_value(resp)
            self.card_conv.update_value(f"{conv:.1f}%")

            self._update_chart()
        except Exception as e:
            logger.error("Dashboard refresh error: %s", e)

    def _update_chart(self):
        if not MATPLOTLIB_AVAILABLE: return
        try:
            if self.canvas:
                self.chart_lay.removeWidget(self.canvas)
                self.canvas.deleteLater()

            # Pobieramy dane z ostatnich 7 dni
            end = datetime.now()
            start = end - timedelta(days=7)

            # Pobranie danych z bazy (uproszczone pobieranie)
            days = [(start + timedelta(days=i)).date().isoformat() for i in range(8)]
            data_sent = [0] * 8
            data_resp = [0] * 8

            fig = Figure(figsize=(8, 4), dpi=100, facecolor=COLOR_BG)
            ax = fig.add_subplot(111)
            ax.set_facecolor(COLOR_BG)

            import numpy as np
            x = range(len(days))
            ax.bar(x, data_sent, color=COLOR_ACCENT, alpha=0.5)
            ax.bar(x, data_resp, color=COLOR_WARNING, alpha=0.5)

            ax.set_xticks(x)
            ax.set_xticklabels(days, rotation=45, ha='right', color='white', fontsize=8)
            ax.tick_params(colors='white')

            fig.tight_layout()
            self.canvas = FigureCanvasQTAgg(fig)
            self.chart_lay.addWidget(self.canvas)
        except Exception as e:
            logger.error("Chart error: %s", e)

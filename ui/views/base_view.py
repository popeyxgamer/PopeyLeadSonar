# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from core.signal_bus import bus

class BaseView(QWidget):
    """Bazowa klasa dla wszystkich widoków w aplikacji."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(20)

        # Inicjalizacja połączeń sygnałów (do nadpisania w podklasach)
        self.setup_ui()
        self.setup_signals()

    def setup_ui(self):
        """Metoda do budowania interfejsu."""
        pass

    def setup_signals(self):
        """Metoda do podłączania sygnałów z bus."""
        pass

    def add_scroll_area(self, widget: QWidget):
        """Pomocnicza metoda do opakowania widgetu w scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.layout.addWidget(scroll)

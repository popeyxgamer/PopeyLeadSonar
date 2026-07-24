# -*- coding: utf-8 -*-
"""Zmodernizowany arkusz stylów PopeyLeadSonar Designer's Cut."""

from core.default_profile import (  # noqa: F401
    DEFAULT_LOCATIONS, DEFAULT_PROFILE_NAME, DEFAULT_QUERIES, DEFAULT_SUBJECT,
    DEFAULT_TEMPLATE,
)

# ----------------------------------------------------------------------
# NOWOCZESNA PALETA BARW (CATPPUCCIN MOCHA INSPIRATION)
# ----------------------------------------------------------------------
COLOR_BG = "#1e1e2e"
COLOR_SURFACE = "#313244"
COLOR_OVERLAY = "#45475a"
COLOR_TEXT = "#cdd6f4"
COLOR_SUBTEXT = "#a6adc8"
COLOR_ACCENT = "#89b4fa"      # Blue
COLOR_SECONDARY = "#cba6f7"   # Mauve (AI)
COLOR_SUCCESS = "#a6e3a1"     # Green
COLOR_ERROR = "#f38ba8"       # Red
COLOR_WARNING = "#f9e2af"     # Yellow
COLOR_BORDER = "#313244"
# ----------------------------------------------------------------------

DARK_STYLESHEET = f"""
QMainWindow {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
}}

QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
}}

/* ---- SCROLL AREA ---- */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

/* ---- TAB WIDGET ---- */
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    background-color: {COLOR_BG};
    margin-top: -1px;
}}

QTabBar::tab {{
    background-color: {COLOR_BG};
    color: {COLOR_SUBTEXT};
    padding: 10px 20px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    border-bottom: 2px solid {COLOR_ACCENT};
}}

QTabBar::tab:hover:!selected {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT};
}}

/* ---- INPUTS & COMBOBOX ---- */
QLineEdit, QTextEdit, QComboBox, QListWidget, QTableWidget, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_OVERLAY};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {COLOR_ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {COLOR_ACCENT};
    background-color: #242437;
}}

QComboBox::drop-down {{ border: none; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {COLOR_SUBTEXT};
    margin-right: 10px;
}}

/* ---- PUSH BUTTONS ---- */
QPushButton {{
    background-color: {COLOR_OVERLAY};
    color: {COLOR_TEXT};
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {COLOR_ACCENT};
    color: {COLOR_BG};
}}

QPushButton:pressed {{
    background-color: #74a0f8;
}}

QPushButton:disabled {{
    background-color: {COLOR_BG};
    color: #585b70;
    border: 1px solid {COLOR_BORDER};
}}

/* ---- GROUP BOX ---- */
QGroupBox {{
    margin-top: 15px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    padding: 20px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 15px;
    padding: 0 8px;
    color: {COLOR_ACCENT};
}}

/* ---- TABLE WIDGET ---- */
QHeaderView::section {{
    background-color: {COLOR_BG};
    color: {COLOR_SUBTEXT};
    padding: 10px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
    font-weight: bold;
    text-transform: uppercase;
}}

QTableWidget::item {{
    padding: 10px;
    border-bottom: 1px solid {COLOR_BORDER};
}}

QTableWidget::item:selected {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_ACCENT};
}}

/* ---- PROGRESS BAR ---- */
QProgressBar {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_OVERLAY};
    border-radius: 10px;
    text-align: center;
    height: 20px;
}}

QProgressBar::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: 8px;
}}

/* ---- CHECKBOX ---- */
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLOR_OVERLAY};
    border-radius: 4px;
    background-color: {COLOR_BG};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
}}

/* ---- SCROLLBARS ---- */
QScrollBar:vertical {{
    background-color: {COLOR_BG};
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLOR_OVERLAY};
    min-height: 20px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLOR_SUBTEXT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

/* ---- TOOLTIP ---- */
QToolTip {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_ACCENT};
    padding: 5px;
    border-radius: 4px;
}}
"""

# Kolory statusów (RGBA) - pasujące do palety Catppuccin
COLOR_SENT_OK = (166, 227, 161, 60)    # Green alpha 60
COLOR_SENT_ERROR = (243, 139, 168, 60) # Red alpha 60
COLOR_LIST_HIGHLIGHT = (137, 180, 250, 40) # Blue alpha 40

# Dla kompatybilności wstecznej (jeśli gdzieś zostały użyte stare nazwy)
COLOR_OK = COLOR_SENT_OK
COLOR_ERROR = COLOR_SENT_ERROR
COLOR_SENT_LIST = COLOR_LIST_HIGHLIGHT
COLOR_SENT_LIST_ALT = COLOR_SENT_ERROR

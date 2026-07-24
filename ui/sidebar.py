# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QRect, QEasingCurve, QPoint, QTimer
from PySide6.QtGui import QIcon, QColor

from ui.i18n import tr

class SidebarButton(QPushButton):
    def __init__(self, text, icon_text="", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setMinimumHeight(45)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(f"  {icon_text}   {text}")
        self.setStyleSheet("""
            SidebarButton {
                background-color: transparent;
                border: none;
                border-radius: 10px;
                color: #a6adc8;
                font-size: 13px;
                font-weight: 500;
                text-align: left;
                padding-left: 20px;
                margin: 2px 0;
            }
            SidebarButton:hover {
                background-color: #313244;
                color: #cdd6f4;
            }
            SidebarButton:checked {
                color: #89b4fa;
                font-weight: 700;
                background-color: #313244;
            }
        """)

    def enterEvent(self, event):
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(200)
        self.anim.setEndValue(QPoint(self.x() + 5, self.y()))
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(200)
        self.anim.setEndValue(QPoint(self.x() - 5, self.y()))
        self.anim.start()
        super().leaveEvent(event)

        # Add transition effect (simulated via animation if needed, but CSS hover is enough for now)

class Sidebar(QWidget):
    indexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setObjectName("Sidebar")
        self.setStyleSheet("""
            #Sidebar {
                background-color: #11111b;
                border-right: 1px solid #313244;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 30, 15, 20)
        self.layout.setSpacing(8)

        # Logo / Title
        logo_container = QHBoxLayout()
        logo_icon = QLabel("🎯")
        logo_icon.setStyleSheet("font-size: 24px; background: transparent;")
        logo_text = QLabel("PopeyLeadSonar")
        logo_text.setStyleSheet("font-size: 20px; font-weight: 900; color: #cdd6f4; background: transparent;")
        logo_container.addWidget(logo_icon)
        logo_container.addWidget(logo_text)
        logo_container.addStretch()
        self.layout.addLayout(logo_container)

        self.layout.addSpacing(30)

        # Container for buttons with relative positioning for indicator
        self.btn_container = QWidget()
        self.btn_container.setStyleSheet("background: transparent;")
        self.btn_lay = QVBoxLayout(self.btn_container)
        self.btn_lay.setContentsMargins(0, 0, 0, 0)
        self.btn_lay.setSpacing(8)

        # Indicator (animated bar)
        self.indicator = QFrame(self)
        self.indicator.setFixedWidth(4)
        self.indicator.setFixedHeight(24)
        self.indicator.setStyleSheet("background-color: #89b4fa; border-radius: 2px;")
        self.indicator.raise_()

        self.button_group = QButtonGroup(self)
        self.button_group.idClicked.connect(self._on_button_clicked)

        self.buttons = []
        self._add_btn(tr("Dashboard"), "🏠", 0)
        self._add_btn(tr("Kampania"), "🔍", 1)
        self._add_btn(tr("Sekwencje"), "🧬", 2)
        self._add_btn(tr("Warm-up"), "🔥", 3)
        self._add_btn(tr("Wysyłka"), "📤", 4)
        self._add_btn(tr("Leadzy"), "📋", 5)
        self._add_btn(tr("Skrzynka"), "📥", 6)
        self._add_btn(tr("Historia"), "📜", 7)
        self._add_btn(tr("AI Lab"), "🤖", 8)
        self._add_btn(tr("Ustawienia"), "⚙️", 9)

        self.layout.addWidget(self.btn_container)
        self.layout.addStretch()

        # Profile Card
        self.profile_card = QFrame()
        self.profile_card.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 12px;
                padding: 10px;
                border: 1px solid #313244;
            }
        """)
        pc_lay = QVBoxLayout(self.profile_card)
        pc_lay.setContentsMargins(10, 10, 10, 10)

        self.profile_label = QLabel(tr("Profil: default"))
        self.profile_label.setStyleSheet("color: #cdd6f4; font-weight: bold; border: none; background: transparent;")
        pc_lay.addWidget(self.profile_label)

        status_label = QLabel(tr("● Aktywny"))
        status_label.setStyleSheet("color: #a6e3a1; font-size: 10px; border: none; background: transparent;")
        pc_lay.addWidget(status_label)

        self.layout.addWidget(self.profile_card)

        # Default select
        if self.buttons:
            self.buttons[0].setChecked(True)
            QTimer.singleShot(100, lambda: self._animate_indicator(0))

    def _add_btn(self, text, icon, index):
        btn = SidebarButton(text, icon)
        self.btn_lay.addWidget(btn)
        self.button_group.addButton(btn, index)
        self.buttons.append(btn)

    def _on_button_clicked(self, index):
        self.indexChanged.emit(index)
        self._animate_indicator(index)

    def _animate_indicator(self, index):
        btn = self.button_group.button(index)
        if not btn: return

        # Position of button relative to sidebar
        btn_pos = btn.mapTo(self, QPoint(0, 0))
        y = btn_pos.y() + (btn.height() - self.indicator.height()) // 2

        self.anim = QPropertyAnimation(self.indicator, b"pos")
        self.anim.setDuration(350)
        self.anim.setEasingCurve(QEasingCurve.OutExpo)
        self.anim.setEndValue(QPoint(5, y))
        self.anim.start()
        self.indicator.show()

    def set_active_profile(self, name):
        self.profile_label.setText(tr("Profil: {}").format(name))

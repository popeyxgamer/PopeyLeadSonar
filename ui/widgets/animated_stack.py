# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QStackedWidget, QWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup

class AnimatedStackedWidget(QStackedWidget):
    """
    Ulepszony QStackedWidget z płynną animacją przesunięcia.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 400
        self.easing = QEasingCurve.OutCubic
        self.animation_group = QParallelAnimationGroup(self)
        self.animation_group.finished.connect(self._on_animation_finished)
        self._current_index = 0
        self._next_index = 0
        self._is_animating = False

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex() or index < 0 or index >= self.count():
            return

        # Jeśli poprzednia animacja trwa, zatrzymujemy ją i wymuszamy koniec
        if self._is_animating:
            self.animation_group.stop()
            self.animation_group.clear()
            self._is_animating = False

        self._next_index = index
        self._current_index = self.currentIndex()

        cur_w = self.widget(self._current_index)
        next_w = self.widget(self._next_index)

        if not cur_w or not next_w:
            super().setCurrentIndex(index)
            return

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            super().setCurrentIndex(index)
            return

        # Przygotuj widgety do animacji
        next_w.setGeometry(0, 0, w, h)
        direction = "up" if index > self._current_index else "down"
        offset = h if direction == "up" else -h

        next_w.move(0, offset)
        next_w.show()
        next_w.raise_()

        # Animacja wejścia nowego (tworzymy nowe obiekty animacji)
        anim_next = QPropertyAnimation(next_w, b"pos", self)
        anim_next.setDuration(self.duration)
        anim_next.setEasingCurve(self.easing)
        anim_next.setStartValue(QPoint(0, offset))
        anim_next.setEndValue(QPoint(0, 0))

        # Animacja wyjścia starego
        anim_cur = QPropertyAnimation(cur_w, b"pos", self)
        anim_cur.setDuration(self.duration)
        anim_cur.setEasingCurve(self.easing)
        anim_cur.setStartValue(QPoint(0, 0))
        anim_cur.setEndValue(QPoint(0, -offset))

        self.animation_group.clear()
        self.animation_group.addAnimation(anim_next)
        self.animation_group.addAnimation(anim_cur)

        self._is_animating = True
        self.animation_group.start()

    def _on_animation_finished(self):
        if not self._is_animating: return

        super().setCurrentIndex(self._next_index)

        # Resetujemy stan starego widgetu
        prev_w = self.widget(self._current_index)
        if prev_w:
            prev_w.hide()
            prev_w.move(0, 0)

        self._is_animating = False

    def resizeEvent(self, event):
        # Upewniamy się, że aktualny widget zawsze wypełnia przestrzeń
        if self.widget(self.currentIndex()):
            self.widget(self.currentIndex()).resize(self.size())
        super().resizeEvent(event)

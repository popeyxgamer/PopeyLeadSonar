# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QStackedWidget, QWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup

class AnimatedStackedWidget(QStackedWidget):
    """
    Ulepszony QStackedWidget z płynną animacją przesunięcia.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 350
        self.easing = QEasingCurve.OutCubic
        self._current_index = 0
        self._next_index = 0
        self._is_animating = False
        self._anim_group = None

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex() or index < 0 or index >= self.count():
            return

        if self._is_animating:
            if self._anim_group:
                self._anim_group.stop()
            self._finalize_transition()

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

        # Przygotuj widgety
        next_w.setGeometry(0, 0, w, h)
        direction = "up" if index > self._current_index else "down"
        offset = h if direction == "up" else -h

        next_w.move(0, offset)
        next_w.show()
        next_w.raise_()

        # Tworzymy nową grupę animacji dla każdego przejścia (bezpieczniejsze dla Qt)
        self._anim_group = QParallelAnimationGroup(self)

        anim_next = QPropertyAnimation(next_w, b"pos", self._anim_group)
        anim_next.setDuration(self.duration)
        anim_next.setEasingCurve(self.easing)
        anim_next.setStartValue(QPoint(0, offset))
        anim_next.setEndValue(QPoint(0, 0))

        anim_cur = QPropertyAnimation(cur_w, b"pos", self._anim_group)
        anim_cur.setDuration(self.duration)
        anim_cur.setEasingCurve(self.easing)
        anim_cur.setStartValue(QPoint(0, 0))
        anim_cur.setEndValue(QPoint(0, -offset))

        self._anim_group.addAnimation(anim_next)
        self._anim_group.addAnimation(anim_cur)
        self._anim_group.finished.connect(self._on_animation_finished)

        self._is_animating = True
        self._anim_group.start()

    def _on_animation_finished(self):
        self._finalize_transition()

    def _finalize_transition(self):
        if not self._is_animating: return

        self._is_animating = False
        super().setCurrentIndex(self._next_index)

        # Resetujemy stan starego widgetu
        prev_w = self.widget(self._current_index)
        if prev_w:
            prev_w.hide()
            prev_w.move(0, 0)

        # Sprzątamy grupę
        if self._anim_group:
            self._anim_group.deleteLater()
            self._anim_group = None

    def resizeEvent(self, event):
        # Upewniamy się, że aktualny widget zawsze wypełnia przestrzeń
        if self.widget(self.currentIndex()):
            self.widget(self.currentIndex()).resize(self.size())
        super().resizeEvent(event)

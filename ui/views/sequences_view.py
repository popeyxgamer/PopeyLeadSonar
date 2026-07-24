# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QListWidget, QGroupBox, QSpinBox,
    QMessageBox, QScrollArea, QFrame, QInputDialog, QListWidgetItem, QWidget
)
from PySide6.QtCore import Qt
from ui.views.base_view import BaseView
from ui.i18n import tr
from core import database as db
from core.signal_bus import bus

class StepItem(QFrame):
    def __init__(self, step_num, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("StepItem { background-color: #2a2a2a; border-radius: 8px; margin: 5px; }")

        lay = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>KROK {step_num}</b>"))
        header.addStretch()
        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedWidth(30)
        self.btn_del.setStyleSheet("background-color: #8b0000;")
        header.addWidget(self.btn_del)
        lay.addLayout(header)

        form = QHBoxLayout()
        form.addWidget(QLabel(tr("Czekaj (dni):")))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 30)
        if step_num == 1: self.delay_spin.setEnabled(False); self.delay_spin.setValue(0)
        form.addWidget(self.delay_spin)
        form.addStretch()
        lay.addLayout(form)

        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText(tr("Temat wiadomości..."))
        lay.addWidget(self.subject_edit)

        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText(tr("Treść wiadomości..."))
        self.template_edit.setMaximumHeight(100)
        lay.addWidget(self.template_edit)

class SequencesView(BaseView):
    def setup_ui(self):
        header = QLabel(tr("Automatyczne Sekwencje (Follow-up)"))
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        self.layout.addWidget(header)

        main_layout = QHBoxLayout()

        # Left: List of sequences
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel(tr("Twoje Sekwencje:")))
        self.seq_list = QListWidget()
        self.seq_list.currentRowChanged.connect(self._on_seq_selected)
        left_panel.addWidget(self.seq_list)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton(tr("➕ Nowa"))
        self.btn_new.clicked.connect(self._new_sequence)
        btn_row.addWidget(self.btn_new)
        self.btn_del = QPushButton(tr("🗑 Usuń"))
        self.btn_del.clicked.connect(self._delete_sequence)
        btn_row.addWidget(self.btn_del)
        left_panel.addLayout(btn_row)

        main_layout.addLayout(left_panel, 1)

        # Right: Editor
        self.editor_panel = QGroupBox(tr("Edytor Sekwencji"))
        self.editor_lay = QVBoxLayout(self.editor_panel)

        self.seq_name_label = QLabel(tr("Wybierz lub utwórz sekwencję"))
        self.seq_name_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #4a9eff;")
        self.editor_lay.addWidget(self.seq_name_label)

        self.steps_scroll = QScrollArea()
        self.steps_scroll.setWidgetResizable(True)
        self.steps_content = QWidget()
        self.steps_lay = QVBoxLayout(self.steps_content)
        self.steps_lay.addStretch()
        self.steps_scroll.setWidget(self.steps_content)
        self.editor_lay.addWidget(self.steps_scroll)

        edit_btns = QHBoxLayout()
        self.btn_add_step = QPushButton(tr("➕ Dodaj kolejny krok"))
        self.btn_add_step.clicked.connect(self._add_step_ui)
        edit_btns.addWidget(self.btn_add_step)

        self.btn_save = QPushButton(tr("💾 ZAPISZ SEKWENCJĘ"))
        self.btn_save.setStyleSheet("background-color: #2b5e2b; font-weight: bold; padding: 10px;")
        self.btn_save.clicked.connect(self._save_sequence)
        edit_btns.addWidget(self.btn_save)
        self.editor_lay.addLayout(edit_btns)

        main_layout.addWidget(self.editor_panel, 2)

        self.layout.addLayout(main_layout)

        self.current_seq_id = None
        self.step_widgets = []
        self._refresh_list()

    def _refresh_list(self):
        self.seq_list.clear()
        seqs = db.get_sequences()
        for s in seqs:
            item = QListWidgetItem(s["name"])
            item.setData(Qt.UserRole, s["id"])
            self.seq_list.addItem(item)

    def _on_seq_selected(self, row):
        if row < 0: return
        seq_id = self.seq_list.item(row).data(Qt.UserRole)
        self._load_sequence(seq_id)

    def _load_sequence(self, seq_id):
        self.current_seq_id = seq_id
        seq = db.get_sequence(seq_id)
        if not seq: return

        self.seq_name_label.setText(seq["name"])
        self._clear_steps()

        for s in seq["steps"]:
            w = self._add_step_ui()
            w.delay_spin.setValue(s["delay"])
            w.subject_edit.setText(s["subject"])
            w.template_edit.setPlainText(s["template"])

    def _new_sequence(self):
        name, ok = QInputDialog.getText(self, tr("Nowa Sekwencja"), tr("Nazwa sekwencji:"))
        if ok and name.strip():
            self.current_seq_id = None
            self.seq_name_label.setText(name.strip())
            self._clear_steps()
            self._add_step_ui() # Add first step automatically

    def _clear_steps(self):
        for w in self.step_widgets:
            self.steps_lay.removeWidget(w)
            w.deleteLater()
        self.step_widgets = []

    def _add_step_ui(self):
        step_num = len(self.step_widgets) + 1
        w = StepItem(step_num)
        w.btn_del.clicked.connect(lambda: self._remove_step_ui(w))
        self.steps_lay.insertWidget(len(self.step_widgets), w)
        self.step_widgets.append(w)
        return w

    def _remove_step_ui(self, widget):
        if len(self.step_widgets) <= 1: return
        self.steps_lay.removeWidget(widget)
        self.step_widgets.remove(widget)
        widget.deleteLater()
        # Update numbers
        for i, w in enumerate(self.step_widgets):
            w.findChild(QLabel).setText(f"<b>KROK {i+1}</b>")

    def _save_sequence(self):
        name = self.seq_name_label.text()
        if name == tr("Wybierz lub utwórz sekwencję"): return

        steps = []
        for w in self.step_widgets:
            steps.append({
                "delay": w.delay_spin.value(),
                "subject": w.subject_edit.text(),
                "template": w.template_edit.toPlainText()
            })

        if self.current_seq_id:
            db.delete_sequence(self.current_seq_id)

        new_id = db.add_sequence(name, steps)
        self.current_seq_id = new_id
        self._refresh_list()
        bus.show_message.emit("Sekwencje", tr("Sekwencja '{}' zapisana!").format(name))

    def _delete_sequence(self):
        row = self.seq_list.currentRow()
        if row < 0: return
        if QMessageBox.question(self, tr("Usuń"), tr("Usunąć tę sekwencję?")) == QMessageBox.Yes:
            seq_id = self.seq_list.item(row).data(Qt.UserRole)
            db.delete_sequence(seq_id)
            self._refresh_list()
            self._clear_steps()
            self.seq_name_label.setText(tr("Wybierz lub utwórz sekwencję"))

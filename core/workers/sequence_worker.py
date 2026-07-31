# -*- coding: utf-8 -*-
import time
from PySide6.QtCore import QThread, Signal
from .. import database as db
from ..profile_manager import get_company_info
from ..email_sender import wyslij_email

class SequenceWorker(QThread):
    status = Signal(str)
    finished = Signal()

    def __init__(self, user, pwd, host, port):
        super().__init__()
        self.user = user; self.pwd = pwd; self.host = host; self.port = port
        self._stop = False
        self.company_info = get_company_info()

    def stop(self): self._stop = True

    def run(self):
        while not self._stop:
            pending = db.get_pending_sequence_steps()
            if not pending:
                for _ in range(60):
                    if self._stop: break
                    time.sleep(5)
                continue

            for step in pending:
                if self._stop: break
                lead_id, seq_id, current_step, subject, template, email, firma = step
                ok, _, _ = wyslij_email(email, subject, template, self.user, self.pwd, self.host, self.port)
                if ok:
                    seq = db.get_sequence(seq_id)
                    next_delay = seq["steps"][current_step]["delay"] if seq and len(seq["steps"]) > current_step else None
                    db.mark_step_done(lead_id, seq_id, next_delay)
                time.sleep(10)
        self.finished.emit()

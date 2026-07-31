# -*- coding: utf-8 -*-
import time
from PySide6.QtCore import QThread, Signal
from .. import database as db
from ..scraping import search_companies_web
from ..email_sender import wyslij_email

class AutoPilotWorker(QThread):
    status = Signal(str)
    counters = Signal(int, int, int)
    finished = Signal()

    def __init__(self, queries, locations, limit, szablon, temat, user, pwd, host, port, session_cap, **kwargs):
        super().__init__()
        self.queries = queries
        self.locations = locations
        self.limit = limit
        self.szablon = szablon
        self.temat = temat
        self.user = user
        self.pwd = pwd
        self.host = host
        self.port = port
        self.session_cap = session_cap
        self._stop = False
        self.excluded = db.get_excluded_emails()
        self.proxies = kwargs.get("proxies") or []
        self.found = 0
        self.sent = 0
        self.errors = 0

    def stop(self): self._stop = True

    def run(self):
        for q in self.queries:
            if self._stop: break
            for l in self.locations:
                if self._stop: break
                self.status.emit(f"🔍 Szukaj: {q} w {l}")
                results, _ = search_companies_web(q, l, self.limit, self, proxies=self.proxies)
                for lead in results:
                    if self._stop or self.sent >= self.session_cap: break
                    email = lead.get('email')
                    if email and email not in self.excluded:
                        self.found += 1
                        ok, _, _ = wyslij_email(email, self.temat, self.szablon, self.user, self.pwd, self.host, self.port)
                        if ok:
                            self.sent += 1
                            self.excluded.add(email)
                            db.mark_sent(email)
                        else: self.errors += 1
                        self.counters.emit(self.found, self.sent, self.errors)
                        time.sleep(2)
        self.finished.emit()

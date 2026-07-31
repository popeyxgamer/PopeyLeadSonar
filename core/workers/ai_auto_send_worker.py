# -*- coding: utf-8 -*-
import time
from PySide6.QtCore import QThread, Signal
from .. import database as db
from ..profile_manager import get_company_info
from ..email_sender import wyslij_email
from ..scraping import fetch_page_text
from ..ai_features import LeadScorer, LeadPersonalizer

class AIAutoSendWorker(QThread):
    status = Signal(str)
    counters = Signal(int, int, int, int)
    finished = Signal()

    def __init__(self, leads, user, pwd, host, port, **kwargs):
        super().__init__()
        self.leads = leads
        self.user = user
        self.pwd = pwd
        self.host = host
        self.port = port
        self.threshold = kwargs.get("ai_scoring_threshold", 50)
        self.email_language = kwargs.get("email_language", "auto")
        self.dry_run = kwargs.get("dry_run", False)
        self._stop = False
        self.excluded = db.get_excluded_emails()
        self.company_info = get_company_info()

    def stop(self): self._stop = True

    def run(self):
        processed, sent, skipped, errors = 0, 0, 0, 0
        for lead in self.leads:
            if self._stop: break
            email = lead.get('email')
            if not email or email in self.excluded:
                skipped += 1; continue

            self.status.emit(f"🌐 Analiza: {lead.get('firma')}")
            page_text = fetch_page_text(lead.get('website'))
            score_data = LeadScorer.score_lead(lead.get('firma'), email, "B2B", lead.get('website'), page_text=page_text)

            if score_data and score_data.get("score", 0) >= self.threshold:
                self.status.emit(f"✍️ Pisanie: {lead.get('firma')}")
                email_data = LeadPersonalizer.write_cold_email(
                    lead.get('firma'), "B2B", self.company_info.get("company_name"),
                    self.company_info.get("company_offer_description"),
                    language=self.email_language, page_text=page_text
                )
                if email_data:
                    ok, msg, _ = wyslij_email(email, email_data["subject"], email_data["body"], self.user, self.pwd, self.host, self.port, dry_run=self.dry_run)
                    if ok:
                        sent += 1; self.excluded.add(email); db.mark_sent(email)
                    else:
                        errors += 1
                        if any(x in msg.lower() for x in ["mx verification failed", "nieprawidłowy adres", "brak rekordu mx", "does not exist"]):
                            db.mark_invalid(email)
                else: errors += 1
            else:
                skipped += 1
            processed += 1
            self.counters.emit(processed, sent, skipped, errors)
            time.sleep(3)
        self.finished.emit()

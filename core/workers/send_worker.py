# -*- coding: utf-8 -*-
import random
import re
import time
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

from .. import database as db
from ..config import (
    SESSION_HARD_CAP, SMTP_RELAY_HOST, SMTP_RELAY_PORT, SMTP_TEMP_FAIL_PAUSE,
    get_abs_session_cap, get_send_delay
)
from ..profile_manager import get_company_info
from ..email_sender import wyslij_email
from ..account_rotator import SMTPAccountRotator
from ..signal_bus import bus
from ui.i18n import tr

class SendWorker(QThread):
    progress = Signal(int, int)
    status = Signal(str)
    lead_done = Signal(dict)
    counters = Signal(int, int, int, int)  # processed, sent, skipped, errors
    finished = Signal()
    error = Signal(str)

    def __init__(self, leads: List[Dict], szablon: str, temat: str,
                 smtp_user: str, smtp_password: str,
                 smtp_host: str = SMTP_RELAY_HOST, smtp_port: int = SMTP_RELAY_PORT,
                 limit_dzienny: int = SESSION_HARD_CAP,
                 custom_delay: Optional[float] = None, custom_cap: Optional[int] = None,
                 html: bool = False, attachments: Optional[List[str]] = None,
                 verify_mx: bool = False, check_blacklist: bool = True,
                 smime_sign: bool = False, personalized_attachments: Optional[Dict[str, str]] = None,
                 use_account_rotation: bool = False, rotator: Optional[SMTPAccountRotator] = None,
                 dry_run: bool = False):
        super().__init__()
        self.dry_run = dry_run
        self.leads = leads
        self.szablon = szablon
        self.temat = temat
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.send_delay = get_send_delay(smtp_host, custom_delay)
        self.limit_dzienny = min(limit_dzienny, get_abs_session_cap(smtp_host, custom_cap))
        self.session_cap = self.limit_dzienny
        self._stop = False
        self.excluded = db.get_excluded_emails()
        self.sent = 0
        self.errors = 0
        self.skipped = 0
        self.already_sent_today = db.count_sent_today()
        self.html = html
        self.attachments = attachments or []
        self.verify_mx = verify_mx
        self.check_blacklist = check_blacklist
        self.smime_sign = smime_sign
        self.personalized_attachments = personalized_attachments or {}
        self.rotator = rotator
        self.use_rotation = use_account_rotation and self.rotator is not None
        self.company_info = get_company_info()

    def stop(self):
        self._stop = True

    @staticmethod
    def parse_zmienne(text: str, dane: Dict) -> str:
        for key, value in dane.items():
            text = text.replace(f"{{{key}}}", str(value or ""))
        return text

    SPINTAX_RE = re.compile(r'\{\{((?:(?!\{\{).)*?)\}\}', re.DOTALL)

    @staticmethod
    def resolve_spintax(text: str) -> str:
        """Rozwiązuje spintax {{opcja1|opcja2}}, wspiera zagnieżdżanie i zmienne {firma}."""
        if not text:
            return ""

        # Iteracyjnie rozwiązujemy najbardziej wewnętrzne bloki spintaxu.
        # Nowy regex pozwala na obecność pojedynczych klamer (zmiennych) w środku.
        iterations = 0
        while "{{" in text and "}}" in text and iterations < 150:
            new_text = SendWorker.SPINTAX_RE.sub(
                lambda m: random.choice(m.group(1).split('|')),
                text
            )
            if new_text == text:
                break
            text = new_text
            iterations += 1
        return text

    def _send_one(self, lead: Dict, temat: str, tresc: str) -> Tuple[bool, str, bool]:
        if self.use_rotation:
            acc = self.rotator.next_account()
            if acc:
                user, pwd, host, port = acc
                return wyslij_email(
                    lead.get('email', ''), temat, tresc, user, pwd, host, port,
                    html=self.html, attachments=self.attachments, verify_mx=self.verify_mx,
                    check_blacklist=self.check_blacklist, personalized_attachments={},
                    smime_sign=self.smime_sign, lead_data=lead, dry_run=self.dry_run,
                    from_addr=self.company_info.get("company_email")
                )
        return wyslij_email(
            lead.get('email', ''), temat, tresc, self.smtp_user, self.smtp_password,
            self.smtp_host, self.smtp_port,
            html=self.html, attachments=self.attachments, verify_mx=self.verify_mx,
            check_blacklist=self.check_blacklist, smime_sign=self.smime_sign,
            lead_data=lead, dry_run=self.dry_run, from_addr=self.company_info.get("company_email")
        )

    def run(self):
        total = len(self.leads)
        if total == 0:
            self.status.emit("⚠️ Brak leadów")
            self.finished.emit(); return

        i = 0
        while i < total:
            if self._stop:
                self.status.emit("⏹️ Zatrzymano"); break

            if self.sent >= self.session_cap:
                self.error.emit(f"🛑 Limit sesji ({self.session_cap})"); break

            lead = self.leads[i]
            email = (lead.get('email') or '').strip()
            if not email or email in self.excluded:
                self.skipped += 1
                self.lead_done.emit({**lead, 'send_status': 'skipped', 'send_msg': tr('Brak adresu e-mail lub już wysłano')})
                self.progress.emit(i+1, total)
                self.counters.emit(i + 1, self.sent, self.skipped, self.errors)
                i += 1; continue

            dane = {'firma': lead.get('firma', ''), 'email': email, 'id': lead.get('id', ''), **self.company_info}
            tresc = self.resolve_spintax(self.parse_zmienne(self.szablon, dane))
            temat = self.resolve_spintax(self.parse_zmienne(self.temat, dane))

            self.status.emit(tr("📤 Wysyłam do {}...").format(email))
            ok, msg, is_temp = self._send_one(lead, temat, tresc)

            if ok:
                db.mark_sent(email)
                self.sent += 1
                self.excluded.add(email)
                db.log_wysylka(lead.get('id', 0), email, temat, tresc, 'wysłano')
                bus.email_sent.emit({'email': email, 'id': lead.get('id')})
                self.lead_done.emit({**lead, 'send_status': 'sent', 'send_msg': tr('Wysłano')})
                self.progress.emit(i + 1, total)
                self.counters.emit(i + 1, self.sent, self.skipped, self.errors)
                i += 1
                time.sleep(self.send_delay)
            elif is_temp:
                self.status.emit(tr("⏳ Chwilowy błąd SMTP dla {}, ponawiam...").format(email))
                time.sleep(SMTP_TEMP_FAIL_PAUSE)
                continue
            else:
                self.errors += 1
                db.log_wysylka(lead.get('id', 0), email, temat, tresc, 'błąd', msg)

                # Jeśli to twardy błąd (np. MX, zły adres), oznacz lead jako błędny na stałe
                if any(x in msg.lower() for x in ["mx verification failed", "nieprawidłowy adres", "brak rekordu mx", "does not exist"]):
                    db.mark_invalid(email)
                    self.status.emit(tr("🚫 {} oznaczony jako błędny (trwały błąd)").format(email))

                self.lead_done.emit({**lead, 'send_status': 'error', 'send_msg': msg or tr('Błąd wysyłki')})
                self.progress.emit(i + 1, total)
                self.counters.emit(i + 1, self.sent, self.skipped, self.errors)
                i += 1
                time.sleep(self.send_delay)

        self.status.emit(tr("✅ Zakończono: wysłano {} | pominięto {} | błędy {}").format(self.sent, self.skipped, self.errors))
        self.finished.emit()

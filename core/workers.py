# -*- coding: utf-8 -*-
"""Wątki QThread – wyszukiwanie, wysyłka, tryb automatyczny, sekwencje i rozgrzewanie."""
import random
import re
import time
from typing import Dict, List, Optional, Any, Tuple

from PySide6.QtCore import QThread, Signal

from . import database as db
from .config import (
    SESSION_HARD_CAP, SMTP_RELAY_HOST, SMTP_RELAY_PORT, SMTP_TEMP_FAIL_PAUSE,
    get_abs_session_cap, get_send_delay, logger,
    ACCOUNT_ROTATION_ENABLED_DEFAULT, ACCOUNT_ROTATION_MAX_PER_ACCOUNT,
    HTML_EMAIL_ENABLED_DEFAULT
)
from .profile_manager import get_company_info, get_current_profile_settings
from .email_sender import wyslij_email
from .scraping import search_companies_web, fetch_page_text
from .account_rotator import SMTPAccountRotator
from .ai_features import LeadScorer, LeadPersonalizer
from .signal_bus import bus
from ui.i18n import tr


class SearchWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    result = Signal(list)
    finished = Signal()
    error = Signal(str)
    live_result = Signal(dict)

    def __init__(self, queries: List[str], locations: List[str],
                 limit_per_query: int = 10, czas_szukania: int = 0,
                 proxies: Optional[List[str]] = None,
                 ai_scoring: bool = False, force_research: bool = False):
        super().__init__()
        self.queries = queries
        self.locations = locations
        self.limit_per_query = limit_per_query
        self.czas_szukania = czas_szukania
        self.proxies = proxies or []
        self._stop = False
        self._is_running = True
        self.domain_cache: Dict[str, str] = db.get_scanned_domains()
        self.ai_scoring = ai_scoring
        self.force_research = force_research
        self.searched_combos = set() if force_research else db.get_searched_combos()

    def stop(self):
        self._stop = True
        self._is_running = False

    def run(self):
        all_results = []
        start_time = time.time()
        total = len(self.queries) * len(self.locations)
        processed = 0
        skipped_already_done = 0

        for query in self.queries:
            if self._stop:
                break
            for location in self.locations:
                if self._stop:
                    self.status.emit("⏹️ Zatrzymano")
                    break
                if self.czas_szukania > 0:
                    elapsed_min = (time.time() - start_time) / 60
                    if elapsed_min >= self.czas_szukania:
                        self.status.emit(f"⏰ Upłynął czas ({self.czas_szukania} min)")
                        self._stop = True
                        break

                if (query, location) in self.searched_combos:
                    skipped_already_done += 1
                    processed += 1
                    self.progress.emit(int(processed / total * 100) if total else 0)
                    continue

                self.status.emit(f"🔍 Szukam: {query} w {location}")
                try:
                    results, newly_scanned = search_companies_web(
                        query, location, self.limit_per_query, self,
                        domain_cache=self.domain_cache, proxies=self.proxies
                    )
                    all_results.extend(results)
                    
                    scored_count = 0
                    if self.ai_scoring:
                        for r in results:
                            email = r.get('email', '')
                            if not email: continue
                            lead_id = db.add_lead(
                                r.get('name', ''), email, r.get('address', ''),
                                '', r.get('website', ''), r.get('category', ''),
                                lead_score=-1, lead_score_reason="oczekuje na ocenę AI",
                                linkedin=r.get('linkedin', '')
                            )
                            if not lead_id: continue
                            r['lead_id'] = lead_id
                            try:
                                score_data = LeadScorer.score_lead(
                                    r.get('name', ''), email, r.get('category', ''), r.get('website', '')
                                )
                            except Exception as e:
                                logger.warning("Błąd oceny AI dla %s: %s", email, e)
                                score_data = None

                            if score_data:
                                score = int(score_data.get('score', -1))
                                reason = score_data.get('reason', '')
                                if score_data.get('is_spam'):
                                    reason = f"[SPAM] {reason}".strip()
                                db.update_lead_score(lead_id, score, reason)
                                r['lead_score'] = score
                                r['lead_score_reason'] = reason
                                scored_count += 1
                            else:
                                db.update_lead_score(lead_id, -1, "Błąd oceny AI")
                    
                    for r in results:
                        self.live_result.emit(r)
                    if newly_scanned:
                        self.domain_cache.update(newly_scanned)
                        db.mark_domains_scanned(newly_scanned)
                    db.mark_combo_searched(query, location)
                    self.searched_combos.add((query, location))
                    status_msg = f"✅ Znaleziono {len(results)} firm"
                    if self.ai_scoring:
                        status_msg += f" (oceniono AI: {scored_count}/{len(results)})"
                    self.status.emit(status_msg)
                    bus.leads_changed.emit()
                except Exception as e:
                    logger.exception("Błąd wyszukiwania %s / %s", query, location)
                    self.error.emit(f"❌ Błąd: {e}")

                processed += 1
                self.progress.emit(int((processed / total) * 100) if total else 100)
                time.sleep(0.5)

        self.result.emit(all_results)
        self.finished.emit()


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
                        if ok: self.sent += 1; self.wyslane.add(email); db.mark_sent(email)
                        else: self.errors += 1
                        self.counters.emit(self.found, self.sent, self.errors)
                        time.sleep(2)
        self.finished.emit()


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


class WarmupWorker(QThread):
    status = Signal(str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, increase=2, max_val=50, auto_reply=True):
        super().__init__()
        self.increase = increase; self.max_val = max_val; self._stop = False

    def stop(self): self._stop = True

    def run(self):
        while not self._stop:
            # 1. Pobieramy ustawienia i konta
            settings = get_current_profile_settings()
            main_user = settings.get("gmail_user")
            main_pass = settings.get("gmail_password")

            all_accounts = db.get_smtp_accounts()
            # Wybieramy konta dodatkowe, które nie są głównym kontem
            extra_senders = [s for s in all_accounts if s.get("enabled", True) and s['user'] != main_user]
            targets = db.get_warmup_targets()

            # Budujemy listę nadawców z priorytetem
            senders = []
            if main_user and main_pass:
                # Konto główne ma 3-krotny priorytet (wysyła 3x częściej w jednej turze)
                for _ in range(3):
                    senders.append({
                        "user": main_user, "password": main_pass,
                        "host": settings.get("smtp_host", SMTP_RELAY_HOST),
                        "port": settings.get("smtp_port", SMTP_RELAY_PORT),
                        "is_main": True
                    })

            # Konta dodatkowe wysyłają po 1 raz
            for s in extra_senders:
                s["is_main"] = False
                senders.append(s)

            if not senders:
                self.status.emit(tr("Błąd: Brak włączonych kont SMTP w ustawieniach!"))
                for _ in range(60):
                    if self._stop: break
                    time.sleep(1)
                continue

            if not targets:
                self.status.emit(tr("Błąd: Brak zaufanych adresów odbiorczych!"))
                for _ in range(60):
                    if self._stop: break
                    time.sleep(1)
                continue

            # Sprawdź dzisiejszy limit rozgrzewania
            sent_today = db.count_warmup_today()
            if sent_today >= self.max_val:
                self.status.emit(tr("Osiągnięto dzienny limit rozgrzewania ({})").format(self.max_val))
                # Odczekaj godzinę przed ponownym sprawdzeniem
                for _ in range(3600):
                    if self._stop: break
                    time.sleep(1)
                continue

            # 2. Wysyłka w bieżącej turze
            self.status.emit(tr("Rozpoczynam priorytetową turę dla konta głównego..."))
            for i, s in enumerate(senders):
                if self._stop: break

                # Sprawdź limit przed każdą wysyłką
                if db.count_warmup_today() >= self.max_val:
                    break

                target = random.choice(targets)["email"]
                label = tr("KONTO GŁÓWNE") if s.get("is_main") else tr("Konto dodatkowe")
                self.status.emit(tr("[{}] Wysyłam warmup z {} do {}...").format(label, s["user"], target))

                temat = "Warmup: Building Deliverability"
                tresc = "Automated warmup message to improve sender reputation."

                # Próbujemy wysłać
                ok, msg, _ = wyslij_email(
                    target, temat, tresc,
                    s["user"], s["password"], s["host"], s["port"]
                )

                if ok:
                    self.status.emit(tr("Pomyślnie wysłano z {}").format(s["user"]))
                    db.log_wysylka(0, target, temat, tresc, 'warmup')
                else:
                    self.status.emit(tr("Błąd wysyłki z {}: {}").format(s["user"], msg))
                    db.log_wysylka(0, target, temat, tresc, 'błąd_warmup', msg)

                self.progress.emit(i+1, len(senders))

                # Krótka przerwa między wiadomościami
                for _ in range(45):
                    if self._stop: break
                    time.sleep(1)

            if self._stop: break

            # 3. Oczekiwanie na kolejną turę
            wait_minutes = 60
            for m in range(wait_minutes, 0, -1):
                if self._stop: break
                self.status.emit(tr("Następna tura za {} min...").format(m))
                for _ in range(60):
                    if self._stop: break
                    time.sleep(1)

        self.finished.emit()


class InboxFetchWorker(QThread):
    finished_ok = Signal(list)
    finished_error = Signal(str)
    def __init__(self, email, pwd, server):
        super().__init__()
        self.email = email; self.pwd = pwd; self.server = server
    def run(self):
        from .mailbox_reader import fetch_recent_messages
        ok, msgs, err = fetch_recent_messages(self.email, self.pwd, self.server)
        if ok: self.finished_ok.emit(msgs)
        else: self.finished_error.emit(err)


class MessageFullWorker(QThread):
    finished_ok = Signal(object)
    finished_error = Signal(str)
    def __init__(self, email, pwd, server, uid):
        super().__init__()
        self.email = email; self.pwd = pwd; self.server = server; self.uid = uid
    def run(self):
        from .mailbox_reader import fetch_message_full
        ok, msg, err = fetch_message_full(self.email, self.pwd, self.server, self.uid)
        if ok: self.finished_ok.emit(msg)
        else: self.finished_error.emit(err)


class MessageActionWorker(QThread):
    finished_ok = Signal()
    def __init__(self, action, email, pwd, server, uid, folder):
        super().__init__()
        self.action = action; self.email = email; self.pwd = pwd; self.server = server; self.uid = uid; self.folder = folder
    def run(self):
        from .mailbox_reader import delete_message
        if self.action == "delete": delete_message(self.email, self.pwd, self.server, self.uid, self.folder)
        self.finished_ok.emit()

# -*- coding: utf-8 -*-
import random
import time
from PySide6.QtCore import QThread, Signal
from .. import database as db
from ..config import SMTP_RELAY_HOST, SMTP_RELAY_PORT
from ..profile_manager import get_current_profile_settings
from ..email_sender import wyslij_email
from ui.i18n import tr

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

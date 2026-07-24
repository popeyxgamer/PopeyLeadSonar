# -*- coding: utf-8 -*-
"""IMAP monitoring for bounce detection (Mailer-Daemon)."""
import imaplib
import re
import time
from threading import Thread
from email import message_from_bytes
from email.policy import default
from typing import Optional, List, Callable

from .config import logger
from . import database as db

BOUNCE_SUBJECTS = (
    "Undelivered Mail Returned to Sender",
    "Delivery Status Notification (Failure)",
    "Returned mail: see transcript for details",
    "failure notice",
    "mail delivery failed",
)

BOUNCE_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


def extract_bounce_recipient(body: str) -> Optional[str]:
    """Wyciąga adres odbiorcy, którego mail nie dotarł."""
    lines = body.splitlines()
    for line in lines:
        if 'for <' in line and '@' in line:
            match = BOUNCE_EMAIL_RE.search(line)
            if match:
                return match.group(0)
        if 'Final-Recipient:' in line and '@' in line:
            match = BOUNCE_EMAIL_RE.search(line)
            if match:
                return match.group(0)
        if 'failed permanently' in line.lower() and '@' in line:
            match = BOUNCE_EMAIL_RE.search(line)
            if match:
                return match.group(0)
    return None


def _is_bounce(subject: str) -> bool:
    return any(kw.lower() in subject.lower() for kw in BOUNCE_SUBJECTS)


class BounceMonitor(Thread):
    """Wątek monitorujący skrzynkę IMAP w poszukiwaniu zwrotów."""

    def __init__(self, email: str, password: str, imap_server: str = "imap.gmail.com",
                 on_bounce: Optional[Callable[[str], None]] = None, interval: int = 300):
        super().__init__(daemon=True)
        self.email = email
        self.password = password
        self.imap_server = imap_server
        self.on_bounce = on_bounce or (lambda addr: db.add_to_blacklist(addr, "bounce"))
        self.interval = interval
        self._running = True
        self._processed_ids: set = set()

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                self._check_once()
            except Exception as e:
                logger.error("Błąd monitora zwrotów: %s", e)
            for _ in range(self.interval):
                if not self._running:
                    break
                time.sleep(1)

    def _check_once(self):
        try:
            conn = imaplib.IMAP4_SSL(self.imap_server)
            conn.login(self.email, self.password)
            conn.select("INBOX")

            status, data = conn.search(None, "UNSEEN")
            if status != "OK":
                return
            msg_ids = data[0].split()
            if not msg_ids:
                return

            for msg_id in msg_ids:
                if msg_id in self._processed_ids:
                    continue
                status, msg_data = conn.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                raw = msg_data[0][1]
                msg = message_from_bytes(raw, policy=default)
                subject = msg.get("Subject", "")
                if not _is_bounce(subject):
                    continue

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                recipient = extract_bounce_recipient(body)
                if recipient and self.on_bounce:
                    self.on_bounce(recipient)
                    logger.info("Dodano do blacklist z powodu zwrotu: %s", recipient)
                elif not _is_bounce(subject):
                    # To może być odpowiedź od leada
                    from_header = msg.get("From", "")
                    from_name, from_email = parseaddr(from_header) if 'parseaddr' in globals() else (None, from_header)
                    if not from_email and '<' in from_header:
                        import email.utils
                        _, from_email = email.utils.parseaddr(from_header)

                    if from_email:
                        db.mark_as_responded(from_email)
                        logger.info("Sequence stopped for %s (reply detected)", from_email)

                self._processed_ids.add(msg_id)
                conn.store(msg_id, "+FLAGS", "\\Seen")

            conn.close()
            conn.logout()
        except Exception as e:
            logger.warning("IMAP nieosiągalny: %s", e)
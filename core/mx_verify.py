# -*- coding: utf-8 -*-
"""MX/DNS verification for email addresses."""
import dns.resolver
import re
import smtplib
import socket
from typing import Optional, Tuple

from .config import logger

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "temp-mail.org", "10minutemail.com",
    "trashmail.com", "spamgourmet.com", "yopmail.com", "throwaway.email",
    "fakeinbox.com", "mytemp.email", "tempmail.net", "getnada.com",
}


def has_mx_record(domain: str) -> bool:
    if not domain:
        return False
    try:
        dns.resolver.resolve(domain, "MX", raise_on_no_answer=False)
        return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        return False
    except Exception as e:
        logger.debug("Błąd MX dla %s: %s", domain, e)
        return False


def is_disposable(email: str) -> bool:
    try:
        domain = email.split('@')[1].lower()
        return domain in DISPOSABLE_DOMAINS or domain.endswith(".temp") or "temp" in domain
    except IndexError:
        return False


def verify_email_mx(email: str) -> Tuple[bool, str]:
    if not email or '@' not in email:
        return False, "Nieprawidłowy adres"
    if is_disposable(email):
        return False, "Domena tymczasowa/jednorazowa"
    domain = email.split('@')[1].lower()
    if has_mx_record(domain):
        return True, "MX OK"
    return False, "Brak rekordu MX"

def deep_verify_email(email: str, sender_email: str = "verify@gmail.com") -> Tuple[bool, str]:
    """Weryfikacja SMTP handshake (RCPT TO) bez wysyłania maila."""
    if not email or '@' not in email: return False, "Invalid address"

    domain = email.split('@')[1].lower()
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_host = str(records[0].exchange)
    except Exception as e:
        return False, f"MX lookup failed: {e}"

    try:
        # SMTP connection
        server = smtplib.SMTP(timeout=10)
        server.set_debuglevel(0)
        server.connect(mx_host)
        server.helo(socket.gethostname())
        server.mail(sender_email)
        code, message = server.rcpt(email)
        server.quit()

        if code == 250:
            return True, "Email exists (SMTP 250)"
        else:
            return False, f"SMTP Error {code}: {message.decode()}"
    except Exception as e:
        return False, f"SMTP connection failed: {e}"

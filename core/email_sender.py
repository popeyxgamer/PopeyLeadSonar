# -*- coding: utf-8 -*-
"""
Wysyłka e-maili z obsługą HTML, załączników, MX, blacklist, S/MIME.
"""
import smtplib
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate
from typing import List, Optional, Tuple, Dict

from .config import (
    SMTP_RELAY_HOST, SMTP_RELAY_PORT, SMTP_TEMP_FAIL_CODES, SMTP_TIMEOUT, logger,
)
from .scraping import is_valid_email
from .database import is_blacklisted, add_to_blacklist
from .mx_verify import verify_email_mx
from .spam_analyzer import analyze_spam
from .smime import load_smime_cert, sign_email_content


def _extract_smtp_code(exc: Exception) -> int:
    if isinstance(exc, smtplib.SMTPResponseException):
        return exc.smtp_code
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        for code, _err in exc.recipients.values():
            return code
    return 0


def test_gmail_connection(user: str, password: str,
                           host: str = SMTP_RELAY_HOST,
                           port: int = SMTP_RELAY_PORT) -> Tuple[bool, str]:
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
        return True, "OK"
    except smtplib.SMTPException as e:
        return False, str(e)
    except OSError as e:
        return False, f"Błąd połączenia: {e}"


def _map_smtp_error(code: int, msg: str) -> str:
    """Mapuje techniczne kody błędów SMTP na czytelne komunikaty po polsku."""
    msg_l = msg.lower()
    if code == 534 or "application-specific password required" in msg_l:
        return "Błąd Google: Wymagane HASŁO APLIKACJI (nie Twoje główne hasło do konta)."
    if code == 535 or "authentication failed" in msg_l or "invalid credentials" in msg_l:
        return "Błąd logowania: Nieprawidłowy e-mail lub hasło. Sprawdź czy hasło aplikacji jest poprawne."
    if code == 550:
        if "sending limit exceeded" in msg_l or "daily limit" in msg_l:
            return "Przekroczono limit wysyłki dostawcy (np. 500 maili/dobę w darmowym Gmailu)."
        if "unverified sender" in msg_l:
            return "Błąd Brevo: Nadawca (pole 'Od:') nie jest zweryfikowany w panelu Brevo."
        return f"Serwer odrzucił adres (550): {msg}"
    if code == 421 or code == 450:
        return "Tymczasowy błąd serwera (np. przeciążenie). Program spróbuje ponownie później."
    return f"Błąd SMTP ({code}): {msg}"


def wyslij_email(
    odbiorca: str,
    temat: str,
    tresc: str,
    smtp_user: str,
    smtp_password: str,
    host: str = SMTP_RELAY_HOST,
    port: int = SMTP_RELAY_PORT,
    html: bool = False,
    attachments: Optional[List[str]] = None,
    verify_mx: bool = False,
    check_blacklist: bool = True,
    personalized_attachments: Optional[Dict[str, str]] = None,
    smime_sign: bool = False,
    lead_data: Optional[Dict] = None,
    dry_run: bool = False,
    from_addr: Optional[str] = None
) -> Tuple[bool, str, bool]:
    """
    Wysyła pojedynczą wiadomość z opcjonalnymi funkcjami.
    """
    if not is_valid_email(odbiorca):
        return False, f"Nieprawidłowy adres: {odbiorca}", False

    if check_blacklist and is_blacklisted(odbiorca):
        return False, "Adres na czarnej liście (rezygnacja/zwrot)", False

    if verify_mx and not dry_run:
        try:
            from .mx_verify import has_mx_record
            domain = odbiorca.split('@')[-1]
            if not has_mx_record(domain):
                return False, "Brak rekordu MX dla domeny odbiorcy (adres prawdopodobnie nie istnieje)", False
        except Exception as e:
            logger.error("Błąd MX verification dla %s: %s", odbiorca, e)
            # Traktuj jako błąd chwilowy, nie blokuj wysyłki
            pass

    # Analiza antyspamowa
    spam_score, spam_warnings, _ = analyze_spam(tresc)
    if spam_score > 70:
        logger.warning("Wysoki wynik spamowy (%d) dla %s: %s", spam_score, odbiorca, ", ".join(spam_warnings))

    naglowek_od = from_addr or smtp_user
    msg = MIMEMultipart()
    msg['From'] = naglowek_od
    msg['To'] = odbiorca
    msg['Subject'] = temat
    msg['Date'] = formatdate(localtime=True)

    # Treść
    if html:
        text_part = MIMEText(tresc, 'plain', 'utf-8')
        html_part = MIMEText(tresc, 'html', 'utf-8')
        alt = MIMEMultipart('alternative')
        alt.attach(text_part)
        alt.attach(html_part)
        msg.attach(alt)
    else:
        msg.attach(MIMEText(tresc, 'plain', 'utf-8'))

    # Załączniki
    for file_path in (attachments or []):
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    msg.attach(part)
            except IOError as e:
                logger.warning("Nie można dodać załącznika %s: %s", file_path, e)

    # Podpis S/MIME
    if smime_sign:
        try:
            msg_bytes = msg.as_bytes()
            sig = sign_email_content(msg_bytes)
            if sig:
                signed_msg = MIMEMultipart(_subtype="signed", micalg="sha-256", protocol="application/pkcs7-signature")
                signed_msg['From'] = naglowek_od
                signed_msg['To'] = odbiorca
                signed_msg['Subject'] = temat
                signed_msg.attach(msg)
                sig_part = MIMEApplication(sig, _subtype="pkcs7-signature", _encoder=lambda x: x)
                sig_part.add_header('Content-Disposition', 'attachment; filename="smime.p7s"')
                sig_part['Content-Transfer-Encoding'] = '7bit'
                signed_msg.attach(sig_part)
                msg = signed_msg
        except Exception as e:
            logger.error("Błąd S/MIME: %s", e)

    if dry_run:
        return True, "Wysłano (DRY RUN)", False

    try:
        with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg, from_addr=naglowek_od, to_addrs=[odbiorca])
        return True, "Wysłano", False
    except (smtplib.SMTPResponseException, smtplib.SMTPRecipientsRefused) as e:
        code = _extract_smtp_code(e)
        error_text = _map_smtp_error(code, str(e))
        is_temp = code in SMTP_TEMP_FAIL_CODES
        logger.warning("SMTP Error: %s", error_text)
        return False, error_text, is_temp
    except smtplib.SMTPException as e:
        return False, f"Błąd SMTP: {str(e)}", False
    except Exception as e:
        return False, f"Błąd połączenia: {str(e)}", False
    except smtplib.SMTPException as e:
        logger.error("Błąd SMTP do %s: %s", odbiorca, e)
        return False, str(e), False
    except OSError as e:
        logger.error("Błąd sieci do %s: %s", odbiorca, e)
        return False, f"Błąd połączenia: {e}", False

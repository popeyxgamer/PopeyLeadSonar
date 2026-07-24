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

    Zwraca (sukces, komunikat, czy_blad_chwilowy).

    `dry_run=True` (tryb demo/nagrywanie): caly proces (walidacja adresu,
    sprawdzanie blacklisty, budowanie wiadomosci, MX, analiza antyspamowa)
    dziala DOKLADNIE tak samo jak normalnie, zeby demo wygladalo autentycznie
    - jedyna roznica to ze na samym koncu program NIE laczy sie z serwerem
    SMTP i nic nie wysyla. Uzyteczne do nagrywania filmikow demo bez ryzyka
    wyslania prawdziwego maila i bez potrzeby pokazywania prawdziwego hasla
    SMTP na ekranie."""
    if not is_valid_email(odbiorca):
        return False, f"Nieprawidłowy adres: {odbiorca}", False

    if check_blacklist and is_blacklisted(odbiorca):
        return False, "Adres na czarnej liście (rezygnacja/zwrot)", False

    if verify_mx and not dry_run:
        try:
            ok, msg_mx = verify_email_mx(odbiorca)
            if not ok:
                return False, f"MX verification failed: {msg_mx}", False
        except Exception as e:
            logger.error("Błąd MX verification dla %s: %s", odbiorca, e)
            return False, f"MX check error: {e}", True  # Traktuj jako błąd chwilowy

    # Analiza antyspamowa (tylko ostrzeżenie)
    spam_score, spam_warnings, _ = analyze_spam(tresc)
    if spam_score > 70:
        logger.warning("Wysoki wynik spamowy (%d) dla %s: %s", spam_score, odbiorca, ", ".join(spam_warnings))

    # Adres w nagłówku "Od:" MUSI być zweryfikowanym nadawcą u dostawcy SMTP
    # (np. Brevo/Sendinblue). Login SMTP (smtp_user) to często techniczne
    # konto typu "xxxxx@smtp-brevo.com" i NIE nadaje się jako "Od:" - jeśli
    # go tam wstawimy, dostawca odrzuci wiadomość (SMTP 550), a program
    # błędnie wpisze odbiorcę na czarną listę, mimo że to konfiguracja
    # nadawcy jest zła, a nie adres odbiorcy.
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

    # Załączniki standardowe
    for file_path in (attachments or []):
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    msg.attach(part)
            except IOError as e:
                logger.warning("Nie można dodać załącznika %s: %s", file_path, e)

    # Załączniki spersonalizowane
    for name, path in (personalized_attachments or {}).items():
        if lead_data:
            for k, v in lead_data.items():
                path = path.replace(f"{{{k}}}", str(v or ""))
        if os.path.isfile(path):
            try:
                with open(path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                    msg.attach(part)
            except IOError as e:
                logger.warning("Nie można dodać załącznika %s: %s", path, e)

    # Podpis S/MIME - podpisz już skonstruowaną wiadomość
    if smime_sign:
        try:
            msg_bytes = msg.as_bytes()
            sig = sign_email_content(msg_bytes)
            if sig:
                # Utwórz prawidłową strukturę multipart/signed (RFC 3851)
                signed_msg = MIMEMultipart(_subtype="signed", micalg="sha-256", protocol="application/pkcs7-signature")
                signed_msg['From'] = naglowek_od
                signed_msg['To'] = odbiorca
                signed_msg['Subject'] = temat
                signed_msg['Date'] = formatdate(localtime=True)
                
                # Część 1: oryginalna wiadomość
                signed_msg.attach(msg)
                
                # Część 2: podpis (musi być exact binary, nie MIME-encoded)
                sig_part = MIMEApplication(sig, _subtype="pkcs7-signature", _encoder=lambda x: x)
                sig_part.add_header('Content-Disposition', 'attachment; filename="smime.p7s"')
                sig_part['Content-Transfer-Encoding'] = '7bit'
                signed_msg.attach(sig_part)
                
                msg = signed_msg
                logger.info("Wiadomość do %s podpisana S/MIME", odbiorca)
        except Exception as e:
            logger.error("Błąd przy podpisywaniu S/MIME dla %s: %s", odbiorca, e)
            # Nie przerywaj wysyłki — wysyłaj bez podpisu

    if dry_run:
        logger.info(
            "[DRY RUN] Symulacja wysylki do %s (temat: %r) - BEZ faktycznego "
            "polaczenia SMTP.", odbiorca, temat
        )
        return True, "Wysłano (DRY RUN - symulacja, e-mail NIE został faktycznie wysłany)", False

    try:
        with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg, from_addr=naglowek_od, to_addrs=[odbiorca])
        return True, "Wysłano", False
    except (smtplib.SMTPResponseException, smtplib.SMTPRecipientsRefused) as e:
        code = _extract_smtp_code(e)
        is_temp = code in SMTP_TEMP_FAIL_CODES
        # UWAGA: automatyczne dopisywanie do blacklisty przy 550 zostało
        # WYŁĄCZONE. Kod 550 bardzo często oznacza problem po stronie
        # nadawcy/dostawcy SMTP (np. niezweryfikowany "Od:" w Brevo, limit
        # dzienny konta itp.), a NIE że adres odbiorcy jest zły. Wcześniej
        # taka pomyłka powodowała masowe, błędne blacklistowanie realnych
        # leadów. Jeśli w przyszłości chcesz przywrócić auto-blacklistę,
        # rób to tylko dla naprawdę jednoznacznych przypadków (np. treść
        # błędu zawiera "user unknown", "does not exist" itp.), a nie dla
        # każdego 550.
        logger.warning("SMTP %s do %s (chwilowy=%s): %s", code, odbiorca, is_temp, e)
        return False, f"SMTP {code}: {e}", is_temp
    except smtplib.SMTPException as e:
        logger.error("Błąd SMTP do %s: %s", odbiorca, e)
        return False, str(e), False
    except OSError as e:
        logger.error("Błąd sieci do %s: %s", odbiorca, e)
        return False, f"Błąd połączenia: {e}", False

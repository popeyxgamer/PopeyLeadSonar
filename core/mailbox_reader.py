# -*- coding: utf-8 -*-
"""
Odczyt i obsługa skrzynki odbiorczej przez IMAP (zakładka "Skrzynka odbiorcza" w GUI).

Prosty, "na żądanie" odczyt (bez wątku w tle) - użytkownik klika "Odśwież"
w zakładce Skrzynka odbiorcza i widzi listę wiadomości dla wybranego konta
i folderu przypisanego do aktualnego profilu.

Część logiki (listowanie folderów, załączniki, oznaczanie/kasowanie) jest
inspirowana projektem OpenMail (moduł server/src/modules/openmail/imap.py),
ale przepisana od zera pod nasz stos: OpenMail wymaga Pythona 3.12+ (składnia
PEP 695 `type X = ...` oraz `typing.override`), a ta aplikacja ma działać na
Pythonie 3.11, więc nie da się tamtego pliku po prostu zaimportować.

Osobno działa już `core/bounce_imap.py` (automatyczne wykrywanie zwrotów
w tle) - ten moduł NIE go zastępuje, służy tylko do ręcznego podglądu/obsługi.
"""
import imaplib
import re
from dataclasses import dataclass, field
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.policy import default
from email.utils import parsedate_to_datetime, parseaddr
from typing import List, Optional, Tuple

from .config import logger

TRASH_FOLDER_HINTS = (
    "trash", "kosz", "papierkorb", "deleted", "gmail]/kosz", "gmail]/trash",
    "bin", "corbeille",
)
SPAM_FOLDER_HINTS = ("spam", "junk", "gmail]/spam")


@dataclass
class MailMessage:
    uid: str
    sender: str
    subject: str
    date: str
    snippet: str
    seen: bool


@dataclass
class Attachment:
    filename: str
    content_type: str
    size: int
    data: bytes = field(repr=False, default=b"")


@dataclass
class FullMessage:
    sender: str
    sender_email: str
    subject: str
    date: str
    body: str
    is_html: bool
    attachments: List[Attachment]


def _decode(value: Optional[str]) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="ignore"))
            except (LookupError, UnicodeDecodeError):
                out.append(text.decode("utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


def guess_imap_server(email_address: str, smtp_host: str = "") -> str:
    """Zgaduje serwer IMAP na podstawie adresu e-mail / hosta SMTP."""
    host_lower = (smtp_host or "").lower()
    addr_lower = (email_address or "").lower()
    if "gmail" in host_lower or "google" in host_lower or addr_lower.endswith("@gmail.com"):
        return "imap.gmail.com"
    if "outlook" in addr_lower or "hotmail" in addr_lower or "live" in addr_lower:
        return "outlook.office365.com"
    if "yahoo" in addr_lower:
        return "imap.mail.yahoo.com"
    domain = addr_lower.split("@")[-1] if "@" in addr_lower else ""
    return f"imap.{domain}" if domain else "imap.gmail.com"


def _imap_utf7_decode(name: bytes) -> str:
    text = name.decode("ascii", errors="ignore")
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "&":
            end = text.find("-", i + 1)
            if end == -1:
                end = len(text)
            chunk = text[i + 1:end]
            if chunk == "":
                result.append("&")
            else:
                b64 = chunk.replace(",", "/") + "=" * (-len(chunk) % 4)
                try:
                    import base64
                    raw = base64.b64decode(b64)
                    result.append(raw.decode("utf-16-be", errors="ignore"))
                except Exception:
                    result.append(chunk)
            i = end + 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def list_folders(email_address: str, password: str, imap_server: str) -> Tuple[bool, List[str], str]:
    """Zwraca listę nazw folderów dostępnych na koncie (np. INBOX, Wysłane, Spam, Kosz)."""
    try:
        conn = imaplib.IMAP4_SSL(imap_server, timeout=15)
        conn.login(email_address, password)
        status, data = conn.list()
        conn.logout()
        if status != "OK":
            return False, [], "Nie udało się pobrać listy folderów"

        folders = []
        pattern = re.compile(r'\((?P<flags>[^)]*)\)\s+"(?P<delim>[^"]*)"\s+(?P<name>.+)')
        for line in data:
            if not line:
                continue
            decoded_line = line.decode("utf-8", errors="ignore")
            m = pattern.match(decoded_line)
            if not m:
                continue
            flags = m.group("flags").lower()
            if "\\noselect" in flags:
                continue
            raw_name = m.group("name").strip().strip('"')
            folders.append(_imap_utf7_decode(raw_name.encode("ascii", errors="ignore")))
        return True, folders, ""
    except imaplib.IMAP4.error as e:
        return False, [], f"Błąd logowania IMAP: {e}"
    except Exception as e:
        logger.warning("Błąd listowania folderów IMAP: %s", e)
        return False, [], str(e)


def guess_trash_folder(folders: List[str]) -> Optional[str]:
    for f in folders:
        if any(hint in f.lower() for hint in TRASH_FOLDER_HINTS):
            return f
    return None


def fetch_recent_messages(
    email_address: str, password: str, imap_server: str,
    folder: str = "INBOX", limit: int = 30,
) -> Tuple[bool, List[MailMessage], str]:
    """
    Łączy się z serwerem IMAP i zwraca `limit` najnowszych wiadomości.
    Zwraca (sukces, lista_wiadomości, komunikat_błędu).
    """
    try:
        conn = imaplib.IMAP4_SSL(imap_server, timeout=15)
        conn.login(email_address, password)
        status, _ = conn.select(f'"{folder}"', readonly=True)
        if status != "OK":
            conn.logout()
            return False, [], f"Nie można otworzyć folderu {folder}"

        status, data = conn.search(None, "ALL")
        if status != "OK":
            conn.logout()
            return False, [], "Błąd wyszukiwania wiadomości"

        msg_ids = data[0].split()
        msg_ids = msg_ids[-limit:] if limit else msg_ids
        msg_ids.reverse()

        messages = []
        for msg_id in msg_ids:
            status, msg_data = conn.fetch(
                msg_id, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])"
            )
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            flags_part = msg_data[0][0].decode("utf-8", errors="ignore")
            seen = "\\Seen" in flags_part
            raw_headers = msg_data[0][1]
            msg = message_from_bytes(raw_headers, policy=default)

            date_str = msg.get("Date", "")
            try:
                dt = parsedate_to_datetime(date_str)
                date_display = dt.strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError):
                date_display = date_str[:16]

            messages.append(MailMessage(
                uid=msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
                sender=_decode(msg.get("From", "")),
                subject=_decode(msg.get("Subject", "(brak tematu)")),
                date=date_display,
                snippet="",
                seen=seen,
            ))

        conn.logout()
        return True, messages, ""
    except imaplib.IMAP4.error as e:
        return False, [], f"Błąd logowania IMAP: {e}"
    except Exception as e:
        logger.warning("Błąd odczytu skrzynki IMAP: %s", e)
        return False, [], str(e)


def _extract_body_and_attachments(msg):
    body = ""
    is_html = False
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            filename = part.get_filename()
            disposition = str(part.get("Content-Disposition") or "")

            if filename or "attachment" in disposition.lower():
                payload = part.get_payload(decode=True)
                if payload is not None:
                    attachments.append(Attachment(
                        filename=_decode(filename) or "załącznik",
                        content_type=content_type,
                        size=len(payload),
                        data=payload,
                    ))
                continue

            if content_type == "text/plain" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")

        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html" and not part.get_filename():
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                        is_html = True
                        break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
            is_html = msg.get_content_type() == "text/html"

    return body, is_html, attachments


def fetch_message_full(
    email_address: str, password: str, imap_server: str,
    uid: str, folder: str = "INBOX",
) -> Tuple[bool, Optional[FullMessage], str]:
    """Pobiera pełną treść wiadomości wraz z załącznikami w jednym zapytaniu."""
    try:
        conn = imaplib.IMAP4_SSL(imap_server, timeout=15)
        conn.login(email_address, password)
        conn.select(f'"{folder}"', readonly=True)

        raw_uid = uid.encode() if isinstance(uid, str) else uid
        status, msg_data = conn.fetch(raw_uid, "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            conn.logout()
            return False, None, "Nie udało się pobrać wiadomości"

        raw = msg_data[0][1]
        msg = message_from_bytes(raw, policy=default)
        conn.logout()

        body, is_html, attachments = _extract_body_and_attachments(msg)
        from_header = msg.get("From", "")
        sender_name, sender_email = parseaddr(from_header)

        date_str = msg.get("Date", "")
        try:
            dt = parsedate_to_datetime(date_str)
            date_display = dt.strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            date_display = date_str[:16]

        full = FullMessage(
            sender=_decode(from_header),
            sender_email=sender_email,
            subject=_decode(msg.get("Subject", "(brak tematu)")),
            date=date_display,
            body=body,
            is_html=is_html,
            attachments=attachments,
        )
        return True, full, ""
    except imaplib.IMAP4.error as e:
        return False, None, f"Błąd logowania IMAP: {e}"
    except Exception as e:
        logger.warning("Błąd odczytu treści wiadomości IMAP: %s", e)
        return False, None, str(e)


def fetch_message_body(
    email_address: str, password: str, imap_server: str,
    uid: str, folder: str = "INBOX",
) -> Tuple[bool, str, str]:
    """Zachowane dla wstecznej kompatybilności - zwraca samą treść tekstową."""
    ok, full, err = fetch_message_full(email_address, password, imap_server, uid, folder)
    if not ok or full is None:
        return False, "", err
    return True, full.body, ""


def set_message_flag(
    email_address: str, password: str, imap_server: str,
    uid: str, folder: str, flag: str = "\\Seen", add: bool = True,
) -> Tuple[bool, str]:
    """Dodaje lub usuwa flagę (np. \\Seen) z wiadomości - do oznaczania przeczytane/nieprzeczytane."""
    try:
        conn = imaplib.IMAP4_SSL(imap_server, timeout=15)
        conn.login(email_address, password)
        conn.select(f'"{folder}"', readonly=False)
        raw_uid = uid.encode() if isinstance(uid, str) else uid
        command = "+FLAGS" if add else "-FLAGS"
        status, _ = conn.store(raw_uid, command, f"({flag})")
        conn.logout()
        if status != "OK":
            return False, "Nie udało się zmienić flagi wiadomości"
        return True, ""
    except imaplib.IMAP4.error as e:
        return False, f"Błąd logowania IMAP: {e}"
    except Exception as e:
        logger.warning("Błąd zmiany flagi wiadomości IMAP: %s", e)
        return False, str(e)


def delete_message(
    email_address: str, password: str, imap_server: str,
    uid: str, folder: str, trash_folder: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Usuwa wiadomość. Jeśli podano `trash_folder` i jest inny niż `folder`,
    najpierw kopiuje wiadomość do kosza (tak działa większość klientów pocztowych),
    a dopiero potem oznacza jako usuniętą i czyści folder źródłowy.
    """
    try:
        conn = imaplib.IMAP4_SSL(imap_server, timeout=15)
        conn.login(email_address, password)
        conn.select(f'"{folder}"', readonly=False)
        raw_uid = uid.encode() if isinstance(uid, str) else uid

        if trash_folder and trash_folder != folder:
            conn.copy(raw_uid, f'"{trash_folder}"')

        conn.store(raw_uid, "+FLAGS", "(\\Deleted)")
        conn.expunge()
        conn.logout()
        return True, ""
    except imaplib.IMAP4.error as e:
        return False, f"Błąd logowania IMAP: {e}"
    except Exception as e:
        logger.warning("Błąd usuwania wiadomości IMAP: %s", e)
        return False, str(e)

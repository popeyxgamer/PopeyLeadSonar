# -*- coding: utf-8 -*-
"""Import listy rezygnacji z pliku CSV/TXT."""
from . import database as db
from .config import logger


def import_blacklist_from_file(path: str, reason: str = "import") -> int:
    """
    Importuje adresy e-mail z pliku (jeden na linię) do blacklist.
    Obsługuje pliki .txt i .csv (pierwsza kolumna).
    """
    count = 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Jeśli CSV, weź pierwszą kolumnę
                if ',' in line:
                    email = line.split(',')[0].strip()
                else:
                    email = line
                email = email.lower()
                if '@' in email:
                    if db.add_to_blacklist(email, reason):
                        count += 1
        logger.info("Zaimportowano %d adresów do blacklist z %s", count, path)
        return count
    except Exception as e:
        logger.error("Błąd importu blacklist: %s", e)
        raise
# -*- coding: utf-8 -*-
"""Spam score analyzer for email content."""
import re
from typing import Dict, List, Tuple

SPAM_WORDS = {
    "kostenlos", "gratis", "sofort", "jetzt", "gewinn", "gewinnen",
    "bonus", "aktion", "einmalig", "begrenzt", "exklusiv", "nur heute",
    "keine verpflichtung", "geld zurueck", "garantie", "erfolg",
    "kredit", "versicherung", "geld", "angebot", "rabatt", "%",
    "dringend", "wichtig", "sofort handeln", "nicht verpassen",
    "free", "cash", "money", "offer", "urgent", "guarantee",
    "cheap", "deal", "discount", "limited", "exclusive",
}


def analyze_spam(text: str) -> Tuple[int, List[str], Dict[str, int]]:
    """
    Analizuje treść pod kątem ryzyka spamowego.
    Zwraca (score 0-100, warnings, details).
    """
    score = 0
    warnings = []
    details: Dict[str, int] = {}

    # CAPS LOCK
    upper_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if upper_ratio > 0.3:
        score += 25
        warnings.append("Ponad 30% tekstu wielkimi literami")
        details["caps_ratio"] = round(upper_ratio * 100)

    # Wykrzykniki
    exclamation_count = text.count('!')
    if exclamation_count > 3:
        score += min(exclamation_count * 2, 15)
        warnings.append(f"Zbyt wiele wykrzykników ({exclamation_count})")
        details["exclamation_count"] = exclamation_count

    # Słowa spamowe
    lower = text.lower()
    found_words = [w for w in SPAM_WORDS if w in lower]
    if found_words:
        score += min(len(found_words) * 5, 30)
        warnings.append(f"Słowa spamowe: {', '.join(found_words[:5])}")
        details["spam_words"] = len(found_words)

    # Linki
    links = re.findall(r'https?://[^\s<>"]+', text)
    link_count = len(links)
    if link_count > 2:
        score += min(link_count * 3, 20)
        warnings.append(f"Zbyt wiele linków ({link_count})")
        details["link_count"] = link_count

    # Długość
    word_count = len(re.findall(r'\S+', text))
    if word_count < 10:
        score += 10
        warnings.append("Bardzo krótka treść")
        details["word_count"] = word_count
    elif word_count > 1000:
        score += 5
        warnings.append("Bardzo długa treść")

    score = min(score, 100)
    details["score"] = score
    return score, warnings, details
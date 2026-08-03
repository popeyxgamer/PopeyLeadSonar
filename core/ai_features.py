# -*- coding: utf-8 -*-
"""
AI funkcjonalności: generatory, optymalizatory, analizatory.
"""
from typing import Optional, List, Dict, Any
import json
import re
from .ai_providers import ai_manager
from .scraping import fetch_page_text
from .config import logger


def _parse_json_response(raw: Optional[str], context: str) -> Optional[Dict[str, Any]]:
    """
    Parsuje JSON zwrócony przez model AI w sposób odporny na typowe
    "ozdobniki" (blok markdown ```json ... ```, zdanie przed/po właściwym
    obiekcie) - lokalne modele (Ollama/LM Studio) bardzo często tak robią,
    mimo że prompt prosi o "czysty" JSON.

    Przy niepowodzeniu loguje surową (skróconą) odpowiedź, żeby dało się
    zdiagnozować co faktycznie odpowiedział provider - wcześniej log mówił
    tylko "nie udało się sparsować", bez treści.
    """
    if not raw:
        return None

    text = raw.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: wytnij fragment od pierwszego "{" do ostatniego "}"
    # (na wypadek gdy model doleci zdanie przed/po samym obiekcie JSON)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    logger.error(
        "Failed to parse %s JSON. Surowa odpowiedź providera (pierwsze 300 znaków): %r",
        context, raw[:300]
    )
    return None


# Wzorce sugerujace ze wygenerowany tekst NEGATYWNIE OCENIA jakosc/kompetencje/
# profesjonalizm ODBIORCY cold maila - np. "schlechte Qualitaet der Bauleistungen",
# "zla jakosc uslug". To DODATKOWA, TECHNICZNA blokada (poza instrukcja w prompcie),
# bo sam prompt nie daje 100% gwarancji przy mniejszych/lokalnych modelach - model
# potrafi mimo zakazu wygenerowac obrazliwe "obserwacje" o firmie odbiorcy (halucynacja
# z etapu analyze_website przepisana wprost do maila). Dopasowanie jest CELOWO
# uproszczone (podciagi, case-insensitive) - to heurystyka/siatka bezpieczenstwa,
# NIE gwarancja: nie wylapie kazdej parafrazy, moze tez sporadycznie dac false
# positive na neutralnym zdaniu zawierajacym takie slowo w innym kontekscie. W razie
# false positive/negative dopisz/usun wzorce w liscie ponizej.
_NEGATIVE_ASSESSMENT_PATTERNS = [
    # niemiecki
    "schlechte qualit", "schlechten qualit", "mangelhaft", "unzureichend",
    "unprofessionell", "minderwertig", "fehlerhaft", "unfähig", "unfahig",
    "enttäuschend", "enttauschend", "unqualifiziert", "schwache leistung",
    "mangel an", "defizit", "problematisch", "nicht zufriedenstellend",
    # polski
    "zla jakosc", "zła jakość", "slaba jakosc", "słaba jakość",
    "niewystarczając", "niewystarczaj", "nieprofesjonaln", "kiepsk",
    "niekompetent", "niedociagni", "niedociągni",
    # angielski
    "poor quality", "inadequate", "unprofessional", "substandard",
    "incompetent", "disappointing", "low quality", "lacking in",
    "fails to deliver", "deficient",
]


def _find_negative_assessment(text: str) -> Optional[str]:
    """Zwraca dopasowany wzorzec, jesli tekst sugeruje negatywna ocene
    jakosci/kompetencji/profesjonalizmu odbiorcy, albo None jesli nic
    nie znaleziono. Patrz komentarz przy _NEGATIVE_ASSESSMENT_PATTERNS."""
    lowered = text.lower()
    for pattern in _NEGATIVE_ASSESSMENT_PATTERNS:
        if pattern in lowered:
            return pattern
    return None


# Mapowanie alternatywnych nazw pol, ktorych model MOZE uzyc zamiast tych ze
# schematu w prompcie, mimo jawnej instrukcji "odpowiedz DOKLADNIE w tym
# formacie". Zaobserwowane w praktyce (DeepSeek): "lead_score" zamiast
# "score", "reasoning"/"match_assessment" zamiast "reason", "recommendation"
# zamiast "recommended_action". Bez tej normalizacji kod wywolujacy
# (workers.py) robi `score_data.get("score", -1)` - gdy klucz sie nie
# zgadza, dostaje -1, co jest ZAWSZE ponizej progu i lead zostaje CICHO
# pominiety, wygladajac identycznie jak normalny "zly lead", zamiast jak
# blad parsowania. To potrafilo psuc caly przebieg (setki leadow pominietych)
# bez zadnego widocznego bledu w logu.
_SCORE_FIELD_ALIASES = {
    "score": ["score", "lead_score", "leadscore", "rating", "punktacja"],
    "reason": ["reason", "reasoning", "match_assessment", "uzasadnienie", "opis"],
    "recommended_action": ["recommended_action", "recommendation", "action", "rekomendacja", "next_steps"],
    "is_spam": ["is_spam", "spam", "isspam"],
    "lead_type": ["lead_type", "leadtype", "type"],
}


def _normalize_score_fields(parsed: Optional[Dict[str, Any]],
                             company_name: str = "") -> Optional[Dict[str, Any]]:
    """Sprowadza odpowiedz AI z score_lead do oczekiwanego schematu, nawet
    jesli model uzyl innych nazw pol niz w prompcie. Loguje WYRAZNE
    ostrzezenie gdy trzeba bylo cokolwiek zmapowac, zeby bylo widac w logach
    ze to problem ze zgodnoscia formatu providera, a nie zwykly niski wynik."""
    if not parsed:
        return None

    normalized = dict(parsed)
    remapped = []
    for canonical, aliases in _SCORE_FIELD_ALIASES.items():
        if canonical in normalized:
            continue
        for alias in aliases:
            if alias in normalized:
                normalized[canonical] = normalized[alias]
                remapped.append(f"{alias}->{canonical}")
                break

    if remapped:
        logger.warning(
            "score_lead: provider dla '%s' nie trzymal sie nazw pol z promptu, "
            "zmapowano: %s. Warto sprawdzic czy provider dobrze rozumie "
            "instrukcje formatu JSON.", company_name, ", ".join(remapped)
        )

    if "score" not in normalized:
        logger.error(
            "score_lead: BRAK pola score (ani zadnego znanego aliasu) w "
            "odpowiedzi dla '%s' - surowe klucze: %s. Lead zostanie "
            "potraktowany jako blad oceny (nie jako niski wynik), zeby nie "
            "zniknal cicho z powodu -1.",
            company_name, list(parsed.keys())
        )
        return None  # jawny blad parsowania, NIE cichy score=-1

    try:
        normalized["score"] = int(float(normalized["score"]))
    except (TypeError, ValueError):
        logger.error(
            "score_lead: pole score dla '%s' nie jest liczba (%r) - "
            "traktowane jako blad oceny.", company_name, normalized.get("score")
        )
        return None

    normalized.setdefault("is_spam", False)
    normalized.setdefault("reason", "")
    normalized.setdefault("recommended_action", "nurture")
    normalized.setdefault("lead_type", "niejasne")
    return normalized


class TemplateGenerator:
    """Generuje szablony e-maili na podstawie branży/produktu."""
    
    @staticmethod
    def generate(industry: str, product: str, tone: str = "professional") -> Optional[List[str]]:
        """Generuj 3 warianty szablonu."""
        system_prompt = f"""Jesteś ekspertem w cold outreach. Generuj szablony e-maili B2B.
Zwróć dokładnie 3 warianty, oddzielone "---".
Każdy wariant powinien:
- Mieć unikalne podejście
- Zawierać {{firma}}, {{kontakt}}, {{adres}}, {{website}}
- Być w tonie: {tone}
- Nie zawierać spamowych fraz
- Być krótki (2-3 akapity)"""
        
        prompt = f"""Wygeneruj 3 warianty szablonu e-maila dla:
Branża: {industry}
Produkt/Usługa: {product}

Zwróć je jako:
WARIANT 1:
[treść]
---
WARIANT 2:
[treść]
---
WARIANT 3:
[treść]"""
        
        result = ai_manager.generate(prompt, system_prompt, temperature=0.8, max_tokens=1500)
        if not result:
            return None
        
        templates = result.split("---")
        templates = [t.strip() for t in templates if t.strip()]
        
        # Wyczyść nagłówki wariantów
        cleaned = []
        for t in templates:
            lines = t.split("\n")
            # Usuń linię z "WARIANT X:"
            clean_lines = [l for l in lines if not l.strip().startswith("WARIANT")]
            cleaned.append("\n".join(clean_lines).strip())
        
        return cleaned[:3]


class SubjectLineOptimizer:
    """Optymalizuje subject lines."""
    
    @staticmethod
    def generate_variants(topic: str, industry: str, count: int = 5) -> Optional[List[str]]:
        """Generuj warianty subject line."""
        system_prompt = """Jesteś ekspertem w copywriting. Twoje subject linie mają wysoki open rate.
Generuj subject linie które:
- Są krótkie (3-6 słów)
- Zawierają copywriting trigger
- Nie są spamowe
- Są personalne
- Nie mają caps lock"""
        
        prompt = f"""Wygeneruj {count} wariantów subject line dla:
Temat: {topic}
Branża: {industry}

Zwróć jako listę, jeden na linię, bez numeracji."""
        
        result = ai_manager.generate(prompt, system_prompt, temperature=0.9, max_tokens=500)
        if not result:
            return None
        
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        return lines[:count]
    
    @staticmethod
    def score_subject_line(subject: str) -> Optional[int]:
        """Ocen subject line od 1-100."""
        system_prompt = """Jesteś ekspertem w email marketingu. 
Oceniaj subject linie na skali 1-100.
Zwróć TYLKO liczbę, nic więcej."""
        
        prompt = f"""Oceń ten subject line:
"{subject}"

Ocena:"""
        
        result = ai_manager.generate(prompt, system_prompt, temperature=0.3, max_tokens=10)
        if not result:
            return None
        
        try:
            return int(result.strip())
        except Exception:
            return None


class LeadPersonalizer:
    """Personalizuje wiadomości na podstawie strony www firmy."""
    
    @staticmethod
    def analyze_website(company_name: str, website: str, industry: str,
                       page_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Analizuj website i zwróć insights.

        WAZNE: to faktycznie pobiera i czyta tresc strony (fetch_page_text),
        zamiast (jak wczesniej) prosic model o zgadywanie insightow na
        podstawie samego URL-a - to prowadzilo do halucynacji. Mozna podac
        `page_text` z gory (np. gdy wywolujacy juz go pobral wczesniej w
        petli), zeby nie pobierac tej samej strony dwa razy."""
        if page_text is None:
            page_text = fetch_page_text(website)

        if not page_text:
            logger.warning(
                "analyze_website: nie udalo sie pobrac tresci strony '%s' - "
                "insighty beda oparte tylko na nazwie/branzy (mniej dokladne).",
                website
            )

        system_prompt = """Jesteś analistą B2B. Na podstawie PRAWDZIWEJ tresci strony firmy
(nie zgaduj, opieraj sie wylacznie na dostarczonym tekscie) zwróć JSON z insights.
Jesli dostarczona tresc jest pusta/nic nie mowi o firmie, ustaw wszystkie pola
na puste listy/stringi zamiast zmyslac.

KRYTYCZNE OGRANICZENIE dla pola "pain_points": to NIE jest miejsce na ocene
jakosci pracy, kompetencji czy profesjonalizmu opisywanej firmy - taka ocena
nie da sie wiarygodnie wyciagnac z samej tresci ich strony, a wyslana pozniej
do tej firmy jako "obserwacja" w cold mailu bylaby niesprawiedliwa i obrazliwa
(np. NIGDY nie pisz czegos w rodzaju "zla jakosc uslug" albo "niewystarczajacy
kontakt z klientami" - to zmyslona krytyka, nie fakt). "pain_points" maja byc
WYLACZNIE NEUTRALNYMI, WERYFIKOWALNYMI brakami/lukami WIDOCZNYMI wprost w
dostarczonym tekscie strony (np. "brak sklepu internetowego", "brak wersji
jezykowej po angielsku", "brak formularza kontaktowego", "brak cennika online")
- czyli rzeczy ktore firma faktycznie MOZE nie miec, a nie ocena tego, jak
dobrze robia to co robia. Jesli tekst strony nie daje podstaw do zadnego
takiego neutralnego spostrzezenia, zostaw "pain_points" jako pusta liste.

Odpowiedz WYŁĄCZNIE surowym obiektem JSON, bez bloków markdown (```),
bez żadnego tekstu przed ani po. Format:
{
  "pain_points": ["problem1", "problem2"],
  "products": ["produkt1"],
  "company_stage": "startup/scaleup/enterprise",
  "decision_maker": "rola",
  "personalization_hooks": ["hook1"]
}"""

        content_block = page_text[:3000] if page_text else "(nie udalo sie pobrac tresci strony)"
        prompt = f"""Analizuj tę firmę na podstawie prawdziwej tresci jej strony:
Nazwa: {company_name}
Website: {website}
Branża: {industry}

Tresc strony (wyciag):
\"\"\"
{content_block}
\"\"\"

Zwróć insights jako JSON."""

        result = ai_manager.generate(prompt, system_prompt, temperature=0.5, max_tokens=500,
                                      expects_json=True)
        if not result:
            return None

        return _parse_json_response(result, "website analysis")
    
    LANGUAGE_NAMES = {
        "auto": None,
        "de": "niemiecki (Deutsch)",
        "pl": "polski",
        "en": "angielski (English)",
    }

    # Providery, dla ktorych warto dopasowac JEZYK CALEGO PROMPTA (nie tylko
    # docelowej tresci) do wybranego jezyka maila - lokalne, mniejsze modele
    # (Ollama/LM Studio) sa bardziej podatne na "przeciek" jezyka dominujacego
    # w kontekscie (np. caly prompt po polsku + jedno zdanie-rozkaz "pisz po
    # niemiecku" -> pojedyncze polskie slowo i tak sie przebija). Hostowane
    # providery (OpenAI, Gemini, DeepSeekLaude) radza sobie z tym dobrze przy
    # dotychczasowym (polskim) prompcie, wiec CELOWO ich tu nie ruszamy.
    _LOCAL_PROVIDERS_MATCH_PROMPT_LANGUAGE = {"ollama", "lmstudio"}

    @staticmethod
    def write_cold_email(company_name: str, industry: str,
                        sender_company: str, sender_offer: str,
                        website_insights: Optional[Dict] = None,
                        contact_name: str = "",
                        language: str = "auto") -> Optional[Dict[str, str]]:
        """Napisz tresc (bez stopki) spersonalizowanego cold maila B2B.

        Zwraca {"subject": ..., "body": ...} albo None. Stopka z danymi firmy
        (nazwa/adres/telefon/Impressum) NIE jest generowana tutaj - doklejana
        jest programowo (patrz workers.AIAutoSendWorker), zeby zawsze byla
        obecna i poprawna, niezaleznie od tego co wygeneruje model.

        `sender_offer` to krotki, ludzki opis czym zajmuje sie NASZA firma
        (np. "tworzymy strony internetowe i sklepy online dla MSP") - model
        MA go uzyc do przedstawienia firmy, a nie zmyslac wlasny opis.

        `language`: "auto" (model sam dopasowuje jezyk do kontekstu firmy,
        domyslnie niemiecki - jak dotychczas) albo jeden z konkretnych kodow
        ("de", "pl", "en") ustawiony w UI (AI Auto Send).

        Gdy aktywny provider to Ollama albo LM Studio (lokalne modele) I
        wybrano konkretny jezyk (nie "auto"), CALY prompt (instrukcje +
        etykiety, nie tylko tresc wynikowa) jest budowany w tym samym
        jezyku co docelowa wiadomosc - eliminuje to kontrast typu "polskie
        instrukcje -> niemiecki wynik", ktory u mniejszych modeli powodowal
        pojedyncze przeciekajace slowa mimo jawnej reguly jezykowej. Dla
        pozostalych providerow (OpenAI/Gemini/DeepSeekLaude) oraz dla
        language="auto" zachowanie jest DOKLADNIE takie jak dotychczas
        (polski prompt) - te sciezki dzialaly dobrze i nie sa tu ruszane.

        Uwaga: to generuje TRESC maila, nie ocenia zgodnosci prawnej wysylki
        z lokalnymi przepisami o e-mail marketingu (np. niemieckim UWG) -
        to lezy po stronie uzytkownika/prawnika."""
        insights_text = json.dumps(website_insights, ensure_ascii=False) if website_insights else "brak danych o stronie"

        active_provider_id = ai_manager.active_provider
        match_prompt_language = (
            active_provider_id in LeadPersonalizer._LOCAL_PROVIDERS_MATCH_PROMPT_LANGUAGE
            and language in ("de", "en")  # "pl" i "auto" ida sciezka polska (patrz nizej)
        )

        if match_prompt_language:
            system_prompt, prompt = LeadPersonalizer._build_cold_email_prompt_native(
                language, company_name, industry, sender_company, sender_offer,
                contact_name, insights_text
            )
        else:
            system_prompt, prompt = LeadPersonalizer._build_cold_email_prompt_pl(
                language, company_name, industry, sender_company, sender_offer,
                contact_name, insights_text
            )

        prompt_language_for_hint = language if language in ("de", "en") and match_prompt_language else "pl"
        base_prompt = prompt

        # AI-review + retry (drugie, "madrzejsze" wywolanie AI oceniajace czy
        # tresc moze byc obrazliwa) dziala TYLKO dla lokalnych providerow
        # (Ollama/LM Studio) - to one generuja obrazliwe tresci w praktyce
        # (patrz zaobserwowany przypadek z llama3.1:8b). Hostowane/platne
        # providery (OpenAI, Gemini, DeepSeekLaude) dostaja tylko darmowy,
        # bezwywolaniowy filtr na slowach kluczowych - bez dodatkowego kosztu/
        # czasu na czyms, co u nich w praktyce nie wystepowalo.
        use_ai_review = active_provider_id in LeadPersonalizer._LOCAL_PROVIDERS_MATCH_PROMPT_LANGUAGE
        MAX_ATTEMPTS = 2 if use_ai_review else 1

        for attempt in range(1, MAX_ATTEMPTS + 1):
            result = ai_manager.generate(prompt, system_prompt, temperature=0.6, max_tokens=700,
                                          expects_json=True)
            if not result:
                return None

            parsed = _parse_json_response(result, "cold email")
            if not parsed or "subject" not in parsed or "body" not in parsed:
                return None

            subject_body = f"{parsed.get('subject', '')}\n{parsed.get('body', '')}"

            # Szybki, darmowy filtr na slowach kluczowych (patrz komentarz przy
            # _NEGATIVE_ASSESSMENT_PATTERNS) - dziala ZAWSZE, dla kazdego
            # providera (zero kosztu, brak dodatkowego wywolania AI).
            flagged_pattern = _find_negative_assessment(subject_body)
            reason = f"zawiera fraze '{flagged_pattern}' sugerujaca negatywna ocene odbiorcy" if flagged_pattern else None

            # Drugi, "madrzejszy" filtr - pytamy sam model (osobnym wywolaniem),
            # czy tresc MOZE zostac odebrana jako obrazliwa/deprecjonujaca przez
            # odbiorce. Wylapuje parafrazy, ktorych lista slow kluczowych nie
            # zlapie. TYLKO dla lokalnych providerow (patrz use_ai_review wyzej).
            if not reason and use_ai_review:
                review = LeadPersonalizer._review_email_for_offense(
                    parsed.get("subject", ""), parsed.get("body", ""), company_name
                )
                if review and review.get("potentially_offensive"):
                    reason = review.get("reason") or "model ocenil tresc jako potencjalnie obrazliwa"

            if not reason:
                return parsed  # przeszlo filtry - OK, wysylamy

            logger.warning(
                "write_cold_email: probe %d/%d dla firmy '%s' odrzucono - powod: %s "
                "(provider: %s). Tresc do wgladu: %r",
                attempt, MAX_ATTEMPTS, company_name, reason, active_provider_id,
                parsed.get("body", "")[:500]
            )

            if attempt < MAX_ATTEMPTS:
                hint = LeadPersonalizer._RETRY_HINTS[prompt_language_for_hint].format(reason=reason)
                prompt = base_prompt + hint

        logger.warning(
            "write_cold_email: proba(y) dla firmy '%s' odrzucone jako potencjalnie "
            "obrazliwe - lead zostanie pominiety zamiast wyslany.", company_name
        )
        return None

    _RETRY_HINTS = {
        "pl": (
            "\n\nWAZNE: poprzednia proba zostala odrzucona, bo mogla zostac odebrana jako "
            "obrazliwa dla odbiorcy (powod: {reason}). Napisz mail OD NOWA, upewniajac sie "
            "ze w zaden sposob nie oceniasz negatywnie odbiorcy ani jego dzialalnosci."
        ),
        "de": (
            "\n\nWICHTIG: Der vorherige Versuch wurde abgelehnt, da er fuer den Empfaenger "
            "beleidigend wirken koennte (Grund: {reason}). Schreibe die E-Mail NEU und stelle "
            "sicher, dass du den Empfaenger oder dessen Taetigkeit in keiner Weise negativ "
            "bewertest."
        ),
        "en": (
            "\n\nIMPORTANT: The previous attempt was rejected because it could be perceived "
            "as offensive to the recipient (reason: {reason}). Rewrite the email from "
            "scratch, making sure you do not negatively assess the recipient or their "
            "business in any way."
        ),
    }

    @staticmethod
    def _review_email_for_offense(subject: str, body: str,
                                   company_name: str) -> Optional[Dict[str, Any]]:
        """Osobne, niezalezne wywolanie AI: oceniamy CZY gotowa tresc maila
        moze zostac odebrana jako obrazliwa/deprecjonujaca przez firme-odbiorce.
        To NIE jest ten sam model/prompt co pisanie maila - swiezy "spojrzenie
        z zewnatrz" lapie parafrazy, ktorych prosty filtr na slowach kluczowych
        (_find_negative_assessment) by nie zlapal.

        Zwraca {"potentially_offensive": bool, "reason": str} albo None jesli
        samo wywolanie AI zawiodlo (np. provider niedostepny) - w takim wypadku
        wywolujacy powinien potraktowac to jako "nie wykryto problemu" (nie
        blokowac wysylki tylko dlatego, ze sam review sie nie udal), bo
        _find_negative_assessment i tak juz wczesniej przepuscil te tresc."""
        system_prompt = """Jestes bezstronnym recenzentem tresci cold maili B2B. Twoim
JEDYNYM zadaniem jest ocenic, czy PONIZSZY e-mail moglby zostac odebrany jako
obrazliwy, deprecjonujacy, oskarzycielski lub lekcewazacy przez firme, do
ktorej jest adresowany - np. sugeruje ze maja zla jakosc uslug/produktow,
brak kompetencji, sa nieprofesjonalni, cos robia zle, maja jakis "problem"
ktory autor maila "zauwazyl". Nie oceniaj stylu, gramatyki ani skutecznosci
sprzedazowej - WYLACZNIE czy tresc mogla by obrazic/zdenerwowac odbiorce.

Odpowiedz WYLACZNIE surowym obiektem JSON, bez markdown, w formacie:
{"potentially_offensive": true/false, "reason": "krotkie uzasadnienie po polsku"}"""

        prompt = f"""Firma-odbiorca: {company_name}

Temat maila:
{subject}

Tresc maila:
{body}

Oceń jako JSON."""

        result = ai_manager.generate(prompt, system_prompt, temperature=0.2, max_tokens=200,
                                      expects_json=True)
        if not result:
            return None
        return _parse_json_response(result, "email offense review")


    @staticmethod
    def _build_cold_email_prompt_pl(language, company_name, industry, sender_company,
                                     sender_offer, contact_name, insights_text):
        """Dotychczasowy wariant: instrukcje po polsku, jezyk wynikowy sterowany
        jednym zdaniem-regula. Uzywany dla providerow hostowanych (OpenAI/
        Gemini/DeepSeekLaude) niezaleznie od wyboru jezyka, oraz zawsze gdy
        language="auto" lub "pl"."""
        forced_language = LeadPersonalizer.LANGUAGE_NAMES.get(language)
        if forced_language:
            language_rule = f"Piszesz WYLACZNIE po {forced_language}."
        else:
            language_rule = (
                "Piszesz PO NIEMIECKU (jesli firma jest niemieckojezyczna) lub po polsku "
                "(jesli nazwa/branza sugeruja polskiego odbiorce) - dopasuj jezyk do "
                "kontekstu, domyslnie niemiecki."
            )

        system_prompt = f"""Jestes copywriterem pierwszego kontaktu B2B (cold outreach).
{language_rule}

KRYTYCZNA ZASADA JEZYKOWA: caly e-mail (temat ORAZ tresc) MUSI byc napisany
w JEDNYM, TYM SAMYM jezyku od pierwszego do ostatniego slowa. Nie wolno Ci
mieszac jezykow w obrebie jednej wiadomosci - ani pojedynczych slow, ani
zdan, ani fragmentow (np. zdanie po polsku wstawione w niemiecki tekst).
Jesli nie jestes pewien/pewna jezyka, wybierz jeden i konsekwentnie go trzymaj
do konca calej wiadomosci.

Mail MUSI miec DOKLADNIE te elementy, w tej kolejnosci:
1. Krotkie, konkretne powitanie (uzyj imienia kontaktu jesli podane, inaczej neutralne "Sehr geehrte Damen und Herren").
2. Przedstawienie NASZEJ firmy - kim jestesmy i CZYM SIE ZAJMUJEMY (na podstawie
   dostarczonego opisu oferty) - 1-2 zdania, konkretnie, bez marketingowego przesadyzmu.
3. Krotkie nawiazanie do OBSERWACJI o firmie odbiorcy (na podstawie insightow z ich
   strony, jesli sa dostepne) - pokazujace ze wiadomosc jest personalizowana, nie masowa.
4. WPROST zadane pytanie, czy maja/moga miec potrzebe takiej uslugi - nie zakladaj
   z gory, ze na pewno potrzebuja, tylko pytaj.
5. Krotkie zakonczenie zachecajace do odpowiedzi (np. "Chetnie odpowiem na pytania"),
   BEZ podpisu/stopki - stopka zostanie doklejona automatycznie.

Zasady:
- Maks. 120-150 slow w tresci (bez stopki).
- Zero pustych fraz marketingowych ("rewolucyjne rozwiazanie", "najlepszy na rynku").
- Bez wymyslania faktow o firmie odbiorcy, ktorych nie ma w insightach - jesli insighty
  sa puste, napisz mail bardziej ogolny, ale wciaz grzeczny i konkretny odnosnie NASZEJ oferty.
- KRYTYCZNE: NIGDY nie krytykuj ani nie oceniaj negatywnie dzialalnosci, jakosci pracy,
  kompetencji czy profesjonalizmu odbiorcy - nawet jesli insighty sugeruja jakis "problem".
  To niesprawiedliwe (nie znamy ich naprawde) i obrazliwe dla potencjalnego klienta.
  Insighty uzywaj WYLACZNIE do pokazania, ze wiadomosc jest spersonalizowana (np. "zauwazylismy,
  ze zajmujecie sie X" / "widzimy ze rozwijacie dzialalnosc w Y") - NIGDY do stwierdzania, czego
  im brakuje, co robia zle, lub sugerowania ze maja jakis niedostatek/problem.
- Nie dodawaj stopki, danych kontaktowych ani podpisu - to dojdzie automatycznie.

Odpowiedz WYLACZNIE surowym obiektem JSON, bez blokow markdown, w formacie:
{{"subject": "...", "body": "..."}}"""

        prompt = f"""Napisz cold mail pierwszego kontaktu.

NASZA firma: {sender_company}
Czym sie zajmujemy: {sender_offer}

Firma odbiorcy: {company_name}
Branza odbiorcy: {industry}
Osoba kontaktowa: {contact_name or "(nieznana)"}

Insighty o stronie odbiorcy (z realnej tresci ich strony):
{insights_text}

Zwroc JSON z "subject" i "body" (bez stopki/podpisu). Pamietaj: caly mail w
JEDNYM jezyku, bez mieszania."""
        return system_prompt, prompt

    @staticmethod
    def _build_cold_email_prompt_native(language, company_name, industry, sender_company,
                                         sender_offer, contact_name, insights_text):
        """Prompt CALY w jezyku docelowym (de/en) - tylko dla lokalnych
        providerow (Ollama/LM Studio), zeby usunac kontrast jezykowy miedzy
        instrukcjami a oczekiwanym wynikiem."""
        if language == "de":
            system_prompt = """Du bist Copywriter fuer die B2B-Erstkontakt-Kaltakquise (Cold Outreach).
Du schreibst AUSSCHLIESSLICH auf Deutsch.

KRITISCHE SPRACHREGEL: Die gesamte E-Mail (Betreff UND Text) MUSS von Anfang
bis Ende in EINER, DERSELBEN Sprache (Deutsch) verfasst sein. Du darfst
innerhalb einer Nachricht keine Sprachen mischen - weder einzelne Woerter
noch Saetze noch Satzteile. Bleibe konsequent bei Deutsch bis zum Ende der
gesamten Nachricht.

Die E-Mail MUSS GENAU diese Elemente in dieser Reihenfolge enthalten:
1. Kurze, konkrete Begruessung (nutze den Namen des Kontakts, falls angegeben, sonst neutral "Sehr geehrte Damen und Herren").
2. Vorstellung UNSERES Unternehmens - wer wir sind und WAS WIR ANBIETEN (basierend auf der bereitgestellten Angebotsbeschreibung) - 1-2 Saetze, konkret, ohne Marketing-Uebertreibung.
3. Kurzer Bezug zu einer BEOBACHTUNG ueber das Unternehmen des Empfaengers (basierend auf den Insights von dessen Website, falls verfuegbar) - zeigt, dass die Nachricht personalisiert und nicht Massenware ist.
4. DIREKT gestellte Frage, ob Bedarf an dieser Dienstleistung besteht oder bestehen koennte - unterstelle nicht von vornherein einen Bedarf, sondern frage.
5. Kurzer Abschluss, der zur Antwort ermutigt (z.B. "Gerne beantworte ich Ihre Fragen"), OHNE Signatur/Fusszeile - diese wird automatisch angehaengt.

Regeln:
- Max. 120-150 Woerter im Text (ohne Fusszeile).
- Keine leeren Marketing-Phrasen ("revolutionaere Loesung", "beste auf dem Markt").
- Erfinde keine Fakten ueber das Empfaengerunternehmen, die nicht in den Insights stehen - wenn die Insights leer sind, schreibe eine allgemeinere, aber weiterhin hoefliche und konkrete E-Mail bezueglich UNSERES Angebots.
- KRITISCH: Kritisiere oder bewerte NIEMALS die Taetigkeit, Arbeitsqualitaet, Kompetenz oder
  Professionalitaet des Empfaengers negativ - auch nicht, wenn die Insights ein "Problem"
  nahelegen. Das ist unfair (wir kennen sie nicht wirklich) und beleidigend fuer einen
  potenziellen Kunden. Nutze Insights AUSSCHLIESSLICH, um zu zeigen, dass die Nachricht
  personalisiert ist (z.B. "wir haben gesehen, dass Sie sich auf X spezialisiert haben") -
  NIEMALS, um zu behaupten, was ihnen fehlt, was sie falsch machen, oder ein Defizit/Problem
  zu unterstellen.
- Fuege keine Fusszeile, Kontaktdaten oder Unterschrift hinzu - das wird automatisch ergaenzt.

Antworte AUSSCHLIESSLICH mit einem rohen JSON-Objekt, ohne Markdown-Bloecke, im Format:
{"subject": "...", "body": "..."}"""

            prompt = f"""Schreibe eine Erstkontakt-Kalt-E-Mail.

UNSER Unternehmen: {sender_company}
Was wir anbieten: {sender_offer}

Empfaengerunternehmen: {company_name}
Branche des Empfaengers: {industry}
Ansprechpartner: {contact_name or "(unbekannt)"}

Insights zur Website des Empfaengers (aus dem tatsaechlichen Inhalt ihrer Website):
{insights_text}

Gib JSON mit "subject" und "body" zurueck (ohne Fusszeile/Unterschrift).
Denk daran: die gesamte E-Mail in EINER Sprache, ohne Sprachmischung."""
            return system_prompt, prompt

        # language == "en"
        system_prompt = """You are a B2B cold outreach first-contact copywriter.
You write EXCLUSIVELY in English.

CRITICAL LANGUAGE RULE: The entire email (subject AND body) MUST be written
in ONE, THE SAME language (English) from the first to the last word. You
must not mix languages within a single message - not single words, not
sentences, not fragments. Stay consistently in English until the end of the
whole message.

The email MUST have EXACTLY these elements, in this order:
1. Short, concrete greeting (use the contact's name if given, otherwise a neutral "Dear Sir or Madam").
2. Introduction of OUR company - who we are and WHAT WE DO (based on the provided offer description) - 1-2 sentences, concrete, without marketing exaggeration.
3. Short reference to an OBSERVATION about the recipient's company (based on insights from their website, if available) - showing the message is personalized, not mass-sent.
4. A DIRECT question whether they have or might have a need for such a service - don't assume they definitely need it, just ask.
5. Short closing encouraging a reply (e.g. "Happy to answer any questions"), WITHOUT a signature/footer - the footer will be appended automatically.

Rules:
- Max. 120-150 words in the body (excluding footer).
- Zero empty marketing phrases ("revolutionary solution", "best on the market").
- Don't invent facts about the recipient's company that aren't in the insights - if insights are empty, write a more general but still polite and concrete email about OUR offer.
- CRITICAL: NEVER criticize or negatively assess the recipient's work, quality, competence,
  or professionalism - even if the insights suggest a "problem". That's unfair (we don't
  really know them) and insulting to a potential customer. Use insights ONLY to show the
  message is personalized (e.g. "we noticed you specialize in X") - NEVER to claim what
  they're missing, doing wrong, or to imply a deficiency/problem.
- Don't add a footer, contact details, or signature - that will be added automatically.

Respond EXCLUSIVELY with a raw JSON object, no markdown blocks, in the format:
{"subject": "...", "body": "..."}"""

        prompt = f"""Write a first-contact cold email.

OUR company: {sender_company}
What we do: {sender_offer}

Recipient company: {company_name}
Recipient industry: {industry}
Contact person: {contact_name or "(unknown)"}

Insights about the recipient's website (from the real content of their site):
{insights_text}

Return JSON with "subject" and "body" (no footer/signature). Remember: the
whole email in ONE language, no mixing."""
        return system_prompt, prompt

    @staticmethod
    def personalize_message(template: str, lead: Dict[str, str], 
                          website_insights: Optional[Dict]) -> Optional[str]:
        """Personalizuj wiadomość."""
        system_prompt = """Jesteś ekspertem w personalizacji. 
Dostosuj szablon do konkretnego leadу.
Zwróć gotową wiadomość."""
        
        insights_text = json.dumps(website_insights) if website_insights else "Brak insights"
        
        prompt = f"""Personalizuj ten szablon:
{template}

Dla firmy:
- Nazwa: {lead.get('firma', 'N/A')}
- Kontakt: {lead.get('kontakt', 'N/A')}
- Website: {lead.get('website', 'N/A')}

Website insights:
{insights_text}

Zwróć personalizowaną wiadomość."""
        
        return ai_manager.generate(prompt, system_prompt, temperature=0.6, max_tokens=800)


class LeadScorer:
    """Ocenia jakość leadów i filtruje spam."""
    
    @staticmethod
    def score_lead(company_name: str, email: str, industry: str,
                   website: str = "", page_text: Optional[str] = None,
                   sender_offer: str = "") -> Optional[Dict[str, Any]]:
        """Oceń lead i zwróć score + flagę spam.

        Podobnie jak analyze_website - realnie czyta tresc strony (chyba ze
        `page_text` zostal juz pobrany wczesniej i podany z gory, np. w petli
        AIAutoSendWorker, zeby nie pobierac tej samej strony dwa razy).
        Jesli podano `sender_offer` (opis NASZEJ uslugi), ocena bierze pod
        uwage czy firma odbiorcy w ogole moze potrzebowac TAKIEJ uslugi, a
        nie tylko czy wyglada na realny biznes."""
        if page_text is None and website:
            page_text = fetch_page_text(website)

        system_prompt = """Jesteś ekspertem w lead qualification B2B dla firmy usługowej/rzemieślniczej
(np. malarskiej, remontowej, sprzątającej).
Oceń lead na skali 1-100 (100 = najlepszy, realnie zainteresowany kupujacy/zleceniodawca).
Opieraj sie na PRAWDZIWEJ tresci strony (jesli dostarczona) - nie zgaduj.
Jesli podano opis naszej uslugi, oce ile TA KONKRETNA firma moze jej potrzebowac,
a nie tylko czy w ogole jest realnym biznesem.

POSTAWA DOMYSLNA: Twoim zadaniem jest AKTYWNIE SZUKAC realnej okazji biznesowej, a nie
szukac powodu zeby odrzucic. "skip" to OSTATECZNOSC, nie domyslna odpowiedz przy
jakiejkolwiek niepewnosci. Jesli firma jest prawdziwym biznesem w branzy budowlanej/
nieruchomosciowej/uslugowej i nie pasuje jednoznacznie do zadnej z kategorii ponizej,
oceniaj to jako niejasne ale WARTE PROBY (np. score ok. 40-55, recommended_action
"nurture"), a nie automatyczny "skip". "skip" rezerwuj dla przypadkow gdzie firma
naprawde nie ma zadnego mozliwego zwiazku z nasza branza, albo to nie jest firma tylko
portal/katalog (patrz wykluczenia nizej).

KRYTYCZNE - TRZY rozne typy dobrego leada, WSZYSTKIE licza sie jako wartosciowe:
1. KLIENT KONCOWY - firma ktora sama potrzebuje tej uslugi do wlasnych nieruchomosci/biur
   (np. zarzadca nieruchomosci, biuro, przychodnia).
2. ZLECENIODAWCA PODWYKONAWSTWA - firma ktora SAMA OFERUJE podobna lub szersza usluge
   swoim klientom (np. generalny wykonawca remontow, firma budowlana, facility management)
   i typowo ZLECA wykonanie konkretnych fachow (jak malowanie) podwykonawcom, bo nie ma
   wlasnej ekipy do kazdej specjalizacji. To CZESTO LEPSZY lead niz klient koncowy, bo
   oznacza potencjalnie POWTARZALNE zlecenia, nie jednorazowa prace.
   Sygnaly ze firma dziala jako generalny wykonawca zlecajacy podwykonawstwo (a NIE ze to
   konkurencja robiaca wszystko sama): wlasny "Bauleiter"/kierownik budowy koordynujacy
   "wszystkie fachy/Gewerke", szeroki zakres uslug obejmujacy wiele roznych specjalizacji
   naraz (dach, elektryka, hydraulika, malowanie, podlogi...) - realistycznie zadna firma
   nie ma wlasnej pelnoetatowej ekipy do wszystkiego naraz, wiec taki zakres to sygnal
   modelu podwykonawczego, nie sygnal ze to konkurent. Dzialanie na terenie calego kraju
   z "regionalnymi zespolami/partnerami" to dodatkowy sygnal sieci podwykonawcow.
   NIE traktuj samego faktu "moga szukac podwykonawcy" jako powodu do obnizenia oceny -
   to ma byc POZYTYWNY sygnal, o ile nasza usluga pasuje do jednej z ich kategorii uslug.
3. PARTNER BRANZOWY (RowNIEz DOBRY LEAD) - inna firma z DOKLADNIE TEJ SAMEJ lub bardzo
   pokrewnej branzy (np. inna firma malarska, ekipa remontowa, firma sprzatajaca).
   W rzemiosle/budowce to NORMALNE i CZESTE, ze takie firmy wspolpracuja: przekazuja sobie
   nawzajem nadmiarowe zlecenia gdy sa przeciazone, podzlecaja czesc duzego projektu, albo
   polecaja klientow ktorych same nie obsluzza (np. zla lokalizacja, zly termin, zla
   specjalizacja). NIE odrzucaj automatycznie firmy tylko dlatego ze robi to samo co my -
   oceniaj ja jako potencjalnego partnera do wspolpracy/podwykonawstwa/wymiany zlecen,
   z umiarkowanie dobrym scorem, chyba ze z tresci strony wynika ze to raczej bezposredni
   rywal o tych samych klientach w tym samym najwezszym segmencie (wtedy nizej, ale wciaz
   nie automatyczny "skip" - moze i tak warto sprobowac wspolpracy).
Geografia: przy zleceniodawcach podwykonawstwa dzialajacych ogolnokrajowo NIE odrzucaj
automatycznie z powodu "brak pokrycia geograficznego" - sprawdz czy dzialaja/maja projekty
w naszym regionie (albo czy w ogole to sprecyzowali), zamiast zakladac niedopasowanie.

TWARDE WYKLUCZENIA (to NIE sa firmy do kontaktu, zawsze is_spam=true, score nisko,
recommended_action "skip", NIEZALEZNIE od powyzszych kategorii):
- Portale ogloszeniowe, katalogi firm, strony typu "Lista 150 najlepszych X w Monachium",
  agregatory wyszukiwarkowe (np. goyellow.de, gelbeseiten, branzowe rankingi/artykuly).
- Strony urzedowe, gminne, stowarzyszenia bez wlasnej dzialalnosci uslugowej.
- Wyniki wygladajace jak fragment wyszukiwarki/spisu tresci strony trzeciej, a nie strona
  konkretnej firmy (np. tytul zaczynajacy sie od nazwy domeny i "https://" w tresci).
Takich wynikow NIGDY nie traktuj jako szansy biznesowej, nawet jesli tematycznie pasuja -
tam nie ma z kim rozmawiac, to nie jest firma tylko tresc/katalog.

SPOJNOSC SCORE <-> REKOMENDACJA (WAZNE, czesty blad): liczba w "score" i slowna
rekomendacja w "reason"/"recommended_action" MUSZA byc ze soba zgodne. Jesli Twoj tekst
mowi "warto zadzwonic", "wyslac oferte", "sprawdzic czy potrzebuja pomocy" - to jest
rekomendacja KONTAKTU, wiec score NIE MOZE byc na poziomie spamu (ponizej ~30). Score
ponizej 30 oznacza w systemie "NIE WYSYLAJ NIC DO TEJ FIRMY" - jesli Twoje wlasne
uzasadnienie sugeruje ze warto sprobowac kontaktu, score musi to odzwierciedlac (co
najmniej 40+), inaczej Twoja wlasna rekomendacja zostanie zignorowana przez system.
Przed odpowiedzia sprawdz sam siebie: czy liczba w score pasuje do tego co napisales
w uzasadnieniu i rekomendacji? Jesli nie - popraw liczbe, nie tekst.

Kalibracja dla PARTNERA BRANZOWEGO: nawet SPORADYCZNA/okazjonalna wspolpraca z innymi
firmami rzemieslniczymi wymieniona na stronie (np. "przy wiekszych projektach
wspolpracujemy z innymi firmami") to WYSTARCZAJACY precedens, zeby dac co najmniej
40-50 punktow - to inwestycja w relacje na przyszlosc, nie wymaga dzisiejszej pilnej
potrzeby. Ustabilizowana, dobrze prosperujaca firma z branzy (dlugi czas oczekiwania na
wolne terminy, wielu pracownikow) to NIE jest powod do niskiego score - to raczej sygnal
ze maja NADMIAR zlecen i moga chciec je komus przekazywac, wiec jesli juz masz w tym
przypadku watpliwosci, przechyl sie w strone wyzszego score (40-55), nie ponizej 30.

Dodaj pole "lead_type": "klient_koncowy" / "zleceniodawca_podwykonawstwa" / "partner_branzowy"
 / "konkurencja_bezposrednia" / "nie_firma" / "niejasne".

Odpowiedz WYŁĄCZNIE surowym obiektem JSON, bez bloków markdown (```),
bez żadnego tekstu przed ani po. Dokładnie w tym formacie:
{
  "score": 75,

  "is_spam": false,
  "lead_type": "klient_koncowy",
  "reason": "opis",
  "recommended_action": "contact/nurture/skip"
}"""

        content_block = page_text[:2500] if page_text else "(brak tresci strony - ocenaj ostrozniej)"
        prompt = f"""Oceń ten lead:
Firma: {company_name}
Email: {email}
Branża: {industry}
Website: {website}
Nasza usluga (do sprawdzenia dopasowania): {sender_offer or "(nie podano)"}

Tresc strony (wyciag):
\"\"\"
{content_block}
\"\"\"

Zwróć assessment jako JSON."""

        result = ai_manager.generate(prompt, system_prompt, temperature=0.3, max_tokens=300,
                                      expects_json=True)
        if not result:
            return None

        parsed = _parse_json_response(result, "lead score")
        return _normalize_score_fields(parsed, company_name)


class ResponseAnalyzer:
    """Analizuje odpowiedzi na e-maile."""
    
    @staticmethod
    def classify_response(email_body: str) -> Optional[Dict[str, Any]]:
        """Zaklasyfikuj typ odpowiedzi."""
        system_prompt = """Analizuj e-mail odpowiedź.
Odpowiedz WYŁĄCZNIE surowym obiektem JSON, bez bloków markdown (```),
bez żadnego tekstu przed ani po. Format:
{
  "type": "interested/rejected/more_info/spam/out_of_office",
  "sentiment": "positive/neutral/negative",
  "next_action": "follow_up/close/add_to_sequence",
  "key_points": ["punkt1"]
}"""
        
        prompt = f"""Analizuj tę odpowiedź:
{email_body}

Zwróć analiza jako JSON."""
        
        result = ai_manager.generate(prompt, system_prompt, temperature=0.3, max_tokens=400,
                                      expects_json=True)
        if not result:
            return None

        return _parse_json_response(result, "response analysis")


class ReplyGenerator:
    """Generuje propozycje odpowiedzi na maile."""

    @staticmethod
    def generate_reply(original_email: str, sender_offer: str,
                       tone: str = "professional") -> Optional[str]:
        """Generuj propozycję odpowiedzi."""
        system_prompt = f"""Jesteś asystentem sprzedaży B2B. Twoim zadaniem jest napisać
uprzejmą i skuteczną odpowiedź na wiadomość od klienta.
Użyj tonu: {tone}.
Nawiąż do naszej oferty: {sender_offer}.
Zwróć TYLKO treść wiadomości, bez tematu i stopki."""

        prompt = f"""Otrzymaliśmy taką wiadomość od leada:
\"\"\"
{original_email}
\"\"\"

Napisz propozycję odpowiedzi:"""

        return ai_manager.generate(prompt, system_prompt, temperature=0.7, max_tokens=600)


class SendTimingOptimizer:
    """Optymalizuje czas wysyłki e-maili."""
    
    @staticmethod
    def recommend_send_time(industry: str, region: str, 
                           target_role: str = "manager") -> Optional[Dict[str, Any]]:
        """Rekomenduj najlepszy czas wysyłki."""
        system_prompt = """Jesteś ekspertem w email deliverability.
Znasz patterns otwarcia e-maili.
Odpowiedz WYŁĄCZNIE surowym obiektem JSON, bez bloków markdown (```),
bez żadnego tekstu przed ani po. Format:
{
  "best_day": "wtorek",
  "best_time": "09:00",
  "best_timezone": "CET",
  "confidence": 0.85,
  "reason": "opis"
}"""
        
        prompt = f"""Rekomenduj czas wysyłki dla:
Branża: {industry}
Region: {region}
Target role: {target_role}

Zwróć rekomendacje jako JSON."""
        
        result = ai_manager.generate(prompt, system_prompt, temperature=0.5, max_tokens=300,
                                      expects_json=True)
        if not result:
            return None

        return _parse_json_response(result, "timing recommendation")


class ABTestingEngine:
    """Engine do A/B testowania."""
    
    @staticmethod
    def generate_variants(content_type: str, original: str, 
                         count: int = 2) -> Optional[List[str]]:
        """Generuj warianty do A/B testów."""
        system_prompt = f"""Jesteś ekspertem w A/B testingu.
Generuj {count} warianty {content_type} które się różnią od oryginału.
Zwróć jako listę, jeden na linię, bez numeracji."""
        
        prompt = f"""Oryginał:
{original}

Generuj {count} alternatywne warianty."""
        
        result = ai_manager.generate(prompt, system_prompt, temperature=0.8, max_tokens=1000)
        if not result:
            return None
        
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        return lines[:count]
    
    @staticmethod
    def analyze_test_results(variant_a: str, variant_b: str,
                            results_a: Dict[str, int], 
                            results_b: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Analizuj wyniki A/B testu."""
        system_prompt = """Jesteś statystykiem w email marketingu.
Analizuj wyniki testów.
Odpowiedz WYŁĄCZNIE surowym obiektem JSON, bez bloków markdown (```),
bez żadnego tekstu przed ani po. Format:
{
  "winner": "A/B/tie",
  "confidence": 0.95,
  "recommendation": "opis",
  "p_value": 0.05
}"""
        
        prompt = f"""Analizuj wyniki A/B testu:

Wariant A: {variant_a[:100]}...
Otwarte: {results_a.get('opens', 0)}, Kliknięcia: {results_a.get('clicks', 0)}, Wysłane: {results_a.get('sent', 0)}

Wariant B: {variant_b[:100]}...
Otwarte: {results_b.get('opens', 0)}, Kliknięcia: {results_b.get('clicks', 0)}, Wysłane: {results_b.get('sent', 0)}

Zwróć analiza jako JSON."""
        
        result = ai_manager.generate(prompt, system_prompt, temperature=0.3, max_tokens=400,
                                      expects_json=True)
        if not result:
            return None

        return _parse_json_response(result, "A/B test analysis")
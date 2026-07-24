# -*- coding: utf-8 -*-
"""
Hybrydowe wyszukiwanie firm (DuckDuckGo + Google + Bing) i wyszukiwanie
adresów e-mail na ich stronach WWW.

Uwaga: scraping wyników Google/Bing przez HTML jest z natury kruchy (strony
zmieniają strukturę, mogą wymagać CAPTCHA przy zbyt dużym ruchu). Kod stara
się nie wywalać całego procesu, gdy jeden z silników zawiedzie - loguje błąd
i kontynuuje z pozostałymi źródłami.
"""
import asyncio
import concurrent.futures
import random
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus, unquote, urlparse

import httpx
import requests
from bs4 import BeautifulSoup

from .config import (
    EMAIL_BLACKLIST, IGNORED_DOMAINS, MAX_ASYNC_CONCURRENT, MAX_HTML_SIZE,
    PORTAL_DOMAIN_KEYWORDS, PORTAL_TITLE_KEYWORDS, REQUEST_TIMEOUT,
    ASYNC_GLOBAL_TIMEOUT, SEARCH_DELAY_RANGE, logger,
)

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    def _random_user_agent() -> str:
        return _UA.random
except Exception as e:  # fake_useragent może nie mieć dostępu do sieci/danych
    logger.warning("fake_useragent niedostępny (%s) - używam statycznej listy User-Agent.", e)
    _FALLBACK_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    def _random_user_agent() -> str:
        return random.choice(_FALLBACK_AGENTS)

EMAIL_RE = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
EMAIL_RE_STRICT = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.warning("Pakiet 'ddgs' nie jest zainstalowany - wyszukiwanie DuckDuckGo pominięte.")


def fetch_page_text(url: str, max_chars: int = 3000) -> Optional[str]:
    """Pobiera strone glowna firmy i zwraca jej tekst (bez HTML/JS), do
    wykorzystania przez AI (analiza website, generowanie maila). Zwraca
    None gdy strona jest niedostepna - wywolujacy powinien wtedy dzialac
    bez insightow ze strony, a nie zmyslac jej tresc."""
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        resp = requests.get(url, headers=_random_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("fetch_page_text: nie udalo sie pobrac '%s': %s", url, e)
        return None

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
        return text[:max_chars] if text else None
    except Exception as e:
        logger.warning("fetch_page_text: blad parsowania '%s': %s", url, e)
        return None


def _random_headers() -> Dict[str, str]:
    return {
        'User-Agent': _random_user_agent(),
        'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.google.de/',
    }


def _is_portal(domain: str, name: str) -> bool:
    """
    Rozpoznaje portale/agregatory/media (np. "Top 10 Restaurants in Berlin",
    katalogi firm, platformy dostaw) na podstawie domeny i tytułu wyniku,
    żeby nie trafiały do listy leadów jako potencjalni klienci.
    """
    domain_l = domain.lower()
    name_l = (name or "").lower()
    if any(p in domain_l for p in IGNORED_DOMAINS):
        return True
    if any(kw in domain_l for kw in PORTAL_DOMAIN_KEYWORDS):
        return True
    if any(kw in name_l for kw in PORTAL_TITLE_KEYWORDS):
        return True
    return False


def _get_domain_root(url: str) -> str:
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return f"{parsed.scheme}://{netloc}"
    except ValueError:
        pass
    return url


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    email = email.lower().strip()
    blocked_ext = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.ico', '.pdf')
    if email.endswith(blocked_ext):
        return False
    return bool(EMAIL_RE_STRICT.match(email))


def extract_email_from_html(html: Optional[str]) -> Optional[str]:
    """Wyszukuje pierwszy sensowny adres e-mail na stronie (najpierw mailto:)."""
    if not html:
        return None

    def _is_acceptable(addr: str) -> bool:
        return not any(x in addr for x in EMAIL_BLACKLIST) and is_valid_email(addr)

    mailto = re.findall(r'mailto:(' + EMAIL_RE + ')', html, re.IGNORECASE)
    for candidate in mailto:
        candidate = candidate.lower()
        if _is_acceptable(candidate):
            return candidate

    html_clean = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html_clean = re.sub(r'<style.*?</style>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
    for candidate in re.findall(EMAIL_RE, html_clean, re.IGNORECASE):
        candidate = candidate.lower()
        if _is_acceptable(candidate):
            return candidate
    return None


def extract_social_links(html: str) -> Dict[str, str]:
    """Wyciąga linki do profili społecznościowych ze strony."""
    socials = {}

    # LinkedIn
    li_match = re.search(r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9\-_]+', html)
    if li_match: socials['linkedin'] = li_match.group(0)

    # Facebook
    fb_match = re.search(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9\._]+', html)
    if fb_match: socials['facebook'] = fb_match.group(0)

    return socials


async def _fetch_single_page(client: httpx.AsyncClient, url: str) -> Tuple[Optional[str], Dict[str, str]]:
    try:
        async with client.stream("GET", url, timeout=REQUEST_TIMEOUT, follow_redirects=True) as response:
            if response.status_code != 200:
                return None, {}
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_HTML_SIZE:
                return None, {}
            body = await response.aread()
            if len(body) > MAX_HTML_SIZE:
                body = body[:MAX_HTML_SIZE]

            html_text = body.decode("utf-8", errors="ignore")
            email = extract_email_from_html(html_text)
            socials = extract_social_links(html_text)

            return email, socials
    except (httpx.HTTPError, asyncio.TimeoutError) as e:
        logger.debug("Nie udało się pobrać %s: %s", url, e)
        return None, {}


async def _fetch_data_from_domain(client: httpx.AsyncClient, domain: str) -> Tuple[str, Optional[str], Dict[str, str]]:
    pages = [
        domain,
        f"{domain.rstrip('/')}/kontakt",
        f"{domain.rstrip('/')}/impressum",
        f"{domain.rstrip('/')}/ueber-uns",
    ]

    final_email = None
    final_socials = {}

    for page in pages:
        email, socials = await _fetch_single_page(client, page)
        if email and not final_email: final_email = email
        final_socials.update(socials)
        if final_email and 'linkedin' in final_socials:
            break

    return domain, final_email, final_socials


async def _fetch_all_data(domains: List[str], proxy: Optional[str] = None) -> Dict[str, Dict]:
    limits = httpx.Limits(max_connections=MAX_ASYNC_CONCURRENT)
    semaphore = asyncio.Semaphore(MAX_ASYNC_CONCURRENT)

    client_kwargs = {"headers": _random_headers(), "limits": limits}
    if proxy:
        client_kwargs["proxy"] = proxy

    async with httpx.AsyncClient(**client_kwargs) as client:
        async def sem_worker(domain: str):
            async with semaphore:
                return await _fetch_data_from_domain(client, domain)

        tasks = [asyncio.create_task(sem_worker(domain)) for domain in domains]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = {}
        for res in results:
            if isinstance(res, tuple):
                valid_results[res[0]] = {"email": res[1], "socials": res[2]}
        return valid_results


def _run_async_fetch(domains: List[str], proxy: Optional[str] = None) -> Dict[str, Dict]:
    """Uruchamia `_fetch_all_data` niezależnie od tego, czy jesteśmy już w pętli asyncio."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_fetch_all_data(domains, proxy))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _fetch_all_data(domains, proxy))
            return future.result(timeout=ASYNC_GLOBAL_TIMEOUT + 5)


def _pick_proxy(proxies: Optional[List[str]]) -> Optional[str]:
    """Losuje jeden adres proxy z listy (jeden proxy na całe wyszukiwanie: 3 silniki + skan domen)."""
    if not proxies:
        return None
    return random.choice(proxies)


def _mask_proxy(proxy: Optional[str]) -> str:
    """Maskuje ewentualne hasło w adresie proxy przed wypisaniem w logu."""
    if not proxy or "@" not in proxy:
        return proxy or "brak"
    scheme_and_creds, host_part = proxy.rsplit("@", 1)
    scheme = scheme_and_creds.split("://")[0]
    return f"{scheme}://***@{host_part}"


# ------------------------------------------------------------------
# Silniki wyszukiwania firm (linki)
# ------------------------------------------------------------------
def _extract_links_ddg(query: str, location: str, limit: int,
                        proxy: Optional[str] = None) -> List[Dict[str, str]]:
    collected = []
    if not DDGS_AVAILABLE:
        return collected
    try:
        ddgs_kwargs = {"proxy": proxy} if proxy else {}
        with DDGS(**ddgs_kwargs) as ddgs:
            for row in ddgs.text(f"{query} {location}", max_results=limit):
                url = row.get("href")
                if url and url.startswith("http"):
                    collected.append({"name": row.get("title", ""), "url": url})
    except Exception as e:
        logger.error("Błąd DuckDuckGo: %s", e)
    return collected


def _extract_links_google_text(query: str, location: str, limit: int,
                                proxy: Optional[str] = None) -> List[Dict[str, str]]:
    collected = []
    try:
        search_url = f"https://www.google.de/search?q={quote_plus(query)}+{quote_plus(location)}&num={limit}"
        proxies_dict = {"http": proxy, "https": proxy} if proxy else None
        resp = requests.get(search_url, headers=_random_headers(), timeout=REQUEST_TIMEOUT,
                             proxies=proxies_dict)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a_tag in soup.select('a'):
                href = a_tag.get('href', '')
                if href.startswith('/url?q='):
                    url = unquote(href.split('/url?q=')[1].split('&')[0])
                    if url.startswith('http') and "google." not in url:
                        h3 = a_tag.select_one('h3')
                        name = h3.get_text(strip=True) if h3 else "Firma"
                        collected.append({"name": name, "url": url})
    except requests.RequestException as e:
        logger.error("Błąd Google: %s", e)
    return collected


def _extract_links_bing(query: str, location: str, limit: int,
                         proxy: Optional[str] = None) -> List[Dict[str, str]]:
    collected = []
    try:
        params = {"q": f"{query} {location}", "count": limit}
        proxies_dict = {"http": proxy, "https": proxy} if proxy else None
        resp = requests.get("https://www.bing.com/search", params=params,
                             headers=_random_headers(), timeout=REQUEST_TIMEOUT,
                             proxies=proxies_dict)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('li.b_algo'):
                link_elem = item.select_one('a')
                if link_elem:
                    url = link_elem.get('href', '')
                    if url.startswith('http'):
                        collected.append({"name": link_elem.get_text(strip=True), "url": url})
    except requests.RequestException as e:
        logger.error("Błąd Bing: %s", e)
    return collected


def _run_single_engine(engine_fn, query: str, location: str, limit: int,
                        proxy: Optional[str] = None) -> List[Dict[str, str]]:
    """Losowe opóźnienie (jitter) przed strzałem do danego silnika, potem samo zapytanie."""
    time.sleep(random.uniform(*SEARCH_DELAY_RANGE))
    return engine_fn(query, location, limit, proxy)


def _search_all_engines_parallel(query: str, location: str, limit: int,
                                  proxy: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Odpytuje DuckDuckGo, Google i Bing RÓWNOLEGLE zamiast po kolei.
    To jest bezpieczne - to trzy różne serwery, więc żaden z nich nie dostaje
    więcej zapytań niż wcześniej (dalej 1 zapytanie na silnik na wyszukiwanie),
    po prostu nie czekamy na odpowiedź jednego, zanim zapytamy kolejny.
    """
    engines = (
        (_extract_links_ddg, limit * 3),
        (_extract_links_google_text, limit * 2),
        (_extract_links_bing, limit * 2),
    )
    raw_links: List[Dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(engines)) as executor:
        futures = [
            executor.submit(_run_single_engine, fn, query, location, lim, proxy)
            for fn, lim in engines
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                raw_links.extend(future.result())
            except Exception as e:
                logger.error("Błąd silnika wyszukiwania: %s", e)
    return raw_links


def search_companies_web(query: str, location: str = "Berlin", limit: int = 10,
                          _worker=None,
                          domain_cache: Optional[Dict[str, Optional[str]]] = None,
                          proxies: Optional[List[str]] = None
                          ) -> Tuple[List[Dict[str, str]], Dict[str, Optional[str]]]:
    """
    Hybrydowe wyszukiwanie firm z adresami e-mail (DDG + Google + Bing równolegle),
    z obsługą przerwania przez `_worker` (obiekt z atrybutem `_is_running`).

    `domain_cache`: opcjonalny słownik {domena: email|None} z wcześniej zeskanowanymi
    domenami (np. z innej kombinacji kategoria/lokalizacja w tym samym przebiegu, albo
    z poprzednich sesji zapisanych w bazie) - domeny w nim obecne NIE są odpytywane
    ponownie, co znacząco przyspiesza kolejne wyszukiwania.

    `proxies`: opcjonalna lista adresów proxy (http:// lub socks5://) - jeden losowy
    proxy jest wybierany na CAŁE to wywołanie (3 silniki wyszukiwania + skan domen),
    żeby uniknąć blokad IP przy dużej liczbie zapytań do wyszukiwarek.

    Zwraca (wyniki, nowo_zeskanowane) - `nowo_zeskanowane` to domeny faktycznie
    sprawdzone w tym wywołaniu (do zapisania w cache przez wywołującego).
    """
    def still_running() -> bool:
        return not _worker or _worker._is_running

    domain_cache = domain_cache or {}
    proxy = _pick_proxy(proxies)
    logger.info("Szukam: %s w %s (proxy: %s)", query, location, _mask_proxy(proxy))

    if not still_running():
        return [], {}
    raw_links = _search_all_engines_parallel(query, location, limit, proxy)

    if not still_running():
        return [], {}

    # Deduplikacja po domenie + odfiltrowanie portali/social media
    domain_to_name: Dict[str, str] = {}
    skipped_portals = 0
    for item in raw_links:
        domain = _get_domain_root(item["url"])
        if _is_portal(domain, item.get("name", "")):
            skipped_portals += 1
            continue
        domain_to_name.setdefault(domain, item["name"])
    if skipped_portals:
        logger.info("Odfiltrowano %d wyników jako portale/agregatory", skipped_portals)

    all_domains = list(domain_to_name.keys())
    to_scan = [d for d in all_domains if d not in domain_cache]
    from_cache = len(all_domains) - len(to_scan)
    if from_cache:
        logger.info("Domeny: %d nowych, %d z cache (pominięto sieć)", len(to_scan), from_cache)
    else:
        logger.info("Unikalne domeny: %d", len(all_domains))

    if not all_domains or not still_running():
        return [], {}

    newly_scanned = _run_async_fetch(to_scan, proxy) if to_scan else {}

    results = []
    for domain in all_domains:
        data = newly_scanned.get(domain)
        email = data.get("email") if data else domain_cache.get(domain)
        if not email:
            continue

        socials = data.get("socials", {}) if data else {}
        results.append({
            "name": domain_to_name.get(domain, "Firma"),
            "website": domain,
            "email": email,
            "linkedin": socials.get("linkedin", ""),
            "facebook": socials.get("facebook", ""),
            "address": "",
            "category": query,
        })
        if len(results) >= limit:
            break

    logger.info("Znaleziono %d firm z emailami", len(results))
    # Return emails for domain_cache
    new_cache = {d: v["email"] for d, v in newly_scanned.items()}
    return results, new_cache

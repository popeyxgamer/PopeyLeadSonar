# INSTRUKCJA_AI.md

> Ten plik to skondensowane podsumowanie projektu wygenerowane po pełnej
> analizie kodu. Cel: żeby AI (lub człowiek) czytający ten projekt po raz
> pierwszy **nie musiał przeglądać wszystkich plików od zera** — wystarczy
> ten plik + ewentualnie konkretny moduł, którego dotyczy zadanie.
> Stan na: 2026-07-07.

## Co to za projekt

Desktopowa aplikacja (PySide6/Qt, Python) do **leadgeneracji + cold mailingu**:
1. Szuka firm w internecie wg zapytania + lokalizacji (DuckDuckGo/Google/Bing scraping).
2. Wyciąga adresy e-mail z ich stron WWW.
3. Weryfikuje maile (MX, format), pozwala je scoringować przez AI.
4. Wysyła spersonalizowane kampanie e-mail (SMTP, rotacja kont, HTML, załączniki, podpis S/MIME).
5. Monitoruje odbicia (bounce) i odpowiedzi (IMAP), ma blacklistę rezygnacji.
6. Ma wbudowanego asystenta AI (OpenAI/Gemini/Ollama/LM Studio) do generowania szablonów,
   tematów, scoringu leadów, A/B testów, optymalizacji czasu wysyłki.

To realne narzędzie robocze (nie demo) — profil `Luftrein-Berlin` to prawdziwa
kampania dla firmy czyszczącej wentylacje w Berlinie.

## Punkt wejścia i przepływ startu

```
main.py
 └─ tworzy folder profiles/ jeśli brak
 └─ jeśli nie ma profilu "default" -> tworzy go
 └─ wczytuje last_profile.txt (ostatnio używany profil)
 └─ switch_profile(last_profile)  [core/profile_manager.py]
 └─ uruchamia ui/main_window.py -> MainWindow (całe GUI, zakładki)
```

## System profili (WAŻNE — nietypowa architektura)

Każda "kampania"/klient = osobny **profil** = osobny folder w `profiles/<nazwa>/`
zawierający: `campaign_data.db` (SQLite), `settings.json`, `app.log`,
opcjonalnie `crypto.key`.

- Aktywny profil trzymany w pamięci (`core/config.py: _active_profile`) i
  zapisywany do `last_profile.txt` przy każdej zmianie.
- **Lista profili w UI = `list_profiles()`** (core/config.py) — **skanuje na
  żywo** folder `profiles/`, bierze każdy podfolder z `campaign_data.db`.
  To jedyne źródło prawdy używane przez interfejs.
- `profiles_index.json` w katalogu głównym to **tylko cache/log**, zapisywany
  przy create/delete/copy profilu. **Nic w UI go nie odczytuje** — jeśli jest
  nieaktualny (nie zawiera wszystkich profili z dysku), to nieszkodliwe,
  kosmetyczne rozjechanie, NIE utrata danych. (Sprawdzone: profil
  `Luftrein-Berlin` istnieje w pełni na dysku, mimo że brakuje go w tym pliku.)
- Stary, jednoprofilowy layout (baza/log/ustawienia w katalogu głównym) był
  używany przed wprowadzeniem systemu profili — migrował go
  `migrate_to_profiles.py` (uruchamiany raz).

## Struktura kodu

```
main.py                 - punkt wejścia
core/                    - logika biznesowa, BEZ importów z ui/
  config.py              - ścieżki, aktywny profil, logger, indeks profili (21 miejsc importu - rdzeń)
  database.py            - SQLite, wielo-profilowe (13 miejsc importu)
  profile_manager.py     - create/switch/delete/copy profilu
  scraping.py            - szukanie firm (DDG/Google/Bing) + wyciąganie maili ze stron
  email_sender.py        - wysyłka SMTP (HTML, załączniki, MX, blacklist, S/MIME)
  workers.py             - QThread: SearchWorker, SendWorker, AutopilotWorker (tryb auto)
  account_rotator.py     - rotacja kont SMTP (limity/dzień)
  mx_verify.py           - weryfikacja MX/DNS maila
  spam_analyzer.py       - scoring "spammowości" treści maila
  smime.py                - podpis cyfrowy S/MIME
  crypto_utils.py         - szyfrowanie hasła Gmail w bazie
  mailbox_reader.py       - odczyt IMAP (zakładka Skrzynka odbiorcza)
  bounce_imap.py          - monitoring odbić (Mailer-Daemon) w tle
  blacklist_import.py     - import listy rezygnacji z CSV/TXT
  default_profile.py      - domyślne przykładowe dane nowego profilu
  ai_providers.py         - abstrakcja: OpenAI / Gemini / Ollama / LM Studio
  ai_features.py          - TemplateGenerator, SubjectLineOptimizer, LeadScorer,
                             LeadPersonalizer, ResponseAnalyzer, SendTimingOptimizer, ABTestingEngine
  ai_workers.py            - QThread dla AI (AIWorker, BatchAIWorker) - async, nie blokuje UI
  ai_database.py           - warstwa DB dla AI (sugestie, A/B testy, scoring) - poprawiona wersja ai_db_functions.py
  ai_db_functions.py       - pierwotna wersja funkcji AI-DB (używana WEWNĘTRZNIE przez ai_database.py, nie usuwać)

ui/                      - PySide6, GUI
  main_window.py (140KB!)  - CAŁE okno główne: wszystkie zakładki, w tym build_ai_tab()
                              (zakładka AI jest zaimplementowana TUTAJ bezpośrednio, nie w osobnym pliku)
  profile_wizard.py        - kreator NOWEGO profilu (krok po kroku)
  quickstart_wizard.py     - kreator pierwszego uruchomienia w ISTNIEJĄCYM profilu
                              (poczta -> dane firmy -> słowa kluczowe -> gotowe)
  styles.py                - QSS dark theme + re-export stałych z default_profile.py

profiles/<nazwa>/        - dane per-profil (baza, ustawienia, log)
```

## Ważne fakty / pułapki, żeby nie tracić czasu na odkrywanie ich od nowa

1. **`ui/main_window.py` ma 140 KB i ~2400+ linii** — to największy plik, zawiera
   właściwie cały interfejs (6 zakładek: Szukaj, Leadzy, Wysyłka, Ustawienia,
   Historia, AI Assistant) w jednej klasie `MainWindow`. Przy edycjach czytaj
   tylko potrzebny fragment (`view` z `view_range`), nie cały plik naraz.
2. **Zakładka AI jest zduplikowana logicznie, ale NIE w kodzie**: `ai_features.py`
   zawiera prawdziwą logikę (klasy generatorów/optymalizatorów), a
   `build_ai_tab()` w `main_window.py` to jedyne miejsce budujące jej UI.
   (Wcześniej istniał plik `ui/ai_tab_code.py` ze szkicem tej samej zakładki —
   **usunięty**, bo nigdzie nie był importowany, patrz sekcja "Historia porządków" niżej.)
3. **`core/ai_database.py` vs `core/ai_db_functions.py`**: to NIE duplikat do
   skasowania — `ai_database.py` to poprawiona wersja (naprawiony brakujący
   import `Optional` i SQL), która **importuje i owija** funkcje z
   `ai_db_functions.py`. Oba pliki są potrzebne.
4. **Baza danych jest per-profil** (osobny plik SQLite w każdym
   `profiles/<nazwa>/campaign_data.db`), NIE jedna wspólna baza. Główne tabele
   (patrz `core/database.py`, funkcja tworząca schemat): `leads`, `settings`,
   `wysylki`, `wyslano`, `scanned_domains`, `searched_combos`, `profiles`,
   `blacklist`, `smtp_accounts`, `ai_suggestions`, `ai_ab_tests`, `ai_lead_scores`.
5. **Hasła (np. Gmail) w `settings.json`/bazie są szyfrowane** przez
   `core/crypto_utils.py` (klucz w `crypto.key` per profil) — nie traktować
   jako plain text nawet jeśli wygląda inaczej w podglądzie.
6. **`add_qdialog.py`** (usunięty, patrz niżej) był jednorazowym skryptem-łatką
   do naprawy brakującego importu `QDialog` w `main_window.py` — łatka jest
   już wgrana na stałe w kodzie, więc jeśli ktoś odtworzy ten plik ze starego
   backupu, nie trzeba go już uruchamiać.
7. **Wymaga PySide6** (nie PyQt5/6) — `requirements.txt` w katalogu głównym.
   Scraping jest z natury kruchy (HTML Google/Bing się zmienia) — jeśli coś
   nie działa w `core/scraping.py`, to pierwsze podejrzane miejsce.

## Historia porządków (co i dlaczego zostało usunięte z tego ZIP-a)

Żeby nie analizować tego ponownie — usunięte zostały wyłącznie realne śmieci
i martwy kod, potwierdzone grep-em po całym repo (zero wystąpień importu):

| Plik | Powód usunięcia |
|---|---|
| `add_qdialog.py` | jednorazowa łatka, już wgrana do main_window.py |
| `tmp.txt` | notatka robocza/debug |
| `campaign_data.db` (root) | stara baza sprzed migracji do profili, zdublowana |
| `ui/profile_selector.py` | klasa `ProfileSelector` nigdzie nie importowana; main_window.py ma własny inline QComboBox |
| `ui/ai_tab_code.py` | szkic zakładki AI, zastąpiony przez `build_ai_tab()` wewnątrz main_window.py; nigdzie nie importowany |
| `profiles/*/app.log` | wyczyszczone (nie usunięte) — logi runtime, odtwarzają się same |

Nic w `core/` nie zostało usunięte — każdy moduł tam ma potwierdzone
przynajmniej jedno miejsce importu w projekcie.

## Znana niespójność (nie naprawiona, tylko odnotowana)

`profiles_index.json` nie wymienia profilu `Luftrein-Berlin`, mimo że jego
folder z pełnymi danymi istnieje. Jak wyjaśniono wyżej — to nie ma znaczenia
dla działania appki (UI skanuje dysk na żywo), ale jeśli kiedyś ktoś zacznie
faktycznie polegać na `load_profiles_index()` (obecnie nieużywanej nigdzie w UI),
warto najpierw odpalić `update_profiles_index()` żeby zsynchronizować plik.

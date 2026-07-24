# 🎯 PopeyLeadSonar

Profesjonalna platforma Sales Engagement do generowania leadów przy pomocy AI i automatyzacji cold mailingu.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://pypi.org/project/PySide6/)

🌍 **Inne wersje językowe:** [English](README.md) · [Deutsch](README.de.md)

PopeyLeadSonar zamienia tradycyjny proces cold mailingu w inteligentny, zautomatyzowany proces. Aplikacja zajmuje się wszystkim — od wyszukiwania firm w internecie, po zarządzanie złożonymi sekwencjami follow-up z personalizacją opartą o AI.

---

## 💎 Funkcje

- **🚀 Inteligentne sekwencje (Follow-up)**: Twórz wieloetapowe ścieżki kontaktu. Sekwencja zatrzymuje się automatycznie, gdy lead odpowie.
- **🧠 AI Auto-Send**: Pozwól AI przeanalizować stronę leada, ocenić dopasowanie biznesowe i napisać unikalny, mocno spersonalizowany e-mail.
- **🔥 Rozgrzewanie skrzynek (Email Warm-up)**: Chroń reputację nadawcy dzięki automatycznemu rozgrzewaniu kont SMTP.
- **🧬 Hybrid Search**: Łącz wyniki z DuckDuckGo, Google i Bing, aby znaleźć najlepsze leady B2B.
- **📥 Smart Inbox AI**: Odpowiadaj potencjalnym klientom jednym kliknięciem, korzystając z sugestii generowanych przez AI na podstawie Twojej oferty.
- **📊 Dashboard lejka sprzedażowego**: Wizualizuj współczynniki konwersji i aktywność kampanii w czasie rzeczywistym.
- **🌍 Wielojęzyczność**: Pełna lokalizacja w języku angielskim, niemieckim i polskim.
- **🛡️ Ochrona reputacji**: Wbudowana weryfikacja MX, zarządzanie blacklistą i podpisywanie cyfrowe S/MIME.

---

## 🛠 Instalacja

### Wymagania
- Python 3.11+
- [Git](https://git-scm.com/)

### Windows (zalecane)
1. **Kliknij dwukrotnie** `install.bat`. Utworzy to środowisko wirtualne i automatycznie zainstaluje wszystkie zależności.
2. **Kliknij dwukrotnie** `start.bat`, aby uruchomić aplikację.

### Ręcznie / Linux / macOS
1. **Sklonuj repozytorium**:
   ```bash
   git clone https://github.com/popeyxgamer/popeyleadsonar.git
   cd popeyleadsonar
   ```

2. **Utwórz środowisko wirtualne**:
   ```bash
   python -m venv env
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

3. **Zainstaluj zależności**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Uruchom aplikację**:
   ```bash
   python main.py
   ```

---

## ⚙️ Konfiguracja

1. **Konfiguracja e-mail**: Przejdź do **Ustawień** i dodaj konto Gmail (użyj hasła aplikacji).
2. **Dostawca AI**: Skonfiguruj OpenAI, Gemini lub model lokalny (Ollama/LM Studio) w zakładce **AI Lab**.
3. **Profil firmy**: Uzupełnij dane firmy, aby włączyć automatyczne stopki e-mail i kontekst dla AI.

---

## 🛡️ Prywatność i bezpieczeństwo

PopeyLeadSonar zaprojektowano z myślą o prywatności:
- **Dane lokalne**: Wszystkie profile, bazy leadów i dane logowania są przechowywane lokalnie w katalogu `profiles/`.
- **Brak synchronizacji z chmurą**: Twoje dane nigdy nie opuszczają Twojego komputera, chyba że wysyłasz e-mail lub wywołujesz API AI.
- **Szyfrowane hasła**: Hasła SMTP są szyfrowane na dysku.

---

## ⚖️ Licencja i zastrzeżenie odpowiedzialności

Projekt udostępniony na licencji **MIT**. Szczegóły w pliku [`LICENSE`](LICENSE).

Oprogramowanie jest udostępniane bezpłatnie i "tak jak jest" (as is). **Autor nie ponosi żadnej odpowiedzialności za sposób wykorzystania tego narzędzia**, w tym za jakiekolwiek użycie naruszające obowiązujące przepisy (np. przepisy antyspamowe czy dotyczące ochrony danych osobowych, takie jak RODO). Korzystasz z aplikacji na własną odpowiedzialność i zobowiązujesz się do przestrzegania przepisów prawa obowiązujących w Twojej jurysdykcji.

---

## ☕ Wesprzyj projekt

Jeśli PopeyLeadSonar okazał się dla Ciebie przydatny, rozważ wsparcie jego dalszego rozwoju — każde wsparcie pomaga utrzymać i rozwijać projekt! 💚

[**Wesprzyj przez Tipply**](https://tipply.pl/@Papajgejmer)

---

## 📬 Kontakt

- GitHub: [popeyxgamer](https://github.com/popeyxgamer)
- E-mail: obserwujnewsymordo@gmail.com

---

*Stworzone z ❤️ przez Roberta (popeyxgamer) / PopeyLeadSonar.*

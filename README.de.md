# 🎯 PopeyLeadSonar

Eine professionelle Sales-Engagement-Plattform für KI-gestützte Leadgenerierung und automatisiertes Cold-Mailing.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://pypi.org/project/PySide6/)

🌍 **Andere Sprachversionen:** [English](README.md) · [Polski](README.pl.md)

PopeyLeadSonar verwandelt den klassischen Cold-Mailing-Prozess in eine intelligente, automatisierte Pipeline. Die Anwendung übernimmt alles — vom Auffinden von Unternehmen im Internet bis zur Verwaltung komplexer Follow-up-Sequenzen mit KI-gestützter Personalisierung.

---

## 💎 Funktionen

- **🚀 Intelligente Sequenzen (Follow-up)**: Erstellen Sie mehrstufige Kontaktpfade. Sequenzen werden automatisch gestoppt, sobald ein Lead antwortet.
- **🧠 KI Auto-Send**: Lassen Sie die KI die Website des Leads analysieren, den Business-Fit bewerten und eine einzigartige, stark personalisierte E-Mail verfassen.
- **🔥 E-Mail Warm-up**: Schützen Sie Ihre Absenderreputation durch automatisches Aufwärmen Ihrer SMTP-Konten.
- **🧬 Hybrid Search**: Kombinieren Sie Ergebnisse von DuckDuckGo, Google und Bing, um die besten B2B-Leads zu finden.
- **📥 Smart Inbox AI**: Antworten Sie potenziellen Kunden mit einem Klick, basierend auf KI-generierten Vorschlägen, die auf Ihrem Angebot beruhen.
- **📊 Sales-Funnel-Dashboard**: Visualisieren Sie Konversionsraten und Kampagnenaktivität in Echtzeit.
- **🌍 Mehrsprachigkeit**: Vollständig lokalisiert in Englisch, Deutsch und Polnisch.
- **🛡️ Reputationsschutz**: Integrierte MX-Verifizierung, Blacklist-Verwaltung und digitale S/MIME-Signierung.

---

## 🛠 Installation

### Voraussetzungen
- Python 3.11+
- [Git](https://git-scm.com/)

### Windows (empfohlen)
1. **Doppelklicken** Sie auf `install.bat`. Dadurch wird eine virtuelle Umgebung erstellt und alle Abhängigkeiten automatisch installiert.
2. **Doppelklicken** Sie auf `start.bat`, um die Anwendung zu starten.

### Manuell / Linux / macOS
1. **Repository klonen**:
   ```bash
   git clone https://github.com/popeyxgamer/popeyleadsonar.git
   cd popeyleadsonar
   ```

2. **Virtuelle Umgebung erstellen**:
   ```bash
   python -m venv env
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

3. **Abhängigkeiten installieren**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Anwendung starten**:
   ```bash
   python main.py
   ```

---

## ⚙️ Konfiguration

1. **E-Mail-Einrichtung**: Gehen Sie zu **Einstellungen** und fügen Sie Ihr Gmail-Konto hinzu (verwenden Sie ein App-Passwort).
2. **KI-Anbieter**: Konfigurieren Sie OpenAI, Gemini oder ein lokales Modell (Ollama/LM Studio) im Tab **AI Lab**.
3. **Firmenprofil**: Geben Sie Ihre Firmendaten ein, um automatische E-Mail-Signaturen und KI-Kontext zu aktivieren.

---

## 🛡️ Datenschutz und Sicherheit

PopeyLeadSonar wurde mit Fokus auf Datenschutz entwickelt:
- **Lokale Daten**: Alle Profile, Lead-Datenbanken und Zugangsdaten werden lokal im Verzeichnis `profiles/` gespeichert.
- **Keine Cloud-Synchronisierung**: Ihre Daten verlassen Ihren Rechner nur, wenn Sie eine E-Mail versenden oder eine KI-API aufrufen.
- **Verschlüsselte Passwörter**: SMTP-Passwörter werden verschlüsselt auf der Festplatte gespeichert.

---

## ⚖️ Lizenz und Haftungsausschluss

Veröffentlicht unter der **MIT-Lizenz**. Details siehe [`LICENSE`](LICENSE).

Diese Software wird kostenlos und "wie besehen" (as is) bereitgestellt. **Der Autor übernimmt keinerlei Verantwortung dafür, wie dieses Tool genutzt wird**, einschließlich jeglicher Nutzung, die geltendes Recht verletzt (z. B. Anti-Spam-Vorschriften oder Datenschutzgesetze wie die DSGVO). Die Nutzung erfolgt auf eigenes Risiko; Sie sind selbst dafür verantwortlich, die für Sie geltenden gesetzlichen Vorschriften einzuhalten.

---

## ☕ Projekt unterstützen

Wenn PopeyLeadSonar für Sie nützlich ist, freuen wir uns über Ihre Unterstützung — jede Unterstützung hilft dabei, das Projekt am Leben zu erhalten und weiterzuentwickeln! 💚

[**Über Tipply spenden**](https://tipply.pl/@Papajgejmer)

---

## 📬 Kontakt

- GitHub: [popeyxgamer](https://github.com/popeyxgamer)
- E-Mail: obserwujnewsymordo@gmail.com

---

*Erstellt mit ❤️ von Robert (popeyxgamer) / PopeyLeadSonar.*

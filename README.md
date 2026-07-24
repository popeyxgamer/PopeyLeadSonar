# 🎯 PopeyLeadSonar

A professional Sales Engagement Platform for AI-driven lead generation and automated cold mailing.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://pypi.org/project/PySide6/)

🌍 **Read this in other languages:** [Polski](README.pl.md) · [Deutsch](README.de.md)

PopeyLeadSonar transforms the traditional cold mailing process into an intelligent, automated pipeline. It handles everything from finding companies online to managing complex follow-up sequences with AI-powered personalization.

---

## 💎 Features

- **🚀 Intelligent Sequences (Follow-up)**: Create multi-step contact paths. Automatically stop sequences when a lead replies.
- **🧠 AI Auto-Send**: Let AI browse the lead's website, evaluate business fit, and write a unique, highly personalized email.
- **🔥 Email Warm-up**: Protect your sender reputation by warming up your SMTP accounts automatically.
- **🧬 Hybrid Search**: Combine results from DuckDuckGo, Google, and Bing to find the best B2B leads.
- **📥 Smart Inbox AI**: Reply to potential clients with one click using AI-generated suggestions based on your offer.
- **📊 Sales Funnel Dashboard**: Visualize your conversion rates and campaign activity in real-time.
- **🌍 Multi-language Support**: Fully localized in English, German, and Polish.
- **🛡️ Reputation Protection**: Built-in MX verification, blacklist management, and S/MIME digital signing.

---

## 🛠 Installation

### Prerequisites
- Python 3.11+
- [Git](https://git-scm.com/)

### Steps (Windows - Recommended)
1. **Double-click** `install.bat`. This will create a virtual environment and install all dependencies automatically.
2. **Double-click** `start.bat` to launch the application.

### Steps (Manual/Linux/macOS)
1. **Clone the repository**:
   ```bash
   git clone https://github.com/popeyxgamer/popeyleadsonar.git
   cd popeyleadsonar
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```

---

## ⚙️ Configuration

1. **Email Setup**: Go to **Settings** and add your Gmail account (use an App Password).
2. **AI Provider**: Configure OpenAI, Gemini, or a local model (Ollama/LM Studio) in the **AI Lab** tab.
3. **Company Profile**: Fill in your company details to enable automatic email footers and AI context.

---

## 🛡️ Privacy & Security

PopeyLeadSonar is designed with privacy in mind:
- **Local Data**: All profiles, lead databases, and credentials are stored locally in the `profiles/` directory.
- **No Cloud Sync**: Your data never leaves your machine unless you send an email or call an AI API.
- **Encrypted Passwords**: SMTP passwords are encrypted on disk.

---

## ⚖️ License & Disclaimer

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

This software is provided free of charge and "as is". **The author takes no responsibility for how this tool is used**, including any use that violates applicable laws (e.g. anti-spam regulations or data protection laws such as GDPR). You are solely responsible for using this application in a legal and ethical way.

---

## ☕ Support the Project

If you find PopeyLeadSonar useful, consider supporting its development — every bit of support helps keep the project alive and improving! 💚

[**Donate via Tipply**](https://tipply.pl/@Papajgejmer)

---

## 📬 Contact

- GitHub: [popeyxgamer](https://github.com/popeyxgamer)
- Email: obserwujnewsymordo@gmail.com

---

*Created with ❤️ by Robert (popeyxgamer) / PopeyLeadSonar.*

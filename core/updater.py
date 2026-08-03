# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import requests
from pathlib import Path
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar
from PySide6.QtCore import Qt, QThread, Signal

from core.config import VERSION, GITHUB_USER, GITHUB_REPO, logger

UPDATE_JSON_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.json"

class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))

            downloaded = 0
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            self.progress.emit(int(downloaded * 100 / total_size))

            self.finished.emit(str(self.save_path))
        except Exception as e:
            self.error.emit(str(e))

class UpdateDialog(QDialog):
    def __init__(self, new_version, download_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aktualizacja PopeyLeadSonar")
        self.setFixedSize(400, 200)
        self.download_url = download_url

        layout = QVBoxLayout(self)

        self.info_label = QLabel(f"<b>Dostępna jest nowa wersja: {new_version}</b><br><br>"
                                 f"Twoja aktualna wersja: {VERSION}<br><br>"
                                 "Czy chcesz pobrać i zainstalować aktualizację?")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.btn_layout = QVBoxLayout()
        self.btn_update = QPushButton("Aktualizuj teraz")
        self.btn_update.clicked.connect(self.start_download)
        self.btn_layout.addWidget(self.btn_update)

        self.btn_close = QPushButton("Później")
        self.btn_close.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_close)

        layout.addLayout(self.btn_layout)

        self.download_thread = None

    def start_download(self):
        self.btn_update.setEnabled(False)
        self.btn_close.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.info_label.setText("Pobieranie aktualizacji... Proszę czekać.")

        temp_dir = Path(os.environ.get("TEMP", "."))
        save_path = temp_dir / "PopeyLeadSonar_Setup.exe"

        self.download_thread = DownloadThread(self.download_url, save_path)
        self.download_thread.progress.connect(self.progress_bar.setValue)
        self.download_thread.finished.connect(self.install_update)
        self.download_thread.error.connect(self.on_error)
        self.download_thread.start()

    def on_error(self, err_msg):
        QMessageBox.critical(self, "Błąd pobierania", f"Nie udało się pobrać aktualizacji:\n{err_msg}")
        self.reject()

    def install_update(self, exe_path):
        self.info_label.setText("Pobieranie zakończone. Uruchamianie instalatora...")
        try:
            # Uruchamiamy instalator w trybie cichym (jeśli to Inno Setup) lub zwykłym
            # /VERYSILENT /SUPPRESSMSGBOXES /RESTARTAPPLICATIONS dla Inno Setup
            subprocess.Popen([exe_path, "/SILENT", "/SP-", "/RESTARTAPPLICATIONS"])
            sys.exit(0)  # Zamykamy bieżącą aplikację
        except Exception as e:
            QMessageBox.critical(self, "Błąd instalacji", f"Nie udało się uruchomić instalatora:\n{e}")
            self.reject()

def check_for_updates(parent=None, silent=False):
    """Sprawdza dostępność aktualizacji na GitHubie."""
    try:
        response = requests.get(UPDATE_JSON_URL, timeout=5)
        response.raise_for_status()
        data = response.json()

        remote_version = data.get("version")
        download_url = data.get("url")

        if remote_version and remote_version != VERSION:
            dialog = UpdateDialog(remote_version, download_url, parent)
            dialog.exec()
        elif not silent:
            QMessageBox.information(parent, "Aktualizacja", "Posiadasz najnowszą wersję programu.")

    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania aktualizacji: {e}")
        if not silent:
            QMessageBox.warning(parent, "Błąd", f"Nie udało się sprawdzić dostępności aktualizacji.\n{e}")

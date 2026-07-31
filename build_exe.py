import PyInstaller.__main__
import os
import shutil

# Konfiguracja
EXE_NAME = "PopeyLeadSonar"
MAIN_SCRIPT = "main.py"
ICON_PATH = "assets/icon.ico"

# Zasoby do dołączenia (format: "source;destination")
DATAS = [
    ("assets", "assets"),
    ("locales", "locales"),
]

# Moduły do wykluczenia (opcjonalnie)
EXCLUDES = [
    "profiles",
    "last_profile.txt",
    "app_language.txt",
    "leady.csv",
    ".git",
    ".artifacts",
]

def build():
    print(f"Rozpoczynam budowę {EXE_NAME}.exe...")

    # Czyszczenie poprzednich buildów
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    params = [
        MAIN_SCRIPT,
        f"--name={EXE_NAME}",
        "--onefile",
        "--windowed",
        f"--icon={ICON_PATH}",
    ]

    for source, dest in DATAS:
        params.extend(["--add-data", f"{source}{os.pathsep}{dest}"])

    for item in EXCLUDES:
        params.extend(["--exclude-module", item])

    # Dodatkowe flagi dla czystości
    params.append("--noconfirm")
    params.append("--clean")

    PyInstaller.__main__.run(params)

    print("\n" + "="*40)
    print(f"PROCES ZAKOŃCZONY POMYŚLNIE!")
    print(f"Twój plik znajduje się w folderze: dist/{EXE_NAME}.exe")
    print("="*40)

if __name__ == "__main__":
    build()

@echo off
title PopeyLeadSonar - Instalator
echo ==================================================
echo   PopeyLeadSonar Premium - Instalacja Srodowiska
echo ==================================================
echo.

:: Sprawdzenie czy Python jest zainstalowany
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [BLAD] Python nie jest zainstalowany lub nie ma go w PATH.
    echo Pobierz go z https://www.python.org/
    pause
    exit /b
)

echo [1/3] Tworzenie srodowiska wirtualnego (folder 'env')...
python -m venv env

echo [2/3] Aktywacja srodowiska i aktualizacja pip...
call env\Scripts\activate
python -m pip install --upgrade pip

echo [3/3] Instalacja bibliotek (moze to potrwac kilka minut)...
pip install -r requirements.txt

echo.
echo ==================================================
echo   INSTALACJA ZAKONCZONA POMYSLNIE!
echo   Mozesz teraz uruchamiac program przez start.bat
echo ==================================================
echo.
pause

@echo off
title PopeyLeadSonar Premium
echo [PopeyLeadSonar] Inicjalizacja...

:: Sprawdzenie czy srodowisko istnieje
if not exist env (
    echo [BLAD] Nie znaleziono folderu 'env'.
    echo Uruchom najpierw install.bat, aby przygotowac aplikacje.
    pause
    exit /b
)

:: Aktywacja i start
call env\Scripts\activate
echo [PopeyLeadSonar] Startowanie aplikacji w wersji Premium...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [INFO] Aplikacja zostala zamknieta lub wystapil blad.
    pause
)

@echo off
set "NAJEM_KATALOG_INSTALACJI=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0program\narzedzia\zatrzymaj.ps1"
pause

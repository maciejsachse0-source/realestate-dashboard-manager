@echo off
rem Sklada plik z informacjami o stanie programu, do wyslania autorowi.
set "NAJEM_KATALOG_INSTALACJI=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0program\narzedzia\diagnostyka.ps1"

@echo off
set "NAJEM_KATALOG_INSTALACJI=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0instalator\cofnij.ps1"

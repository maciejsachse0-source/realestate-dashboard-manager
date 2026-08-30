@echo off
rem Uruchom raz, po rozpakowaniu paczki instalacyjnej.
set "NAJEM_KATALOG_INSTALACJI=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0instalator\zainstaluj.ps1"

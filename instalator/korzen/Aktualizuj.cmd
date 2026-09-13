@echo off
rem Przeciagnij na ten plik zip z nowa wersja programu.
rem Mozna tez kliknac dwa razy i wskazac plik w oknie wyboru.
set "NAJEM_KATALOG_INSTALACJI=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0instalator\aktualizuj.ps1" %*

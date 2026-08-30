@echo off
rem Ten plik lezy w korzeniu instalacji i przezywa kazda aktualizacje.
rem Skrot na pulpicie celuje wlasnie tutaj, a nie w katalog "program",
rem ktory przy aktualizacji zmienia nazwe.
set "NAJEM_KATALOG_INSTALACJI=%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0program\narzedzia\uruchom.ps1"

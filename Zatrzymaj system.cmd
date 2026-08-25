@echo off
rem Zatrzymuje baze danych, jesli zostala uruchomiona i nie wylaczyla sie sama.
rem Potrzebne tylko wtedy, gdy okno programu zostalo zamkniete krzyzykiem.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0narzedzia\lokalny-postgres.ps1" stop
timeout /t 3 >nul

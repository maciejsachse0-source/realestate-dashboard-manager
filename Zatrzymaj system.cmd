@echo off
rem Zatrzymuje program i baze danych.
rem Potrzebne wtedy, gdy okno programu zostalo zamkniete krzyzykiem: proces
rem aplikacji potrafi wtedy zostac i trzymac port 8010.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0narzedzia\zatrzymaj.ps1"
timeout /t 3 >nul

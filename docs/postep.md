# Stan projektu

**Aktualizowane na koniec każdego etapu.** Kilkanaście linii, nie więcej —
ten plik ładuje się do kontekstu przy każdej sesji.

## Gdzie jestem

Etap **E0 + E0.5 ukończone** (25.08.2026). Fundament stoi, Claude Code skonfigurowany.
Baza pusta poza rozszerzeniami — żadnych tabel domenowych jeszcze nie ma.

## Co następne

**E1: model danych i migracje.** Encje z sekcji 3.2 koncepcji. Warunek wstępny:
odpowiedzi na pytania A (VAT), B (waluta i indeksacja walutowa) i F (stany
okresu najmu) z sekcji 1.1 planu budowy. Bez nich schemat finansowy jest zgadywany.

## Co jest kruche

- `narzedzia/lokalny-postgres.ps1`: ścieżka repozytorium zawiera spację, więc każdy
  argument przekazywany do binariów PostgreSQL musi być jawnie cytowany.
  Wszędzie `127.0.0.1`, nigdy `localhost` — rozwiązanie na `::1` wisi
  kilkadziesiąt sekund zamiast odmówić od razu.
- `frontend/src/funkcje/format.ts`: `useGrouping: 'always'` jest konieczne,
  bo CLDR dla `pl-PL` domyślnie nie grupuje czterocyfrowych kwot.

## Czego nie ruszać

- `tests/domena/test_granice_warstw.py` pilnuje czystości warstwy domenowej.
  Jeśli zacznie być niewygodny, to znak, że kod idzie w złą stronę, a nie test.

# Stan projektu

**Aktualizowane na koniec każdego etapu.** Kilkanaście linii, nie więcej —
ten plik ładuje się do kontekstu przy każdej sesji.

## Gdzie jestem

Etapy **E0, E0.5 i E1 ukończone** (25.08.2026). Fundament działa od przeglądarki
po bazę, Claude Code skonfigurowany, schemat bazy postawiony: 14 tabel,
16 ograniczeń CHECK, migracje `001_fundament` i `002_model_danych`.
Warstwa domenowa ma na razie tylko słowniki i maszyny stanów. Zero danych,
zero endpointów poza `/api/v1/health`, zero ekranów.

## Co następne

**E2: warstwa domenowa i reguły biznesowe.** To najważniejszy etap projektu.
Trzy sesje, po jednej grupie reguł:
1. `pieniadze.py` (Kwota, VAT, zaokrąglanie) i `kalendarz.py` (święta, dni robocze)
2. `stan_efektywny.py` — odczyt parametrów obowiązujących na dany dzień
3. Reguły R1, R2, R4–R7 — każda z testami napisanymi przed implementacją

Używaj `/nowa-regula`. Skill wymusza właściwą kolejność.

## Czego nadal nie wiem

- **Punkt A:** czynsz w umowach netto czy brutto, czy stawka VAT to zawsze 23%.
  Schemat jest odporny — każda kwota niesie rodzaj i stawkę — ale reguła
  waloryzacji w E2 musi wiedzieć, na czym liczy.
- **Punkt B:** czy występują umowy w EUR płatne w PLN po kursie NBP. Jeśli tak,
  potrzebna waluta płatności odrębna od waluty umowy i reguła kursu.
- Pytania 1–10 z sekcji 11 koncepcji, w szczególności miejsca postojowe
  (osobny lokal czy składnik opłaty) i który dokładnie wskaźnik GUS.

## Co jest kruche

- `narzedzia/lokalny-postgres.ps1`: ścieżka repozytorium zawiera spację, więc każdy
  argument przekazywany do binariów PostgreSQL musi być jawnie cytowany.
  Wszędzie `127.0.0.1`, nigdy `localhost` — rozwiązanie na `::1` wisi
  kilkadziesiąt sekund zamiast odmówić od razu.
- `narzedzia/uruchom.ps1`: żadnych `2>&1` przy programach natywnych. PowerShell 5.1
  zamienia stderr w błędy i przerywa skrypt na zwykłym logu INFO Alembica.
- `frontend/src/funkcje/format.ts`: `useGrouping: 'always'` jest konieczne,
  bo CLDR dla `pl-PL` domyślnie nie grupuje czterocyfrowych kwot.

## Czego nie ruszać

- `tests/domena/test_granice_warstw.py` pilnuje czystości warstwy domenowej.
  Jeśli zacznie być niewygodny, to znak, że kod idzie w złą stronę, a nie test.
- Wyzwalacz `trg_log_audytu_bez_zmian` blokuje UPDATE i DELETE na `log_audytu`.
  To jest zamierzone. Poprawianie logu audytu nie jest dozwolone również dla nas.
- `skladnik_oplaty` celowo nie ma kolumny z kwotą. Uzasadnienie: ADR 004.

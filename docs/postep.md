# Stan projektu

**Aktualizowane na koniec każdego etapu.** Kilkanaście linii, nie więcej —
ten plik ładuje się do kontekstu przy każdej sesji.

## Gdzie jestem

Etapy **E0, E0.5, E1 i E2 sesja 1** ukończone (25.08.2026). Fundament działa
od przeglądarki po bazę, Claude Code skonfigurowany, schemat bazy postawiony:
14 tabel, 16 ograniczeń CHECK, migracje `001_fundament` i `002_model_danych`.

Warstwa domenowa ma słowniki, maszyny stanów, `pieniadze.py` i `kalendarz.py`.
Pokrycie `domena/` wynosi 100%, 115 testów. Zero danych, zero endpointów
poza `/api/v1/health`, zero ekranów.

## Co następne

**E2 sesja 2: `stan_efektywny.py`** — odczyt parametrów obowiązujących na dany
dzień. Obsłużyć trzeba: brak wartości, wartości nakładające się w czasie oraz
wartości niezatwierdzone (te NIE wchodzą do stanu efektywnego, decyzja D4).

Potem **E2 sesja 3:** reguły R1, R2, R4–R7. Używaj `/nowa-regula`; skill wymusza
kolejność „najpierw test".

## Czego nadal nie wiem

- **Punkt A:** czynsz w umowach netto czy brutto, czy stawka VAT to zawsze 23%.
  Schemat i typ `Kwota` są odporne — każda kwota niesie rodzaj, stawkę i walutę —
  ale reguła waloryzacji R2 (sesja 3) musi wiedzieć, na czym mnoży: waloryzacja
  netto i brutto dają po zaokrągleniu różne kwoty.
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
- `domena/pieniadze.py`: zaokrąglanie wyłącznie przez `zaokraglij`, zawsze
  `ROUND_HALF_UP`. Python domyślnie zaokrągla bankowo i 2,345 dałoby 2,34.

## Czego nie ruszać

- `tests/domena/test_granice_warstw.py` pilnuje czystości warstwy domenowej.
  Jeśli zacznie być niewygodny, to znak, że kod idzie w złą stronę, a nie test.
- Wyzwalacz `trg_log_audytu_bez_zmian` blokuje UPDATE i DELETE na `log_audytu`.
  To jest zamierzone. Poprawianie logu audytu nie jest dozwolone również dla nas.
- `skladnik_oplaty` celowo nie ma kolumny z kwotą. Uzasadnienie: ADR 004.
- `Kwota` jest niezmienna i sama się kwantyzuje przy tworzeniu. Każda operacja
  zwraca nową kwotę. Nie dorabiaj do niej setterów.

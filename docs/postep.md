# Stan projektu

**Aktualizowane na koniec każdego etapu.** Kilkanaście linii, nie więcej —
ten plik ładuje się do kontekstu przy każdej sesji.

## Gdzie jestem

Etapy **E0, E0.5, E1 i cały E2** ukończone (25.08.2026). Fundament działa
od przeglądarki po bazę, Claude Code skonfigurowany, schemat bazy postawiony:
14 tabel, 16 ograniczeń CHECK, migracje `001_fundament` i `002_model_danych`.

Warstwa domenowa jest kompletna: słowniki, maszyny stanów, `pieniadze.py`,
`kalendarz.py`, `parametry.py` (stan efektywny) oraz reguły R1, R2, R4–R7 i R9
w `domena/reguly/`. Pokrycie `domena/` wynosi 100%. Zero danych, zero endpointów
poza `/api/v1/health`, zero ekranów.

## Co następne

**E3: generator zdarzeń.** Katalog z sekcji 6 koncepcji, idempotentnie.
Czysta funkcja `(stan_umowy, data_odniesienia) -> lista zdarzeń` w domenie,
usługa zapisująca z `ON CONFLICT DO NOTHING`, zadanie APScheduler raz na dobę
o 6:00 i endpoint administracyjny do ręcznego uruchomienia.

Klucz naturalny `(typ, encja, data)` jest już unikalny w bazie od E1, więc
idempotencja jest wymuszona po stronie danych, nie tylko w kodzie.

## Czego nadal nie wiem

- **Punkt A przestał blokować.** Typ `Kwota` niesie rodzaj i stawkę, a R2
  waloryzuje kwotę w tej postaci, w jakiej definiuje ją umowa. Odpowiedź nadal
  jest potrzebna do importu z Excela (E7), gdzie ktoś musi zadeklarować,
  czym są liczby w arkuszu.
- **Konwencja końca umowy:** `KONIEC_WLACZNIE = True` w `reguly/data_zakonczenia.py`
  oznacza, że 24 miesiące od 01.02.2026 kończą się 31.01.2028. Wariant zgodny
  z art. 112 k.c. dałby 01.02.2028. Do potwierdzenia na realnych umowach —
  zmiana to jedna stała.
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
- `OcenaKompletnosci.wskaznik` jest wartością dokładną, nie zaokrągloną.
  Zaokrąglanie robi dopiero `procent`. Inaczej profil o kompletności 0,395
  przekraczałby próg użyteczności przez artefakt zaokrąglenia.
- Funkcje sprawdzające w `reguly/zabezpieczenia.py` zwracają `False` przy braku
  danych. Alarm bez pokrycia w danych uczy ludzi ignorowania alarmów.

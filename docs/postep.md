# Stan projektu

**Aktualizowane na koniec każdego etapu.** Kilkanaście linii, nie więcej —
ten plik ładuje się do kontekstu przy każdej sesji.

## Gdzie jestem

Etapy **E0, E0.5, E1, E2 i E3** ukończone (25.08.2026). Fundament działa
od przeglądarki po bazę, Claude Code skonfigurowany, schemat bazy postawiony:
14 tabel, 16 ograniczeń CHECK, migracje `001_fundament` i `002_model_danych`.

Warstwa domenowa jest kompletna: słowniki, maszyny stanów, `pieniadze.py`,
`kalendarz.py`, `parametry.py` (stan efektywny) oraz reguły R1, R2, R4–R7 i R9
w `domena/reguly/`. Pokrycie `domena/` wynosi 100%. Zero danych, zero endpointów
poza `/api/v1/health` i `/api/v1/zdarzenia/generuj`, zero ekranów.

Generator zdarzeń działa: pokrywa katalog z sekcji 6, chodzi codziennie o 6:00
przez APScheduler i jest idempotentny — sprawdzone na żywej bazie.

## Co następne

**E4: API i uwierzytelnianie.** Argon2id, sesje w ciasteczkach HttpOnly,
cztery role z sekcji 7.9, blokada konta po 5 nieudanych próbach, wymuszona
zmiana hasła przy pierwszym logowaniu. CRUD wszystkich encji, lista lokali
z filtrowaniem i paginacją, `GET /lokale/{id}/stan?na_dzien=`, obsługa zdarzeń,
audyt każdej zmiany i konflikt wersji jako 409.

Warstwa domenowa jest gotowa i przetestowana, więc API ma być cienkie:
tłumaczy HTTP na wywołania usług i z powrotem, bez logiki biznesowej.

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
- `ProponowaneZdarzenie.data_zdarzenia` to data, KTÓREJ zdarzenie DOTYCZY,
  nigdy dzień uruchomienia generatora. Zmiana tego zamieni kokpit terminów
  w listę duplikatów rosnącą o jeden wpis dziennie.
- Stany trwałe (niekompletny profil, polisa poniżej kwoty) kotwiczą się na
  pierwszym dniu miesiąca, więc przypomnienie wraca raz w miesiącu.

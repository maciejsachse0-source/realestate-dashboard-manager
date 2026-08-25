# Pułapki i decyzje, których nie wolno cofnąć

Wiedza zebrana w trakcie budowy. **Nie jest importowana do kontekstu** — czytaj
ją, kiedy dotykasz opisanego miejsca albo kiedy coś zachowuje się dziwnie.

Podział jest prosty: „kruche" to rzeczy, które łatwo zepsuć nie wiedząc o nich,
„nie ruszać" to decyzje, które wyglądają na przeoczenie, a są zamierzone.

---

## Kruche

### `narzedzia/lokalny-postgres.ps1`
Ścieżka repozytorium zawiera spację, więc **każdy** argument przekazywany do
binariów PostgreSQL musi być jawnie cytowany. `Start-Process` w PowerShell 5.1
nie cytuje elementów tablicy — `-ArgumentList '-D', $sciezka` rozpada się
na trzy argumenty.

Wszędzie `127.0.0.1`, nigdy `localhost`. Rozwiązanie na `::1` przy
nieuruchomionym serwerze wisi kilkadziesiąt sekund zamiast odmówić od razu.
To samo dotyczy `DATABASE_URL`.

### `narzedzia/uruchom.ps1`
Żadnych `2>&1` przy programach natywnych. PowerShell 5.1 opakowuje każdą linię
stderr w `ErrorRecord`, więc zwykły log `INFO` Alembica przerywa cały skrypt
startowy.

### `frontend/src/funkcje/format.ts`
`useGrouping: 'always'` jest konieczne. CLDR dla `pl-PL` domyślnie nie grupuje
czterocyfrowych kwot i `1234,56 zł` zostałoby bez spacji.

Daty parsujemy ręcznie z ISO, nie przez `new Date()`. `new Date('2027-03-01')`
to północ UTC, która w niektórych strefach cofa się o dzień.

### `frontend/vite.config.ts`
`fileURLToPath`, nie `.pathname`. Na Windows `.pathname` daje `/C:/dev/...`,
czego bundler nie rozumie.

### Adres aplikacji
Serwer nasłuchuje wyłącznie na `127.0.0.1`. Chrome potrafi rozwiązać `localhost`
na `::1` i wtedy połączenia nie ma. Skrót otwiera jawnie
`http://127.0.0.1:8010` i tak ma zostać.

---

## Czego nie ruszać

### Zaokrąglanie pieniędzy
`domena/pieniadze.py`, funkcja `zaokraglij`, zawsze `ROUND_HALF_UP`. Python
domyślnie zaokrągla bankowo i `2,345` dałoby `2,34` — jeden grosz różnicy wobec
tego, co policzyła księgowa.

`Kwota` jest niezmienna i sama się kwantyzuje przy tworzeniu. Każda operacja
zwraca nową kwotę. Nie dorabiaj setterów.

### `OcenaKompletnosci.wskaznik`
Wartość dokładna, nie zaokrąglona. Zaokrągla dopiero właściwość `procent`.
Inaczej profil o kompletności 0,395 przekroczyłby próg użyteczności 40%
przez artefakt zaokrąglenia, a nie przez uzupełnienie danych.

### `ProponowaneZdarzenie.data_zdarzenia`
To data, **której zdarzenie dotyczy**, nigdy dzień uruchomienia generatora.
Zmiana tego zamieni kokpit terminów w listę duplikatów rosnącą o jeden wpis
dziennie, bo klucz naturalny przestanie dawać idempotencję.

Stany trwałe (niekompletny profil, polisa poniżej kwoty) kotwiczą się na
pierwszym dniu miesiąca — przypomnienie wraca raz w miesiącu, dopóki stan trwa.

### Funkcje sprawdzające w `reguly/zabezpieczenia.py`
Zwracają `False` przy braku danych. Alarm bez pokrycia w danych uczy ludzi
ignorowania alarmów, a to kosztuje więcej niż jeden pominięty termin.

### Optimistic locking
Działa **tylko dlatego**, że `PUT` wymaga pola `wersja` w treści żądania.
Bez niego serwer wczytuje rekord świeżo, nadpisuje go i nigdy nie zauważa,
że ktoś zmienił go w międzyczasie.

### `POLA_UTAJNIONE` w `uslugi/audyt.py`
Trzyma `hash_hasla` i `token_hash` poza logiem. Skrót hasła w logu audytu
to ten sam sekret w drugiej tabeli, czytanej przez szerszy krąg osób.

### Status nowego parametru
Nowa wartość wchodzi jako `zaproponowana` także przy ręcznym wpisaniu z klawiatury.
Decyzja D4 nie robi wyjątku dla człowieka.

### Baza testowa
Testy pracują na osobnej bazie `najem_testy`, zakładanej automatycznie przez
`tests/conftest.py`. Rola `najem` ma do tego uprawnienie `CREATEDB`, nadawane
przez `narzedzia/lokalny-postgres.ps1 setup`.

Bez tego rozdzielenia testy padają, gdy tylko w bazie pojawią się prawdziwe
dane — asercja „lista jest pusta" psuje się od pierwszego wprowadzonego lokalu.
Zdarzyło się to raz, po wgraniu danych przykładowych: 6 testów nie przeszło,
58 wywaliło się na naruszeniu unikalności.

**Przełączenie adresu bazy dzieje się przy imporcie `tests/conftest.py`,
nie w `pytest_configure`.** Pytest najpierw importuje pliki conftest, a dopiero
potem woła hak. Conftest w `tests/api/` importuje `najem.baza`, który tworzy
silnik z adresu odczytanego w tym momencie. Gdy przełączenie siedziało w haku,
`pytest tests/api/...` pracowało na prawdziwej bazie i nikt tego nie widział.

Gdy bazy testowej nie ma, ostrzeżenie leci na stderr, a nie do nagłówka
przebiegu — `addopts = "-q"` nagłówek tłumi. Ostrzeżenie, którego nikt nie
zobaczy, jest gorsze niż jego brak: daje fałszywe poczucie, że testy przeszły.

### `tests/domena/test_granice_warstw.py`
Pilnuje, że `domena/` nie importuje SQLAlchemy, FastAPI ani niczego z I/O.
Jeśli zacznie być niewygodny, to znak, że kod idzie w złą stronę, a nie test.

### Wyzwalacz `trg_log_audytu_bez_zmian`
Blokuje `UPDATE` i `DELETE` na `log_audytu`. To jest zamierzone. Poprawianie
logu audytu nie jest dozwolone również dla nas.

### `skladnik_oplaty` bez kolumny z kwotą
Zamierzone. Uzasadnienie: [ADR 004](decyzje/004-kwoty-poza-tabela-umowy.md).

### Waluta bez wartości domyślnej
Zamierzone. Baza, która sama dopisuje `PLN`, zamienia brak danych w fakt.
Uzasadnienie: [ADR 005](decyzje/005-waluta-bez-wartosci-domyslnej.md).

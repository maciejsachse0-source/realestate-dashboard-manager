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

### Audyt nie zapisuje, kto zmienił
`log_audytu` odpowiada na pytanie **co, kiedy i z jakiej wartości na jaką**,
ale nie **kto**. Kolumny autora nie ma, bo program nie ma logowania
([ADR 009](decyzje/009-usuniecie-logowania.md)). To wygląda na przeoczenie
przy czytaniu sekcji 8.1 koncepcji, a jest decyzją. Przy drugim użytkowniku
trzeba to cofnąć.

Zniknął razem z tym mechanizm `POLA_UTAJNIONE`, który trzymał `hash_hasla`
i `token_hash` poza logiem — nie ma już takich kolumn.

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

### Rozpoznawanie typu pliku
`dokumenty/przechowalnia.py` sprawdza **pierwsze bajty**, nie rozszerzenie
i nie nagłówek `Content-Type`. Oba są deklaracją nadawcy: `umowa.pdf` bywa
plikiem wykonywalnym, a skan bez rozszerzenia bywa poprawnym PDF-em.

DOCX i XLSX mają wspólną sygnaturę ZIP, więc rozróżnia je zawartość archiwum
(`word/document.xml` kontra `xl/`). Zwykłe archiwum ZIP jest odrzucane.

Nazwa pliku w przechowalni pochodzi ze skrótu treści, nigdy z uploadu.
Nadawca nie ma wpływu na to, gdzie plik wyląduje.

### Import z arkusza jest transakcyjny
`uslugi/import_danych.py` sprawdza **wszystko** przed zapisaniem czegokolwiek
i rzuca `ImportPrzerwany` przy pierwszym błędzie w arkuszu. Endpoint robi jawny
`rollback()`. Import, który zapisuje trzydzieści wierszy i wywala się
na trzydziestym pierwszym, zostawia bazę w stanie, którego nikt nie posprząta.

Powtórzenie importu nie duplikuje: budynek, lokal i najemca są odnajdywani
po naturalnych cechach, a umowa nie powstaje drugi raz dla lokalu, który już
ją ma. Dzięki temu poprawiony arkusz można wgrać ponownie.

Wartość czynszu z arkusza wchodzi jako **zatwierdzona**, a nie zaproponowana.
To świadome odstępstwo od decyzji D4: arkusz wypełnia człowiek, a import
uruchamia człowiek, który przed chwilą oglądał podgląd.

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

### Waloryzacja: sumy osobno dla każdej waluty
`PrzebiegWaloryzacji.podsumowanie()` zwraca listę po jednej pozycji na walutę,
nie jedną liczbę. Dodanie umowy w EUR do umowy w PLN dałoby wartość, która
wygląda na pieniądze i nie znaczy nic. Gdyby kiedyś wróciła pokusa uproszczenia
tego do jednego pola — to jest powód, dla którego go nie ma.

Sumę zaznaczonych propozycji liczy endpoint `POST /waloryzacja/podsumowanie`,
także przy odznaczaniu pojedynczej umowy. Front mógłby to zsumować sam, ale
regułą projektu jest, że nie liczy niczego na pieniądzach — w JS są tylko
liczby zmiennoprzecinkowe.

### Waloryzacja rozpoznaje własny przebieg po znaczniku, nie po dacie
`parametr_wartosc.waloryzacja_rok` mówi, który przebieg utworzył dany wiersz.
Rozpoznawanie po samej dacie wejścia myliło aneks z waloryzacją i pozwalało
niezatwierdzonej propozycji zablokować przebieg. Uzasadnienie:
[ADR 007](decyzje/007-znacznik-waloryzacji-na-parametrze.md).

Konsekwencja przy czytaniu starych danych: wiersze sprzed migracji
`004_slad_waloryzacji` nie mają znacznika, więc eksport zmian zatwierdzonych
za tamte lata będzie pusty. To nie jest błąd, tylko brak informacji, której
nikt nigdy nie zapisał.



### Umowa poza terminem nie wchodzi do waloryzacji
Przebieg pomija umowy, które kończą się przed dniem wejścia podwyżki i te,
które zaczynają się po nim. Nie wystarczy filtr po statusie okresu najmu:
status zmienia **człowiek**, a generator zdarzeń tylko wystawia alert
„umowa wygasła". Umowa zakończona w czerwcu potrafi więc wisieć w bazie jako
aktywna aż do momentu, gdy ktoś to poprawi. Bez tego filtru podwyżka trafiłaby
do pisma dla byłego najemcy.

### R5 w warstwie domenowej ma tylko część opisową
`domena/reguly/waloryzacja.py` **nie liczy** wartości zabezpieczenia jako
wielokrotności czynszu. Wymagałoby to krotności jako liczby, a model trzyma
`zabezpieczenie.sposob_wyliczenia` jako wolny tekst („czterokrotność czynszu
podstawowego"). Funkcje, które to liczyły, zostały usunięte razem z testami,
bo nie były wołane z żadnego miejsca w aplikacji, a podbijały pokrycie
`domena/` kodem, którego program nie uruchamia.

Dziś system tylko przypomina człowiekowi, że zabezpieczenie trzeba przeliczyć
— i nie robi tego przy wskaźniku 0%, bo wtedy czynsz się nie zmienił.
Zamiana opisu słownego na liczbę to zadanie ekstrakcji (E9).

### Format liczb w eksportach XLSX
Sam `arkusz.append([...])` daje komórki bez formatu, więc Excel pokazuje
`9851,5` zamiast `9 851,50`. Arkusze waloryzacji idą do pism dla najemców,
więc kolumny kwotowe dostają `number_format = "# ##0.00"`, wskaźnik `"0.00"`
(procent nie jest kwotą i nie dostaje separatora tysięcy), a data
`"DD.MM.YYYY"`. Ten sam zabieg trzeba powtórzyć w każdym kolejnym eksporcie.

Kwoty przekazujemy jako `Decimal`, nigdy przez `float()`. Sam plik XLSX nie ma
typu dziesiętnego, więc odczyt i tak zwróci `float` — ale to jest ograniczenie
formatu, a nie powód, żeby łamać zasadę po naszej stronie.

### Propozycje i zatwierdzone zmiany w osobnych arkuszach
Decyzja D4 mówi, że wartość niezatwierdzona nie wchodzi do raportów, a z arkusza
waloryzacji ktoś robi korespondencję seryjną. Kolumna „Stan" w jednym arkuszu
była za słabym rozróżnieniem: wystarczyło pobrać plik przed zatwierdzeniem,
żeby najemca dostał pismo o podwyżce, której w systemie nie ma. Propozycje mają
własną zakładkę „Propozycje niezatwierdzone", więc pomyłka wymaga przejścia
na inny arkusz, a nie przeoczenia jednej kolumny.

### Front nie dokleja znaku „+" do kwoty
`formatujRoznice` z `format.ts` bierze znak z wartości. Sztywne `+${...}`
przy wskaźniku ujemnym dawało „+-250,00 zł" na zielono, czyli obniżkę
pokazaną jako podwyżkę. Wskaźnik ujemny jest dopuszczalny i po stronie API,
i po stronie interfejsu, więc ten przypadek nie jest teoretyczny.

### Pole roku trzymamy jako tekst, nie jako liczbę
`Number('')` to `0`, a klient HTTP odsiewa tylko `undefined`, `null` i pusty
tekst. Skasowanie zawartości pola przed wpisaniem innego roku wysyłało więc
`?rok=0` i pokazywało użytkownikowi błąd 422 z Pydantica. Do zapytań idzie
dopiero wartość z dozwolonego zakresu — to samo dotyczy każdego innego pola
liczbowego sterującego zapytaniem.

### `expire_on_commit=False` a odpowiedzi z POST
Sesja nie odświeża obiektów po `commit()`, więc endpoint tworzący rekord odda
to, co przyszło w żądaniu, a nie to, co jest w bazie. Przy `NUMERIC(5,2)`
POST zwracał `"3.7"`, a GET `"3.70"` — ta sama wartość pokazywana na dwa
sposoby. `dodaj_wskaznik` woła `baza.refresh()` po commicie. Warto o tym
pamiętać przy każdym nowym endpointcie tworzącym rekord z kolumną o ustalonej
precyzji albo z wartością nadawaną przez bazę.

Osobna sprawa: sprawdzenie `SELECT`-em przed `INSERT`-em nie jest atomowe.
Dwa równoległe żądania zatrzyma dopiero unikalny indeks, więc `IntegrityError`
jest przechwytywany i mapowany na 409, a nie zostawiany jako 500.

### Przebieg waloryzacji nie jest stronicowany
Świadomie, wbrew regule „każdy endpoint listujący ma paginację". Waloryzacja
jest operacją na całym portfelu naraz: użytkownik zaznacza i zatwierdza
wszystko jednym ruchem. Strona po pięćdziesiąt umów zamieniłaby jeden rytuał
raz do roku w dwadzieścia osobnych zatwierdzeń i ukryła część wyłączeń.
`/waloryzacja/wskazniki` paginację ma, bo to zwykła lista.

### Dokumenty z dysku są odnośnikami, nie kopiami
`dokument.przechowywanie` rozstrzyga, względem czego liczy się `plik_sciezka`:
`kopia` → `KATALOG_DOKUMENTOW`, `link` → `KATALOG_SKANU`. Endpoint pobierający
plik musi wybrać właściwy katalog, inaczej zlinkowany dokument zwraca 410
mimo istniejącego pliku. Szczegóły i odrzucone warianty: [ADR 008](decyzje/008-dokumenty-linkowane-nie-kopiowane.md).

**Kopia zapasowa samej bazy nie wystarcza.** Backup musi obejmować bazę razem
z katalogiem wskazanym przez `KATALOG_SKANU`. Przeniesienie albo przemianowanie
pliku w Eksploratorze zrywa odnośnik — wykrywa to dopiero przycisk
„Sprawdź odnośniki" (`GET /api/v1/skan/sprawdz`).

### Skan nie parsuje oznaczeń lokali z nazw folderów
Oznaczenia są nieregularne: raz od zera, raz od jedynki, czasem `1.A` i `1.B`,
czasem z podkreśleniem. Każde parsowanie dawałoby ciche pomyłki, czyli dokument
przypięty do nie tej umowy. Zamiast tego folder paruje się z umową raz, ręcznie,
a `powiazanie_folderu` to pamięta. To ta sama zasada, co decyzja D5: brak danych
jest informacją, nie powodem do zgadywania.

Konsekwencja, o której trzeba wiedzieć: lista wyboru przy parowaniu pokazuje
**aktualne** umowy lokali. Folderu po poprzednim najemcy nie da się dziś
przypiąć do jego zakończonej umowy — trzeba by endpointu listującego okresy
najmu razem z historycznymi.

### Pominięcia pamiętane po skrócie, nie po ścieżce
`pominiety_plik` trzyma SHA-256, bo plik przemianowany albo przeniesiony do
innego folderu to nadal ten sam plik. Dopasowanie po ścieżce jest tylko
przyspieszaczem (żeby nie liczyć skrótu każdego pliku przy każdym skanie),
a nie kryterium.

### Stary format Worda rozpoznajemy po strumieniu OLE
`.doc`, `.xls` i `.ppt` mają **wspólną** sygnaturę OLE2 (`D0CF11E0A1B11AE1`),
więc sama sygnatura nie mówi, co to za plik. Rozróżnia je obecność nazwy
strumienia `WordDocument` (UTF-16LE) w pierwszym megabajcie. To nie jest pełne
parsowanie struktury OLE i celowo nim nie jest — wystarcza, a pełny parser
byłby nową zależnością dla jednego formatu.

### Skrót przebudowuje interfejs po czasie plików, nie po jego istnieniu
`narzedzia/uruchom.ps1`, krok 4. Pierwotny warunek brzmiał „buduj, jeśli nie ma
`dist/index.html`". Po pierwszym zbudowaniu skrót nie przebudował interfejsu już
nigdy: backend startował z bieżącego kodu, front z bundla sprzed zmian.
Dla osoby klikającej ikonkę wyglądało to tak, jakby zmiany nie istniały —
i tak właśnie zostało zgłoszone.

Teraz `Powod-Przebudowy` porównuje czas modyfikacji `dist/index.html` z plikami
w `frontend/src`, `index.html`, `package.json` i `vite.config.ts`.
`node_modules` celowo poza listą: `npm install` dotyka tysięcy plików i przy
każdym uruchomieniu wymuszałby przebudowę.

### `index.html` serwowany z `Cache-Control: no-cache`
`main.py`, klasa `InterfejsBezCache`. Pliki w `assets/` mają skrót treści
w nazwie, więc mogą leżeć w cache'u przeglądarki dowolnie długo. `index.html`
skrótu nie ma i to on wskazuje na aktualne pliki — podany z cache'u pokazuje
poprzednią wersję programu mimo zaktualizowanego serwera.

`no-cache` nie zabrania cache'owania, tylko wymusza sprawdzenie: przy
niezmienionym pliku przeglądarka dostaje 304 i nie pobiera go ponownie.
Ma to dwa testy w `tests/api/test_zdrowie.py` — jeden pilnuje nagłówka na
`index.html`, drugi tego, żeby nie trafił na pliki z `assets/`.

### `GET /api/v1/skan` nie jest stronicowany
Świadomie, tak jak przebieg waloryzacji. To nie jest lista rekordów, tylko
drzewo katalogów zestawione ze stanem bazy — stronicowanie rozbiłoby budynek
na dwie strony i ukryło część folderów. Zamiast paginacji jest `LIMIT_PLIKOW`
(3000) i pole `obcietych`, które mówi wprost, ile pozycji nie weszło.

Osobno `niedostepnych` liczy katalogi i pliki, których system nie udostępnił
(brak uprawnień, ścieżka dłuższa niż limit Windowsa, odłączony dysk sieciowy).
Wcześniej jeden taki katalog kończył cały skan błędem 500 i użytkownik nie
widział ani jednego swojego dokumentu. Milczące pomijanie byłoby złamaniem
decyzji D5, więc liczba trafia na ekran.

### Katalog skanu: baza wygrywa z plikiem `.env`
`uslugi/ustawienia_systemu.katalog_skanu()` czyta najpierw tabelę
`ustawienie_systemu`, a dopiero potem `KATALOG_SKANU` z `.env`. Kolejność jest
celowa: wartość w pliku ustawia ten, kto instaluje program, wartość w bazie —
użytkownik. Pusta tabela znaczy „bierz to, co w pliku", więc instalacja bez
żadnego kliknięcia działa jak wcześniej.

Skutek dla diagnozy: gdy skan patrzy „nie tam, gdzie mówi `.env`", zajrzyj do
`ustawienie_systemu`, nie do pliku. Ekran pokazuje źródło wprost (`z pliku .env`
albo nic, gdy wartość pochodzi z bazy).

Zmiana wymaga roli administratora, ale **odczyt ma każdy** — bez tego nie da się
odpowiedzieć na pytanie „gdzie ten program właściwie szuka".

### Dwie instalacje na jednym komputerze rozmawiają z tą samą bazą
Port `5434` jest stałą w `lokalny-postgres.ps1`. `Czy-Dziala` sprawdza wyłącznie,
czy **coś** odpowiada na tym porcie — nie czy to ten właściwy serwer. Skutek:
przy uruchomionej bazie deweloperskiej instalacja testowa w innym katalogu
nie wystartuje własnego Postgresa, tylko cicho podłączy się do tamtego
i puści na nim `alembic upgrade head`.

Dla docelowego użycia (jeden komputer, jedna instalacja) to bez znaczenia.
Ale **próbę generalną aktualizacji rób z zatrzymaną bazą deweloperską**, inaczej
przećwiczysz ją na swoich prawdziwych danych.

### `$env:TEMP` bywa ścieżką 8.3 i wywraca `Remove-Item`
Na koncie z nazwą dłuższą niż osiem znaków `TEMP` to
`C:\Users\HPOMEN~1\AppData\Local\Temp`. `Remove-Item -LiteralPath` na ścieżce
zbudowanej z takiego prefiksu kończy się `An object at the specified path
C:\Users\HPOMEN~1 does not exist`, mimo że katalog istnieje.

Dlatego `spakuj-wydanie.ps1`, `aktualizuj.ps1` i `diagnostyka.ps1` trzymają
katalogi robocze obok celu, nie w `TEMP`. W aktualizatorze ma to drugą zaletę:
`program-nowa` leży na tym samym wolumenie co `program`, więc `Move-Item` jest
zmianą nazwy, a nie kopiowaniem setek megabajtów.

### `robocopy` zwraca mapę bitową, nie kod błędu
`0–7` to sukces (`1` = skopiowano pliki, `2` = w celu są pliki nadmiarowe…),
dopiero `8` w górę to awaria. Bez `if ($LASTEXITCODE -ge 8)` w
`kopia-zapasowa.ps1` pierwsza udana kopia wyglądałaby jak błąd.

### Aktualizacja nie podmienia skryptów z `instalator\`
`aktualizuj.ps1` zmienia nazwę katalogu `program`, więc sam musi leżeć poza nim.
Konsekwencja: paczka wydania **nie aktualizuje aktualizatora**. Poprawka w nim
wymaga ręcznej podmiany pliku u użytkownika. To powód, żeby trzymać te skrypty
krótkie — opisane w [ADR 010](decyzje/010-instalacja-u-uzytkownika-i-kanal-aktualizacji.md).

### `instalator\` celowo nie dołącza `narzedzia\sciezki.ps1`
Wygląda to na przeoczenie: cały projekt bierze ścieżki z jednego miejsca,
a te trzy skrypty liczą je same. Powód jest twardy — `sciezki.ps1` leży
w `program\`, a aktualizator w połowie pracy zmienia nazwę tego katalogu.
Skrypt dołączający plik z jego wnętrza wyciągałby sobie grunt spod nóg.

Wspólne kawałki tych trzech skryptów mieszkają w `instalator\wspolne.ps1`,
który leży razem z nimi. Nie „naprawiaj" tego przez podpięcie `sciezki.ps1` —
zepsuje się dopiero u użytkownika, w trakcie aktualizacji.

### Cofnięcie wersji nie cofa bazy
`Cofnij aktualizacje.cmd` zamienia katalogi z kodem. Struktura bazy zostaje ta,
którą zrobiła z niej migracja. W tym projekcie migracje są dokładające (nic nie
usuwamy fizycznie), więc starsza wersja programu zwykle sobie poradzi — ale
„zwykle" to nie „zawsze". Ratunkiem jest zrzut z `dane\kopie`, a jego
odtworzenie kasuje wszystko wprowadzone po zrzucie, więc żaden skrypt nie robi
tego sam.

### `| Out-Null` na wywołaniu `lokalny-postgres.ps1 start` wiesza skrypt
`Start-Serwer` odpala `postgres.exe` przez `Start-Process` z przekierowanymi
strumieniami, a uruchomiony serwer **dziedziczy uchwyt wyjścia procesu
potomnego**. Potok czeka na zamknięcie tego uchwytu, czyli na zatrzymanie bazy —
i skrypt wisi w nieskończoność mimo poprawnie działającej bazy.

Kosztowało to zawieszony aktualizator na kroku „robię kopię bazy danych":
z perspektywy użytkownika okno, które nigdy się nie kończy. Nie tłumi się
wyjścia tych wywołań. Ta sama uwaga stoi już w `uruchom.ps1` przy kroku 2.

### Środowisko Pythona musi leżeć poza katalogiem `program`
Domyślnie `uv` trzyma je w `backend\.venv`, czyli w katalogu, który aktualizacja
podmienia. Efekt: każde wydanie odbudowuje środowisko od zera — minuta czekania
i **wymóg internetu albo pełnego cache `uv`** na komputerze, który miał działać
bez sieci. Dlatego `zainstaluj.ps1`, `aktualizuj.ps1` **i `uruchom.ps1`**
ustawiają `UV_PROJECT_ENVIRONMENT` na `<instalacja>\srodowisko`.

`uruchom.ps1` dopisano do tej listy 31.08.2026 i to nie było uzupełnienie
kosmetyczne. Instalator zakładał środowisko we właściwym miejscu, ale skrypt
startowy o nim nie wiedział, więc **pierwsze uruchomienie programu budowało
drugie środowisko** w `program\backend\.venv` — i robiło to od nowa po każdej
aktualizacji, bo aktualizacja ten katalog kasuje. Dokładnie ten scenariusz,
przed którym broni cała reszta wpisu. Nie wyszło wcześniej, bo próba generalna
sprawdzała instalację i skrypty obsługowe, a nie start samego programu.

Ścieżkę podaje `Katalog-Srodowiska` z `narzedzia\sciezki.ps1`; w układzie
deweloperskim zwraca `$null` i wtedy zmiennej **nie ustawiamy wcale**, żeby
`uv` wziął `backend\.venv` jak zawsze. Skrypty z `instalator\` liczą tę samą
ścieżkę u siebie, bo nie wolno im sięgać do `program\` — obie definicje muszą
zostać zgodne.

### `[string]$null` w PowerShellu 5.1 to nadal `$null`
`Read-Host` bez konsoli (uruchomienie z potoku, z zadania, ze zdalnej sesji)
zwraca `$null`, a `.Trim()` na nim przerywa skrypt komunikatem
`You cannot call a method on a null-valued expression`. Instalator wywracał się
przez to w połowie zakładania katalogów, nie mówiąc, na czym.

Rzutowanie `([string](Read-Host ...))` **nie pomaga** — sprawdzone, daje z
powrotem `$null`. Działa podstawienie w cudzysłowach: `"$(Read-Host ...)"`.
To samo dotyczy każdego innego miejsca, gdzie wynik `Read-Host` idzie prosto
do metody. Porównania (`-ne 'TAK'`) są bezpieczne, bo `$null` po prostu nie
równa się wzorcowi.

### Pusta wartość w `.env` to `Path(".")`, czyli katalog roboczy
Instalator zapisuje `KATALOG_SKANU=` bez wartości, bo katalog wskazuje się
dopiero w programie. Pydantic robił z pustego napisu `Path("")`, a to jest
`Path(".")` — istniejący katalog. Skan przechodził przez `is_dir()`, meldował
„dostępny" i pokazywał użytkownikowi `alembic` oraz `src` jako jego budynki.
Pierwszy ekran świeżej instalacji pokazywał więc wnętrze samego programu
zamiast komunikatu „wskaż katalog".

Broni tego walidator `_brak_katalogu_to_none` w `config.py`: pusty napis,
same spacje, `""` i `.` dają `None`. Przy każdym nowym polu typu `Path | None`
czytanym z `.env` trzeba o tym pamiętać — sam typ nie wystarcza.

Osobno: **ścieżek w `.env` nie bierzemy w cudzysłowy.** Czytnik przetwarza
wtedy sekwencje z ukośnikiem wstecznym i `C:\Temp\tmp` traci `\t` na rzecz
tabulatora. Cudzysłowy zdejmujemy, ale zamienionego znaku nie da się odzyskać.
Ścieżkę wskazuje się na ekranie „Dokumenty z dysku", gdzie `sprawdz_katalog`
zdejmuje cudzysłowy z tego, co wkleił człowiek, i sprawdza katalog przy zapisie.

### Nazwa pliku w nagłówku HTTP musi być zakodowana procentowo
`Content-Disposition: inline; filename*=UTF-8''...` wygląda na załatwiony
przypadek polskich nazw, ale wartość po `UTF-8''` **musi być zakodowana
procentowo** (RFC 5987). Nagłówki HTTP są latin-1, więc wstawiona wprost „ł"
nie przechodzi przez kodowanie odpowiedzi: pobranie kończy się błędem kodeka
zamiast plikiem, a użytkownik widzi komunikat o `'latin-1' codec`.

Dotyczyło to **większości dokumentów w archiwum** („Załącznik do Aneksu.pdf",
„Umowa Najmu.Rycerska - wzór 3.docx"). Nie wyszło w testach, bo wszystkie
nazwy plików w nich były po angielsku i bez znaków diakrytycznych. Każdy nowy
test na wgrywanie i pobieranie plików ma używać nazwy z polskimi znakami —
u tego użytkownika to jest przypadek typowy, nie brzegowy.

### Normalizacja kodowania: otwarcie pliku do zapisu czyści go przed zapisem
Skrypt porządkujący pliki na ASCII skasował treść `zaplanuj-kopie.ps1`:
`open(p, 'w')` obciął plik, a `write()` zaraz potem wywalił się na polskim
znaku. Został pusty plik, a instalator uruchamiał go bez słowa skargi — bo pusty
skrypt PowerShella nic nie robi i o niczym nie informuje.

Wniosek na przyszłość: konwersje kodowania rób do bufora i zapisuj dopiero po
udanej konwersji, a po każdej masowej operacji na plikach sprawdź ich rozmiary.

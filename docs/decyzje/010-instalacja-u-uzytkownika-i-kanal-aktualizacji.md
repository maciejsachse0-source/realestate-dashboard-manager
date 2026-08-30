# ADR 010: Instalacja u użytkownika i kanał aktualizacji

**Data:** 28.08.2026
**Status:** przyjęta
**Dotyczy:** `narzedzia/sciezki.ps1`, `instalator/`, `backend/src/najem/config.py`

## Kontekst

Program ma trafić na komputer księgowej i tam pracować lokalnie. Autor rozwija
go u siebie i musi umieć wydać poprawkę zdalnie. Warunki zastane, nie do
negocjacji:

- brak wspólnego dysku między tymi dwoma komputerami,
- brak serwera włączonego non stop,
- dokumenty leżą na lokalnym dysku użytkownika,
- kontakt tylko przez internet (mail).

Stan wyjściowy uniemożliwiał jedno i drugie. `pgdata/` leżało **wewnątrz**
katalogu programu, więc każda aktualizacja typu „podmień katalog" kasowała bazę.
Uruchomienie wymagało Node.js, choć zbudowany interfejs jest do działania
wystarczający. Nie istniała żadna paczka wydania.

## Decyzja

### 1. Program i dane w rozłącznych katalogach

```
C:\SystemNajmu\
  program\             kod, podmieniany przy aktualizacji
  program-poprzednia\  jedna wersja wstecz, na cofnięcie
  silnik-bazy\pgsql\   binaria PostgreSQL, niezależne od wersji
  instalator\          instalator, aktualizator, cofanie
  dane\                pgdata, dokumenty, kopie, logi, .env
```

`dane\` nie pojawia się w aktualizatorze ani razu — nie przez ostrożność, tylko
dlatego, że fizycznie nie ma jak go dotknąć.

Przełącznikiem między układem deweloperskim a instalacyjnym jest jedna zmienna
środowiskowa `NAJEM_KATALOG_INSTALACJI`, czytana wyłącznie w
`narzedzia/sciezki.ps1`. Nieustawiona = dzisiejsze ścieżki w repozytorium.
Po stronie Pythona odpowiada jej `NAJEM_PLIK_ENV` w `config.py`.

### 2. Podmiana wersji przez zmianę nazwy katalogu, nie junction

Junction wyglądał atrakcyjniej (N wersji obok siebie, przełączenie wskaźnika),
ale `Remove-Item` na junctionie w PowerShell 5.1 potrafi wejść w cel i skasować
to, na co wskazuje. Zmiana nazwy nie ma tej pułapki, nie wymaga uprawnień
administratora i daje cofnięcie za darmo. Kosztem jest jedna wersja wstecz
zamiast wielu — w praktyce wystarcza.

### 3. Aktualizacja przez plik przysłany mailem, bez pobierania z internetu

Odrzucony wariant: aktualizator sam sprawdza nowe wydanie w prywatnym
repozytorium. To dodatkowy program do utrzymania, poświadczenia na cudzej
maszynie i token wygasający po roku — awaria, która ujawnia się przez „nie
działa" w chwili, gdy potrzebna jest pilna poprawka.

Przyjęte: autor wysyła zip, użytkownik przeciąga go na `Aktualizuj.cmd`.
Dołożenie automatycznego pobierania później nie unieważnia niczego z tego ADR —
zmienia się tylko sposób, w jaki plik trafia na dysk.

### 4. Kolejność kroków aktualizacji

Rozpakowanie i sprawdzenie kompletności paczki dzieje się **przed**
zatrzymaniem programu. Zepsuta paczka ma się wyłożyć, zanim ktokolwiek przerwie
pracę. Dalej: zrzut bazy → zmiana nazwy → wstawienie nowej wersji → migracja.
Błąd migracji cofa katalogi automatycznie; **zrzutu bazy nie przywracamy sami** —
odtworzenie kasuje wszystko wprowadzone po zrzucie i jest decyzją człowieka.

### 5. Wyjątek od zasady „zero wywołań sieciowych"

`CLAUDE.md` i sekcja 8.1 koncepcji zakazują wychodzenia na zewnątrz. Zakaz
dotyczy **procesu aplikacji** i pozostaje w mocy bez zmian. Wyjmujemy spod niego
dwie rzeczy, obie uruchamiane świadomie i osobno od serwera:

| Co | Kiedy | Dokąd |
|---|---|---|
| `uv` w instalatorze | raz, przy zakładaniu | repozytorium Pythona i pakietów |
| kopia zapasowa | codziennie | katalog z `KATALOG_KOPII` (może być chmurowy) |

Sam aktualizator nie wychodzi nigdzie — dostaje plik z dysku.

## Konsekwencje

**Dobre.** Aktualizacja nie może skasować danych. Użytkownik nie potrzebuje
Node.js ani repozytorium. Cofnięcie wersji trwa sekundę. Wydanie jest opisane
w `WERSJA.txt` i w `dane\historia-wersji.txt`, więc wiadomo, co gdzie stoi.

**Kosztowne.** Skrypty w `instalator\` leżą poza katalogiem programu, bo zmieniają
jego nazwę — **nie aktualizują się same**. Ich poprawka wymaga ręcznej podmiany.
Dlatego mają być możliwie krótkie i rzadko ruszane.

**Nierozwiązane.** Migracja Alembica wykonana na danych użytkownika może wyłożyć
się na czymś, czego nie ma w danych testowych. Zrzut przed aktualizacją ogranicza
szkodę do przestoju, nie do zera. Prawdziwym zabezpieczeniem byłby zrzut jej bazy
u autora **przed** wydaniem migracji ruszającej istniejące dane — a to wymaga
zanonimizowanej kopii, której nie ma. Do rozstrzygnięcia, zanim powstanie
pierwsza migracja przepisująca dane, a nie tylko dokładająca kolumny.

## Odrzucone warianty

**Program na serwerze, użytkownik przez przeglądarkę.** Rozwiązywałby aktualizacje
i kopie zapasowe za jednym zamachem. Odpada: nie ma maszyny włączonej non stop,
a dokumenty leżą na lokalnym dysku.

**Kopia repozytorium u użytkownika i `git pull`.** Wymaga gita, poświadczeń
i katalogu roboczego, który da się rozjechać jednym `git checkout`. Zysk wyłącznie
po stronie autora.

**PyInstaller albo spakowany Python.** Jedna zależność (`uv`) instalowana raz
to mniejszy koszt niż utrzymywanie procesu budowania pliku wykonywalnego.

## Uzupełnienie z 28.08.2026: brak chmury po stronie użytkownika

Ustalone po fakcie: użytkowniczka **nie ma OneDrive** ani żadnego dysku
sieciowego. Celem kopii zapasowej zostaje dysk USB zostawiony na stałe w porcie
albo druga partycja. Oba warianty chronią przed awarią dysku i pomyłką, żaden
przed kradzieżą, pożarem ani ransomware — i tak trzeba to nazwać, zamiast
udawać, że kopia zapasowa jest zrobiona.

Konsekwencja techniczna: nie ma drugiego miejsca, w którym byłoby widać, że
kopie przestały się wykonywać. Zadanie z Harmonogramu chodzi w ukrytym oknie,
więc wyjęty pendrive zatrzymałby je bez śladu.

Dlatego `kopia-zapasowa.ps1` zapisuje wynik **każdej** próby do
`dane\stan-kopii.txt` — lokalnie, celowo nie w katalogu kopii, bo to właśnie
tam nie da się nic zapisać w chwili awarii. `uruchom.ps1` czyta ten plik przy
starcie i ostrzega, gdy ostatnia kopia się nie udała albo była dawniej niż
trzy dni temu. Start programu to jedyny moment, w którym człowiek na pewno
patrzy na ekran.

Niekompletny albo uszkodzony plik stanu daje komunikat „nie umiem odczytać",
a nie fałszywy alarm o awarii. Fałszywe ostrzeżenie powtarzane codziennie
przestaje być czytane po tygodniu, a wtedy prawdziwe też przepadnie.

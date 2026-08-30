# System Zarządzania Umowami Najmu

Wewnętrzna aplikacja do prowadzenia rejestru stanu umów najmu: kto, gdzie, na jakich
warunkach, do kiedy i co się wkrótce dzieje. Działa w całości lokalnie, bez internetu
i bez żadnych usług zewnętrznych.

- Koncepcja i model danych: [`docs/system-najem-koncepcja.md`](docs/system-najem-koncepcja.md)
- Plan budowy i etapy: [`docs/plan-budowy-claude-code.md`](docs/plan-budowy-claude-code.md)
- Stan prac i co dalej: [`docs/postep.md`](docs/postep.md)
- Pułapki i decyzje nie do cofnięcia: [`docs/pulapki.md`](docs/pulapki.md)
- Odstępstwa od planu: [`docs/decyzje/`](docs/decyzje/)

## Stan: etapy E0 – E8 ukończone

Program działa od kliknięcia skrótu po dane. Otwiera się od razu na liście
lokali: można je filtrować, wejść w profil lokalu i zobaczyć stan umowy na
dowolny dzień wstecz oraz listę terminów wymagających uwagi.

Waloryzacja roczna: wskaźnik wprowadza się **raz**, a system liczy propozycję
dla każdej umowy, która mu podlega, pokazuje wyłączenia z powodem i zapisuje
zatwierdzone zmiany w jednej transakcji. Dotąd była to praca na kilkanaście
godzin raz do roku.

| Warstwa | Stan |
|---|---|
| Baza | 16 tabel, 17 ograniczeń CHECK, 7 migracji |
| Reguły biznesowe | R1, R2, R4–R7, R9 — pokrycie testami 100% |
| API | 56 endpointów, bez logowania i ról, audyt każdej zmiany |
| Generator zdarzeń | codziennie o 6:00, idempotentny |
| Interfejs | dashboard, kartoteka, kokpit terminów, profil lokalu, dokumenty z dysku, import, waloryzacja |
| Dokumenty | typ rozpoznawany po zawartości, deduplikacja, hierarchia aneksów |

Kontrola: 630 testów backendu, 56 frontendu, `mypy` strict i `ruff` czysto.

**Od tego miejsca system zastępuje Excela.** Czego jeszcze nie ma: ekstrakcji
danych z umów (OCR), podglądu PDF w aplikacji, edycji i usuwania rekordów
z interfejsu. Kolejność prac: [`docs/postep.md`](docs/postep.md).

## Uruchomienie dla użytkownika

Dwa razy kliknąć **`Uruchom system najmu.cmd`** albo skrót **System Najmu** na pulpicie.

Otworzy się okno z postępem, a po chwili przeglądarka pod adresem `http://127.0.0.1:8010`.

Program zamyka się przez `Ctrl+C` w oknie — wtedy zatrzymuje też bazę danych.
Jeśli okno zostanie zamknięte krzyżykiem, baza może zostać uruchomiona w tle.
Nic złego się nie stanie (kolejny start ją rozpozna), ale można ją wyłączyć
klikając **`Zatrzymaj system.cmd`**.

Pierwsze uruchomienie pobiera bazę danych (około 350 MB) i trwa kilka minut.
Kolejne startują w kilka sekund.

**Program nie ma logowania.** Otwiera się od razu na liście lokali. Dostępu
pilnuje dostęp do komputera — powód i konsekwencje opisuje
[ADR 009](docs/decyzje/009-usuniecie-logowania.md).

Adres to `127.0.0.1:8010`, a nie `localhost:8010`. Skrót otwiera go poprawnie;
wpisanie `localhost` ręcznie może nie zadziałać (szczegóły w `docs/pulapki.md`).

Skrót na pulpicie zakłada się raz:

```
powershell -ExecutionPolicy Bypass -File narzedzia\utworz-skrot.ps1
```

## Instalacja od zera

Na komputerze muszą być dwa programy. Reszta pobiera się sama.

| Program | Do czego | Skąd |
|---|---|---|
| **uv** | uruchamia część serwerową (Python) | https://docs.astral.sh/uv/ |
| **Node.js 20+** | buduje interfejs | https://nodejs.org/ |

Potem wystarczy pobrać ten katalog i kliknąć `Uruchom system najmu.cmd`.

To jest instalacja **dla autora**. Osoba, która ma tylko używać programu,
dostaje paczkę wydania i nie potrzebuje ani Node.js, ani repozytorium.

## Instalacja u użytkownika

Program działa na jej komputerze, dane i dokumenty zostają u niej, a poprawki
wysyła się mailem jako plik. Szczegóły i odrzucone warianty:
[ADR 010](docs/decyzje/010-instalacja-u-uzytkownika-i-kanal-aktualizacji.md).

### Raz, przy zakładaniu

```powershell
powershell -File narzedzia\spakuj-wydanie.ps1 -Pelna    # ~310 MB, z bazą w środku
```

Paczkę rozpakowuje się na jej komputerze do `C:\SystemNajmu` i klika
`Zainstaluj.cmd`. Instalator zakłada katalog na dane, konfigurację, bazę, skrót
na pulpicie i codzienną kopię zapasową. Pyta o jedną rzecz: **dokąd mają trafiać
kopie zapasowe**.

Jedyne, co trzeba doinstalować osobno, to [uv](https://docs.astral.sh/uv/).
Instalacja wymaga internetu (uv pobiera Pythona i biblioteki); codzienna praca
programu już nie.

### Przy każdej poprawce

```powershell
powershell -File narzedzia\spakuj-wydanie.ps1           # kilka MB, do maila
```

Ona przeciąga przysłany plik na `Aktualizuj.cmd`. Aktualizator sprawdza paczkę,
robi zrzut bazy, podmienia program i uruchamia migracje. Gdy coś pójdzie nie tak,
sam wraca do poprzedniej wersji. `Cofnij aktualizacje.cmd` robi to samo na
żądanie.

**Ustawienia i dane przeżywają aktualizację** — katalog skanu, sparowane foldery
i cała zawartość bazy leżą poza katalogiem programu i aktualizator ich nie dotyka.

### Kiedy coś nie działa

`Diagnostyka.cmd` składa na pulpicie plik z wersją, stanem bazy i logami —
bez nazw najemców, kwot i treści dokumentów. Ona wysyła go mailem.

## Praca deweloperska

```bash
# baza danych
powershell -File narzedzia/lokalny-postgres.ps1 setup    # raz, pierwsze uruchomienie
powershell -File narzedzia/lokalny-postgres.ps1 start
powershell -File narzedzia/lokalny-postgres.ps1 status
powershell -File narzedzia/lokalny-postgres.ps1 psql
powershell -File narzedzia/lokalny-postgres.ps1 stop

# backend, port 8010
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn najem.main:app --reload --port 8010
uv run pytest
uv run mypy
uv run ruff check . && uv run ruff format .

# frontend, port 5180 z proxy /api na 8010
cd frontend
npm install
npm run dev
npm test
npm run build
```

Dokumentacja API: `http://127.0.0.1:8010/api/docs`.

## Konfiguracja

Wszystko przez zmienne środowiskowe. Wzór w [`.env.example`](.env.example) —
skopiuj do `.env`, jeśli chcesz zmienić domyślne wartości. Plik `.env`
nigdy nie trafia do repozytorium.

## Kopia zapasowa

```powershell
powershell -File narzedzia\kopia-zapasowa.ps1        # ręcznie, tu i teraz
powershell -File narzedzia\zaplanuj-kopie.ps1        # codziennie o 12:30
```

Kopiowane są **trzy** rzeczy, nie dwie: zrzut bazy (`pg_dump -F c`), katalog
`dane/dokumenty/` i katalog z dokumentami na dysku użytkownika. Ten trzeci jest
konieczny, bo dokumenty wskazane na dysku nie są kopiowane do programu, tylko
linkowane ([ADR 008](docs/decyzje/008-dokumenty-linkowane-nie-kopiowane.md)) —
sama kopia bazy zostawiłaby ścieżki do plików, których już nie ma.

Cel wskazuje `KATALOG_KOPII` w `.env`. Pusty = skrypt kończy się **błędem**,
a nie ciszą: kopia, o której nikt nie wie, że się nie robi, jest gorsza niż jej
brak. Instalacja u użytkownika pyta o ten katalog i zakłada zadanie w
Harmonogramie Windows.

**Bez chmury nie ma drugiego miejsca, w którym awarię widać.** Zadanie chodzi
w ukrytym oknie, więc wyjęty pendrive albo zmieniona litera dysku zatrzymałyby
kopie po cichu. Dlatego każda próba zapisuje wynik do `dane/stan-kopii.txt`
(lokalnie, bo to jedyne miejsce zapisywalne, gdy dysku kopii nie ma),
a `uruchom.ps1` przy starcie programu mówi wprost, jeśli ostatnia kopia się nie
udała albo była dawniej niż trzy dni temu. Start programu to jedyny moment,
w którym użytkownik na pewno patrzy na ekran.

Kopia, której nikt nie odtworzył, nie istnieje — zrzut sprawdza się przez
`pg_restore --list nazwa.dump`.

## Struktura

```
backend/          FastAPI, SQLAlchemy 2.0, Alembic
  src/najem/
    domena/       czysta logika biznesowa: zero bazy, zero HTTP, zero I/O
    modele/       SQLAlchemy
    schematy/     Pydantic, wejście i wyjście API
    repozytoria/  dostęp do danych
    uslugi/       przypadki użycia
    api/v1/       endpointy
  tests/domena/   tu jest najwięcej testów i tak ma zostać
frontend/         Vite, React, TypeScript, Tailwind, TanStack
narzedzia/        skrypty uruchomieniowe, pakowanie wydań, kopia zapasowa
instalator/       zakładanie i aktualizacja instalacji u użytkownika
docs/             koncepcja, plan, decyzje, stan prac
tools/, pgdata/   binaria i dane PostgreSQL (poza repozytorium)
wydania/          złożone paczki (poza repozytorium)
```

Najważniejsza granica w tej strukturze: `domena/` nie importuje SQLAlchemy,
FastAPI ani niczego, co dotyka sieci lub dysku. Pilnuje tego test
`backend/tests/domena/test_granice_warstw.py`.

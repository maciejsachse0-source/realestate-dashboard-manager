# System Zarządzania Umowami Najmu

Wewnętrzna aplikacja do prowadzenia rejestru stanu umów najmu: kto, gdzie, na jakich
warunkach, do kiedy i co się wkrótce dzieje. Działa w całości lokalnie, bez internetu
i bez żadnych usług zewnętrznych.

- Koncepcja i model danych: [`docs/system-najem-koncepcja.md`](docs/system-najem-koncepcja.md)
- Plan budowy i etapy: [`docs/plan-budowy-claude-code.md`](docs/plan-budowy-claude-code.md)
- Stan prac i co dalej: [`docs/postep.md`](docs/postep.md)
- Pułapki i decyzje nie do cofnięcia: [`docs/pulapki.md`](docs/pulapki.md)
- Odstępstwa od planu: [`docs/decyzje/`](docs/decyzje/)

## Stan: etapy E0 – E6 ukończone

Program działa od kliknięcia skrótu po dane. Można się zalogować, przeglądać
lokale, filtrować je, wejść w profil lokalu i zobaczyć stan umowy na dowolny
dzień wstecz oraz listę terminów wymagających uwagi.

| Warstwa | Stan |
|---|---|
| Baza | 14 tabel, 16 ograniczeń CHECK, 3 migracje |
| Reguły biznesowe | R1, R2, R4–R7, R9 — pokrycie testami 100% |
| API | 40 endpointów, cztery role, audyt każdej zmiany |
| Generator zdarzeń | codziennie o 6:00, idempotentny |
| Interfejs | logowanie, dashboard, kartoteka, kokpit terminów, profil lokalu |

Kontrola: 385 testów backendu, 8 frontendu, `mypy` strict i `ruff` czysto.

**Czego jeszcze nie ma:** dokumentów, importu z Excela, ekranu waloryzacji
i ekstrakcji z umów. Kolejność prac: [`docs/postep.md`](docs/postep.md).

## Uruchomienie dla użytkownika

Dwa razy kliknąć **`Uruchom system najmu.cmd`** albo skrót **System Najmu** na pulpicie.

Otworzy się okno z postępem, a po chwili przeglądarka pod adresem `http://127.0.0.1:8010`.

Program zamyka się przez `Ctrl+C` w oknie — wtedy zatrzymuje też bazę danych.
Jeśli okno zostanie zamknięte krzyżykiem, baza może zostać uruchomiona w tle.
Nic złego się nie stanie (kolejny start ją rozpozna), ale można ją wyłączyć
klikając **`Zatrzymaj system.cmd`**.

Pierwsze uruchomienie pobiera bazę danych (około 350 MB) i trwa kilka minut.
Kolejne startują w kilka sekund.

**Przy pierwszym starcie** program zakłada konto `administrator` i pokazuje
losowe hasło **raz**, w oknie startowym. Zapisz je — komunikat nie wróci.
Program poprosi o zmianę hasła przy pierwszym logowaniu.

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

Do zrobienia w etapie E12. Kopiowane muszą być dwie rzeczy: baza (`pg_dump`)
i katalog `dane/dokumenty/`. Kopia, której nikt nie odtworzył, nie istnieje.

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
narzedzia/        skrypty uruchomieniowe i hooki
docs/             koncepcja, plan, decyzje, stan prac
tools/, pgdata/   binaria i dane PostgreSQL (poza repozytorium)
```

Najważniejsza granica w tej strukturze: `domena/` nie importuje SQLAlchemy,
FastAPI ani niczego, co dotyka sieci lub dysku. Pilnuje tego test
`backend/tests/domena/test_granice_warstw.py`.

# System Zarządzania Umowami Najmu

Wewnętrzna aplikacja on-prem. Rejestr stanu umów najmu z ekstrakcją danych
z dokumentów. Nie jest to projekt "AI czyta umowy" — AI to jeden z kanałów
zasilania danymi, wchodzi dopiero w etapie E9.

Pełna koncepcja (model danych, reguły R1–R9, katalog zdarzeń, mapa ekranów):
@docs/system-najem-koncepcja.md
Plan budowy z etapami i definicjami ukończenia: `docs/plan-budowy-claude-code.md`
(czytaj na żądanie, nie jest importowany — jest długi).

## Komendy

- Cały program (dla użytkownika): `Uruchom system najmu.cmd` albo skrót na pulpicie
- Zatrzymanie: `Zatrzymaj system.cmd` (program **i** baza).
  Sam program: `powershell -File narzedzia/zatrzymaj.ps1 -TylkoAplikacja`
- Baza: `powershell -File narzedzia/lokalny-postgres.ps1 start|stop|status|psql`
- Backend dev: `cd backend && uv run uvicorn najem.main:app --reload --port 8010`
- Testy backend: `cd backend && uv run pytest`
- Lint + format: `cd backend && uv run ruff check --fix . && uv run ruff format .`
- Typy: `cd backend && uv run mypy`
- Migracja: `cd backend && uv run alembic revision --autogenerate -m "opis"`
- Frontend dev: `cd frontend && npm run dev` (port 5180, proxy /api na 8010)
- Testy frontend: `cd frontend && npm test`
- Paczka wydania: `powershell -File narzedzia/spakuj-wydanie.ps1` (aktualizacja,
  ~0,4 MB) albo z `-Pelna` (pierwsza instalacja, ~310 MB)
- Kopia zapasowa: `powershell -File narzedzia/kopia-zapasowa.ps1`

Skrót sam przebudowuje interfejs, gdy cokolwiek w `frontend/src` jest nowsze
niż `frontend/dist/index.html`. Wymuszenie: `narzedzia/uruchom.ps1 -PrzebudujInterfejs`.

## Zasady architektury

- `backend/src/najem/domena/` to czysty Python. Zero SQLAlchemy, zero FastAPI,
  zero I/O, zero `datetime.now()` w środku funkcji (datę przekazuj argumentem).
  Każda reguła biznesowa mieszka tutaj i ma test jednostkowy.
  Pilnuje tego automatycznie `tests/domena/test_granice_warstw.py`.
- Warstwy: `api` → `uslugi` → `repozytoria` → `modele`. Nigdy w drugą stronę.
- Frontend nie liczy niczego na pieniądzach. Wszystkie wyliczenia po stronie API.
- Formatowanie w interfejsie tylko przez `frontend/src/funkcje/format.ts`.
- Ścieżki do bazy, katalogu danych, `.env` i **środowiska Pythona** bierz
  z `narzedzia/sciezki.ps1` (PowerShell) i ze zmiennej `NAJEM_PLIK_ENV` (Python).
  U użytkownika program i dane leżą w rozłącznych katalogach, żeby aktualizacja
  „podmień katalog" nie kasowała bazy
  ([ADR 010](docs/decyzje/010-instalacja-u-uzytkownika-i-kanal-aktualizacji.md)).
  Nieustawione `NAJEM_KATALOG_INSTALACJI` = dzisiejsze ścieżki repozytorium.
  **Jedyny wyjątek:** skrypty w `instalator/` liczą ścieżki same, bo zmieniają
  nazwę katalogu `program`, w którym `sciezki.ps1` leży. Mają własny
  `instalator/wspolne.ps1` i nie wolno im dołączać niczego z `program\`.
- Każdy skrypt wołający `uv run` u użytkownika ustawia `UV_PROJECT_ENVIRONMENT`
  na `Katalog-Srodowiska` (instalator liczy tę ścieżkę sam). Domyślne miejsce
  `uv` to `program\backend\.venv`, czyli katalog kasowany przy aktualizacji —
  bez tego program buduje środowisko od nowa przy każdym starcie po wydaniu
  i wymaga do tego internetu. Kosztowało to już jeden przeoczony błąd.
- Konfiguracja bez wartości (`KLUCZ=` w `.env`) ma dawać `None`, nie wartość
  pozorną. `Path("")` to `Path(".")`, czyli istniejący katalog roboczy — pusty
  `KATALOG_SKANU` pokazywał użytkownikowi wnętrze programu jako jego budynki.
  Nowe pole `Path | None` czytane z `.env` potrzebuje walidatora, sam typ nie
  wystarcza.
- Zbudowany interfejs serwuje `InterfejsSPA` w `main.py`. Nieznany adres ekranu
  dostaje `index.html` (bez tego odświeżenie podstrony daje 404), a `index.html`
  idzie z `Cache-Control: no-cache`. Nie zamieniaj tego na zwykłe `StaticFiles` —
  jedno i drugie kosztowało już godzinę szukania „dlaczego nie widać zmian".

## Zasady twarde

- Pieniądze: `Decimal` w Pythonie, `NUMERIC(12,2)` w bazie. Nigdy `float`.
  Zaokrąglanie tylko przez `domena/pieniadze.py`, `ROUND_HALF_UP`.
- Każda kwota ma jawnie: netto czy brutto, stawkę VAT i walutę.
- Daty biznesowe: `date`. Znaczniki techniczne: `datetime` w UTC (`TIMESTAMPTZ`).
  Konwersja na Europe/Warsaw dopiero w warstwie prezentacji.
- Nic nie usuwamy fizycznie. Soft delete (`usunieto_dnia`) plus wpis
  w `audit_log`, który jest tylko do zapisu.
- Program **nie ma logowania ani pojęcia użytkownika** ([ADR 009](docs/decyzje/009-usuniecie-logowania.md)).
  Nie ma sesji, ról ani kolumn z autorem operacji. Audyt zapisuje co, kiedy
  i z jakiej wartości na jaką — nie kto. Nie dodawaj sprawdzeń uprawnień.
- Każda zmiana modelu = migracja Alembic w tym samym commicie.
- Parametry umowy nie są nadpisywane, tylko wersjonowane w czasie
  (tabela `parametr_wartosc`, pola `obowiazuje_od` / `obowiazuje_do`).
  To decyzja D2 z koncepcji i najważniejsza decyzja w całym projekcie.
- Wartość niezatwierdzona przez człowieka nie wchodzi do alertów ani raportów
  (decyzja D4). Ekstrakcja proponuje, nie decyduje.
- Brak danych to informacja, nie pusta komórka (decyzja D5). Nigdy nie podstawiaj
  zera ani wartości domyślnej za brakującą daną.
- Dokument wczytany z dysku (`przechowywanie = link`) **nie jest kopiowany**.
  W bazie leży ścieżka względna wobec katalogu skanu, SHA-256 i rozmiar.
  Sam katalog ustawia się na ekranie „Dokumenty z dysku" (tabela
  `ustawienie_systemu`); `KATALOG_SKANU` z `.env` jest tylko wartością
  zapasową, gdy w bazie nic nie ma. Baza wygrywa z plikiem.
  Skutek operacyjny: kopia zapasowa musi obejmować bazę **razem** z tym
  katalogiem. Decyzja i odrzucone warianty: `docs/decyzje/008-dokumenty-linkowane-nie-kopiowane.md`.
- Oznaczeń lokali nie parsujemy z nazw folderów. Są nieregularne, a cicha
  pomyłka przypina dokument do nie tej umowy. Folder paruje z umową człowiek,
  raz, a system pamięta to w `powiazanie_folderu`. To decyzja D5 w praktyce.
- Nazwy tabel, kolumn i pól domenowych po polsku. Nazwy techniczne po angielsku.
  Komentarze i komunikaty użytkownika po polsku.
- Zero wywołań sieciowych do zewnętrznych usług, w szczególności do API modeli AI.
  To wymóg bezpieczeństwa z sekcji 8 koncepcji, nie preferencja.
- Nie dodawaj nowych zależności bez pytania. Jeśli uważasz, że biblioteka jest
  potrzebna, napisz dlaczego i poczekaj na zgodę.

## Testy

- Nowa reguła biznesowa: najpierw test, potem implementacja.
- Przypadki brzegowe obowiązkowo: brak danych, granica miesiąca i roku,
  rok przestępny, kwoty z groszami.
- **Nazwy plików i teksty w testach po polsku, ze znakami diakrytycznymi.**
  Testy z nazwami typu `umowa.pdf` przepuściły błąd, przez który żaden
  dokument z „ł" albo „ą" w nazwie nie dawał się pobrać — a w archiwum
  użytkownika takie są prawie wszystkie. To nie jest przypadek brzegowy.
- Wzorzec ekstrakcji sprawdzony wyłącznie na wymyślonym tekście jest sprawdzony
  pozornie. Zanim uznasz go za gotowy, puść go na prawdziwym pliku
  (`narzedzia/sprawdz-dokumenty.py` mówi, na czym w ogóle da się to zrobić).
- Nie oznaczaj etapu jako gotowego, dopóki `pytest`, `mypy` i `npm test`
  nie przechodzą. Pokaż wynik, nie streszczaj go.
- Przed wydaniem paczki: instalacja od zera w osobnym katalogu **i uruchomienie
  z niej programu**. Sama instalacja nie wystarcza — trzy błędy blokujące
  wysyłkę siedziały dopiero w starcie programu i w pierwszym ekranie.

## Czego nie robić

- Nie refaktoruj kodu, o który nie pytałem.
- Nie twórz warstw abstrakcji "na przyszłość".
- Nie dodawaj README ani docstringów do wszystkiego "przy okazji".
- Nie pracuj na produkcyjnych danych w środowisku deweloperskim.

## Stan projektu

Aktualny etap i następne kroki: @docs/postep.md

Zebrane pułapki i decyzje, które wyglądają na przeoczenie, a są zamierzone:
`docs/pulapki.md`. Nie jest importowany celowo — przeczytaj go, kiedy dotykasz
opisanego miejsca albo kiedy coś zachowuje się dziwnie.

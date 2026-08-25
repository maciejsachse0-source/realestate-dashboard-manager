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
- Baza: `powershell -File narzedzia/lokalny-postgres.ps1 start|stop|status|psql`
- Backend dev: `cd backend && uv run uvicorn najem.main:app --reload --port 8010`
- Testy backend: `cd backend && uv run pytest`
- Lint + format: `cd backend && uv run ruff check --fix . && uv run ruff format .`
- Typy: `cd backend && uv run mypy`
- Migracja: `cd backend && uv run alembic revision --autogenerate -m "opis"`
- Frontend dev: `cd frontend && npm run dev` (port 5180, proxy /api na 8010)
- Testy frontend: `cd frontend && npm test`

## Zasady architektury

- `backend/src/najem/domena/` to czysty Python. Zero SQLAlchemy, zero FastAPI,
  zero I/O, zero `datetime.now()` w środku funkcji (datę przekazuj argumentem).
  Każda reguła biznesowa mieszka tutaj i ma test jednostkowy.
  Pilnuje tego automatycznie `tests/domena/test_granice_warstw.py`.
- Warstwy: `api` → `uslugi` → `repozytoria` → `modele`. Nigdy w drugą stronę.
- Frontend nie liczy niczego na pieniądzach. Wszystkie wyliczenia po stronie API.
- Formatowanie w interfejsie tylko przez `frontend/src/funkcje/format.ts`.

## Zasady twarde

- Pieniądze: `Decimal` w Pythonie, `NUMERIC(12,2)` w bazie. Nigdy `float`.
  Zaokrąglanie tylko przez `domena/pieniadze.py`, `ROUND_HALF_UP`.
- Każda kwota ma jawnie: netto czy brutto, stawkę VAT i walutę.
- Daty biznesowe: `date`. Znaczniki techniczne: `datetime` w UTC (`TIMESTAMPTZ`).
  Konwersja na Europe/Warsaw dopiero w warstwie prezentacji.
- Nic nie usuwamy fizycznie. Soft delete (`usunieto_dnia`, `usunal_uzytkownik_id`)
  plus wpis w `audit_log`, który jest tylko do zapisu.
- Każda zmiana modelu = migracja Alembic w tym samym commicie.
- Parametry umowy nie są nadpisywane, tylko wersjonowane w czasie
  (tabela `parametr_wartosc`, pola `obowiazuje_od` / `obowiazuje_do`).
  To decyzja D2 z koncepcji i najważniejsza decyzja w całym projekcie.
- Wartość niezatwierdzona przez człowieka nie wchodzi do alertów ani raportów
  (decyzja D4). Ekstrakcja proponuje, nie decyduje.
- Brak danych to informacja, nie pusta komórka (decyzja D5). Nigdy nie podstawiaj
  zera ani wartości domyślnej za brakującą daną.
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
- Nie oznaczaj etapu jako gotowego, dopóki `pytest`, `mypy` i `npm test`
  nie przechodzą. Pokaż wynik, nie streszczaj go.

## Czego nie robić

- Nie refaktoruj kodu, o który nie pytałem.
- Nie twórz warstw abstrakcji "na przyszłość".
- Nie dodawaj README ani docstringów do wszystkiego "przy okazji".
- Nie pracuj na produkcyjnych danych w środowisku deweloperskim.

## Stan projektu

Aktualny etap i następne kroki: @docs/postep.md

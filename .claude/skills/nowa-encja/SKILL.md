---
name: nowa-encja
description: Dodaje encję: model, migrację, schematy, repozytorium i testy
argument-hint: [nazwa-encji]
disable-model-invocation: true
---

Dodaj encję: $ARGUMENTS

1. Sprawdź opis encji w `docs/system-najem-koncepcja.md`, sekcja 3.2.
   Jeśli encji tam nie ma, zapytaj, zanim cokolwiek napiszesz.
2. Model SQLAlchemy w `backend/src/najem/modele/`, styl 2.0
   (`Mapped`, `mapped_column`). Obowiązkowo:
   - kwoty jako `Numeric(12, 2)`, nigdy `Float`,
   - daty biznesowe `Date`, znaczniki techniczne `DateTime(timezone=True)`,
   - `usunieto_dnia` i `usunal_uzytkownik_id` — soft delete,
   - `wersja` jako `mapped_column(..., nullable=False, default=1)`
     plus `__mapper_args__ = {"version_id_col": wersja}` — optimistic locking,
   - `utworzono` i `zmodyfikowano` w UTC.
3. Migracja: `uv run alembic revision --autogenerate -m "opis"`.
   POKAŻ mi wygenerowany plik i poczekaj na akceptację, zanim pójdziesz dalej.
   Sprawdź, czy nie ma niezamierzonego `DROP`.
4. Schematy Pydantic w `schematy/`: osobno wejście i wyjście.
   Wyjście nigdy nie zwraca modelu SQLAlchemy.
5. Repozytorium w `repozytoria/`: zapytania filtrują `usunieto_dnia IS NULL`
   domyślnie. Metody listujące mają paginację.
6. Testy: tworzenie, unikalność, kaskady, działanie soft delete,
   konflikt wersji przy równoległej edycji.
7. Uruchom `pytest`, `mypy`, `ruff`. Pokaż wynik.

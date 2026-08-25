---
name: przeglad-etapu
description: Przegląd i domknięcie etapu przed commitem i przed nową sesją
disable-model-invocation: true
---

Domknij bieżący etap.

1. `git status` i `git diff` na całości zmian. Przeczytaj je, nie streszczaj.
2. Uruchom i pokaż wyniki:
   - `cd backend && uv run pytest`
   - `cd backend && uv run mypy`
   - `cd backend && uv run ruff check . && uv run ruff format --check .`
   - `cd frontend && npm test && npm run build`
3. Sprawdź, czy w zmianach nie ma: `TODO`, `FIXME`, zakomentowanego kodu,
   `print()`, `console.log`, sekretów, `float` przy kwotach,
   `datetime.now()` wewnątrz `domena/`.
4. Sprawdź, czy zmiany modeli mają odpowiadającą migrację Alembic
   i czy `downgrade` działa.
5. Uruchom podagenta `recenzent` na zmianach z tego etapu i obsłuż znaleziska.
6. Zaproponuj commit z opisem po polsku, w trybie rozkazującym.
7. Zaktualizuj `docs/postep.md`: co zrobione, co następne, co jest kruche
   i czego nie ruszać. Kilkanaście linii, nie więcej.
8. Wypisz to, czego NIE udało się zrobić, i dlaczego. Bez upiększania.

---
paths:
  - "backend/**/*.py"
---
# Reguły backendu

- FastAPI: endpointy zwracają schematy Pydantic, nigdy modeli SQLAlchemy.
- Zależności wstrzykuj przez `Annotated[...]`, nie przez wartość domyślną argumentu
  (`s: SesjaBazy`, nie `s: Session = Depends(sesja)`).
- Zapytania z `selectinload`, żeby nie robić N+1.
- Każdy endpoint listujący ma paginację: limit domyślnie 50, maksymalnie 500.
- Wyjątki domenowe (`BladDomenowy`) mapowane na kody HTTP w jednym handlerze,
  nie w każdym endpoincie osobno.
- Endpointy pod `/api/v1/`.
- Optimistic locking: konflikt wersji zwraca 409 z aktualnym stanem zasobu.
- Każda zmiana danych zapisuje wpis w `audit_log`. Bez wyjątków, także dla
  zmian ręcznych.

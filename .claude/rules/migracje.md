---
paths:
  - "backend/alembic/**"
---
# Migracje

- Zawsze `--autogenerate`, ale ZAWSZE przejrzyj wygenerowany plik przed commitem.
  Autogenerate potrafi zaproponować `DROP COLUMN`.
- Każda migracja ma działający `downgrade`. Jeśli nie da się cofnąć, napisz to
  w docstringu migracji i wyjaśnij dlaczego.
- Migracja zmieniająca dane, a nie tylko schemat, ma osobny test.
- Nie edytuj migracji, która trafiła na główną gałąź. Dopisz nową.
- Numeracja plików: `NNN_krotki_opis.py`, rosnąco.
- Jedna głowa Alembica. Jeśli powstały dwie, scal je od razu, a nie później.

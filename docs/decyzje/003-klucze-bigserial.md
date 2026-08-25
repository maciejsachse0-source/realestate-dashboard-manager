# ADR 003: Klucze główne jako BIGSERIAL, nie UUID v7

**Data:** 25.08.2026
**Status:** przyjęte
**Dotyczy:** `docs/plan-budowy-claude-code.md`, sekcja 2.2

## Kontekst

Plan dopuszcza dwie opcje i wymaga wybrania jednej: UUID v7 albo `BIGSERIAL`.

## Decyzja

`BIGSERIAL` (`BigInteger` z autoinkrementacją) we wszystkich tabelach.

## Uzasadnienie

- Jedna baza, jedno miejsce zapisu. UUID rozwiązuje problem generowania kluczy
  w rozproszonych zapisach, którego tutaj nie ma.
- Indeksy na liczbach 8-bajtowych są mniejsze i szybsze od 16-bajtowych UUID,
  a `parametr_wartosc` będzie największą tabelą w systemie i to po niej idzie
  najczęstsze zapytanie (stan efektywny na dzień).
- Przy zgłaszaniu problemów „lokal 412" jest wypowiadalne, `a3f1c9...` nie jest.
- Aplikacja jest wewnętrzna, za logowaniem, w sieci firmowej. Ryzyko zgadywania
  identyfikatorów przez URL nie występuje w istotnym stopniu.

## Konsekwencje

- Identyfikatory są sekwencyjne i pozwalają wnioskować o liczbie rekordów.
  Akceptowalne w systemie wewnętrznym.
- Gdyby kiedyś pojawiła się synchronizacja między instancjami, potrzebny będzie
  osobny klucz naturalny albo migracja. Na dziś nie ma takiego wymagania.

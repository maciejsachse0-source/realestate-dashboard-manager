---
name: nowa-regula
description: Dodaje nową regułę biznesową do warstwy domenowej wraz z testami
argument-hint: [nazwa-reguly]
disable-model-invocation: true
---

Dodaj regułę biznesową: $ARGUMENTS

Kolejność jest obowiązkowa. Nie skracaj jej, nawet jeśli reguła wygląda prosto —
reguły w tym projekcie nie są proste, tylko tak wyglądają.

1. Sprawdź, czy reguła jest opisana w `docs/system-najem-koncepcja.md`, sekcja 5.
   Jeśli tak, pracuj na tym opisie. Jeśli nie, dopytaj o przypadki brzegowe.
   Nie zgaduj.
2. Napisz testy w `backend/tests/domena/` PRZED implementacją. Uwzględnij:
   - przypadek typowy,
   - brak danych wejściowych — musi zwrócić stan „nieustalone", nie wyjątek
     i nie wartość domyślną (decyzja D5),
   - granicę miesiąca i roku,
   - rok przestępny, jeśli reguła dotyczy dat,
   - kwoty z groszami i zaokrąglanie, jeśli reguła dotyczy pieniędzy,
   - wartość niezatwierdzoną, jeśli reguła czyta `parametr_wartosc`
     — taka wartość nie wchodzi do wyniku (decyzja D4).
3. Uruchom testy i upewnij się, że są czerwone z właściwego powodu.
4. Zaimplementuj w `backend/src/najem/domena/reguly/`. Czysta funkcja:
   bez dostępu do bazy, bez `datetime.now()` w środku (datę podaj argumentem),
   wejście to dataclass albo dict, wyjście to struktura ze składnikami wyniku,
   a nie sama liczba.
5. Uruchom `uv run pytest` i `uv run mypy`. Pokaż wynik.
6. Dopisz regułę do tabeli w `docs/system-najem-koncepcja.md`, sekcja 5,
   jeśli jej tam jeszcze nie ma.
7. Podsumuj: co robi reguła, jakie przypadki brzegowe są pokryte i czego
   świadomie nie obsłużyłeś.

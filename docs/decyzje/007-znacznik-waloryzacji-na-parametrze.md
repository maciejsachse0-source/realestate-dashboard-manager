# ADR 007: Znacznik waloryzacji na wierszu parametru

**Data:** 25.08.2026
**Status:** przyjęte
**Dotyczy:** etap E8, reguła R2, decyzja D2

## Kontekst

Pierwsza wersja E8 rozpoznawała własne poprzednie przebiegi **po dacie
wejścia**: jeśli dla umowy istniał już czynsz obowiązujący od 1 stycznia,
system uznawał, że waloryzacja tego roku już się odbyła.

Przegląd kodu pokazał, że to rozpoznanie myli trzy różne rzeczy:

1. **Aneks wchodzący w tym samym dniu.** Umowa z aneksem podnoszącym czynsz
   z 9 500 zł na 12 000 zł od 1 stycznia trafiała do eksportu jako
   waloryzacja z wyliczonym wskaźnikiem **26,32%**. Taki wskaźnik nigdy nie
   istniał, a arkusz służy do pisania pism do najemców.
2. **Niezatwierdzoną propozycję czynszu.** Wiersz o statusie `zaproponowana`
   — którego `stan_efektywny` w ogóle nie widzi — wykluczał umowę z przebiegu
   komunikatem „ta umowa była już w tym roku waloryzowana". Nieprawdziwym.
   To łamało decyzję D4 w drugą stronę: wartość niezatwierdzona wpływała
   na wynik wyliczenia.
3. **Pierwotny czynsz umowy zaczynający się 1 stycznia.** Umowa, której
   pierwsza wersja czynszu wchodziła dokładnie w dniu waloryzacji, była
   pomijana na zawsze.

Wszystkie trzy przypadki są ciche: umowa wypada z listy, czynsz zostaje płaski
przez rok, a ekran podaje wiarygodnie brzmiący powód.

## Decyzja

`parametr_wartosc` dostaje dwie kolumny (migracja `004_slad_waloryzacji`):

- `waloryzacja_rok` — rok przebiegu, który utworzył ten wiersz,
- `waloryzacja_wskaznik_procent` — zastosowany wskaźnik.

Oba są `NULL` dla każdego innego źródła: aneksu, wpisu ręcznego, importu
z arkusza, przyszłej ekstrakcji. Ograniczenie `CHECK` wymaga, żeby były
wypełnione razem albo wcale.

Wykrywanie powtórzonego przebiegu pyta o `waloryzacja_rok`, a eksport zmian
czyta zapisany wskaźnik zamiast odtwarzać go z pary kwot.

## Uzasadnienie

Data wejścia jest **właściwością zmiany**, nie jej **pochodzeniem**. Dwie
różne rzeczy — aneks i waloryzacja — mogą mieć tę samą datę i identyczny
kształt wiersza. Żadna heurystyka po dacie tego nie rozróżni, bo informacji
o pochodzeniu po prostu nie ma w danych.

Wskaźnik zapisujemy, zamiast liczyć go z ilorazu kwot, bo iloraz jest równy
wskaźnikowi tylko wtedy, gdy zmiana faktycznie była waloryzacją. W każdym
innym przypadku daje liczbę, która wygląda na wskaźnik GUS i nią nie jest.
Z pisma do najemcy ma wynikać ten procent, który zastosowano.

## Konsekwencje

- Wiersze sprzed migracji **nie są oznaczane**. Nie da się z dołu ustalić,
  które powstały z waloryzacji, a zgadywanie po dacie jest dokładnie tym
  błędem, który ta kolumna usuwa. Skutek: eksport za lata sprzed wdrożenia
  E8 pokaże pusty arkusz zmian zatwierdzonych.
- Umowa zwaloryzowana ręcznie (przez wpisanie nowego czynszu w profilu)
  nie ma znacznika, więc przebieg zaproponuje ją ponownie. To zachowanie
  zamierzone: system nie zgaduje, co człowiek miał na myśli, tylko pokazuje
  propozycję do odznaczenia.
- Rozpoznawanie po dacie zostało usunięte razem z opisującą je pułapką
  w `docs/pulapki.md`.

## Odrzucone warianty

**Filtrowanie po `status_weryfikacji` bez nowej kolumny.** Naprawiało punkt 2,
ale nie 1 i nie 3. Zatwierdzony aneks nadal wyglądałby jak waloryzacja.

**Rozpoznawanie po treści pola `uwagi`** (wiersze z waloryzacji dostają opis
„Waloryzacja {rok}: …"). Wolny tekst jako klucz logiki biznesowej psuje się
przy pierwszej zmianie brzmienia komunikatu i nie da się go objąć
ograniczeniem w bazie.

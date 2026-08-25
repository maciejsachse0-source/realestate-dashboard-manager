# ADR 004: Kwoty składników opłat żyją w `parametr_wartosc`, nie w `skladnik_oplaty`

**Data:** 25.08.2026
**Status:** przyjęte
**Dotyczy:** `docs/system-najem-koncepcja.md`, decyzja D2 kontra szkic encji w sekcji 3.2

## Kontekst

Sekcja 3.2 koncepcji wymienia `kwota` jako pole encji `SKLADNIK_OPLATY`.
Decyzja D2 z tej samej koncepcji mówi natomiast wprost: *„Nie ma pola
`stawka_za_m2` w tabeli umowy. Jest tabela wartości parametrów"*, i nazywa to
najważniejszą decyzją w całym projekcie.

Te dwa zapisy są ze sobą sprzeczne. Kwota w kolumnie zostałaby nadpisana przez
aneks, co niszczy odpowiedź na pytanie „jaka była stawka w maju 2025".

## Decyzja

`skladnik_oplaty` nie ma kolumny z kwotą. Ma pole `klucz_parametru`, które
wskazuje wpisy w `parametr_wartosc` niosące kwoty tego składnika w czasie.

Tabela odpowiada więc na pytania **co** jest płatne i **kiedy** (dzień płatności,
okres rozliczeniowy, czy podlega waloryzacji), a **ile** mówi parametr.

## Uzasadnienie

Rozstrzygamy sprzeczność na korzyść D2, bo to decyzja świadoma i uzasadniona,
a wzmianka w 3.2 jest skrótem w szkicu encji. Kwota w kolumnie oznaczałaby, że
mechanizm wersjonowania obowiązuje wszędzie poza tym jednym miejscem, w którym
najbardziej go potrzeba.

## Wyjątek: zabezpieczenia

`zabezpieczenie.wymagana_wartosc` **jest** kolumną. Powód: to wartość pochodna,
wyliczana z reguły R5 („czterokrotność czynszu") i przeliczana po każdej
waloryzacji, a nie wartość wyekstrahowana z dokumentu. Wersjonowanie dotyczy
parametrów odczytanych z umowy. Ślad zmian wartości zabezpieczenia zostaje
w `log_audytu`.

## Konsekwencje

- Odczyt kwoty składnika wymaga złączenia z `parametr_wartosc` i wyliczenia
  stanu efektywnego. Wspiera to indeks `ix_parametr_stan_efektywny`.
- Unikalność `(okres_najmu_id, klucz_parametru)` pilnuje, żeby dwa składniki
  nie wskazywały na ten sam parametr.
- Warstwa domenowa (etap E2) dostarczy funkcję czytającą stan efektywny,
  żeby to złączenie nie było powtarzane w każdym zapytaniu.

# Stan projektu

Ten plik ładuje się do kontekstu przy **każdej** sesji, więc jest krótki celowo.
Zebrane pułapki i decyzje nie do cofnięcia: [`docs/pulapki.md`](pulapki.md)
(czytaj na żądanie). Odstępstwa od planu: [`docs/decyzje/`](decyzje/).

## Gdzie jestem

Etapy **E0 – E6 ukończone** (25.08.2026). Program działa od kliknięcia skrótu po dane
i **da się w nim pracować**: wprowadzić budynek, lokal, najemcę, umowę, warunki,
zabezpieczenia i przeglądy, zatwierdzić wartości, obsłużyć terminy.

40 endpointów. Interfejs: logowanie, dashboard, kartoteka z formularzami,
kokpit terminów z filtrami i akcjami, profil lokalu z siedmioma zakładkami.

Warstwa domenowa jest kompletna (reguły R1, R2, R4–R7, R9), pokrycie `domena/`
wynosi 100%. Generator zdarzeń chodzi codziennie o 6:00 i jest idempotentny.
Trzy migracje Alembica, jedna głowa.

Kontrola na dziś: **385 testów backendu + 8 frontendu**, `mypy` strict i `ruff`
czysto, `npm run build` przechodzi.

## Co następne

**E7: dokumenty i import z Excela.** Wgrywanie plików z walidacją typu MIME
po zawartości, deduplikacja po SHA-256, hierarchia umowa → aneks, podgląd PDF.
Import startowy z arkusza: kreator mapowania kolumn, walidacja przed zapisem,
import transakcyjny.

To pierwszy etap, w którym **naprawdę** potrzebna jest odpowiedź na punkt B
(waluta), bo ktoś musi zadeklarować, czym są liczby w arkuszu.

Zostało na później z E5 i E6: eksport XLSX, zapisane widoki, wybór kolumn,
wirtualizacja, edycja i usuwanie istniejących rekordów z interfejsu.
Wirtualizacja wymaga wcześniej migracji TanStack Table na API v9
([ADR 006](decyzje/006-tanstack-table-legacy.md)).

## Czego nadal nie wiem

- **Punkt A** (netto czy brutto, czy VAT to zawsze 23%) przestał blokować —
  typ `Kwota` niesie rodzaj i stawkę. Odpowiedź będzie potrzebna przy imporcie
  z Excela (E7), gdzie ktoś musi zadeklarować, czym są liczby w arkuszu.
- **Punkt B**: czy są umowy w EUR płatne w PLN po kursie NBP. Jeśli tak,
  potrzebna waluta płatności odrębna od waluty umowy i reguła kursu —
  **to zmiana schematu**, więc lepiej wiedzieć przed E7.
- **Konwencja końca umowy**: `KONIEC_WLACZNIE = True` znaczy, że 24 miesiące
  od 01.02.2026 kończą się 31.01.2028. Wariant zgodny z art. 112 k.c. dałby
  01.02.2028. Do potwierdzenia na realnych umowach; zmiana to jedna stała.
- Pytania 1–10 z sekcji 11 koncepcji, w szczególności miejsca postojowe
  (osobny lokal czy składnik opłaty) i który dokładnie wskaźnik GUS.
- **Interfejsu nikt nie widział w przeglądarce.** Buduje się i odpowiada, ale
  układu graficznego nie sprawdzono. Do zrobienia przy najbliższej okazji.

## Jak wrócić do pracy

1. `powershell -File narzedzia/lokalny-postgres.ps1 start`
2. `cd backend && uv run pytest` — powinno być zielone.
   Nagłówek przebiegu pokazuje `baza testowa: najem_testy`; jeśli zamiast tego
   jest ostrzeżenie, testy integracyjne są pomijane, a nie zaliczone.
3. Przeczytaj „Co następne" i wybierz zakres na jedną sesję
4. Nowa gałąź, `/plan`, dopiero potem kod

Dane przykładowe są w bazie. Logowanie testowe: `jan` / `HasloTestowe123`.

# ADR 006: TanStack Table przez wejście `legacy`

**Data:** 25.08.2026
**Status:** przyjęte, z wyznaczoną ścieżką wyjścia
**Dotyczy:** `docs/plan-budowy-claude-code.md`, sekcja 2.3

## Kontekst

Plan wskazuje TanStack Table. Zainstalowana wersja to 9.1.2, która przebudowała
API: `useReactTable` i `getCoreRowModel` zastąpiono przez `useTable` z generykami
`TableFeatures` i jawną kompozycją cech.

Wersja 9 dostarcza jednocześnie wejście `@tanstack/react-table/legacy`
z pełnym, wspieranym interfejsem v8 (`useLegacyTable`, `getCoreRowModel`,
`LegacyColumnDef`).

## Decyzja

Dashboard używa wejścia `legacy`.

## Uzasadnienie

Dzisiejsza tabela jest sterowana serwerem: filtrowanie, sortowanie i stronicowanie
robi `GET /api/v1/lokale`. Biblioteka odpowiada więc wyłącznie za odwzorowanie
definicji kolumn na komórki. Przepisanie tego na nowe API v9 nie daje w tej chwili
żadnej funkcji, a kosztuje czas i ryzyko na etapie, w którym ważniejsze jest,
żeby ekran w ogóle stanął.

Wejście `legacy` nie jest obejściem ani łatką: to interfejs dostarczony przez
autorów biblioteki jako wspierana ścieżka migracji.

## Kiedy to zmienić

Przy pierwszej z tych potrzeb:

* wirtualizacja przy ponad 500 wierszach (przewidziana w E5),
* sortowanie albo filtrowanie po stronie klienta,
* grupowanie wierszy w raportach (E12).

Wtedy przejście na natywne API v9 przestaje być kosmetyką i staje się warunkiem
działania funkcji. Do tego czasu zmiana byłaby refaktorem dla samego refaktoru.

## Konsekwencje

* Import w `Dashboard.tsx` idzie z `@tanstack/react-table/legacy`, a `flexRender`
  z wejścia głównego. Ta niesymetryczność jest zamierzona i opisana komentarzem
  w kodzie.
* Kolumny są typowane przez `LegacyColumnDef`, nie `ColumnDef`.

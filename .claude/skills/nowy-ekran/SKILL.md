---
name: nowy-ekran
description: Dodaje ekran frontendu: strona, routing, typy, zapytania i stany
argument-hint: [nazwa-ekranu]
disable-model-invocation: true
---

Dodaj ekran: $ARGUMENTS

1. Znajdź opis ekranu w `docs/system-najem-koncepcja.md`, sekcja 7.
   Zbuduj dokładnie to, co tam jest. Nie dokładaj funkcji od siebie.
2. Katalog `frontend/src/strony/<NazwaEkranu>/`, routing w `main.tsx`.
3. Dane wyłącznie przez TanStack Query. Typy odpowiedzi z `src/api/`.
4. Zaprojektuj wszystkie cztery stany, każdy z osobna:
   ładowanie, pusty, błąd, dane. Stan pusty musi mówić, co zrobić dalej.
5. Formatowanie tylko przez `src/funkcje/format.ts`.
6. Obsługa z klawiatury: fokus widoczny, kolejność Tab sensowna,
   akcje główne dostępne bez myszy.
7. Test w Vitest na logice ekranu (filtry, wyliczenia widoku), nie na wyglądzie.
8. Uruchom `npm test` i `npm run build`. Pokaż wynik.

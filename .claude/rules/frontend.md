---
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
---
# Reguły frontendu

- Żadnych obliczeń na pieniądzach. Kwoty przychodzą z API jako string i tak
  są wyświetlane. Front tylko formatuje.
- Formatowanie wyłącznie przez `src/funkcje/format.ts`. Nie wołaj `Intl`
  ani `toLocaleString` bezpośrednio w komponencie.
- Dane serwera przez TanStack Query, nie przez `useEffect` z `fetch`.
- Formularze: React Hook Form + Zod. Schemat Zod jest jedynym źródłem walidacji
  po stronie klienta.
- Każdy widok pobierający dane ma zaprojektowane cztery stany: ładowanie, pusty,
  błąd, dane. Stan pusty i błąd nie mogą być domyślne ani puste.
- Brak danych wyświetlamy jako `BRAK_DANYCH`, nigdy jako pustą komórkę
  (decyzja D5 z koncepcji).
- Nazwy komponentów i plików po polsku, zgodnie z resztą projektu.

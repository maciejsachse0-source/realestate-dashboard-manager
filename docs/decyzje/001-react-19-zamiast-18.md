# ADR 001: React 19 zamiast React 18

**Data:** 25.08.2026
**Status:** przyjęte
**Dotyczy:** `docs/plan-budowy-claude-code.md`, sekcja 2.3

## Kontekst

Plan budowy wskazuje React 18. Szablon `create-vite@latest react-ts` instaluje
dziś React 19.2 razem z Vite 8, TypeScript 6 i `@vitejs/plugin-react` 6.

## Decyzja

Zostajemy przy React 19.

## Uzasadnienie

Wersja Reacta nie jest w tym projekcie nośna. Powód wyboru Reacta w planie to
„typy po obu stronach", a to spełnia zarówno 18, jak i 19. Cofnięcie do 18
oznaczałoby walkę z całym łańcuchem narzędzi, który domyślnie celuje w 19,
i pinowanie wersji `@types/react`. Wszystkie wybrane biblioteki (TanStack Query,
TanStack Table, React Hook Form, React Router, shadcn/ui) wspierają 19.

## Konsekwencje

- `frontend/tsconfig` ma włączone `erasableSyntaxOnly` (domyślne w TS 6),
  więc skróty w konstruktorze (`constructor(readonly x: number)`) są zabronione.
  Pola deklarujemy jawnie.
- `openapi-typescript` 7 wymaga TypeScript 5.x i na razie nie instaluje się
  obok TS 6. Generowanie klienta z OpenAPI wchodzi w E4/E5 — wtedy albo będzie
  wersja zgodna z TS 6, albo przypniemy TypeScript do 5.x.

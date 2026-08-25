# ADR 005: Waluta bez wartości domyślnej w bazie

**Data:** 25.08.2026
**Status:** przyjęte
**Dotyczy:** `docs/plan-budowy-claude-code.md`, sekcja 1.1 punkt B

## Kontekst

Kolumny walut miały początkowo `server_default = 'PLN'`. Test sprawdzający,
że kwota bez waluty jest odrzucana, nie przechodził: baza po cichu dopisywała
`PLN` zamiast odmówić zapisu.

## Decyzja

Kolumny `wartosc_waluta` i `wymagana_waluta` nie mają wartości domyślnej.
Ograniczenia `CHECK` wymagają waluty przy każdej kwocie.

## Uzasadnienie

Punkt B planu mówi, że czynsz bywa w EUR płatny w PLN po kursie NBP. Baza,
która sama dopisuje `PLN`, zamienia brak danych w fakt — dokładnie to,
przed czym ostrzega decyzja D5 koncepcji. Przy migracji archiwum umów taki
domyślny wpis byłby nie do odróżnienia od świadomej deklaracji.

Podpowiedź `PLN` należy do formularza, gdzie człowiek ją widzi i może zmienić,
a nie do warstwy danych, gdzie jest niewidoczna.

## Konsekwencje

- Każdy zapis kwoty musi jawnie podać walutę. Wymusza to `CHECK`, nie konwencja.
- Formularze w interfejsie mają mieć `PLN` wstępnie wybrane.
- Pozostaje otwarte, czy potrzebna jest waluta płatności odrębna od waluty
  umowy oraz reguła kursu. To zależy od odpowiedzi na punkt B i dotyczy
  etapu E2, nie schematu.

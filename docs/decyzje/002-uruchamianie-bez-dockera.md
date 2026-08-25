# ADR 002: Uruchamianie bez Dockera, jednym kliknięciem

**Data:** 25.08.2026
**Status:** przyjęte
**Dotyczy:** `docs/plan-budowy-claude-code.md`, sekcje 2.5 i E0

## Kontekst

Plan budowy zakłada `docker compose up` jako sposób uruchomienia. Wymaganie
zamawiającego jest inne: **program ma uruchamiać osoba nieznająca się na
programowaniu, jednym kliknięciem, w całości lokalnie.** Na maszynie
deweloperskiej nie ma Dockera i jego instalacja wymaga uprawnień administratora.

## Decyzja

1. PostgreSQL 16 jako przenośne binaria w katalogu projektu (`tools/`),
   dane w `pgdata/`. Stawia je `narzedzia/lokalny-postgres.ps1`.
2. `Uruchom system najmu.cmd` w katalogu głównym uruchamia całość: bazę,
   migracje, budowanie interfejsu, aplikację i przeglądarkę.
   `narzedzia/utworz-skrot.ps1` zakłada skrót na pulpicie.
3. Zbudowany frontend serwuje FastAPI z tego samego portu, co API.
   Użytkownik ma jeden adres i jedno okno, nie dwa serwery.
4. `docker-compose.yml` zostaje w repozytorium jako wariant na przyszłość.
   `DATABASE_URL` jest identyczny w obu wariantach, więc przejście na Dockera
   nie zmienia ani linii kodu aplikacji.

## Konsekwencje

- Pierwsze uruchomienie pobiera około 350 MB binariów PostgreSQL. Jednorazowo.
- Baza nasłuchuje wyłącznie na pętli zwrotnej, zgodnie z sekcją 8.1 koncepcji.
- Spakowanie całości do pojedynczego pliku `.exe` zostaje na etap E12.
- Wariant sieciowy (kilku użytkowników na jednym serwerze) wymaga powrotu do
  tematu przy E4, bo koncepcja przewiduje role i logowanie imienne.

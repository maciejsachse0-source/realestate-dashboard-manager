# Plan budowy systemu najmu w Claude Code

## Od pustego repo do wdrożenia, krok po kroku

**Wersja:** 0.1
**Data:** 25.08.2026
**Dokument towarzyszący:** `system-najem-koncepcja.md` (model danych, reguły, mapa ekranów)
**Zweryfikowano na dokumentacji Claude Code:** sierpień 2026

---

## 0. Jak używać tego pliku

Ten dokument ma trzy warstwy i każda odpowiada na inne pytanie:

| Sekcja | Odpowiada na |
|---|---|
| 1 | Czego brakowało w specyfikacji, a bez czego program nie zadziała |
| 2 do 4 | Jak przygotować repo i Claude Code, zanim padnie pierwsza linia kodu |
| 5 | Jak pracować z Claude Code, żeby po trzech tygodniach nadal panować nad projektem |
| 6 | Etapy budowy, każdy z gotowym promptem i definicją ukończenia |
| 7 do 9 | Testy, wdrożenie, checklisty |

**Zasada nadrzędna:** nie buduj tego w jednej długiej sesji. Jeden etap to jedna sesja Claude Code, jedna gałąź gita, jeden commit lub kilka. Po etapie: `/clear` i start od nowa. Kontekst przenosisz przez `CLAUDE.md` i gita, nie przez pamięć rozmowy.

---

## 1. Czego brakowało w specyfikacji

Specyfikacja opisuje dobrze **co pracownik ma zobaczyć**. Nie opisuje rzeczy, które decydują o tym, czy system w ogóle da się zbudować i utrzymać. Poniżej lista tego, co trzeba rozstrzygnąć. Podzielona na trzy poziomy pilności.

### 1.1 Blokujące, czyli bez tego nie zaczynaj

**A. VAT i kwoty netto/brutto**
Specyfikacja mówi o "kwocie czynszu" bez rozróżnienia. W praktyce umowa podaje netto, faktura brutto, a stawka VAT dla najmu komercyjnego to zwykle 23 procent, ale nie zawsze. Każda kwota w systemie musi mieć jawnie zdefiniowane, czy jest netto czy brutto, i jaka stawka VAT ją dotyczy. Doklejenie tego później oznacza migrację wszystkich danych finansowych.

**B. Waluta i indeksacja walutowa**
Umowy najmu komercyjnego bardzo często mają czynsz w EUR płatny w PLN po kursie NBP z określonego dnia. Jeśli w tym portfelu takie umowy występują, model potrzebuje: waluty umowy, waluty płatności, reguły kursu (tabela NBP, dzień odniesienia). Trzeba to sprawdzić na realnych umowach **przed** zaprojektowaniem tabel.

**C. Typ liczbowy dla pieniędzy**
Nigdy `float`. W bazie `NUMERIC(12,2)`, w Pythonie `Decimal`, w JavaScript nigdy nie licz na pieniądzach po stronie frontu. Zaokrąglanie: jawnie zdefiniowane (`ROUND_HALF_UP`) i w jednym miejscu w kodzie. To brzmi banalnie i jest najczęstszym źródłem rozbieżności groszowych, które podważają zaufanie do systemu.

**D. Daty: co jest datą, a co momentem**
`data_przekazania` to data (bez godziny). `utworzono` to moment (z godziną i strefą). Reguła: daty biznesowe jako `DATE`, znaczniki techniczne jako `TIMESTAMPTZ` w UTC, wyświetlane w Europe/Warsaw. Mieszanie tych dwóch to gwarantowany błąd o jeden dzień przy przełomie miesiąca.

**E. Kalendarz dni roboczych i świąt**
Termin płatności "do 10-go" wypadający w niedzielę. Termin "14 dni od przekazania". System musi mieć tabelę świąt (polskie, ruchome, Wielkanoc liczona algorytmem) i funkcję "następny dzień roboczy". Bez tego alerty będą kłamać kilka razy w roku.

**F. Maszyna stanów, nie pole tekstowe**
`status` okresu najmu musi być zdefiniowany jako zbiór stanów i dozwolonych przejść, wymuszony w kodzie. Inaczej po pół roku w bazie będą umowy jednocześnie "zakończone" i "aktywne".

**G. Nic się nie kasuje**
Soft delete wszędzie (`usunięto_dnia`, `usunął_użytkownik`) plus osobna, tylko dopisywalna tabela audytu. W systemie, który ma rozstrzygać spory z najemcami, twarde usunięcie rekordu to problem prawny, nie techniczny.

**H. Konflikt edycji**
Dwie osoby otwierają ten sam profil lokalu. Potrzebne optimistic locking (kolumna `wersja`, przy zapisie sprawdzenie, czy się nie zmieniła). Bez tego cicha utrata zmian.

### 1.2 Ważne, potrzebne przed wdrożeniem

**I. Wyszukiwanie pełnotekstowe po polsku**
PostgreSQL nie ma domyślnie polskiej konfiguracji do wyszukiwania. Trzeba dodać słownik (hunspell polski) albo pójść w `pg_trgm` z wyszukiwaniem podobieństwa. To wpływa na konfigurację bazy, więc na wybór obrazu Dockera. Decyzja przy stawianiu bazy, nie na końcu.

**J. Formaty polskie w interfejsie**
Przecinek dziesiętny, spacja jako separator tysięcy, daty `DD.MM.RRRR`, kwoty `1 234,56 zł`. Wymuszone przez jedną funkcję formatującą, nie ad hoc w komponentach. Do tego walidacja NIP (suma kontrolna), REGON i KRS.

**K. Uwierzytelnianie i sesje**
Konkretne decyzje: hasła haszowane Argon2id, sesje w ciasteczkach HttpOnly + SameSite, blokada konta po N nieudanych próbach, wymuszona zmiana hasła przy pierwszym logowaniu. Jeśli firma ma AD lub LDAP, integracja od razu, bo doklejenie jej później oznacza przebudowę warstwy auth.

**L. Bezpieczeństwo uploadu**
Limit rozmiaru pliku, biała lista typów MIME sprawdzana po zawartości a nie po rozszerzeniu, pliki przechowywane poza katalogiem serwowanym przez web, nazwy generowane a nie z uploadu, deduplikacja po SHA-256, skan antywirusowy (ClamAV) jeśli polityka firmy tego wymaga.

**M. Harmonogram zadań i idempotencja alertów**
Generator zdarzeń chodzi raz na dobę. Musi być idempotentny: uruchomiony trzy razy tego samego dnia nie tworzy trzech takich samych alertów. Klucz naturalny na zdarzeniu (typ + encja + data) i `ON CONFLICT DO NOTHING`.

**N. Import startowy z Excela**
Firma prawie na pewno ma jakiś arkusz, w którym to dziś prowadzi. Import tego arkusza to osobny, nietrywialny etap i najszybsza droga do tego, żeby system był użyteczny w pierwszym tygodniu. Warto go zaplanować, a nie improwizować.

**O. Dane testowe bez danych prawdziwych**
Deweloper nie może pracować na produkcyjnych umowach. Potrzebny generator realistycznych, ale wymyślonych danych (Faker z polskim locale) i osobny zestaw przykładowych dokumentów.

**P. Logowanie strukturalne i identyfikator żądania**
Logi w JSON, z `request_id` przechodzącym przez cały stos. Przy on-premie bez zewnętrznego monitoringu to jedyne narzędzie diagnostyczne, jakie będziesz mieć.

**Q. Kopie zapasowe z przetestowanym odtworzeniem**
Backup, którego nikt nie odtworzył, nie istnieje. Procedura `pg_dump` + katalog dokumentów, plus jednorazowy test pełnego odtworzenia na czystej maszynie, wpisany w harmonogram wdrożenia.

**R. Model lokalny: sprzęt i licencja**
Zanim ktokolwiek napisze linijkę kodu ekstrakcji, trzeba wiedzieć: jaki model, na jakim sprzęcie (GPU czy CPU), jaka licencja (czy pozwala na użycie komercyjne wewnątrz firmy), ile RAM. Model 7B na CPU przetwarza umowę w minuty, nie w sekundy, i to zmienia projekt interfejsu (kolejka zamiast oczekiwania).

### 1.3 Do przemyślenia, ale nie blokuje startu

- **Uprawnienia na poziomie wiersza**: czy każdy pracownik widzi wszystkie budynki, czy tylko przypisane.
- **Wielu wynajmujących**: czy w grupie jest kilka spółek będących stroną umów.
- **Podnajem i cesje**: jeśli występują, model najemcy potrzebuje relacji nadrzędnej.
- **Wersjonowanie API**: prefiks `/api/v1` od początku, kosztuje nic.
- **Wydruk karty lokalu do PDF**: przydatne przy negocjacjach i kontrolach.
- **Retencja danych**: ile lat po zakończeniu umowy trzymamy dane osobowe i jak je usuwamy.
- **Integralność dokumentów**: hash pliku zapisany przy imporcie pozwala udowodnić, że dokument się nie zmienił.
- **Healthcheck i monitoring**: endpoint `/health`, prosty alert mailowy gdy usługa padnie.

**Rekomendacja:** przejdź przez punkty A do H z osobą z księgowości lub administracji **przed** etapem E1. Odpowiedzi na te osiem pytań determinują schemat bazy.

---

## 2. Stack: konkretne decyzje

Ogólny kierunek był ustalony (lokalna web-app, FastAPI, React, Postgres). Tutaj konkrety, żeby Claude Code nie wybierał za ciebie w połowie projektu.

### 2.1 Backend

| Element | Wybór | Dlaczego |
|---|---|---|
| Język | Python 3.12 | stabilny, wszystkie biblioteki do dokumentów dostępne |
| Framework | FastAPI | typy, automatyczna dokumentacja OpenAPI, async gdzie potrzeba |
| Walidacja | Pydantic v2 | jedno źródło definicji kształtu danych dla API i domeny |
| ORM | SQLAlchemy 2.0 (styl deklaratywny) | dojrzałe, dobrze radzi sobie z zapytaniami czasowymi |
| Migracje | Alembic | obowiązkowe od pierwszej tabeli, bez wyjątków |
| Menedżer zależności | uv (albo Poetry) | uv jest szybszy i prostszy w Dockerze |
| Testy | pytest + pytest-asyncio + factory_boy | testy reguł biznesowych to serce jakości tego projektu |
| Zadania cykliczne | APScheduler w procesie, docelowo osobny worker | generator zdarzeń raz na dobę, nie potrzeba Celery na start |
| Kolejka przetwarzania | RQ + Redis (dopiero w fazie ekstrakcji) | OCR nie może blokować requestu |
| Logi | structlog, JSON | diagnostyka on-prem |
| Format kodu | ruff (format + lint) | jedno narzędzie zamiast black + flake8 + isort |
| Typy | mypy w trybie strict na warstwie domenowej | tam gdzie liczą się pieniądze, typy się opłacają |

### 2.2 Baza

| Element | Wybór |
|---|---|
| Silnik | PostgreSQL 16 |
| Rozszerzenia | `pg_trgm` (wyszukiwanie), `unaccent`, opcjonalnie słownik hunspell PL |
| Pieniądze | `NUMERIC(12,2)` |
| Daty biznesowe | `DATE` |
| Znaczniki techniczne | `TIMESTAMPTZ` w UTC |
| Klucze | UUID v7 (sortowalne w czasie) albo `BIGSERIAL`, wybierz jedno i trzymaj się |
| Audyt | osobna tabela `audit_log`, tylko INSERT |

SQLite tylko do najwcześniejszego prototypu. Jeśli od razu masz Dockera, zaczynaj na Postgresie, bo różnice w typach dat i `NUMERIC` potrafią zaboleć przy migracji.

### 2.3 Frontend

| Element | Wybór | Dlaczego |
|---|---|---|
| Framework | React 18 + TypeScript | typy po obu stronach zmniejszają liczbę głupich błędów |
| Bundler | Vite | prostszy niż Next.js, a SSR tu do niczego nie jest potrzebny |
| Routing | React Router | wystarczy |
| Stan serwera | TanStack Query | cache, refetch, stany ładowania za darmo |
| Formularze | React Hook Form + Zod | walidacja po stronie klienta zgodna ze schematem |
| Tabela | TanStack Table | dashboard to w praktyce jedna bardzo dobra tabela: sortowanie, filtry, kolumny, wirtualizacja |
| Style | Tailwind CSS | szybkie, spójne, nie wymaga systemu designu na starcie |
| Komponenty | shadcn/ui | kopiowane do repo, więc nie ma zależności od zewnętrznej biblioteki, co przy on-premie jest zaletą |
| Daty | date-fns z locale `pl` | lekkie, dobre formatowanie polskie |
| Klient API | generowany z OpenAPI (openapi-typescript) | typy endpointów bez ręcznego przepisywania |
| Podgląd PDF | pdf.js | potrzebny do podświetlania fragmentów przy weryfikacji |
| Testy | Vitest + Testing Library, Playwright na E2E | |

Świadomie **bez Next.js**: aplikacja jest wewnętrzna, za logowaniem, nie potrzebuje SEO ani SSR. Vite to mniej ruchomych części przy wdrożeniu on-prem.

### 2.4 Przetwarzanie dokumentów (etapy późniejsze)

| Zadanie | Narzędzie |
|---|---|
| PDF natywny do tekstu | pdfplumber lub PyMuPDF (uwaga na licencję AGPL przy PyMuPDF) |
| DOCX do tekstu | python-docx |
| OCR skanów | Tesseract z `pol` (albo PaddleOCR, jeśli jakość skanów jest słaba) |
| Wykrywanie układu | pdfplumber words + pozycje, do podświetlania fragmentów |
| Model lokalny | Ollama albo llama.cpp, model 7B do 14B, licencja sprawdzona pod kątem użycia komercyjnego |

Uwaga licencyjna: PyMuPDF jest na AGPL, co w korporacji potrafi być problemem. pdfplumber (MIT) jest bezpieczniejszy prawnie, choć wolniejszy. Sprawdź to z działem prawnym zanim wejdzie do zależności.

### 2.5 Wdrożenie

Docker Compose z czterema usługami: `api`, `web` (nginx serwujący zbudowany front i proxy do api), `db` (Postgres), `worker` (zadania w tle, od fazy ekstrakcji). Wolumeny na dane bazy i katalog dokumentów. Wszystko konfigurowane przez zmienne środowiskowe, żaden sekret w repo.

---

## 3. Struktura repozytorium

```
system-najem/
├── CLAUDE.md                    # instrukcje dla Claude Code, poniżej 200 linii
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── README.md
│
├── .claude/
│   ├── settings.json            # hooki, uprawnienia (commitowane)
│   ├── settings.local.json      # prywatne, w .gitignore
│   ├── rules/
│   │   ├── backend.md           # paths: backend/**/*.py
│   │   ├── frontend.md          # paths: frontend/**/*.{ts,tsx}
│   │   ├── migracje.md          # paths: backend/alembic/**
│   │   └── pieniadze-i-daty.md  # reguły domenowe, ładowane zawsze
│   ├── skills/
│   │   ├── nowa-encja/SKILL.md
│   │   ├── nowa-regula/SKILL.md
│   │   └── przeglad-etapu/SKILL.md
│   └── agents/
│       └── recenzent.md
│
├── docs/
│   ├── system-najem-koncepcja.md
│   ├── plan-budowy-claude-code.md
│   ├── decyzje/                 # ADR: jedna decyzja, jeden plik
│   └── postep.md                # stan projektu między sesjami
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   │   └── versions/
│   ├── src/najem/
│   │   ├── domena/              # CZYSTA logika, zero SQLAlchemy, zero HTTP
│   │   │   ├── pieniadze.py     # Kwota, VAT, zaokrąglanie
│   │   │   ├── kalendarz.py     # dni robocze, święta
│   │   │   ├── stan_efektywny.py
│   │   │   ├── reguly/
│   │   │   │   ├── data_zakonczenia.py
│   │   │   │   ├── waloryzacja.py
│   │   │   │   ├── zabezpieczenia.py
│   │   │   │   └── przeglady.py
│   │   │   └── zdarzenia.py
│   │   ├── modele/              # SQLAlchemy
│   │   ├── schematy/            # Pydantic (wejście/wyjście API)
│   │   ├── repozytoria/         # dostęp do danych
│   │   ├── uslugi/              # przypadki użycia, orkiestracja
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── auth/
│   │   ├── dokumenty/           # pipeline: ingest, ocr, ekstrakcja
│   │   ├── zadania/             # scheduler
│   │   └── config.py
│   └── tests/
│       ├── domena/              # najwięcej testów TUTAJ
│       ├── api/
│       └── integracja/
│
└── frontend/
    ├── package.json
    └── src/
        ├── api/                 # klient generowany z OpenAPI
        ├── komponenty/
        ├── funkcje/             # format PLN, daty, walidacja NIP
        ├── strony/
        │   ├── Dashboard/
        │   ├── ProfilLokalu/
        │   ├── KokpitTerminow/
        │   ├── Import/
        │   ├── Weryfikacja/
        │   ├── Waloryzacja/
        │   └── Admin/
        └── typy/
```

**Najważniejsza granica w tej strukturze:** katalog `domena/` nie importuje niczego z `modele/`, `api/` ani z SQLAlchemy. To czysty Python z typami. Dzięki temu reguły biznesowe testuje się w milisekundach, bez bazy, i nie da się ich przypadkiem popsuć zmianą w API. Jeśli Claude Code zacznie tam wstawiać zapytania do bazy, to znak, że trzeba go poprawić i dopisać regułę do `CLAUDE.md`.

---

## 4. Konfiguracja Claude Code

### 4.1 CLAUDE.md

Ładowany do kontekstu przy każdej sesji, więc płacisz za niego tokenami zawsze. Cel: **poniżej 200 linii**. Wszystko dłuższe idzie do `.claude/rules/` (ładowane warunkowo) albo do skilla (ładowany na żądanie).

Szkielet:

```markdown
# System Zarządzania Umowami Najmu

Wewnętrzna aplikacja on-prem. Rejestr stanu umów najmu z ekstrakcją danych
z dokumentów. Pełna koncepcja: @docs/system-najem-koncepcja.md

## Komendy

- Backend: `cd backend && uv run uvicorn najem.main:app --reload`
- Testy backend: `cd backend && uv run pytest`
- Lint + format: `cd backend && uv run ruff check --fix . && uv run ruff format .`
- Typy: `cd backend && uv run mypy src/najem/domena`
- Migracja: `cd backend && uv run alembic revision --autogenerate -m "opis"`
- Frontend: `cd frontend && npm run dev`
- Testy frontend: `cd frontend && npm test`
- Cały stack: `docker compose up`

## Zasady architektury

- `src/najem/domena/` to czysty Python. Zero SQLAlchemy, zero FastAPI, zero I/O.
  Każda reguła biznesowa mieszka tutaj i ma test jednostkowy.
- Warstwy: api → uslugi → repozytoria → modele. Nigdy w drugą stronę.
- Frontend nie liczy niczego na pieniądzach. Wszystkie wyliczenia po stronie API.

## Zasady twarde

- Pieniądze: `Decimal` w Pythonie, `NUMERIC(12,2)` w bazie. Nigdy `float`.
  Zaokrąglanie tylko przez `domena/pieniadze.py`.
- Daty biznesowe: `date`. Znaczniki techniczne: `datetime` w UTC (`TIMESTAMPTZ`).
- Nic nie usuwamy fizycznie. Soft delete + wpis w `audit_log`.
- Każda zmiana modelu = migracja Alembic w tym samym commicie.
- Parametry umowy nie są nadpisywane, tylko wersjonowane w czasie
  (tabela `parametr_wartosc`, pola `obowiazuje_od` / `obowiazuje_do`).
- Nazwy tabel, kolumn i pól domenowych po polsku. Nazwy techniczne po angielsku.
- Zero wywołań sieciowych do zewnętrznych usług AI. To wymóg bezpieczeństwa.

## Testy

- Nowa reguła biznesowa: najpierw test, potem implementacja.
- Nie oznaczaj etapu jako gotowego, dopóki `pytest` i `mypy` nie przechodzą.

## Stan projektu

Aktualny etap i następne kroki: @docs/postep.md
```

Uwaga na import `@docs/postep.md`: importowane pliki są rozwijane do kontekstu przy starcie, więc trzymaj `postep.md` krótki (kilkanaście linii). Jeśli urośnie, usuń import i każ Claude'owi czytać ten plik na żądanie.

Sprawdzenie, co faktycznie się załadowało: `/context` w sesji, sekcja **Memory files**.

### 4.2 Reguły zakresowe (`.claude/rules/`)

To jest mechanizm, który realnie oszczędza kontekst. Regułę z frontmatterem `paths` Claude wciąga dopiero wtedy, gdy dotyka pasujących plików.

`.claude/rules/backend.md`:
```markdown
---
paths:
  - "backend/**/*.py"
---
# Reguły backendu

- FastAPI: endpointy zwracają schematy Pydantic, nigdy modeli SQLAlchemy.
- Zapytania z `selectinload`, żeby nie robić N+1.
- Każdy endpoint listujący ma paginację (limit domyślnie 50, maks 500).
- Wyjątki domenowe (`BladDomenowy`) mapowane na kody HTTP w jednym handlerze.
- Endpointy pod `/api/v1/`.
```

`.claude/rules/pieniadze-i-daty.md` (bez `paths`, więc ładowana zawsze, bo to najczęstsze źródło błędów):
```markdown
# Pieniądze, daty, formaty

- Kwoty: `Decimal`, kwantyzacja do 2 miejsc, `ROUND_HALF_UP`.
- Każda kwota ma jawnie: netto/brutto i stawkę VAT.
- Format wyświetlania: `1 234,56 zł` (spacja jako separator tysięcy, przecinek dziesiętny).
- Daty wyświetlane `DD.MM.RRRR`.
- Terminy płatności przesuwane na następny dzień roboczy przez `domena/kalendarz.py`.
- Wielkanoc i święta ruchome: liczone algorytmem, nie wpisywane na sztywno.
```

`.claude/rules/migracje.md`:
```markdown
---
paths:
  - "backend/alembic/**"
---
# Migracje

- Zawsze `--autogenerate`, ale ZAWSZE przejrzyj wygenerowany plik przed commitem.
- Każda migracja ma działający `downgrade`.
- Migracja zmieniająca dane (nie tylko schemat) ma osobny test.
- Nie edytuj migracji, która trafiła na główną gałąź. Dopisz nową.
```

### 4.3 Skille projektowe (`.claude/skills/`)

Skill to procedura ładowana na żądanie, więc długa instrukcja nie kosztuje kontekstu, dopóki jej nie wywołasz. Katalog daje nazwę komendy: `.claude/skills/nowa-regula/SKILL.md` to `/nowa-regula`.

`.claude/skills/nowa-regula/SKILL.md`:
```markdown
---
name: nowa-regula
description: Dodaje nową regułę biznesową do warstwy domenowej wraz z testami
argument-hint: [nazwa-reguly]
disable-model-invocation: true
---

Dodaj regułę biznesową: $ARGUMENTS

Kolejność obowiązkowa:

1. Dopytaj o przypadki brzegowe, jeśli opis jest niejednoznaczny. Nie zgaduj.
2. Napisz testy w `backend/tests/domena/` PRZED implementacją. Uwzględnij:
   - przypadek typowy,
   - brak danych wejściowych (musi zwrócić stan "nieustalone", nie wyjątek),
   - granice miesiąca i roku,
   - rok przestępny, jeśli reguła dotyczy dat,
   - kwoty z groszami, jeśli reguła dotyczy pieniędzy.
3. Uruchom testy, upewnij się, że są czerwone z właściwego powodu.
4. Zaimplementuj w `backend/src/najem/domena/reguly/`. Czysta funkcja,
   bez dostępu do bazy, bez `datetime.now()` w środku (datę podaj argumentem).
5. Uruchom `pytest` i `mypy`.
6. Dopisz regułę do tabeli w `docs/system-najem-koncepcja.md`, sekcja 5.
7. Pokaż podsumowanie: co robi reguła, jakie przypadki brzegowe pokryte.
```

`.claude/skills/przeglad-etapu/SKILL.md`:
```markdown
---
name: przeglad-etapu
description: Przegląd i domknięcie etapu przed commitem i przed nową sesją
disable-model-invocation: true
---

Domknij bieżący etap:

1. `git status` i `git diff` na całości zmian.
2. Uruchom: testy backendu, mypy na domenie, lint, testy frontendu.
3. Sprawdź, czy nie ma: `TODO`, `FIXME`, zakomentowanego kodu, `print()`,
   `console.log`, sekretów, `float` przy kwotach.
4. Sprawdź, czy zmiany modelu mają odpowiadającą migrację Alembic.
5. Zaproponuj commit z opisem po polsku w trybie rozkazującym.
6. Zaktualizuj `docs/postep.md`: co zrobione, co następne, na co uważać.
7. Wypisz to, czego NIE udało się zrobić, i dlaczego. Bez upiększania.
```

Warto też mieć `/nowa-encja` (model + migracja + schematy + repozytorium + CRUD + testy) i `/nowy-ekran` (strona + routing + typy + zapytania + stany ładowania i błędu).

### 4.4 Podagent do recenzji

`.claude/agents/recenzent.md`:
```markdown
---
name: recenzent
description: Krytyczny przegląd kodu pod kątem reguł tego projektu. Uruchamiaj przed commitem etapu.
tools: Read, Grep, Glob, Bash
---

Jesteś recenzentem kodu w projekcie systemu najmu. Twoje zadanie to znaleźć
problemy, nie chwalić.

Sprawdź w kolejności:
1. Czy `domena/` nie importuje SQLAlchemy, FastAPI ani niczego z I/O.
2. Czy kwoty używają `Decimal`, a nie `float`. Grep po `float(`.
3. Czy daty biznesowe to `date`, a techniczne `datetime` z UTC.
4. Czy zmiany modeli mają migrację Alembic.
5. Czy nowe reguły mają testy przypadków brzegowych, a nie tylko happy path.
6. Czy endpointy listujące mają paginację.
7. Czy nie ma twardego usuwania rekordów.
8. Czy nie ma wywołań sieciowych do zewnętrznych usług.

Zwróć listę znalezisk uszeregowaną od najpoważniejszego. Przy każdym: plik,
linia, na czym polega problem, jak to naprawić. Jeśli nic nie znalazłeś,
napisz to wprost, ale najpierw sprawdź jeszcze raz punkty 2 i 5.
```

Uruchamiasz przez `/agents` albo prosząc wprost: "uruchom podagenta recenzent na zmianach z tego etapu".

### 4.5 Hooki (`.claude/settings.json`)

Hooki to jedyny mechanizm, który wykonuje się **niezależnie od tego, co Claude uzna**. Wszystko, co musi się zdarzyć zawsze, dawaj tutaj, a nie do `CLAUDE.md`.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "if": "Edit(backend/**/*.py)",
            "command": "cd backend && uv run ruff format $CLAUDE_FILE_PATHS && uv run ruff check --fix $CLAUDE_FILE_PATHS",
            "timeout": 60
          },
          {
            "type": "command",
            "if": "Edit(frontend/**/*.{ts,tsx})",
            "command": "cd frontend && npx prettier --write $CLAUDE_FILE_PATHS && npx eslint --fix $CLAUDE_FILE_PATHS",
            "timeout": 60
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd backend && uv run pytest tests/domena -q",
            "timeout": 180
          }
        ]
      }
    ]
  }
}
```

Efekt: kod jest sformatowany od razu po zapisie, a testy reguł biznesowych chodzą po każdej odpowiedzi Claude'a. Błąd wraca do niego natychmiast, a nie po godzinie.

Podgląd tego, co faktycznie jest skonfigurowane: `/hooks`.

### 4.6 Uprawnienia

Bez allowlisty będziesz klikał "zezwól" co trzydzieści sekund i przestaniesz czytać, co zatwierdzasz. To realne ryzyko, nie tylko irytacja.

W `.claude/settings.json`, sekcja `permissions.allow`, wpisz operacje bezpieczne i częste: uruchamianie testów, lint, `git status`, `git diff`, `git log`, generowanie migracji, `npm test`. W `permissions.deny` wpisz to, co nigdy: `git push --force`, kasowanie katalogów, `alembic downgrade` na produkcji.

Konfiguracja przez `/permissions` w sesji albo bezpośrednio w pliku.

### 4.7 MCP

| Serwer | Do czego | Kiedy dodać |
|---|---|---|
| **Context7** | aktualna dokumentacja FastAPI, SQLAlchemy 2.0, TanStack | od razu, oszczędza pół godziny na każdym "jak to się teraz robi" |
| **PostgreSQL** | podglądanie schematu i danych bez pisania skryptów | od etapu E1 |
| **Playwright** | testy E2E, zrzuty ekranu, weryfikacja UI | od etapu E4 |
| **GitHub** | PR-y, issues, jeśli repo jest na GitHubie | opcjonalnie |

Konfiguracja projektowa w `.mcp.json` w katalogu repo (commitowana, więc zespół ma to samo), osobista w scope użytkownika. Dodawanie: `claude mcp add`, zarządzanie w sesji: `/mcp`.

Szczególnie **Context7 się opłaca**, bo SQLAlchemy 2.0 i Pydantic v2 mają API znacząco inne od wersji poprzednich, a modele językowe chętnie generują składnię z wersji 1.x.

---

## 5. Metoda pracy

### 5.1 Pętla jednego etapu

```
1. /clear                          świeży kontekst, CLAUDE.md ładuje się sam
2. przeczytaj docs/postep.md       gdzie skończyłeś
3. git checkout -b etap/nazwa      osobna gałąź
4. /plan <opis etapu>              tryb planowania, ZANIM cokolwiek powstanie
5. przeczytaj plan i popraw go     to jest najważniejsze 5 minut całego etapu
6. zatwierdź plan
7. praca, małe commity po drodze
8. /przeglad-etapu                 własny skill z sekcji 4.3
9. podagent recenzent
10. poprawki, commit, merge
11. aktualizacja docs/postep.md
12. koniec sesji
```

### 5.2 Zasady, które robią różnicę

**Tryb planowania przed każdym większym etapem.** `/plan` sprawia, że Claude najpierw przedstawia podejście, a ty je akceptujesz lub poprawiasz, zanim powstanie kod. Poprawienie planu kosztuje minutę, poprawienie zaimplementowanego złego pomysłu kosztuje godzinę.

**Testy przed implementacją tam, gdzie chodzi o liczby.** Reguła waloryzacji napisana bez testu wygląda dobrze i liczy źle. Dla warstwy `domena/` to nie jest ideologia TDD, tylko praktyczna konieczność.

**Mały zakres na sesję.** "Zbuduj dashboard" to nie jest zadanie. "Dodaj filtrowanie po kwartale zakończenia umowy, z testem, do istniejącej tabeli" to jest zadanie. Im węższy zakres, tym mniejsza szansa, że Claude zacznie przebudowywać rzeczy, których nie prosiłeś.

**`/clear` częściej niż `/compact`.** Kompaktowanie w nieskończoność prowadzi do sesji, w której Claude pamięta streszczenie streszczenia. Po zamkniętym etapie czyść. Kontekst odtwarza się z `CLAUDE.md`, gita i `postep.md`, a to jest zawsze aktualne.

**`/context` gdy coś idzie nie tak.** Pokazuje, co realnie siedzi w kontekście i ile miejsca zostało. Jeśli Claude ignoruje regułę z `CLAUDE.md`, najpierw sprawdź, czy plik się w ogóle załadował.

**`/rewind` zamiast ratowania.** Gdy zmiana poszła w złą stronę, cofnij kod i rozmowę do punktu kontrolnego i sformułuj polecenie inaczej. Doprowadzanie do porządku popsutego stanu przez kolejne poprawki to najdroższy sposób pracy z narzędziem, które ma cofanie wbudowane.

**Commituj częściej niż ci się wydaje potrzebne.** Git jest twoim systemem punktów kontrolnych między sesjami.

**`docs/postep.md` to nie dokumentacja, to notatka dla siebie z przyszłości.** Kilkanaście linii: gdzie skończyłem, co następne, co jest kruche, czego nie ruszać.

**Automatyczna pamięć.** Claude Code sam zapisuje w tle wnioski i twoje korekty (`/memory` pokazuje co). To działa niezależnie od `CLAUDE.md`. Zajrzyj tam po kilku sesjach, bo czasem zapisuje rzeczy warte przeniesienia do `CLAUDE.md` na stałe.

### 5.3 Czego nie robić

| Antywzorzec | Dlaczego boli |
|---|---|
| Jedna sesja na cały projekt | kontekst puchnie, jakość spada, w połowie zaczyna zapominać ustalenia |
| "Napisz mi cały backend" | dostajesz 40 plików, których nikt nie przejrzy, i długu technicznego na miesiąc |
| Akceptowanie migracji bez czytania | autogenerate potrafi zaproponować `DROP COLUMN` |
| Pomijanie testów, bo "to proste" | reguły waloryzacji nie są proste, tylko wyglądają |
| Praca na produkcyjnych danych w devie | RODO plus jedna pomyłka w `DELETE` |
| Trzymanie wszystkiego w CLAUDE.md | plik rośnie, adherencja spada, płacisz kontekstem co sesję |

---

## 6. Etapy budowy

Każdy etap ma: cel, gotowy prompt, definicję ukończenia (DoD) i pułapki. Czas jest orientacyjny i zakłada pracę z Claude Code, nie ręczne pisanie.

---

### E0. Fundament, bez logiki biznesowej

**Cel:** repo, które się uruchamia, ma testy i wymusza jakość.

**Prompt:**
```
Zbuduj szkielet projektu wg struktury z docs/plan-budowy-claude-code.md, sekcja 3.

Backend: Python 3.12, uv, FastAPI, SQLAlchemy 2.0, Alembic, pytest, ruff, mypy.
Frontend: Vite + React 18 + TypeScript, Tailwind, TanStack Query, React Router.
docker-compose.yml z usługami: api, web, db (Postgres 16 z pg_trgm), bez workera.
Konfiguracja przez zmienne środowiskowe, plik .env.example, żadnych sekretów w repo.

Zakres tego etapu:
- endpoint GET /api/v1/health zwracający status aplikacji i połączenia z bazą
- jeden przykładowy test backendu i jeden frontendu, oba przechodzą
- pusta migracja początkowa Alembic
- README z instrukcją uruchomienia od zera

NIE dodawaj żadnych modeli domenowych ani ekranów. To ma być fundament.
```

**DoD:**
- `docker compose up` podnosi całość, `/api/v1/health` odpowiada
- `pytest`, `mypy`, `ruff`, `npm test` przechodzą
- świeży klon plus README daje działające środowisko

**Pułapki:** wersje bibliotek. Poproś wprost o SQLAlchemy w stylu 2.0 (`Mapped`, `mapped_column`) i Pydantic v2, bo domyślnie potrafi wygenerować składnię z wersji poprzednich.

---

### E0.5. Konfiguracja Claude Code

**Cel:** narzędzie skonfigurowane, zanim zacznie się prawdziwa praca.

**Prompt:**
```
Skonfiguruj Claude Code dla tego projektu wg sekcji 4 z docs/plan-budowy-claude-code.md:

1. CLAUDE.md wg szkieletu z 4.1, poniżej 200 linii
2. .claude/rules/: backend.md, frontend.md, migracje.md, pieniadze-i-daty.md
3. .claude/skills/: nowa-encja, nowa-regula, przeglad-etapu, nowy-ekran
4. .claude/agents/recenzent.md
5. .claude/settings.json z hookami formatującymi i uruchamiającymi testy domeny
6. docs/postep.md z pierwszym wpisem

Po utworzeniu pokaż mi CLAUDE.md do akceptacji, zanim zapiszesz resztę.
```

**DoD:** `/context` pokazuje załadowane pliki pamięci, `/hooks` pokazuje hooki, edycja pliku `.py` uruchamia formatowanie.

---

### E1. Model danych i migracje

**Cel:** schemat bazy odzwierciedlający koncepcję, z wersjonowaniem parametrów.

**Warunek wstępny:** odpowiedzi na pytania A do H z sekcji 1.1. Bez nich to jest zgadywanie.

**Prompt:**
```
Zaimplementuj model danych wg docs/system-najem-koncepcja.md, sekcja 3.

Encje: Budynek, Lokal, Najemca, OkresNajmu, Dokument, ParametrWartosc,
SkladnikOplaty, Zabezpieczenie, ObowiazekPrzegladu, Zdarzenie, Uzytkownik, AuditLog.

Wymagania twarde:
- kwoty NUMERIC(12,2), każda z polami: netto/brutto i stawka VAT
- daty biznesowe DATE, znaczniki techniczne TIMESTAMPTZ w UTC
- soft delete na wszystkich encjach biznesowych (usunieto_dnia, usunal_uzytkownik_id)
- kolumna wersja do optimistic locking na encjach edytowalnych
- ParametrWartosc: klucz, wartosc, obowiazuje_od, obowiazuje_do, dokument_zrodlowy_id,
  lokalizacja_w_dokumencie, status_weryfikacji, zatwierdzil, zatwierdzono_dnia
- Dokument: dokument_nadrzedny_id (hierarchia umowa → aneks), hash SHA-256, typ
- indeksy pod zapytania: stan efektywny na dzień, filtrowanie po budynku i dacie końca
- audit_log tylko do zapisu

Wygeneruj migrację Alembic i pokaż mi ją do przejrzenia PRZED zapisaniem.
Napisz testy sprawdzające: tworzenie encji, kaskady, unikalność, działanie soft delete.
```

**DoD:** migracja w górę i w dół działa na czystej bazie, testy przechodzą, indeksy istnieją.

**Pułapki:** to jest etap, w którym najbardziej opłaca się czytać wygenerowany kod linijka po linijce. Błąd w schemacie kosztuje najwięcej ze wszystkich błędów w tym projekcie.

---

### E2. Warstwa domenowa i reguły biznesowe

**Cel:** cała logika policzona i przetestowana, bez API i bez UI.

To jest **najważniejszy etap projektu**. Warto poświęcić mu więcej czasu, niż się wydaje potrzebne.

**Prompt (rozbij na kilka sesji, po jednej grupie reguł):**
```
Zaimplementuj warstwę domenową w backend/src/najem/domena/.
Czysty Python: bez SQLAlchemy, bez FastAPI, bez I/O, bez datetime.now() w środku funkcji
(datę przekazuj argumentem, żeby testy były deterministyczne).

Sesja 1: fundamenty
- pieniadze.py: typ Kwota (Decimal + waluta + netto/brutto + VAT), dodawanie,
  mnożenie przez wskaźnik, zaokrąglanie ROUND_HALF_UP, konwersja netto↔brutto
- kalendarz.py: święta polskie z Wielkanocą liczoną algorytmem, dni robocze,
  funkcja nastepny_dzien_roboczy, przesuwanie terminów płatności

Sesja 2: stan efektywny
- stan_efektywny.py: dla listy ParametrWartosc i podanej daty zwróć obowiązujące
  wartości. Obsłuż: brak wartości, wartości nakładające się, wartości niezatwierdzone
  (te NIE wchodzą do stanu efektywnego)

Sesja 3: reguły
- data_zakonczenia.py (reguła R1)
- waloryzacja.py (R2)
- zabezpieczenia.py (R4, R5, R6)
- przeglady.py (R7)

Dla każdej reguły najpierw testy, potem implementacja. Przypadki brzegowe obowiązkowo:
brak danych, granica miesiąca i roku, rok przestępny, kwoty z groszami,
waloryzacja przy zmianie stawki w trakcie roku.
```

**DoD:** `pytest tests/domena` zielone, pokrycie warstwy domenowej powyżej 90 procent, `mypy --strict` przechodzi, żaden plik w `domena/` nie importuje SQLAlchemy (sprawdź gerpem).

---

### E3. Generator zdarzeń

**Cel:** katalog alertów z sekcji 6 koncepcji, idempotentnie.

**Prompt:**
```
Zaimplementuj generator zdarzeń wg docs/system-najem-koncepcja.md, sekcja 6.

- zdarzenia.py w warstwie domenowej: czysta funkcja
  (stan_umowy, data_odniesienia) -> lista zdarzeń do wygenerowania
- usługa w warstwie uslugi/: pobiera dane, woła domenę, zapisuje z ON CONFLICT DO NOTHING
- klucz naturalny zdarzenia: (typ, encja_id, data_zdarzenia). Uruchomienie generatora
  trzy razy tego samego dnia MUSI dać ten sam efekt co jedno uruchomienie
- zadanie APScheduler: raz na dobę o 6:00 czasu lokalnego
- endpoint administracyjny do ręcznego uruchomienia (przydatny w testach i przy debugowaniu)

Test obowiązkowy: trzykrotne uruchomienie generatora na tych samych danych
tworzy dokładnie tyle samo zdarzeń co jednokrotne.
```

**DoD:** test idempotencji przechodzi, wszystkie typy zdarzeń z tabeli w sekcji 6 pokryte testami.

---

### E4. API i uwierzytelnianie

**Prompt:**
```
Zbuduj warstwę API pod /api/v1/ oraz uwierzytelnianie.

Auth:
- logowanie hasłem, Argon2id, sesje w ciasteczkach HttpOnly + SameSite=Lax
- role: podglad, operator, zarzadca, administrator (wg sekcji 7.9 koncepcji)
- blokada konta po 5 nieudanych próbach na 15 minut
- wymuszona zmiana hasła przy pierwszym logowaniu
- zależność FastAPI sprawdzająca rolę na każdym chronionym endpoincie

API:
- CRUD: budynki, lokale, najemcy, okresy najmu, składniki opłat, zabezpieczenia, przeglądy
- GET /api/v1/lokale z filtrowaniem (budynek, status, zakres daty końca, waloryzacja,
  kompletność), sortowaniem, paginacją i wyszukiwaniem pełnotekstowym
- GET /api/v1/lokale/{id}/stan?na_dzien=YYYY-MM-DD zwracający stan efektywny
- GET /api/v1/zdarzenia z filtrami i akcjami: oznacz obsłużone, odrocz, przypisz
- każda zmiana danych zapisuje wpis w audit_log
- optimistic locking: konflikt wersji zwraca 409 z aktualnym stanem

Testy API dla ról: sprawdź, że podglad NIE może modyfikować danych.
```

**DoD:** `/docs` (OpenAPI) kompletne, testy autoryzacji przechodzą dla każdej roli, konflikt wersji zwraca 409.

---

### E5. Dashboard

**Prompt:**
```
Zbuduj ekran Dashboard wg docs/system-najem-koncepcja.md, sekcja 7.1.

- TanStack Table: sortowanie, filtry, wybór kolumn, wirtualizacja przy 500+ wierszach
- filtry: budynek, status, kwartał/miesiąc/rok zakończenia, waloryzacja, kompletność
- wyszukiwarka pełnotekstowa z debounce
- pasek kompletności profilu w wierszu
- licznik alertów u góry, klikalny, prowadzi do kokpitu terminów
- eksport widocznego zestawu do XLSX
- zapisane widoki (nazwane zestawy filtrów, per użytkownik)
- przełącznik: tabela / kafelki
- pełna obsługa z klawiatury i skróty na najczęstsze filtry
- stany: ładowanie, pusty, błąd, każdy zaprojektowany, nie domyślny

Formatowanie polskie przez wspólne funkcje z src/funkcje/format.ts.
Klient API generowany z OpenAPI, nie pisany ręcznie.
```

**DoD:** filtrowanie po każdym wymiarze ze specyfikacji działa, eksport daje poprawny plik, tabela nie zacina się na 1000 wierszy.

---

### E6. Profil lokalu i kokpit terminów

**Prompt:**
```
Zbuduj dwa ekrany:

1. Profil lokalu (sekcja 7.2 koncepcji): zakładki Przegląd, Najemca, Finanse,
   Zabezpieczenia, Przeglądy, Dokumenty, Historia, Zdarzenia.
   Zasada twarda: każda wartość pochodząca z dokumentu jest klikalna i prowadzi
   do dokumentu źródłowego. Wartości niezatwierdzone wyróżnione wizualnie.
   Zakładka Historia: oś czasu zmian parametrów z informacją, z jakiego dokumentu wynikają.

2. Kokpit terminów (sekcja 7.3): zdarzenia pogrupowane wg pilności,
   akcje: obsłużone, odrocz z notatką, przypisz, przejdź do lokalu.
   Filtry: budynek, typ zdarzenia, przypisanie.
```

**DoD:** przejście z alertu do lokalu i z liczby do dokumentu działa w obie strony.

---

### E7. Dokumenty i import z Excela

**Prompt:**
```
Dwie rzeczy:

1. Obsługa dokumentów:
- upload z walidacją: limit rozmiaru, biała lista MIME sprawdzana po zawartości pliku
  (nie po rozszerzeniu), nazwa generowana, katalog poza obszarem serwowanym przez web
- deduplikacja po SHA-256 z komunikatem "ten dokument już jest w systemie przy lokalu X"
- hierarchia: przypisanie aneksu do umowy nadrzędnej
- podgląd PDF w przeglądarce (pdf.js)
- pobieranie z kontrolą uprawnień i wpisem do audytu

2. Import startowy z Excela:
- kreator: wgraj plik → zmapuj kolumny na pola systemu → podgląd → import
- walidacja przed zapisem, raport błędów z numerami wierszy
- import transakcyjny: albo cały plik, albo nic
- możliwość powtórzenia importu bez duplikowania danych
```

**DoD:** import przykładowego arkusza z celowo wprowadzonymi błędami daje czytelny raport i nie zapisuje niczego połowicznie.

---

### E8. Waloryzacja roczna

**Prompt:**
```
Zbuduj ekran waloryzacji rocznej wg sekcji 7.6 koncepcji, oparty o regułę R2 z E2.

- panel wprowadzania wskaźnika (wartość, rodzaj, rok)
- lista umów objętych waloryzacją z wyliczoną propozycją nowego czynszu
- umowy wyłączone z waloryzacji pokazane z powodem wyłączenia
- zbiorcze zatwierdzenie z podglądem sumy zmian
- zatwierdzenie tworzy nowe wiersze ParametrWartosc od miesiąca waloryzacji
- po waloryzacji: automatyczne zdarzenie "weksel do przeliczenia" dla umów,
  gdzie wartość weksla jest wielokrotnością czynszu
- eksport listy zmian do XLSX (do powiadomień dla najemców)

Operacja w jednej transakcji, z możliwością wycofania przed zatwierdzeniem.
```

**DoD:** waloryzacja na zestawie testowym daje kwoty co do grosza zgodne z ręcznym wyliczeniem.

---

### E9. Pipeline dokumentu: OCR i ekstrakcja regułowa

**Warunek wstępny:** rozstrzygnięty punkt R z sekcji 1.1 (sprzęt, model, licencja).

**Prompt:**
```
Zbuduj pipeline przetwarzania dokumentu wg sekcji 4.3 koncepcji.
Worker w tle (RQ + Redis), bo przetwarzanie trwa minuty, nie sekundy.

Etapy:
1. normalizacja: PDF natywny (pdfplumber) lub DOCX (python-docx) do tekstu
   z zachowaniem pozycji słów (strona, współrzędne), potrzebne do podświetlania
2. OCR dla skanów: Tesseract z językiem pol, z oceną jakości i ostrzeżeniem
   przy niskiej pewności
3. segmentacja na paragrafy i sekcje, przetwarzany CAŁY dokument
   (adres do korespondencji często jest na ostatniej stronie)
4. ekstrakcja regułowa: kwoty, daty, powierzchnia, terminy płatności
   ("do 10-tego dnia"), wielokrotności ("czterokrotność czynszu"), NIP/REGON/KRS
5. wynik: lista propozycji ParametrWartosc ze statusem "zaproponowana",
   każda z pewnością i lokalizacją w dokumencie

Zero wywołań sieciowych na zewnątrz. Sprawdź to testem.
Status przetwarzania widoczny w interfejsie, z możliwością ponowienia.
```

**DoD:** na 10 realnych (zanonimizowanych) umowach ekstrakcja regułowa trafia w kwoty i daty w większości przypadków, a każda propozycja ma poprawną lokalizację w dokumencie.

---

### E10. Ekran weryfikacji

**Prompt:**
```
Zbuduj ekran weryfikacji ekstrakcji wg sekcji 7.5 koncepcji.

- układ dwukolumnowy: po lewej podgląd dokumentu, po prawej lista propozycji
- kliknięcie propozycji przewija dokument do fragmentu źródłowego i podświetla go
- akcje: zatwierdź, popraw (z edycją wartości), odrzuć, oznacz jako niejednoznaczne
- skróty klawiszowe: Enter zatwierdza, Tab przechodzi dalej, Shift+Tab wstecz,
  cyfry wybierają akcję. Cały przepływ ma być obsługiwalny bez myszki
- "zatwierdź wszystkie o pewności powyżej X procent" z podglądem, czego dotyczy
- wskaźnik postępu: ile propozycji z ilu zweryfikowanych
- dla aneksu: widok różnicowy (obecnie / po aneksie) zamiast surowych wartości,
  z zaznaczeniem wartości przeliczonych automatycznie

Ten ekran decyduje o tym, czy migracja archiwum się skończy. Optymalizuj pod szybkość.
```

**DoD:** weryfikacja jednej umowy zajmuje poniżej dwóch minut, cały przepływ działa z klawiatury.

---

### E11. Model lokalny do zapisów opisowych

**Prompt:**
```
Dodaj warstwę 2 ekstrakcji: lokalny model językowy dla zapisów, których nie da się
złapać regułami: zasady waloryzacji, zakres przeglądów, warunki wypowiedzenia.

- integracja z Ollama uruchomionym lokalnie, adres z konfiguracji
- prompty z wymuszonym wyjściem w JSON o zdefiniowanym schemacie, walidacja Pydantic
- fallback: jeśli model nie odpowiada lub zwraca niepoprawny JSON, pole zostaje puste
  ze statusem "do wprowadzenia ręcznie". System NIGDY nie zgaduje.
- pomiar czasu przetwarzania i logowanie, żeby dało się ocenić wydajność
- test integracyjny sprawdzający, że aplikacja NIE wychodzi poza localhost

Dodaj też zapis poprawek pracowników z ekranu weryfikacji do osobnej tabeli.
To będzie materiał do oceny i poprawiania jakości ekstrakcji.
```

**DoD:** brak modelu nie wywala aplikacji, tylko degraduje ją do wprowadzania ręcznego. Test izolacji sieciowej przechodzi.

---

### E12. Raporty, wdrożenie, dopięcie

**Prompt:**
```
Domknij projekt:

1. Raporty (sekcja 7.7 koncepcji): umowy kończące się w okresie, przychód miesięczny
   wg budynków, obłożenie, zabezpieczenia do rozliczenia, harmonogram przeglądów,
   luki w danych. Eksport XLSX i CSV.

2. Powiadomienia e-mail: dzienne lub tygodniowe podsumowanie zdarzeń,
   przez wewnętrzny SMTP, konfigurowalne per użytkownik.

3. Wdrożenie:
   - docker-compose.prod.yml z healthchecks i restart policy
   - skrypt backupu: pg_dump + katalog dokumentów, z rotacją
   - skrypt odtworzenia z backupu (i instrukcja jego przetestowania)
   - endpoint /health rozszerzony o stan bazy, workera i wolnego miejsca na dysku
   - instrukcja wdrożenia w README: od czystego serwera do działającej aplikacji
   - lista portów i reguł firewalla, z domyślną blokadą ruchu wychodzącego

4. Testy E2E (Playwright) na krytycznych ścieżkach: logowanie, filtrowanie na dashboardzie,
   wejście w profil, weryfikacja dokumentu, waloryzacja.
```

**DoD:** wdrożenie na czystej maszynie wg README działa. Backup odtworzony na czystej maszynie daje działający system z danymi.

---

## 7. Testy: co i na jakim poziomie

| Poziom | Czego dotyczy | Ile |
|---|---|---|
| **Jednostkowe, domena** | reguły biznesowe, pieniądze, kalendarz, stan efektywny | najwięcej, powyżej 90 procent pokrycia, to jest priorytet |
| **Integracyjne, repozytoria** | zapytania czasowe, indeksy, migracje | średnio, głównie zapytania o stan efektywny |
| **API** | autoryzacja per rola, walidacja wejścia, kody błędów | średnio, obowiązkowo testy ról |
| **Frontend jednostkowe** | funkcje formatujące, walidacja NIP, logika filtrów | mało, tylko logika |
| **E2E** | pięć krytycznych ścieżek | mało, ale muszą działać |

**Przypadki brzegowe, które muszą mieć testy:**

- umowa bez protokołu przekazania (data zakończenia nieustalona)
- aneks obowiązujący wstecz
- dwa aneksy zmieniające ten sam parametr z różnymi datami
- waloryzacja w roku, w którym była też zmiana stawki aneksem
- termin płatności wypadający w święto ruchome
- luty w roku przestępnym
- zmiana najemcy w trakcie miesiąca
- polisa dostarczona po terminie
- kwota z groszami mnożona przez wskaźnik waloryzacji (zaokrąglanie)
- dwie osoby edytujące ten sam profil (konflikt wersji)

---

## 8. Kolejność, w jakiej to ma sens robić

```
E0  fundament            ──┐
E0.5 konfiguracja CC     ──┘  tydzień 1

E1  model danych         ──┐
E2  domena i reguły      ──┤  tygodnie 2 do 4   ← tu leży wartość projektu
E3  generator zdarzeń    ──┘

E4  API i auth           ──┐
E5  dashboard            ──┤  tygodnie 5 do 7
E6  profil i kokpit      ──┘

        ↓ TU SYSTEM JUŻ DZIAŁA I MOŻNA GO POKAZAĆ ↓

E7  dokumenty i import   ──┐  tydzień 8
E8  waloryzacja          ──┘

        ↓ TU SYSTEM JEST UŻYTECZNY W CODZIENNEJ PRACY ↓

E9  OCR i ekstrakcja     ──┐
E10 weryfikacja          ──┤  tygodnie 9 do 12
E11 model lokalny        ──┘

E12 raporty i wdrożenie  ──   tydzień 13
```

Dwa momenty przełomowe są zaznaczone celowo. Po E6 masz coś, co można pokazać i o czym można rozmawiać z użytkownikami. Po E8 masz coś, czego można używać zamiast Excela. Wszystko po E8 to poprawa efektywności, nie warunek działania.

To ma znaczenie przy rozmowie o budżecie i priorytetach: **AI jest ostatnią trzecią projektu, nie pierwszą.**

---

## 9. Checklisty

### 9.1 Przed pierwszą sesją

- [ ] Odpowiedzi na pytania A do H z sekcji 1.1
- [ ] Dostęp do 10 do 15 realnych umów, aneksów i protokołów (mogą być zanonimizowane)
- [ ] Wiadomo, czy jest istniejący Excel do zaimportowania i jak wygląda
- [ ] Znane wymagania sprzętowe serwera i czy będzie GPU
- [ ] Zatwierdzone decyzje D1 do D6 z dokumentu koncepcji
- [ ] Repo utworzone, git skonfigurowany

### 9.2 Przed każdą sesją

- [ ] `/clear`
- [ ] Przeczytany `docs/postep.md`
- [ ] Nowa gałąź
- [ ] Zakres tej sesji spisany w jednym zdaniu
- [ ] `/plan` przed implementacją

### 9.3 Przed commitem etapu

- [ ] `pytest` zielone
- [ ] `mypy` na domenie bez błędów
- [ ] `ruff check` i `ruff format` czyste
- [ ] Testy frontendu zielone
- [ ] Migracja Alembic przejrzana ręcznie, `downgrade` działa
- [ ] Brak `float` przy kwotach, brak `TODO`, brak sekretów
- [ ] Podagent `recenzent` uruchomiony, znaleziska obsłużone
- [ ] `docs/postep.md` zaktualizowany

### 9.4 Przed wdrożeniem

- [ ] Backup wykonany i **odtworzony na czystej maszynie**
- [ ] Ruch wychodzący z serwera zablokowany na poziomie firewalla
- [ ] Konta testowe usunięte, hasła domyślne zmienione
- [ ] Role sprawdzone na realnych użytkownikach
- [ ] Instrukcja dla użytkowników napisana (jedna strona wystarczy)
- [ ] Ustalone, kto zgłasza problemy i do kogo
- [ ] Test odtworzenia z backupu wpisany w kalendarz jako cykliczny

---

## 10. Ryzyka specyficzne dla pracy z Claude Code

| Ryzyko | Objaw | Przeciwdziałanie |
|---|---|---|
| Rozjazd między kodem a dokumentacją | koncepcja mówi jedno, kod robi drugie | `/przeglad-etapu` aktualizuje koncepcję, ADR-y w `docs/decyzje/` |
| Ciche przebudowanie działającej rzeczy | "przy okazji poprawiłem X" | wąski zakres promptu, `git diff` przed commitem, `/rewind` |
| Wygenerowana migracja niszczy dane | `DROP COLUMN` w autogenerate | czytanie każdej migracji przed zapisem, backup przed migracją produkcyjną |
| Reguła biznesowa wygląda dobrze i liczy źle | brak testów przypadków brzegowych | testy przed implementacją, skill `/nowa-regula` wymusza kolejność |
| Przestarzała składnia bibliotek | SQLAlchemy 1.x zamiast 2.0 | Context7 przez MCP, jawne wskazanie wersji w `CLAUDE.md` |
| Utrata wątku między sesjami | powtarzanie ustaleń, sprzeczne decyzje | `docs/postep.md`, ADR-y, małe etapy |
| Rozdęte CLAUDE.md, spadek posłuszeństwa | Claude ignoruje reguły | poniżej 200 linii, reszta do `.claude/rules/` z `paths` |
| Klikanie "zezwól" bez czytania | przypadkowe destrukcyjne polecenie | allowlist w `permissions.allow`, deny na operacjach niszczących |

---

## 11. Co zrobić w tym tygodniu

1. Zebrać odpowiedzi na pytania A do H (rozmowa z księgowością lub administracją, godzina).
2. Zdobyć 10 do 15 realnych dokumentów i przejrzeć je ręcznie pod kątem: VAT, waluta, waloryzacja, protokoły przekazania.
3. Zrobić E0 i E0.5. To jedna sesja, może dwie.
4. Dopiero potem E1.

Punkty 1 i 2 są nudne i kuszą do pominięcia. To dokładnie ten moment, w którym takie projekty się wykrzaczają.

---

*Dokument roboczy, towarzyszy `system-najem-koncepcja.md`. Fakty o Claude Code zweryfikowane na oficjalnej dokumentacji w sierpniu 2026; narzędzie zmienia się szybko, więc przy rozbieżności ufaj `/help` i dokumentacji, nie temu plikowi.*

Źródła (dokumentacja Claude Code):
- [Jak Claude pamięta projekt: CLAUDE.md, rules, auto memory](https://code.claude.com/docs/en/memory)
- [Skille i komendy własne](https://code.claude.com/docs/en/skills)
- [Komendy wbudowane](https://code.claude.com/docs/en/commands)
- [Hooki](https://code.claude.com/docs/en/hooks)

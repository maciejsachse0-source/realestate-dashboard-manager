# System Zarządzania Umowami Najmu

## Koncepcja, model danych, architektura i mapa funkcji

**Wersja:** 0.1 (draft koncepcyjny)
**Data:** 25.08.2026
**Podstawa:** "Specyfikacja Wymagań: System do Zarządzania Umowami Najmu"
**Status:** dokument do dyskusji, nie jest jeszcze specyfikacją wdrożeniową

---

## 0. TL;DR (jeśli czytasz tylko jedno)

1. To **nie jest projekt "AI czyta umowy"**. To projekt **rejestru stanu umów**, do którego AI jest tylko jednym z kanałów zasilania danymi.
2. Sercem systemu jest jedna mechanika: **stan efektywny na dzień**. Każdy parametr umowy (stawka, data końca, powierzchnia) ma wartość, okres obowiązywania i źródło. Aneks nie nadpisuje, tylko dokłada nową wersję parametru. Dashboard zawsze pokazuje "co obowiązuje dziś", a historia zostaje nienaruszona.
3. Dane dzielą się na **dwa tory**: dane wyekstrahowane z dokumentu (warunki, kwoty, terminy) i dane poufne dopisywane ręcznie w programie (nazwa najemcy, NIP, adresy, kontakty). Dokumenty idące do ekstrakcji są pozbawione danych identyfikacyjnych.
4. Prawdziwą wartością dla pracownika nie jest tabela, tylko **kalendarz zdarzeń**: co wygasa, co się waloryzuje, czyja polisa nie dotarła, który przegląd przepadł. Tabela to widok. Alerty to produkt.
5. MVP nie zawiera AI. MVP to: baza + import dokumentów + profil lokalu + dashboard + alerty. Ekstrakcja wchodzi dopiero, gdy model danych jest sprawdzony na prawdziwych umowach.

---

## 1. Jak rozumiem problem

### 1.1 Co dzisiaj boli

Pracownik, żeby odpowiedzieć na proste pytanie ("kiedy kończy się umowa w 18A/12?", "czy ten najemca ma waloryzację?", "czy dostarczył polisę?"), musi:

- znaleźć właściwy plik umowy,
- sprawdzić, czy nie ma aneksu, który to zmienił,
- sprawdzić protokół przekazania, bo od niego liczy się okres najmu,
- przeczytać kilkanaście stron prawniczego tekstu, często kończąc na ostatniej stronie, gdzie schowany jest adres do korespondencji.

Czyli: **informacja istnieje, ale jest rozproszona po dokumentach i niemożliwa do przeszukania zbiorczo.** Nie da się zadać pytania "pokaż wszystkie umowy kończące się w Q2 2027", bo taka informacja nie żyje nigdzie poza czyjąś głową i Excelem, który jest nieaktualny.

### 1.2 Co system ma naprawdę zrobić

Zamienić **zbiór dokumentów** w **bazę stanu**.

| Dziś | Po wdrożeniu |
|---|---|
| Dokument to źródło prawdy, czytane ręcznie | Dokument to źródło dowodu, dane są w bazie i linkują do fragmentu dokumentu |
| Pytanie = przeszukanie plików | Pytanie = filtr na dashboardzie |
| Termin = ktoś pamięta albo nie | Termin = zdarzenie w kalendarzu z alertem |
| Aneks = kolejny plik obok | Aneks = zmiana stanu z datą obowiązywania |

### 1.3 Czego system NIE robi (świadome ograniczenie zakresu)

- Nie generuje umów ani aneksów.
- Nie fakturuje i nie księguje (może eksportować dane do systemu finansowego, ale nie zastępuje go).
- Nie jest repozytorium prawnym z obiegiem podpisów.
- Nie interpretuje prawa. Jeśli zapis jest niejednoznaczny, system oznacza go jako "do decyzji człowieka", a nie zgaduje.

---

## 2. Kluczowe decyzje projektowe

To są rozstrzygnięcia, które determinują cały resztę dokumentu. Warto je zatwierdzić lub odrzucić zanim cokolwiek powstanie.

### D1. Bytem centralnym jest LOKAL, nie umowa i nie najemca

Lokal jest jedyną rzeczą, która trwa. Najemcy się zmieniają, umowy wygasają, aneksy dochodzą. Lokal 18A/12 istnieje zawsze.

Konsekwencja: dashboard to lista lokali, a nie lista umów. Zmiana najemcy w lokalu to nowy okres najmu przypięty do tego samego lokalu. To automatycznie rozwiązuje wymóg ze specyfikacji: "nowy najemca automatycznie zastępuje w widoku nieaktywnego", bo widok domyślnie pokazuje aktywny okres najmu dla lokalu, a poprzedni ląduje w historii lokalu.

### D2. Parametry są wersjonowane w czasie, nie nadpisywane

Nie ma pola `stawka_za_m2` w tabeli umowy. Jest tabela wartości parametrów, gdzie każdy wiersz to: *jaki parametr, jaka wartość, od kiedy obowiązuje, z jakiego dokumentu pochodzi*.

Dzięki temu:
- aneks podnoszący stawkę = nowy wiersz od 01.03.2027, stary zostaje,
- da się odpowiedzieć na pytanie "jaka była stawka w maju 2025",
- audyt "skąd ta liczba" prowadzi zawsze do konkretnego dokumentu i strony.

To jest najważniejsza decyzja w całym projekcie. Bez niej obsługa aneksów zawsze będzie zlepkiem hacków.

### D3. Dwa tory danych: ekstrahowane i poufne

Zgodnie z ustaleniem: dokumenty poddawane ekstrakcji nie zawierają danych identyfikujących klienta.

| Tor A: z dokumentu | Tor B: ręcznie w programie |
|---|---|
| powierzchnia, stawka, czynsz | pełna nazwa firmy / imię i nazwisko |
| daty (zawarcia, przekazania, zakończenia) | NIP, REGON, KRS |
| terminy płatności poszczególnych składników | adres siedziby, adres do korespondencji |
| zasady waloryzacji | e-mail, telefon, osoby kontaktowe |
| kaucja, weksel, wymagana polisa | numery rachunków, dane wrażliwe |
| zakres przeglądów obciążających najemcę | |

Konsekwencja praktyczna: **profil najemcy i profil warunków to dwa osobne formularze.** Pracownik po imporcie umowy uzupełnia "kto to jest", system dostarcza "na jakich warunkach".

Konsekwencja bezpieczeństwa: nawet gdyby kiedyś rozważać mocniejszy model do ekstrakcji, obszar ryzyka jest ograniczony do tekstu bez danych osobowych. Nie zmienia to jednak wymogu ze specyfikacji: **na dziś zakładamy przetwarzanie wyłącznie lokalne** (patrz sekcja 8). Traktuję anonimizację jako drugą warstwę ochrony, nie jako furtkę do chmury.

### D4. Człowiek zatwierdza każdą liczbę, zanim trafi do bazy

Ekstrakcja proponuje, nie decyduje. Każda wyekstrahowana wartość ma status: `zaproponowana` → `zatwierdzona` / `poprawiona` / `odrzucona`. Do czasu zatwierdzenia wartość jest widoczna w interfejsie jako niepewna i nie wchodzi do alertów.

Powód: cena pomyłki jest asymetryczna. Źle odczytany termin płatności albo kwota kaucji kosztuje realne pieniądze i zaufanie do systemu. Jedna głośna pomyłka zabija adopcję narzędzia na rok.

### D5. Brak danych to informacja, nie pusta komórka

Jeśli data przekazania lokalu nie została jeszcze wprowadzona, system nie pokazuje pustego pola. Pokazuje status `brak protokołu przekazania` i wystawia zadanie. Dziury w danych są widoczne i policzalne, bo to one generują ryzyko.

### D6. Kompletność danych jest mierzona

Każdy lokal ma wskaźnik kompletności profilu (ile krytycznych pól jest wypełnionych i zatwierdzonych). Dashboard pozwala filtrować "pokaż lokale z niekompletnym profilem". To jedyny sposób, żeby migracja starych umów kiedykolwiek się skończyła.

---

## 3. Model domeny

### 3.1 Encje główne

```
BUDYNEK
  └── LOKAL  (nr, powierzchnia bazowa, typ, kondygnacja)
        └── OKRES_NAJMU  (jeden najemca, jeden ciąg umowny)
              ├── NAJEMCA (dane poufne, tor B)
              ├── DOKUMENT[]  (umowa, aneks, protokół, polisa, protokół z przeglądu)
              ├── PARAMETR_WARTOSC[]  (wersjonowane w czasie, tor A)
              ├── SKLADNIK_OPLATY[]  (czynsz, eksploatacja, media, parking)
              ├── ZABEZPIECZENIE[]  (kaucja, weksel, polisa)
              ├── OBOWIAZEK_PRZEGLADU[]
              └── ZDARZENIE[]  (generowane, terminowe)
```

### 3.2 Opis encji

**BUDYNEK**
`id`, `nazwa` (np. "18A"), `adres`, `aktywny`. Obecnie 3, planowany 4. Model musi zakładać dowolną liczbę, w tym budynek w budowie z lokalami jeszcze niewynajętymi.

**LOKAL**
`id`, `budynek_id`, `oznaczenie`, `powierzchnia_ewidencyjna`, `typ` (handlowy / biurowy / magazyn / miejsce postojowe), `status` (wolny / wynajęty / w trakcie wydania).

Uwaga: powierzchnia z ewidencji i powierzchnia z umowy potrafią się różnić. Trzymamy obie, a różnica jest sygnalizowana.

**OKRES_NAJMU** (kluczowa encja pośrednicząca)
`id`, `lokal_id`, `najemca_id`, `data_rozpoczecia`, `data_zakonczenia_planowana`, `data_zakonczenia_faktyczna`, `status` (przygotowanie / aktywna / wypowiedziana / zakończona), `okres_zawarcia` (np. 24 miesiące), `bazuje_na_dacie` (data zawarcia | data przekazania).

To tu żyje reguła: *okres najmu liczony jest od daty przekazania lokalu, nie od daty podpisania*. Pole `bazuje_na_dacie` mówi systemowi, którą datę wziąć do wyliczenia końca umowy.

**NAJEMCA** (tor B, dane poufne)
`id`, `nazwa_pelna`, `nip`, `regon`, `krs`, `adres_siedziby`, `adres_korespondencyjny`, `email`, `telefon`, `osoby_kontaktowe[]`, `notatki`.

Najemca jest osobnym bytem, nie polem w umowie, bo ten sam podmiot może wynajmować kilka lokali w kilku budynkach. Widok "wszystko co ma ten najemca" jest wtedy darmowy.

**DOKUMENT**
`id`, `okres_najmu_id`, `typ` (umowa | aneks | protokol_przekazania | protokol_zdawczy | polisa | protokol_przegladu | wypowiedzenie | inne), `numer`, `data_dokumentu`, `data_obowiazywania_od`, `plik_sciezka`, `hash`, `dokument_nadrzedny_id`, `status_przetworzenia`.

`dokument_nadrzedny_id` buduje hierarchię: aneks nr 2 wskazuje na umowę. To realizuje wymóg "system musi rozumieć hierarchię dokumentów".

**PARAMETR_WARTOSC** (mechanizm wersjonowania, serce systemu)

| pole | znaczenie |
|---|---|
| `okres_najmu_id` | do kogo należy |
| `klucz` | np. `stawka_m2`, `czynsz_podstawowy`, `powierzchnia`, `data_zakonczenia` |
| `wartosc` | wartość znormalizowana (liczba / data / bool / tekst) |
| `obowiazuje_od` | od kiedy ta wartość jest prawdą |
| `obowiazuje_do` | null = do odwołania |
| `dokument_zrodlowy_id` | z czego to wynika |
| `lokalizacja_w_dokumencie` | strona, paragraf, offset tekstu |
| `status_weryfikacji` | zaproponowana / zatwierdzona / poprawiona |
| ~~`zatwierdzil_uzytkownik_id`~~, `zatwierdzono_dnia` | ślad audytowy — została sama data, kolumny „kto" nie ma ([ADR 009](decyzje/009-usuniecie-logowania.md)) |

Zapytanie o "stan na dziś" to zawsze: weź dla każdego klucza wiersz, gdzie `obowiazuje_od <= dziś` i (`obowiazuje_do` jest null lub `>= dziś`), o najpóźniejszym `obowiazuje_od`.

**SKLADNIK_OPLATY**
`id`, `okres_najmu_id`, `nazwa` (czynsz podstawowy / opłata eksploatacyjna / media / parking / fundusz remontowy), `kwota` lub `sposob_wyliczenia`, `dzien_platnosci_miesiaca`, `czy_waloryzowany`, `okres_rozliczeniowy` (miesięczny / kwartalny), `uwagi`.

To rozwiązuje wymóg rozróżnienia terminów: czynsz do 10-go, eksploatacja do 14-go albo 28-go. Każdy składnik ma własny dzień płatności, bo w praktyce prawie nigdy nie są takie same.

**ZABEZPIECZENIE**
`id`, `okres_najmu_id`, `rodzaj` (kaucja | weksel | gwarancja bankowa | polisa), `wymagana_wartosc`, `sposob_wyliczenia` (np. "czterokrotność czynszu"), `status` (wymagane / dostarczone / zwrócone / brak), `data_wymagalnosci`, `data_dostarczenia`, `dokument_id`, `data_waznosci` (dla polis).

Polisa ma dodatkowo `data_waznosci`, bo polisa wygasa co rok i trzeba jej pilnować cyklicznie, a nie raz.

**OBOWIAZEK_PRZEGLADU**
`id`, `lokal_id`, `okres_najmu_id`, `element` (brama | gaśnice | butle | hydranty wewnątrzlokalowe | instalacja elektryczna | wentylacja | ...), `kto_obciazany` (najemca / wynajmujący), `czestotliwosc_miesiace`, `ostatni_przeglad_data`, `nastepny_przeglad_data`, `protokol_dokument_id`, `status`.

Element jest osobnym wierszem, a nie jednym polem tekstowym, bo specyfikacja wprost wymaga "precyzyjnego wyodrębnienia elementów". Dopiero wtedy da się zrobić widok "wszystkie gaśnice do przeglądu w tym kwartale".

**ZDARZENIE** (generowane, nie wpisywane)
`id`, `typ`, `encja_zrodlowa`, `data_zdarzenia`, `waga` (informacja / ostrzeżenie / krytyczne), `status` (otwarte / obsłużone / odroczone), `przypisany_uzytkownik`, `notatka`.

Zdarzenia są produktem reguł z sekcji 5. Nikt ich nie tworzy ręcznie, poza wyjątkiem "zadanie własne".

**UZYTKOWNIK, LOG_AUDYTU**
Kto, kiedy, co zmienił, ze starej wartości na nową. Bez wyjątków, także dla zmian ręcznych.

### 3.3 Relacje, które nie są oczywiste

- **Najemca : Lokal to relacja wiele do wielu, rozłożona w czasie.** Nie da się jej trzymać jako pola. Stąd OKRES_NAJMU.
- **Aneks może dotyczyć więcej niż jednego parametru.** Jeden dokument generuje N wierszy PARAMETR_WARTOSC.
- **Aneks może dodać lokal** (np. dodanie miejsca postojowego). Wtedy powstaje albo nowy OKRES_NAJMU pod tą samą umową, albo nowy SKLADNIK_OPLATY, w zależności od tego, czy miejsce postojowe jest osobnym lokalem w ewidencji. To trzeba rozstrzygnąć na realnych danych.
- **Protokół przekazania jest dokumentem umowy, ale zasila datę, od której liczy się wszystko inne.** Dlatego jego brak jest traktowany jako blokada kompletności profilu.

---

## 4. Architektura

### 4.1 Stack

Zgodnie z decyzją: **lokalna aplikacja webowa** uruchamiana na wewnętrznym serwerze firmy.

| Warstwa | Wybór | Uzasadnienie |
|---|---|---|
| Backend | Python + FastAPI | naturalny dla przetwarzania dokumentów i modeli lokalnych, dobrze się testuje |
| Baza | PostgreSQL (docelowo), SQLite (prototyp) | potrzebne są zapytania czasowe i pełnotekstowe, Postgres to daje |
| ORM / migracje | SQLAlchemy + Alembic | model będzie się zmieniał, migracje są obowiązkowe od dnia 1 |
| Frontend | React (Next.js lub Vite) + biblioteka tabel z filtrowaniem | dashboard to w 80% jedna bardzo dobra tabela |
| Kolejka zadań | prosty worker w tle (RQ / Celery / APScheduler) | OCR i ekstrakcja nie mogą blokować requestu |
| Pliki | katalog na serwerze + hash w bazie | brak chmury, backup na poziomie infrastruktury |
| ~~Auth~~ | ~~logowanie wewnętrzne lub integracja z AD/LDAP~~ | **NIEZREALIZOWANE.** Logowanie zbudowano w E4 i usunięto 28.08.2026 — [ADR 009](decyzje/009-usuniecie-logowania.md) |

### 4.2 Warstwy

```
┌─────────────────────────────────────────────┐
│  UI (React)                                  │
│  Dashboard | Profil lokalu | Kokpit terminów │
│  Import | Weryfikacja | Admin                │
└────────────────────┬────────────────────────┘
                     │ REST / JSON
┌────────────────────┴────────────────────────┐
│  API (FastAPI)                               │
│  autoryzacja, walidacja, serializacja        │
└────────────────────┬────────────────────────┘
┌────────────────────┴────────────────────────┐
│  WARSTWA DOMENOWA (tu żyje cała logika)      │
│  ┌────────────┬────────────┬──────────────┐ │
│  │ stan       │ reguły     │ generator    │ │
│  │ efektywny  │ biznesowe  │ zdarzeń      │ │
│  │ na dzień   │ (waloryza- │ (scheduler)  │ │
│  │            │  cja itd.) │              │ │
│  └────────────┴────────────┴──────────────┘ │
└────────────────────┬────────────────────────┘
┌────────────────────┴────────────────────────┐
│  PIPELINE DOKUMENTU (asynchroniczny)         │
│  ingest → OCR → segmentacja → ekstrakcja     │
│  → propozycje → kolejka weryfikacji          │
└────────────────────┬────────────────────────┘
┌────────────────────┴────────────────────────┐
│  DANE: PostgreSQL + repozytorium plików      │
└─────────────────────────────────────────────┘
```

Zasada: **żadna reguła biznesowa nie mieszka w komponencie React ani w zapytaniu SQL.** Wyliczenie daty końca umowy, waloryzacji czy terminu polisy to funkcje w warstwie domenowej, pokryte testami. UI tylko je wyświetla.

### 4.3 Pipeline dokumentu

```
1. WRZUCENIE
   pracownik wgrywa plik i wskazuje: typ dokumentu + lokal/okres najmu
   (albo "nowy okres najmu")
        ↓
2. NORMALIZACJA
   PDF/DOCX → tekst. Jeśli skan: OCR lokalny (Tesseract / PaddleOCR)
   zapis: tekst + mapa pozycji (strona, offset) do późniejszego podświetlania
        ↓
3. SEGMENTACJA
   podział na paragrafy i sekcje, rozpoznanie nagłówków
   ważne: adres do korespondencji często siedzi na ostatniej stronie,
   więc segmentacja musi objąć CAŁY dokument, nie pierwsze 5 stron
        ↓
4. EKSTRAKCJA (hybryda)
   warstwa 1: reguły i wyrażenia regularne dla rzeczy przewidywalnych
              (kwoty, daty, NIP, "do 10-tego dnia miesiąca", "czterokrotność")
   warstwa 2: lokalny model językowy dla rzeczy opisowych
              (zakres przeglądów, zasady waloryzacji, warunki wypowiedzenia)
   wynik: lista propozycji, każda z: klucz, wartość, pewność, cytat + lokalizacja
        ↓
5. KOLEJKA WERYFIKACJI
   ekran side-by-side: po lewej podgląd dokumentu z podświetlonym fragmentem,
   po prawej formularz z proponowaną wartością
   pracownik: zatwierdź / popraw / odrzuć / oznacz "niejednoznaczne"
        ↓
6. COMMIT
   zatwierdzone wartości → PARAMETR_WARTOSC z datą obowiązywania
   przeliczenie stanu efektywnego → regeneracja zdarzeń dla tego okresu najmu
        ↓
7. AUDYT
   log: kto zatwierdził, co zmienił względem propozycji
   (te poprawki są jednocześnie zbiorem uczącym dla ulepszania reguł)
```

Punkt 7 jest niedoceniany: **poprawki pracowników to najcenniejszy zasób projektu.** Po 200 umowach wiadomo dokładnie, gdzie ekstrakcja się myli i co poprawić.

### 4.4 Obsługa aneksu (przepływ krytyczny)

```
Aneks nr 3 do umowy X, data obowiązywania 01.03.2027
   ↓
system rozpoznaje: dokument nadrzędny = umowa X
   ↓
ekstrakcja zwraca zmiany: stawka_m2: 52 → 58, data_zakonczenia: 2027-12-31 → 2029-12-31
   ↓
ekran weryfikacji pokazuje DIFF, nie surowe wartości:
   ┌──────────────────┬─────────────┬─────────────┐
   │ parametr         │ obecnie     │ po aneksie  │
   ├──────────────────┼─────────────┼─────────────┤
   │ stawka za m2     │ 52,00 zł    │ 58,00 zł    │
   │ czynsz podst.    │ 6 240 zł    │ 6 960 zł ⟳  │  ⟳ = przeliczone
   │ data zakończenia │ 31.12.2027  │ 31.12.2029  │
   └──────────────────┴─────────────┴─────────────┘
   ↓
zatwierdzenie → domknięcie starych wierszy (obowiazuje_do = 28.02.2027)
             → dodanie nowych (obowiazuje_od = 01.03.2027)
   ↓
dashboard pokazuje nową wartość, historia lokalu pokazuje obie
```

Pokazywanie diffu zamiast wartości to nie kosmetyka. Pracownik weryfikujący aneks myśli kategoriami "co się zmieniło", nie "jakie są warunki".

---

## 5. Reguły biznesowe

To jest ta część, która decyduje o tym, czy system jest użyteczny, czy jest tylko ładniejszym Excelem.

### R1. Wyliczanie daty zakończenia umowy

```
jeśli okres_najmu.bazuje_na_dacie = "data przekazania":
    jeśli protokół przekazania istnieje i data jest zatwierdzona:
        data_zakonczenia = data_przekazania + okres_zawarcia
    inaczej:
        data_zakonczenia = NIEUSTALONA
        → zdarzenie: "brak protokołu przekazania, nie można wyliczyć końca umowy"
inaczej:
    data_zakonczenia = data_zawarcia + okres_zawarcia
```

Data zakończenia nigdy nie jest zgadywana. Lepiej pokazać "nieustalona" niż fałszywy termin.

### R2. Waloryzacja

Model przechowuje: `czy_podlega`, `miesiac_waloryzacji` (styczeń / luty / miesiąc rocznicy), `wskaznik` (GUS r/r, GUS średnioroczny, stała stawka %), `data_pierwszej_waloryzacji`, `historia_waloryzacji[]`.

Przebieg roczny:

```
15 stycznia: GUS publikuje wskaźnik
   ↓
administrator wprowadza wskaźnik JEDEN RAZ w panelu (np. "GUS 2026 r/r = 3,7%")
   ↓
system znajduje wszystkie okresy najmu z czy_podlega = TAK
   ↓
dla każdego wylicza propozycję: nowy czynsz = stary × (1 + wskaźnik)
   ↓
lista propozycji do zbiorczego zatwierdzenia (jeden ekran, checkboxy)
   ↓
zatwierdzone → nowe wiersze PARAMETR_WARTOSC od miesiąca waloryzacji
   ↓
opcjonalnie: generowanie listy powiadomień do najemców
```

Kluczowe: wskaźnik wprowadzany raz, efekt na wszystkich umowach. Dziś to prawdopodobnie kilkanaście godzin ręcznej pracy raz do roku.

### R3. Terminy płatności

Każdy składnik opłaty ma własny `dzien_platnosci_miesiaca`. System nie pilnuje, czy zapłacono (to rola księgowości), ale:
- pokazuje kalendarz "co jest płatne którego dnia",
- pozwala odpowiedzieć "kto płaci do 28-go" bez czytania umów,
- eksportuje harmonogram do systemu finansowego.

Jeśli dzień płatności wypada w weekend lub święto, system pokazuje faktyczny dzień roboczy obok umownego.

### R4. Kaucja

```
status: wymagana → wpłacona (data, kwota, dokument) → zwrócona / zatrzymana
```
Zdarzenia: kaucja wymagana a niewpłacona po X dniach od przekazania. Kaucja do zwrotu w ciągu Y dni od zakończenia najmu (to jest termin, o którym łatwo zapomnieć i który generuje roszczenia).

### R5. Weksel

Pola: `czy_wystawiony` (T/N), `sposob_wyliczenia_wartosci` (np. "czterokrotność czynszu"), `wartosc_wyliczona`, `data_wystawienia`, `miejsce_przechowywania`, `data_zwrotu`.

Uwaga: jeśli wartość weksla jest wielokrotnością czynszu, a czynsz podlega waloryzacji, to **wartość weksla należy przeliczać po każdej waloryzacji**. System powinien o tym przypominać, bo to typowe miejsce, gdzie zabezpieczenie po kilku latach przestaje pokrywać ekspozycję.

### R6. Polisa ubezpieczeniowa

```
wymagana kwota polisy: z umowy
termin dostarczenia: zwykle relatywny, np. "14 dni od dnia przekazania lokalu"
   → system wylicza konkretną datę na podstawie daty przekazania
data ważności polisy: z dokumentu polisy
   → cykliczne przypomnienie 30 dni przed wygaśnięciem
```

Trzy osobne zdarzenia: polisa niedostarczona w terminie, polisa wygasa, polisa na kwotę niższą niż wymagana.

### R7. Przeglądy okresowe

```
dla każdego elementu (brama, gaśnice, butle, hydranty, ...):
    następny_przegląd = ostatni_przegląd + częstotliwość
    jeśli następny_przegląd < dziś + 30 dni → zdarzenie
    jeśli następny_przegląd < dziś → zdarzenie krytyczne (przeterminowany)
```
Po wgraniu protokołu z przeglądu system aktualizuje `ostatni_przeglad_data` i przelicza następny termin. Widok zbiorczy: "wszystkie przeglądy w budynku 18A w tym kwartale", bo w praktyce zleca się je hurtowo.

### R8. Zmiana najemcy w lokalu

```
stary okres najmu: status → "zakończona", data_zakonczenia_faktyczna
   ↓
protokół zdawczy → checklista zwrotu (kaucja, klucze, stan lokalu)
   ↓
lokal: status → "wolny"
   ↓
nowy okres najmu → lokal: status → "wynajęty"
   ↓
dashboard: automatycznie pokazuje nowego najemcę
historia lokalu: oba okresy widoczne w osi czasu
```

### R9. Kompletność profilu

Pola krytyczne (bez nich profil jest niekompletny): najemca, powierzchnia, data przekazania, data zakończenia, czynsz, terminy płatności, status kaucji, status polisy.

`kompletnosc = zatwierdzone_pola_krytyczne / wszystkie_pola_krytyczne`

Widoczne jako pasek przy każdym lokalu i jako filtr na dashboardzie.

---

## 6. Katalog zdarzeń i alertów

To jest lista, którą warto skonfrontować z pracownikami, bo pewnie mają jeszcze trzy własne.

| Zdarzenie | Kiedy | Waga |
|---|---|---|
| Zbliża się koniec umowy | 180 / 90 / 60 / 30 dni przed | ostrzeżenie, rosnąca |
| Minął termin wypowiedzenia bez decyzji | data końca minus okres wypowiedzenia | krytyczne |
| Umowa wygasła, brak następczej | dzień po dacie zakończenia | krytyczne |
| Zbliża się waloryzacja | 30 dni przed miesiącem waloryzacji | informacja |
| Opublikowano wskaźnik GUS, są umowy do przeliczenia | po wprowadzeniu wskaźnika | ostrzeżenie |
| Polisa niedostarczona w terminie | dzień po terminie dostarczenia | krytyczne |
| Polisa wygasa | 30 dni przed | ostrzeżenie |
| Polisa poniżej wymaganej kwoty | przy zatwierdzaniu polisy | ostrzeżenie |
| Kaucja niewpłacona | X dni po przekazaniu | krytyczne |
| Kaucja do zwrotu | po zakończeniu najmu | ostrzeżenie |
| Weksel do przeliczenia po waloryzacji | po zatwierdzeniu waloryzacji | informacja |
| Przegląd zbliża się | 30 dni przed | ostrzeżenie |
| Przegląd przeterminowany | po terminie | krytyczne |
| Brak protokołu przekazania | po 14 dniach od startu umowy | ostrzeżenie |
| Profil lokalu niekompletny | stale, dopóki trwa | informacja |
| Dokument czeka na weryfikację | po ekstrakcji | informacja |

Kanały: panel w aplikacji (zawsze), e-mail podsumowujący (dzienny lub tygodniowy, konfigurowalnie). Bez wyskakujących powiadomień, bo w tego typu pracy szum zabija uwagę szybciej niż brak alertu.

---

## 7. Mapa funkcji: gdzie co siedzi w interfejsie

### 7.1 Ekran 1: DASHBOARD (widok zbiorczy)

Ekran startowy programu. Jedna tabela lokali, bardzo dobra tabela.

```
┌───────────────────────────────────────────────────────────────────────┐
│ [ALERTY: 3 krytyczne · 11 ostrzeżeń]              [+ Nowy dokument]   │
├───────────────────────────────────────────────────────────────────────┤
│ Filtry: Budynek ▾ | Status ▾ | Koniec umowy: Q/M/Rok ▾ |             │
│         Waloryzacja ▾ | Kompletność ▾ | Szukaj: [__________]          │
├──────┬──────────┬─────────┬──────┬────────┬─────────┬────────┬───────┤
│ Lokal│ Najemca  │ Pow. m² │Czynsz│ Koniec │ Walory- │ Polisa │ Kompl.│
│      │          │         │      │ umowy  │  zacja  │        │       │
├──────┼──────────┼─────────┼──────┼────────┼─────────┼────────┼───────┤
│18A/12│ [nazwa]  │  124,5  │6 960 │31.12.29│ tak, I  │  ✓     │ ████░ │
│18A/14│ [nazwa]  │   88,0  │4 400 │30.06.27│ nie     │  ⚠ brak│ ███░░ │
│ 22/03│ WOLNY    │  210,0  │  ,   │   ,    │   ,     │   ,    │  ,    │
└──────┴──────────┴─────────┴──────┴────────┴─────────┴────────┴───────┘
                                     Widok: [Tabela] [Kafelki] [Oś czasu]
```

**Funkcje osadzone tutaj:**
- filtrowanie po budynku, kwartale/miesiącu/roku zakończenia, statusie, waloryzacji, kompletności,
- sortowanie po każdej kolumnie,
- wyszukiwarka pełnotekstowa (najemca, NIP, numer lokalu, numer umowy),
- przełącznik widoku: tabela / kafelki / oś czasu,
- zapisane widoki ("moje umowy kończące się w tym roku"),
- eksport widocznego zestawu do XLSX/CSV,
- wejście w wiersz otwiera profil lokalu.

Widok "oś czasu" to dodatkowo wykres Gantta okresów najmu na przestrzeni lat. Dla planowania obłożenia budynku to często czytelniejsze niż tabela.

### 7.2 Ekran 2: PROFIL LOKALU / NAJMU

Serce systemu. Wszystko o jednym lokalu w jednym miejscu, zakładkowo.

```
┌───────────────────────────────────────────────────────────────────────┐
│ ← 18A / lokal 12 · 124,5 m² · WYNAJĘTY          Kompletność: ████░ 82%│
│ Najemca: [nazwa firmy]                                                 │
├───────────────────────────────────────────────────────────────────────┤
│ [Przegląd] [Najemca] [Finanse] [Zabezpieczenia] [Przeglądy]           │
│ [Dokumenty] [Historia] [Zdarzenia]                                     │
└───────────────────────────────────────────────────────────────────────┘
```

| Zakładka | Co zawiera | Skąd dane |
|---|---|---|
| **Przegląd** | karta skrótowa: kluczowe daty, kwoty, statusy, otwarte alerty | agregat |
| **Najemca** | nazwa, NIP, REGON, KRS, adres siedziby, adres korespondencyjny, kontakty | tor B, ręcznie |
| **Finanse** | stawka za m², czynsz, składniki opłat z terminami płatności, zasady waloryzacji, historia zmian stawek | tor A + reguły |
| **Zabezpieczenia** | kaucja (kwota, status, daty), weksel (T/N, wartość, przechowywanie), polisa (wymagana kwota, dostarczona, ważność) | tor A + statusy ręczne |
| **Przeglądy** | lista elementów, kto obciążany, cykl, ostatni, następny, protokoły | tor A + protokoły |
| **Dokumenty** | umowa, aneksy, protokoły, polisy, w drzewie hierarchii, z podglądem | pipeline |
| **Historia** | oś czasu wszystkich zmian parametrów: co, kiedy, z czego wynikało, kto zatwierdził | PARAMETR_WARTOSC + audyt |
| **Zdarzenia** | otwarte i zamknięte alerty dla tego lokalu, z notatkami | generator zdarzeń |

Zasada: **każda liczba w tym ekranie jest klikalna i prowadzi do dokumentu źródłowego z podświetlonym fragmentem.** To jedyny sposób, żeby pracownik zaufał systemowi zamiast na wszelki wypadek otwierać PDF.

### 7.3 Ekran 3: KOKPIT TERMINÓW

Widok zorientowany na czas, a nie na lokal. Odpowiada na pytanie "czym mam się zająć".

```
┌──────────────────────────────────────────────────────┐
│ KRYTYCZNE (3)                                         │
│  ⛔ 22/03 · przegląd hydrantów przeterminowany 12 dni │
│  ⛔ 18A/14 · brak polisy, termin minął 03.08          │
│  ⛔ 18A/07 · umowa wygasła, brak decyzji              │
├──────────────────────────────────────────────────────┤
│ NAJBLIŻSZE 30 DNI (8)                    [rozwiń]     │
├──────────────────────────────────────────────────────┤
│ KWARTAŁ (14)                             [rozwiń]     │
├──────────────────────────────────────────────────────┤
│ Filtry: budynek ▾ | typ zdarzenia ▾ | przypisane ▾   │
└──────────────────────────────────────────────────────┘
```

Funkcje: oznacz jako obsłużone, odrocz z notatką, przypisz do osoby, przejdź do lokalu, eksport listy zadań.

### 7.4 Ekran 4: IMPORT DOKUMENTU

Krokowy kreator, nie formularz.

```
[1 Wgraj plik] → [2 Wskaż typ i lokal] → [3 Przetwarzanie...] → [4 Weryfikacja]
```

Obsługa wsadowa: możliwość wrzucenia całego katalogu przy migracji historycznych umów, z kolejką przetwarzania w tle.

### 7.5 Ekran 5: WERYFIKACJA EKSTRAKCJI

Ekran, na którym pracownik spędzi najwięcej czasu w pierwszych miesiącach. Warto go zrobić dobrze.

```
┌─────────────────────────┬────────────────────────────────┐
│                         │  PROPONOWANE WARTOŚCI          │
│   PODGLĄD DOKUMENTU     │                                │
│                         │  Stawka za m²                  │
│   ...§ 5 ust. 2         │  [ 58,00 ] zł    pewność: 94%  │
│   Czynsz wynosi         │  ✓ zatwierdź  ✎ popraw  ✕ odrzuć│
│  ▓▓58,00 zł/m²▓▓ ...    │  ─────────────────────────────  │
│                         │  Termin płatności czynszu      │
│   (podświetlony         │  [ 10 ] dzień miesiąca  87%    │
│    fragment)            │  ✓ zatwierdź  ✎ popraw  ✕ odrzuć│
│                         │  ─────────────────────────────  │
│                         │  Waloryzacja                   │
│                         │  [ tak, od stycznia, GUS ] 71% │
│                         │  ⚠ niska pewność, sprawdź       │
└─────────────────────────┴────────────────────────────────┘
      [Zatwierdź wszystkie wysokiej pewności]  [Zapisz i zakończ]
```

Skróty klawiszowe (Enter = zatwierdź, Tab = następne pole) skracają ten proces z minut do sekund na pole. To realna różnica przy 200 umowach do zmigrowania.

### 7.6 Ekran 6: WALORYZACJA ROCZNA

Osobny ekran, bo to osobny rytuał raz do roku.

```
Wskaźnik GUS 2027: [ 3,7 ] %      Podstawa: [GUS r/r ▾]   [Zastosuj]

☑ 18A/12 · czynsz 6 960 → 7 218 zł · od 01.01.2027
☑ 18A/14 · czynsz 4 400 → 4 563 zł · od 01.01.2027
☐ 22/03  · WYŁĄCZONY: stała stawka w aneksie nr 2
                          [Zatwierdź zaznaczone: 14 umów]
```

### 7.7 Ekran 7: RAPORTY I EKSPORT

Gotowe zestawienia: umowy kończące się w okresie, przychód miesięczny w podziale na budynki, obłożenie lokali, lista zabezpieczeń do rozliczenia, harmonogram przeglądów, luki w danych.

Eksport XLSX i CSV. Bez integracji zewnętrznych w pierwszej fazie.

### 7.8 Ekran 8: ADMIN

~~Użytkownicy i role~~, budynki i lokale (kartoteka), słowniki (typy dokumentów, elementy przeglądów, składniki opłat), wskaźniki waloryzacji, konfiguracja alertów (progi dni), log audytu, kopie zapasowe.

> **Nieaktualne:** użytkowników i ról nie ma — [ADR 009](decyzje/009-usuniecie-logowania.md).

### 7.9 Role i uprawnienia

> **NIEAKTUALNE od 28.08.2026.** Program nie ma logowania ani ról. Każdy, kto ma
> dostęp do komputera, ma dostęp do wszystkiego. Tabela poniżej opisuje pierwotny
> zamysł i to, co trzeba by odbudować, gdyby program miał obsłużyć więcej niż
> jedną osobę. Powód i konsekwencje: [ADR 009](decyzje/009-usuniecie-logowania.md).

| Rola | Zakres |
|---|---|
| **Podgląd** | odczyt dashboardu i profili, bez danych finansowych wrażliwych |
| **Operator** | wszystko powyżej + import dokumentów, weryfikacja ekstrakcji, obsługa zdarzeń |
| **Zarządca** | wszystko powyżej + edycja parametrów, zatwierdzanie waloryzacji, zmiana najemców |
| **Administrator** | wszystko + użytkownicy, słowniki, kartoteka budynków, audyt |

---

## 8. Bezpieczeństwo i poufność

Specyfikacja stawia to jako wymóg twardy, więc traktuję to jako ograniczenie architektoniczne, nie jako opcję.

### 8.1 Zasady

1. **Środowisko zamknięte.** Aplikacja działa na serwerze wewnątrz sieci firmowej. Brak dostępu z internetu. Backend nie ma prawa wychodzić na zewnątrz, poza ewentualnym serwerem SMTP do powiadomień.
2. **Zero chmurowego AI.** Żadnych wywołań do zewnętrznych API modeli. Ekstrakcja: reguły + model uruchamiany lokalnie.
3. **Blokada wychodząca na poziomie infrastruktury.** Nie ufamy deklaracji w kodzie. Firewall po stronie serwera z listą dozwoloną, domyślnie pustą. To jedyna gwarancja, że przypadkowa zależność nie wyśle danych na zewnątrz.
4. **Anonimizacja jako druga warstwa.** Dokumenty poddawane ekstrakcji nie zawierają danych identyfikacyjnych. Dane poufne wprowadza człowiek bezpośrednio w aplikacji, poza torem przetwarzania automatycznego.
5. ~~**Dostęp wyłącznie dla uprawnionych.** Logowanie imienne, role, brak kont współdzielonych.~~
   **NIE OBOWIĄZUJE od 28.08.2026** ([ADR 009](decyzje/009-usuniecie-logowania.md)). Program nie ma logowania ani ról.
   Dostępu pilnuje dostęp do komputera, na którym stoi.
6. **Pełny audyt.** Każdy odczyt danych wrażliwych i każda zmiana są logowane —
   **z jednym wyjątkiem**: log zapisuje co, kiedy i z jakiej wartości na jaką,
   ale nie **kto**, bo nie ma pojęcia użytkownika ([ADR 009](decyzje/009-usuniecie-logowania.md)).
7. **Szyfrowanie.** Baza i katalog dokumentów na zaszyfrowanym wolumenie. Kopie zapasowe szyfrowane, testowane z odtworzenia.
8. **RODO.** Dane najemców będących osobami fizycznymi to dane osobowe. Potrzebne: rejestr czynności przetwarzania, polityka retencji (ile lat po zakończeniu umowy), procedura usunięcia.

### 8.2 Otwarta kwestia do decyzji

Skoro dokumenty idące do ekstrakcji są pozbawione danych klienta, teoretycznie otwiera się możliwość użycia mocniejszego modelu. **Rekomendacja: nie robić tego w pierwszej wersji.** Powody:

- specyfikacja mówi o kategorycznym zakazie, a zmiana takiej zasady wymaga świadomej decyzji, nie technicznego wybiegu,
- anonimizacja umów jest trudniejsza niż się wydaje: nazwa firmy potrafi wracać w treści paragrafów, w numerach rachunków, w opisach lokalu,
- lokalne modele są dziś wystarczające do tego zadania, bo umowy najmu są bardzo powtarzalne strukturalnie.

Jeśli kiedyś ta decyzja ma być podjęta, powinna być podjęta jawnie i z audytem procesu anonimizacji, a nie po cichu.

---

## 9. Roadmapa

### Faza 0: rozpoznanie (przed kodowaniem)

- 10 do 15 realnych umów i aneksów na stół, przeanalizowanych ręcznie,
- odpowiedź na pytania: ile jest wariantów zapisów o waloryzacji, jak wyglądają protokoły przekazania, czy miejsca postojowe są osobnymi lokalami,
- rozmowa z 2 do 3 osobami, które dziś to obsługują, o tym co robią w poniedziałek rano,
- efekt: potwierdzony lub poprawiony model danych.

Ten krok jest kuszący do pominięcia i to jest dokładnie ten moment, w którym projekty tego typu się wykrzaczają.

### Faza 1: MVP, bez AI (fundament)

Zakres:
- model danych z wersjonowaniem parametrów,
- kartoteka budynków i lokali,
- ręczne wprowadzanie okresów najmu, najemców, warunków,
- wgrywanie dokumentów jako załączników z podglądem,
- dashboard z pełnym filtrowaniem,
- profil lokalu ze wszystkimi zakładkami,
- generator zdarzeń i kokpit terminów,
- reguły: data zakończenia, polisa, kaucja, przeglądy,
- eksport do XLSX,
- ~~role~~ i audyt (role usunięte — [ADR 009](decyzje/009-usuniecie-logowania.md)).

**Po tej fazie system już przynosi wartość**, nawet jeśli dane wprowadza się ręcznie. To ważne, bo daje czas na dopracowanie ekstrakcji bez presji.

### Faza 2: ekstrakcja wspomagana

- pipeline: OCR, segmentacja, warstwa regułowa,
- ekran weryfikacji side-by-side z podświetlaniem,
- ekstrakcja parametrów przewidywalnych: kwoty, daty, terminy płatności, powierzchnia,
- obsługa aneksów z widokiem diffu,
- migracja wsadowa archiwum umów.

### Faza 3: model lokalny i waloryzacja

- lokalny model językowy do zapisów opisowych (waloryzacja, zakres przeglądów, warunki wypowiedzenia),
- pętla uczenia z poprawek pracowników,
- ekran waloryzacji rocznej z przeliczeniem zbiorczym,
- powiadomienia e-mail.

### Faza 4: rozbudowa

- raporty przychodowe i obłożenia,
- integracja z systemem finansowym (eksport harmonogramu płatności),
- portal podglądowy dla zarządu,
- obsługa czwartego budynku i lokali w budowie.

---

## 10. Ryzyka

| Ryzyko | Skutek | Jak ograniczyć |
|---|---|---|
| Umowy są mniej powtarzalne niż zakładamy | ekstrakcja słaba, dużo pracy ręcznej | Faza 0 na realnych dokumentach, MVP nie zależy od AI |
| Model danych nie obsłuży realnego aneksu | przebudowa w połowie projektu | wersjonowanie parametrów od początku, migracje Alembic od dnia 1 |
| Pracownicy nie zaufają danym w systemie | równoległe prowadzenie Excela, projekt umiera | każda liczba klikalna do źródła, weryfikacja obowiązkowa, wskaźnik kompletności |
| Migracja archiwum utknie | system pusty, więc nieużywany | ekran weryfikacji zoptymalizowany pod szybkość, import wsadowy, mierzenie postępu |
| Skany złej jakości | OCR zawodzi | fallback na wprowadzanie ręczne, dokument zawsze dostępny do podglądu |
| Zakres pełznie w stronę "systemu do wszystkiego" | brak wdrożenia | sekcja 1.3 jako twarda granica |
| Jednorazowa głośna pomyłka w kwocie | utrata zaufania | zasada D4, wartość niezatwierdzona nie wchodzi do alertów ani raportów |

---

## 11. Pytania otwarte

Rzeczy, których nie da się rozstrzygnąć bez kontaktu z realnymi danymi i ludźmi:

1. **Miejsca postojowe**: osobny lokal w ewidencji czy składnik opłaty przy lokalu głównym?
2. **Podnajem i cesje**: czy występują? Jeśli tak, model najemcy potrzebuje relacji nadrzędnej.
3. **Media**: refakturowane, ryczałt, czy licznikowe? To wpływa na model składników opłat.
4. **Wskaźnik waloryzacji**: który dokładnie GUS (r/r grudzień do grudnia, średnioroczny, inny)? Umowy potrafią to definiować różnie i wtedy potrzebny jest słownik wskaźników, nie jedno pole.
5. **Ile jest umów do zmigrowania?** 50 to inna decyzja projektowa niż 800.
6. **Kto będzie to obsługiwał na co dzień?** Jedna osoba czy zespół? To determinuje potrzebę przypisywania zadań.
7. **Czy istnieje system finansowy, z którym trzeba się integrować?** Jeśli tak, kierunek integracji i format.
8. **Retencja danych**: jak długo trzymamy dane zakończonych umów?
9. **Okres wypowiedzenia**: czy jest jednolity, czy per umowa? To dodatkowy parametr i dodatkowe zdarzenie.
10. **Czy potrzebna jest obsługa wielu wynajmujących** (różne spółki w grupie), czy jeden podmiot?

---

## 12. Co dalej

Sugerowana kolejność:

1. Przejść przez sekcję 2 (decyzje projektowe) i potwierdzić lub odrzucić każdą z nich.
2. Odpowiedzieć na pytania z sekcji 11, choćby częściowo.
3. Faza 0: 10 do 15 realnych dokumentów, weryfikacja modelu danych.
4. Dopiero potem: schemat bazy, makiety ekranów, kodowanie MVP.

---

*Dokument roboczy. Wszystko tutaj jest do zakwestionowania, szczególnie sekcja 2 i 3, bo one determinują koszt zmiany później.*

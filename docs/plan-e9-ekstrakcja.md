# E9: dane z dokumentów zamiast z klawiatury

**Data:** 28.08.2026
**Cel:** wszystko, co widać w profilu lokalu, ma pochodzić z dokumentu — poza
danymi najemcy, które z założenia nie przechodzą przez ekstrakcję (tor B,
decyzja D3).
**Stan wyjściowy:** program nie czyta treści plików w ogóle. Czyta nazwę
(podpowiedź typu), pierwsze bajty (weryfikacja formatu) i SHA-256 (deduplikacja).

---

## 1. Co się właściwie zmienia

Dziś człowiek czyta umowę i przepisuje liczby do formularza. Po E9 program
czyta umowę, wypełnia formularz propozycjami i pokazuje przy każdej, **z którego
zdania na której stronie** ją wziął. Człowiek klika „zatwierdź" zamiast pisać.

Czego **nie** zmieniamy: decyzji D4. Wartość niezatwierdzona nadal nie wchodzi
do alertów ani raportów. Zmienia się koszt zatwierdzenia — z przepisania kwoty
na jedno kliknięcie, a przy wysokiej pewności na jedno kliknięcie dla całej
umowy. To jest cała różnica i to wystarczy.

Powód, dla którego nie ruszamy D4: cena pomyłki jest niesymetryczna. Źle
odczytany dzień płatności albo kwota kaucji kosztuje realne pieniądze, a jedna
głośna pomyłka zabija zaufanie do narzędzia na rok. Ekstrakcja skraca drogę
do danych, nie zdejmuje odpowiedzialności.

---

## 2. Co realnie da się wyciągnąć

Uczciwa ocena per pole. „Wysoka" znaczy: zapis jest na tyle stały, że wzorzec
regułowy trafia prawie zawsze, a pomyłka jest widoczna gołym okiem.

| Pole | Realność | Na czym stoi wzorzec |
|---|---|---|
| `powierzchnia` | **wysoka** | „o powierzchni 124,50 m²" — bardzo stały zapis |
| `czynsz_podstawowy` | **wysoka** | kwota + „czynsz" + „miesięcznie" w jednym zdaniu |
| `stawka_m2` | **wysoka** | „zł/m²", „za 1 m² powierzchni" |
| `data_zawarcia` | **wysoka** | data w komparycji, pierwsza strona |
| `data_przekazania` | **wysoka** | protokół przekazania, zwykle jedna data w dokumencie |
| `okres_miesiace` | **wysoka** | „na czas określony 24 miesięcy" |
| `dzien_platnosci` | **wysoka** | „do 10-go dnia każdego miesiąca" |
| `kaucja` | **wysoka** | „kaucja w wysokości … zł" |
| `oplata_eksploatacyjna` | średnia | nazwa składnika bywa inna w każdej umowie |
| `polisa_kwota` | średnia | kwota jest, ale bywa nazwana „sumą gwarancyjną" |
| `polisa_termin` | średnia | termin relatywny: „14 dni od dnia przekazania" — trzeba przeliczyć |
| `weksel_krotnosc` | średnia | „czterokrotność czynszu" — liczebnik słownie, nie cyfra |
| `waloryzacja` | **niska jako liczba** | zdanie opisowe. Wyciągamy flagę i cytat, nie parsujemy reguły |
| `przeglady` (elementy) | **niska** | lista wyliczeniowa, w każdej umowie inna |
| dane najemcy | **wykluczone** | tor B, decyzja D3 — nigdy nie idzie przez ekstrakcję |

Wniosek do przyjęcia z góry: pola „niskie" nie dostaną wartości, tylko
**wyciągnięty cytat z lokalizacją**, podany człowiekowi do decyzji. To nie jest
porażka wzorca. Podanie liczby tam, gdzie w dokumencie stoi zdanie opisowe,
byłoby zamianą braku danych w fakt (decyzja D5).

---

## 3. Architektura

Pipeline z sekcji 4.3 koncepcji, z jednym rozstrzygnięciem, które decyduje
o wszystkim dalej: **tylko pierwszy krok dotyka plików i bibliotek.
Kroki 2–4 to czysty Python w `domena/`.**

```
plik (PDF / DOCX / skan)
  │
  │  [1] dokumenty/tekst_z_pliku.py         ← JEDYNE miejsce z nowymi bibliotekami
  ▼      bajty → tekst stron + numer strony + warstwa (pdf_tekst | docx | ocr)
TekstDokumentu
  │
  │  [2] domena/ekstrakcja/segmentacja.py   ← czysty Python
  ▼      tekst → paragrafy, §, offsety; sklejanie przeniesień wyrazów
Segmenty
  │
  │  [3] domena/ekstrakcja/{liczby,daty}.py ← czysty Python
  ▼      „6 960,00 zł" → Decimal; „1 marca 2027" → date; „czterokrotność" → 4
Wartości znormalizowane
  │
  │  [4] domena/ekstrakcja/wzorce/*.py      ← czysty Python, serce sprawy
  ▼      segment + wartość → Propozycja(klucz, wartość, pewność, cytat, lokalizacja)
Propozycje
  │
  │  [5] uslugi/ekstrakcja.py                ← zapis, w tle
  ▼      parametr_wartosc ze statusem ZAPROPONOWANA
  │
  │  [6] frontend: ekran weryfikacji
  ▼      side-by-side, zatwierdź / popraw / odrzuć
parametr_wartosc ZATWIERDZONA → stan efektywny → dashboard
```

Dlaczego ta granica jest kluczowa: wzorce to jedyna część, która będzie się
zmieniać co tydzień przez pierwsze pół roku. Muszą dać się testować na zwykłym
napisie — bez pliku, bez bazy, bez OCR-a. `tests/domena/test_granice_warstw.py`
już pilnuje, że `domena/` nie zaimportuje niczego z infrastruktury, więc nowy
kod wpada pod ten test automatycznie.

### Nowe pliki

```
backend/src/najem/domena/ekstrakcja/
  propozycja.py      Propozycja, Pewnosc, Lokalizacja — struktura wyniku
  tekst.py           TekstDokumentu, StronaTekstu, WarstwaTekstu; normalizacja
  segmentacja.py     podział na paragrafy i §, mapa offsetów
  liczby.py          kwoty polskie, procenty, liczebniki słownie
  daty.py            daty polskie w czterech zapisach + terminy relatywne
  silnik.py          uruchamia wzorce, scala wyniki, rozstrzyga konflikty
  wzorce/
    __init__.py      rejestr wzorców
    powierzchnia.py  czynsz.py  terminy.py  okres.py
    zabezpieczenia.py  waloryzacja.py

backend/src/najem/dokumenty/
  tekst_z_pliku.py   CzytnikTekstu (Protocol) + implementacje per format

backend/src/najem/uslugi/
  ekstrakcja.py      przebieg dla jednego dokumentu, w tle, idempotentny

backend/src/najem/api/v1/
  ekstrakcja.py      uruchom / status / propozycje / decyzja

frontend/src/strony/Weryfikacja/
  Weryfikacja.tsx  PanelDokumentu.tsx  PanelPropozycji.tsx
```

---

## 4. Model danych

Dobra wiadomość: **`parametr_wartosc` jest już gotowa.** Kolumny
`dokument_zrodlowy_id`, `zrodlo_strona`, `zrodlo_paragraf`, `zrodlo_offset_od`,
`zrodlo_offset_do`, `pewnosc` i `status_weryfikacji` istnieją od migracji 002
i dotąd stały puste. Propozycja z ekstrakcji to zwykły wiersz tej tabeli
ze statusem `zaproponowana` — żadnej nowej encji.

Migracja `008_ekstrakcja` dokłada trzy rzeczy:

**`dokument_tekst`** — odczytany tekst, strona po stronie.
Bez tego ekran weryfikacji musiałby parsować PDF przy każdym otwarciu,
a podświetlenie fragmentu wymaga dokładnie tego tekstu, na którym działał
wzorzec. Kolumny: `dokument_id`, `strona`, `tekst`, `warstwa`
(`pdf_tekst` / `docx` / `ocr`), `utworzono`.

**`przebieg_ekstrakcji`** — kiedy, na jakiej wersji wzorców, ile propozycji,
ile zatwierdzono bez poprawki. To realizacja punktu 7 z sekcji 4.3 koncepcji:
poprawki pracownika są najcenniejszym zasobem projektu, bo po dwustu umowach
mówią dokładnie, który wzorzec się myli.

**`parametr_wartosc.zrodlo_cytat`** (Text, NULL) — zdanie, na którym stoi
propozycja. Dałoby się je odtworzyć z offsetów, ale wtedy ponowna ekstrakcja
nowszą wersją czytnika zmieniałaby uzasadnienie już zatwierdzonej wartości.
Cytat ma być zamrożony w chwili propozycji.

---

## 5. Pewność — skąd się bierze ta liczba

Pewność nie może być zmyślona, bo na niej stoi przycisk „zatwierdź wszystkie
wysokiej pewności". Liczymy ją ze składników, każdy jawny i przetestowany:

| Składnik | Waga |
|---|---|
| kotwica („czynsz", „kaucja") w tym samym zdaniu co wartość | +0,40 |
| jednostka zgodna z typem („zł", „m2", „dnia miesiąca") | +0,25 |
| segment leży pod nagłówkiem § o pasującym tytule | +0,15 |
| wartość mieści się w zakresie zdroworozsądkowym | +0,10 |
| jedyny kandydat w całym dokumencie | +0,10 |
| **warstwa tekstu to OCR** | **× 0,7** |
| dwóch kandydatów o zbliżonej pewności | → `niejednoznaczna` |

Dwie zasady twarde:

1. **Tekst z OCR-a nigdy nie ma pewności wysokiej.** Mnożnik 0,7 to nie
   ostrożność, tylko fakt: OCR myli 0 z O i 6 z 8, a to są cyfry w kwocie.
2. **Remis nie jest rozstrzygany losowo.** Dwóch kandydatów na czynsz → status
   `niejednoznaczna` i oba cytaty pokazane człowiekowi. Zgadywanie tutaj to
   dokładnie ten scenariusz z tabeli ryzyk, który zabija zaufanie do systemu.

---

## 6. Etapy

Idziemy pionowym plastrem: jedno pole przechodzi całą drogę, zanim dołożymy
drugie. Alternatywa („najpierw cały OCR, potem wszystkie wzorce, potem UI")
kończy się trzema tygodniami pracy bez niczego działającego.

### E9.0 — Co jest w archiwum *(bez zależności)* — **ZROBIONE**
`narzedzia/sprawdz-dokumenty.py`. Statystyka formatów i warstw tekstowych,
bez wypisywania treści. Sekcja 8. **Czeka na uruchomienie na prawdziwym
archiwum** — to jedyne, co dziś blokuje decyzję o OCR-ze (E9.7).

### E9.1 — Tekst z pliku — **ZROBIONE**
`dokumenty/tekst_z_pliku.py`: `CzytnikPdf` (pypdf), `CzytnikDocx` (sama
standardowa biblioteka), `CzytnikStaregoDoc` (jawna odmowa z instrukcją).
Biblioteka do PDF-ów: **pypdf**, zatwierdzona 28.08.2026. Jeden pakiet,
licencja MIT, zero zależności pochodnych. Wybrana dlatego, że ekran
weryfikacji podświetla fragment w odczytanym tekście, a nie na renderowanym
PDF-ie, więc ramki współrzędnych z `pdfplumber` nie są do niczego potrzebne,
a kosztowałyby kilkanaście megabajtów w paczce wydania.

### E9.2 — Segmentacja i normalizacja — **CZĘŚCIOWO**
`domena/ekstrakcja/{tekst,liczby,daty}.py` gotowe, pokrycie 100%.
Zostaje `segmentacja.py`: podział na paragrafy i §.

Trzy rzeczy, które wyszły przy pisaniu i o których musi wiedzieć każdy,
kto tknie wzorce:

* **Normalizacja NFKC zamienia „m²" na „m2"** — wzorzec powierzchni ma
  szukać „m2". Zamienia też wszystkie odmiany spacji na zwykłą, więc kwota
  z Worda i z PDF-a wygląda tak samo.
* **Offsety odnoszą się do tekstu po normalizacji** i ten sam tekst ląduje
  w `dokument_tekst`. Gdyby w bazie leżał tekst surowy, podświetlenie
  rozjeżdżałoby się przy każdym przeniesieniu wyrazu.
* **`6.960` czytamy jako 6960** (po polsku), ale zapis jest oznaczany jako
  niejednoznaczny i obniża pewność propozycji.

### E9.3 — Pierwszy wzorzec end-to-end: powierzchnia
Najprostsze pole, pełna droga: plik → propozycja → ekran → zatwierdzenie →
dashboard. Cel to przejść przez wszystkie warstwy, nie pokryć pól.
**Gotowe, gdy:** wgranie umowy daje na profilu lokalu propozycję powierzchni
z cytatem i numerem strony, a „zatwierdź" zmienia dashboard.

### E9.4 — Ekran weryfikacji
Side-by-side z sekcji 7.5 koncepcji. **Bez pdf.js w pierwszym podejściu:**
po lewej odczytany tekst strony z podświetlonym fragmentem, pod nim odnośnik
otwierający oryginał. Podgląd samego PDF-a dochodzi później i niczego nie
blokuje. Skróty klawiszowe (Enter = zatwierdź, Tab = następne) — przy dwustu
umowach to różnica między godzinami a dniami.
**Gotowe, gdy:** da się przejść umowę od pierwszej do ostatniej propozycji
bez sięgania po mysz.

### E9.5 — Reszta wzorców
Kolejno: czynsz, stawka za m², daty, okres, dzień płatności, kaucja, polisa,
weksel, waloryzacja (flaga i cytat).
**Gotowe, gdy:** na próbce realnych umów każde pole z tabeli w sekcji 2 albo
ma propozycję, albo ma jawny powód, dlaczego jej nie ma.

### E9.6 — Aneksy jako diff
Aneks ma dokument nadrzędny, więc propozycja z aneksu to **zmiana** względem
stanu efektywnego, nie nowa wartość w próżni. Ekran pokazuje diff z sekcji 4.4
koncepcji, a zatwierdzenie domyka stary wiersz i otwiera nowy.
**Gotowe, gdy:** aneks podnoszący stawkę pokazuje dwie kolumny „obecnie" /
„po aneksie", a zatwierdzenie nie rusza historii.

### E9.7 — OCR *(warunkowe)*
Wchodzi tylko, jeśli w archiwum faktycznie są skany bez warstwy tekstowej.
Odpowiedź daje E9.0, zanim cokolwiek zainstalujemy.

---

## 7. Ryzyka

| Ryzyko | Skutek | Cięcie |
|---|---|---|
| Umowy mniej powtarzalne, niż zakładamy | wzorce trafiają w 30% | E9.3 na realnej umowie, zanim powstanie dziesięć wzorców |
| Cicha pomyłka w kwocie | utrata zaufania, projekt umiera | D4 bez wyjątków; remis → `niejednoznaczna`; OCR nigdy z wysoką pewnością |
| OCR wciąga 150 MB do paczki wydania | paczka pełna rośnie z 310 MB | OCR dopiero po dowodzie, że jest potrzebny (E9.0) |
| Wzorce rozpełzają się po `uslugi/` | nie da się ich testować bez bazy | `test_granice_warstw.py` łapie to automatycznie |
| Ekstrakcja blokuje request przy 80-stronicowej umowie | interfejs staje | przebieg w tle na APScheduler, który już jest w projekcie |
| Ponowna ekstrakcja dubluje propozycje | bałagan w historii | przebieg idempotentny po `(dokument_id, klucz)`; ruszamy tylko wiersze `zaproponowana` |

---

## 8. Zanim zainstalujemy cokolwiek: co jest w archiwum

Pytanie „czy potrzebny jest OCR" ma odpowiedź empiryczną, nie uznaniową.
PDF wygenerowany z Worda ma warstwę tekstową i nie wymaga OCR-a w ogóle.
PDF ze skanera to obrazek i bez OCR-a jest bezużyteczny. To dwie zupełnie
różne decyzje o zakresie prac i o rozmiarze paczki wydania.

Dlatego pierwszą rzeczą, która powstaje, jest `narzedzia/sprawdz-dokumenty.py`:
przechodzi po katalogu skanu i podaje **wyłącznie statystykę** — ile plików,
w jakich formatach, ile PDF-ów ma warstwę tekstową, ile stron. Nie wypisuje
żadnej treści dokumentów. Zero zależności: sam `zipfile`, `zlib` i `re`
ze standardowej biblioteki.

---

## 9. Decyzje do podjęcia

1. **Biblioteki.** PDF-a nie da się czytać standardową biblioteką w rozsądny
   sposób. DOCX — da się. OCR — zależy od wyniku E9.0.
2. **Stare `.doc`** (binarny format Worda sprzed 2007). Czytanie go bez ciężkich
   narzędzi jest praktycznie niewykonalne. Propozycja: nieobsługiwane, z jawnym
   komunikatem „zapisz jako PDF", zamiast cichego pominięcia.

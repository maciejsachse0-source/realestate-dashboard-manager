# Stan projektu

Ten plik ładuje się do kontekstu przy **każdej** sesji, więc jest krótki celowo.
Zebrane pułapki i decyzje nie do cofnięcia: [`docs/pulapki.md`](pulapki.md)
(czytaj na żądanie). Odstępstwa od planu: [`docs/decyzje/`](decyzje/).

## Gdzie jestem

Etapy **E0 – E8 ukończone** (25.08.2026). Program działa od kliknięcia skrótu po dane
i **da się w nim pracować**: wprowadzić budynek, lokal, najemcę, umowę, warunki,
zabezpieczenia i przeglądy, zatwierdzić wartości, obsłużyć terminy, przeprowadzić
waloryzację roczną.

56 endpointów (było 62 — ubyły cztery z logowania, lista użytkowników
i przypisywanie zdarzeń). Interfejs: dashboard, kartoteka z formularzami,
kokpit terminów z filtrami i akcjami, profil lokalu z ośmioma zakładkami,
kreator importu z arkusza, waloryzacja roczna.

**Program nie ma logowania** ([ADR 009](decyzje/009-usuniecie-logowania.md),
28.08.2026). Otwiera się od razu na dashboardzie. Zniknęły sesje, hasła, role
i wszystkie kolumny z autorem operacji, razem z tabelami `uzytkownik`
i `sesja_uzytkownika`. Audyt nadal zapisuje **co, kiedy i z jakiej wartości
na jaką**, ale nie **kto** — to świadome odstępstwo od sekcji 8.1 koncepcji.
Migracja `007_bez_logowania` jest nieodwracalna w sensie danych: `downgrade`
odtwarza sam schemat, historia autorstwa przepada.

**Po E8 system zastępuje Excela.** Wszystko dalej to poprawa efektywności,
nie warunek działania.

Dokumenty: wgrywanie z rozpoznaniem typu po zawartości pliku, deduplikacja
po SHA-256, hierarchia umowa → aneks, pobieranie ze śladem w audycie.
Doszedł drugi kanał: **„Dokumenty z dysku"** — program czyta gotowe drzewo
katalogów (`KATALOG_SKANU`, układ `budynek/Umowy najmu/folder lokalu/pliki`),
podpowiada rodzaj dokumentu z nazwy pliku i pozwala go dodać **jako odnośnik,
bez kopiowania** ([ADR 008](decyzje/008-dokumenty-linkowane-nie-kopiowane.md)).
Folder paruje się z umową raz, ręcznie; pominięty plik nie wraca przy kolejnym
skanie. Przycisk „Sprawdź odnośniki" wykrywa pliki przeniesione albo podmienione.
**Skutek dla kopii zapasowych: backup musi obejmować bazę razem z katalogiem
dokumentów użytkownika.**
Ekran ma zakładkę **„Jak to działa"** z opisem mechanizmu: co program odczytuje
z pliku (nazwę, sygnaturę pierwszych bajtów, SHA-256 treści), czego nie
odczytuje i co z tego wynika. Powstała 28.08.2026 po pytaniu, na jakiej zasadzie
program zczytuje zawartość dokumentów. Gdy zmieni się `domena/skan.py` albo
`dokumenty/przechowalnia.py`, ten opis trzeba poprawić razem z kodem.

Warstwa domenowa jest kompletna (reguły R1, R2, R4–R7, R9), pokrycie `domena/`
wynosi 100%. Generator zdarzeń chodzi codziennie o 6:00 i jest idempotentny.
Siedem migracji Alembica, jedna głowa.

Zastrzeżenie do R5: część liczbowa (wartość zabezpieczenia jako wielokrotność
czynszu) **nie jest zaimplementowana**. Wymaga krotności jako liczby, a model
trzyma opis słowny. System przypomina o przeliczeniu, nie liczy za człowieka.

Kontrola na dziś: **630 testów backendu + 56 frontendu**, `mypy` strict i `ruff`
czysto, `npm run build` przechodzi. E8 przeszedł też próbę na żywych danych:
propozycja, zatwierdzenie, idempotencja przy powtórzeniu, waloryzacja rok po
roku i eksport XLSX.

E8 przeszedł przegląd kodu, który znalazł kilkanaście defektów. Poprawione są
wszystkie poza jednym (patrz niżej). Najpoważniejsze: waloryzacja rozpoznawała
własny poprzedni przebieg po dacie, przez co brała aneks za waloryzację
i pozwalała niezatwierdzonej propozycji zablokować umowę na cały rok
([ADR 007](decyzje/007-znacznik-waloryzacji-na-parametrze.md)).

### Poprawki interfejsu z 28.08.2026

Pierwszy dzień, w którym program oglądał człowiek. Wyszło z tego:

* profil lokalu stracił pole „Kondygnacja"; zwrot i zatrzymanie zabezpieczenia
  da się cofnąć (były jednym klikiem od pomyłki, bez drogi powrotnej);
* kartoteka to jedna tabela pogrupowana budynkami zamiast trzech zakładek.
  Nagłówek budynku ma tło, grube obramowanie i wersaliki, bo przy przewijaniu
  oko musi mieć zaczepienie;
* kokpit terminów pokazuje liczbę dni do terminu („za 12 dni", „8 dni po
  terminie"). Liczy to API (`dni_do_terminu`, `domena/kalendarz.dni_do`),
  w strefie warszawskiej, nie w UTC;
* **dashboard też jest pogrupowany budynkami**, tak samo jak kartoteka:
  nagłówek sekcji zamiast nazwy budynku powtarzanej pod każdym oznaczeniem.
  Domyślne sortowanie listy to `sortuj=budynek`, a API dokłada oznaczenie
  jako drugi klucz — bez tego lokale w budynku szłyby w kolejności zakładania.
  Licznik w nagłówku dotyczy strony, nie całego budynku, i przy stronicowaniu
  mówi to wprost („na tej stronie: 12").

Trzy błędy infrastrukturalne, przez które zmian **nie było widać** mimo
poprawnego kodu — wszystkie załatane i opisane w `pulapki.md`:

1. skrót budował interfejs tylko wtedy, gdy `dist/index.html` nie istniał,
   więc po pierwszym uruchomieniu nie przebudował go nigdy;
2. `index.html` szedł bez nagłówka cache, więc przeglądarka podawała własną
   kopię wskazującą na stary bundle;
3. **serwer zwracał 404 na każdy adres poza stroną główną** — odświeżenie
   podstrony, wklejony adres i zakładka w przeglądarce kończyły się błędem.
   Działało wyłącznie klikanie w menu.

## E9 w toku: dane z dokumentów, nie z klawiatury

Zaczęte 28.08.2026. Pełny plan: [`docs/plan-e9-ekstrakcja.md`](plan-e9-ekstrakcja.md).

Do dziś **każda liczba w profilu lokalu była wpisana ręcznie albo wzięta
z arkusza**. Program czytał z pliku wyłącznie nazwę, sygnaturę pierwszych
bajtów i SHA-256 — zero tekstu. Kolumny `dokument_zrodlowy_id`,
`zrodlo_strona`, `pewnosc` w `parametr_wartosc` istnieją od E2 i stoją puste.
E9 je wypełnia.

Gotowe są **fundamenty, jeszcze bez efektu widocznego w programie**:

* `narzedzia/sprawdz-dokumenty.py` — statystyka archiwum bez zależności
  (E9.0). Mówi, ile plików ma warstwę tekstową, a ile jest skanem. Wypisuje
  same liczby; nazwy plików tylko z jawnym `--pliki`, bo w nazwie umowy
  zwykle siedzi nazwa najemcy;
* `dokumenty/tekst_z_pliku.py` — trzy czytniki za wspólnym `Protocol` (E9.1).
  PDF przez `pypdf`, DOCX samą standardową biblioteką, stary `.doc` odmawia
  z instrukcją „zapisz jako PDF" zamiast po cichu zwrócić pustkę nie do
  odróżnienia od skanu;
* `domena/ekstrakcja/{tekst,liczby,daty}.py` — czytanie polskich kwot, dat
  i terminów względnych (E9.2, część).

Zostaje: `segmentacja.py` (podział na § z mapą offsetów), `propozycja.py`,
`silnik.py`, migracja `008_ekstrakcja`, pierwszy wzorzec end-to-end
(powierzchnia), ekran weryfikacji, reszta wzorców, aneksy jako diff.

### Cztery rzeczy, które łatwo zepsuć

* **Granica warstw jest tu ważniejsza niż gdziekolwiek indziej.** Tylko
  `dokumenty/tekst_z_pliku.py` zna formaty plików. Wszystko powyżej pracuje
  na napisach. `pypdf` i `openpyxl` są na liście zakazanych importów
  w `test_granice_warstw.py` — gdyby `pypdf` wszedł do `domena/`, każdy test
  wzorca wymagałby zbudowania pliku PDF.
* **NFKC zamienia `m²` na `m2`** i każdą odmianę spacji na zwykłą. Wzorzec
  powierzchni ma szukać `m2`. Sprawdzone empirycznie — pierwotny komentarz
  w kodzie twierdził coś przeciwnego i był nieprawdą.
* **Offsety odnoszą się do tekstu po normalizacji** i ten sam tekst pójdzie
  do `dokument_tekst`. Gdyby w bazie leżał surowy, podświetlenie rozjeżdżałoby
  się przy każdym przeniesieniu wyrazu.
* **`6.960` czytamy po polsku jako 6960**, ale zapis jest oznaczany jako
  niejednoznaczny i obniża pewność. Różnica między odczytem polskim
  a angielskim to trzy rzędy wielkości na czynszu.

### Czego ekstrakcja nie zrobi

Kwoty, powierzchnie, daty i dni płatności — tak, z wysoką pewnością.
**Zasady waloryzacji i zakres przeglądów — nie.** To zapisy opisowe,
w każdej umowie sformułowane inaczej. Tam program pokaże znaleziony fragment
i poprosi o decyzję. Zgadywanie przy waloryzacji kosztuje realne pieniądze,
więc to ograniczenie jest zamierzone, nie tymczasowe.

### Co blokuje

**Nie wiadomo, czy umowy użytkownika to PDF-y z tekstem, czy skany.**
Ze skanu bez OCR nie wyjdzie ani jedna liczba, a OCR to kilkaset megabajtów
w instalatorze i osobny podetap (E9.7). Odpowiedź daje jedno uruchomienie
`narzedzia/sprawdz-dokumenty.py` na prawdziwym archiwum — dopóki go nie ma,
zakres E9.7 jest nierozstrzygnięty.

## Co następne

**E9 i dalej** według planu budowy. Nic z tego nie jest już warunkiem, żeby
system działał — od E8 zastępuje Excela.

Fundament E9 stoi, ale **nie jest podpięty do niczego** — opis wyżej.
Dopóki tak jest, zakładka „Jak to działa" mówi prawdę: program czyta o pliku
tylko nazwę, sygnaturę i SHA-256. Etap, który to zmieni, musi poprawić ten
opis razem z kodem.

Najpilniejsze z zaległości: **odpowiedź na punkt B** (EUR/NBP). Waloryzacja
liczy już sumy osobno dla każdej waluty, ale waluta płatności odrębna
od waluty umowy to nadal zmiana schematu.

Znane, świadomie niezałatane: **błędnego wskaźnika nie da się poprawić**.
Jest tylko POST, a powtórzenie daje 409. Literówka („37" zamiast „3,7")
mieści się w walidacji i po zatwierdzeniu wymaga odrzucenia wierszy w profilu
umowy. Poprawka to PUT z blokadą optymistyczną — do zrobienia, gdy będzie
wiadomo, czy korekta ma zostawiać ślad w audycie jako osobna operacja.

Zostało na później: podgląd PDF przez pdf.js (dziś plik otwiera się w karcie
przeglądarki), eksport XLSX, zapisane widoki, wybór kolumn, wirtualizacja,
edycja i usuwanie rekordów z interfejsu.

Ze skanu folderów zostały dwie rzeczy do dołożenia, obie znane i opisane
w `pulapki.md`: parowanie folderu z **zakończoną** umową (dziś lista pokazuje
tylko aktualne, bo nie ma endpointu listującego okresy najmu) oraz ustawianie
`budynek.nazwa_folderu` z interfejsu (kolumna jest, formularza kartoteki jeszcze
nie; dopóki jej nie ma, dopasowanie idzie po nazwie budynku).

## Wydawanie programu użytkownikowi (28.08.2026)

Program ma trafić na komputer księgowej, a poprawki mają dać się wysyłać zdalnie.
Warunki: brak wspólnego dysku, brak serwera włączonego non stop, dokumenty na jej
lokalnym dysku, kontakt tylko mailem. Rozwiązanie i odrzucone warianty:
[ADR 010](decyzje/010-instalacja-u-uzytkownika-i-kanal-aktualizacji.md).

Kluczowa zmiana: **program i dane leżą w rozłącznych katalogach**. Dotąd `pgdata/`
było w środku katalogu programu, więc aktualizacja „podmień katalog" kasowała bazę.
Teraz `dane\` (baza, dokumenty, kopie, logi, `.env`) jest poza `program\`
i aktualizator nie ma jak go dotknąć. Przełącznikiem jest jedna zmienna
`NAJEM_KATALOG_INSTALACJI`, czytana wyłącznie w `narzedzia/sciezki.ps1`;
nieustawiona = dzisiejsze ścieżki repozytorium, bez żadnej różnicy w pracy autora.

Doszły: `spakuj-wydanie.ps1` (dwa rodzaje paczek — pełna ~400 MB i aktualizacja
~0,4 MB), `instalator/` z zakładaniem, aktualizacją i cofaniem wersji,
`kopia-zapasowa.ps1` z zadaniem w Harmonogramie oraz `diagnostyka.ps1`.
Uruchomienie nie wymaga już Node.js, gdy interfejs jest zbudowany — a w paczce
zawsze jest.

**Ustawienia użytkownika przeżywają aktualizację**, bo katalog skanu
(`ustawienie_systemu`) i sparowane foldery (`powiazanie_folderu`) siedzą w bazie,
a nie w plikach programu.

Świadome ograniczenia: aktualizator nie pobiera nic z internetu (dostaje plik),
skrypty z `instalator\` nie aktualizują się same, a cofnięcie wersji cofa kod,
nie bazę. Wszystkie trzy opisane w ADR 010 i `pulapki.md`.

### Kopia zapasowa bez chmury

Ustalone 28.08.2026: użytkowniczka **nie ma OneDrive** ani dysku sieciowego.
Celem kopii zostaje pendrive zostawiony na stałe w porcie albo druga partycja.
Chroni to przed awarią dysku i pomyłką, nie przed kradzieżą, pożarem ani
ransomware — i tak trzeba to nazwać, zamiast udawać, że kopia jest zrobiona.

Skutek: nie ma drugiego miejsca, w którym byłoby widać, że kopie przestały się
wykonywać. Zadanie z Harmonogramu chodzi w ukrytym oknie, więc wyjęty pendrive
zatrzymałby je bez śladu. Dlatego `kopia-zapasowa.ps1` zapisuje wynik **każdej**
próby do `dane\stan-kopii.txt` — lokalnie, celowo nie w katalogu kopii, bo to
właśnie tam nie da się nic zapisać w chwili awarii. `uruchom.ps1` czyta ten plik
przy starcie i ostrzega, gdy ostatnia kopia się nie udała albo była dawniej niż
trzy dni temu. Start programu to jedyny moment, w którym człowiek na pewno
patrzy na ekran.

Uszkodzony albo niekompletny plik stanu daje komunikat „nie umiem odczytać",
a nie fałszywy alarm o awarii. Ostrzeżenie powtarzane codziennie bez powodu
przestaje być czytane po tygodniu, a wtedy prawdziwe przepada razem z nim.

### Próba generalna przeszła i wyłapała cztery błędy

Przećwiczone na instalacji testowej w `C:\SystemNajmu-proba`, pełny przebieg:
instalacja od zera → wprowadzenie ustawienia i danych → aktualizacja 0.1.0 → 0.1.1
→ cofnięcie → ponowna aktualizacja → diagnostyka → kopia zapasowa.

**Ustawienie `katalog_skanu`, wiersz w `budynek`, stan migracji i plik `.env`
przetrwały podmianę katalogu programu.** To była główna wątpliwość i jest
rozstrzygnięta.

Błędy, których nie dało się znaleźć inaczej niż uruchomieniem instalacji:

1. **`initdb` wywracał się przy pierwszym zakładaniu bazy** — `$env:TEMP`
   w formacie 8.3 z tyldą. Ta gałąź wykonuje się **wyłącznie przy pierwszej
   instalacji**, więc u autora nigdy, a u użytkownika za każdym razem. Błąd był
   w kodzie sprzed tej zmiany.
2. **Aktualizator wisiał na kroku „robię kopię bazy"** — `| Out-Null` i uchwyt
   odziedziczony przez `postgres.exe`.
3. **Druga instalacja cicho podłączała się do bazy pierwszej** i puszczała na
   niej migracje. Zdarzyło się to naprawdę, w trakcie próby. Doszło
   `Sprawdz-Czy-Nasz`: serwer o niezgodnym katalogu danych to teraz głośny błąd
   z nazwami obu katalogów.
4. **`zaplanuj-kopie.ps1` był pustym plikiem** po nieudanej konwersji kodowania,
   a instalator uruchamiał go bez słowa — zadanie kopii zapasowej nie powstawało
   i nikt by się o tym nie dowiedział.

Nie sprawdzone jeszcze na żywo: uruchomienie samego programu z instalacji
(sprawdzony był start bazy, migracje i wszystkie skrypty obsługowe) oraz
zachowanie przy paczce celowo uszkodzonej.

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
- Ekran „Dokumenty z dysku" **nie był jeszcze uruchomiony na prawdziwym
  drzewie katalogów użytkownika**. Testy chodzą po katalogu tymczasowym.
  Pierwsze uruchomienie wymaga ustawienia `KATALOG_SKANU` w pliku `.env`.

## Jak wrócić do pracy

1. `powershell -File narzedzia/lokalny-postgres.ps1 start`
2. `cd backend && uv run pytest` — powinno być zielone.
   Nagłówek przebiegu pokazuje `baza testowa: najem_testy`; jeśli zamiast tego
   jest ostrzeżenie, testy integracyjne są pomijane, a nie zaliczone.
3. Przeczytaj „Co następne" i wybierz zakres na jedną sesję
4. Nowa gałąź, `/plan`, dopiero potem kod

Dane przykładowe są w bazie. Logowania nie ma — program otwiera się od razu.

W bazie deweloperskiej został po tej próbie lokal **`WERYF/E8`** z umową
kontrolną, wskaźniki na lata 2026–2029 i zwaloryzowane czynsze umów `WERYF/E8`
oraz `18A/12`. To dane testowe, nie import użytkownika — można je zignorować
albo wyczyścić razem z resztą demo.

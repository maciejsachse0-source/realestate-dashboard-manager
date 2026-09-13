# ADR 009: Program nie ma logowania ani pojęcia użytkownika

**Data:** 28.08.2026
**Status:** przyjęte
**Dotyczy:** cała aplikacja — schemat bazy, API, interfejs, audyt

## Kontekst

Do tej pory program wymagał logowania imiennego. Sesja żyła w bazie, ciasteczko
było HttpOnly, konta miały role (podgląd → operator → zarządca → administrator),
blokadę po pięciu nieudanych próbach i wymuszoną zmianę hasła przy pierwszym
wejściu. Każda operacja zapisu zostawiała w bazie ślad, kto ją wykonał.

Wynikało to z sekcji 8.1 koncepcji, punkty 5 i 6: „dostęp wyłącznie dla
uprawnionych, logowanie imienne, brak kont współdzielonych" oraz „każdy odczyt
danych wrażliwych i każda zmiana są logowane".

Praktyka rozjechała się z tym założeniem. Program chodzi **na jednym komputerze,
u jednej osoby**, w sieci wewnętrznej, bez dostępu z internetu. Logowanie było
w tej sytuacji kosztem bez odpowiadającej mu korzyści: ekran do przeklikania
przy każdym wejściu i hasło do pamiętania, przy jednym człowieku, który i tak
jest jedynym operatorem.

Użytkownik poprosił o usunięcie całego mechanizmu, świadomie wybierając wariant
pełny (razem z kolumnami w bazie) zamiast samego ukrycia ekranu logowania.

## Decyzja

Program nie ma pojęcia użytkownika. Znika:

* ekran logowania, sesje, hasła, blokada konta, zmiana hasła,
* role i wszystkie sprawdzenia uprawnień w API (każdy endpoint jest otwarty),
* tabele `uzytkownik` i `sesja_uzytkownika`,
* wszystkie kolumny wskazujące autora operacji — `usunal_uzytkownik_id`
  (14 tabel z miękkim usuwaniem), `wgral_uzytkownik_id`,
  `zatwierdzil_uzytkownik_id`, `powiazal_uzytkownik_id`, `pominal_uzytkownik_id`,
  `zmienil_uzytkownik_id`, `wprowadzil_uzytkownik_id`, `przypisany_uzytkownik_id`,
  `obsluzyl_uzytkownik_id`, `log_audytu.uzytkownik_id`,
* przypisywanie zdarzeń do osoby w kokpicie terminów,
* zależność `argon2-cffi`.

Migracja: `007_bez_logowania`.

## Co to łamie

To odstępstwo od trzech rzeczy zapisanych wcześniej. Zapisujemy je wprost,
żeby nikt nie odkrył tego przypadkiem przy czytaniu koncepcji:

1. **Sekcja 8.1 koncepcji, punkt 5** (logowanie imienne, brak kont
   współdzielonych) — nie obowiązuje. Dostępu pilnuje dostęp do komputera.
2. **Sekcja 8.1 koncepcji, punkt 6** (pełny audyt) — obowiązuje połowicznie.
   `log_audytu` nadal zapisuje **co, kiedy i z jakiej wartości na jaką**,
   ale nie **kto**. Przy jednym użytkowniku odpowiedź na „kto" jest znana
   z góry; przy dwóch przestanie być i wtedy trzeba to cofnąć.
3. **Decyzja D4** (człowiek zatwierdza każdą liczbę) — sama reguła zostaje:
   wartość niezatwierdzona nadal nie wchodzi do alertów ani raportów, a
   `parametr_wartosc.zatwierdzono_dnia` nadal mówi **kiedy** zatwierdzono.
   Zniknęło samo nazwisko zatwierdzającego. Wraz z nim odpadło ograniczenie
   `ck_parametr_slad_zatwierdzenia`, które pilnowało pary „kto i kiedy".

## Nieodwracalność

`downgrade` migracji 007 odtwarza **schemat, nie dane**. Historia autorstwa
przepada w chwili `upgrade` i żadna migracja jej nie przywróci — kolumny wracają
puste. Ograniczenie `ck_parametr_slad_zatwierdzenia` wraca jako `NOT VALID`,
bo wiersze zatwierdzone przed usunięciem logowania mają datę bez autora
i pary „kto i kiedy" nie da się już domknąć wstecz.

Kto chce zachować historię autorstwa, musi zrobić kopię bazy **przed**
zastosowaniem tej migracji.

## Odrzucone warianty

**Ukryć sam ekran logowania, resztę zostawić.** Backend działałby zawsze jako
jeden ustalony użytkownik techniczny, audyt i role zostałyby nietknięte, a
powrót do logowania byłby kwestią jednego commita. Odrzucone: użytkownik
świadomie wybrał wariant pełny, znając zapisany wyżej koszt.

**Zostawić tabelę `uzytkownik` jako sierotę.** Odrzucone: tabela bez żadnego
klucza obcego wskazującego na nią to martwy kod, a przechowywanie skrótów
haseł dla mechanizmu, którego już nie ma, jest gorsze niż ich brak.

## Powrót

Gdyby program miał kiedyś obsłużyć więcej niż jedną osobę, logowanie trzeba
odbudować od zera: migracja `downgrade` da sam schemat, a kod uwierzytelniania
trzeba przywrócić z historii Gita (commit sprzed tej zmiany, katalog
`backend/src/najem/auth/`). Nie jest to duża praca — pod warunkiem, że
zrobi się ją świadomie, a nie przy okazji.

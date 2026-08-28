# ADR 008: Dokumenty z dysku są linkowane, nie kopiowane

**Data:** 28.08.2026
**Status:** przyjęte
**Dotyczy:** ekran „Dokumenty z dysku", tabela `dokument`, kopie zapasowe

## Kontekst

Do tej pory każdy dokument trafiał do systemu przez formularz w przeglądarce
i lądował w przechowalni (`dane/dokumenty/`) pod nazwą pochodzącą ze skrótu
treści. System odpowiadał za trwałość pliku od chwili wgrania.

Użytkownik ma jednak gotowe, uporządkowane drzewo katalogów na dysku:

```
Budynki/<budynek>/Umowy najmu/<folder lokalu>/<pliki>
```

Wgrywanie każdego pliku po kolei przez przeglądarkę oznaczałoby przy migracji
archiwum kilkaset ręcznych operacji, a po nich dwie kopie każdej umowy:
jedną w folderze użytkownika, drugą w przechowalni.

Program działa **na jednym komputerze, u jednej osoby**. Użytkownik poprosił
wprost, żeby dokumenty były linkowane.

## Decyzja

Dokument wczytany z dysku jest **odnośnikiem**, nie kopią. Kolumna
`dokument.przechowywanie` rozróżnia dwa tryby:

* `kopia` — plik wgrany przez przeglądarkę, leży w przechowalni systemu,
  ścieżka jest względna wobec `KATALOG_DOKUMENTOW`;
* `link` — plik został wskazany na dysku i tam **zostaje**, ścieżka jest
  względna wobec `KATALOG_SKANU`.

W obu trybach zapisujemy SHA-256 i rozmiar, więc dowód, że dokument się nie
zmienił, działa tak samo.

## Konsekwencje

**Dobre:**

* zero duplikacji — jeden plik, jedno miejsce, ten sam, który użytkownik zna
  z Eksploratora;
* migracja archiwum to przejrzenie listy, a nie kilkaset wgrań;
* zmiana pliku na dysku jest wykrywalna, bo skrót przestaje się zgadzać.

**Zła, i to jest realny koszt:**

* **przeniesienie albo przemianowanie pliku w Eksploratorze zrywa odnośnik.**
  System nie ma jak temu zapobiec — nie kontroluje tego katalogu.

Dlatego są dwa mechanizmy obronne:

1. `GET /api/v1/skan/sprawdz` (przycisk „Sprawdź odnośniki") przechodzi po
   wszystkich zlinkowanych dokumentach i mówi, których plików nie ma pod
   zapisaną ścieżką albo którym zmieniła się treść;
2. pobranie zerwanego dokumentu zwraca 410 z komunikatem mówiącym, co się
   stało, a nie pustą stronę.

**Najważniejsza konsekwencja operacyjna:** kopia zapasowa samej bazy przestaje
wystarczać. Backup musi obejmować **bazę razem z katalogiem `KATALOG_SKANU`**.
Przy trybie `kopia` wystarczyłaby baza plus `dane/dokumenty/`.

## Rozważone i odrzucone

**Kopiowanie do przechowalni (dotychczasowe zachowanie).** Odporne na
przenoszenie plików, ale podwaja miejsce i tworzy drugą wersję prawdy:
użytkownik poprawia plik w swoim folderze, a system pokazuje starą kopię
i nawet o tym nie wie. Odrzucone na wyraźną prośbę użytkownika.

**Przenoszenie plików do przechowalni.** Rozwiązuje duplikację, ale zabiera
użytkownikowi jego własne drzewo katalogów, do którego zagląda też poza
programem. Nie do przyjęcia.

**Dowiązania symboliczne systemu plików.** Na Windowsie wymagają uprawnień
administratora albo trybu dewelopera. Odpada dla aplikacji, która ma się
uruchamiać kliknięciem skrótu.

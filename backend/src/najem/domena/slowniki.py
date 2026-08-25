"""Slowniki wartosci uzywane przez caly system.

Mieszkaja w warstwie domenowej, bo sa czystym Pythonem i bo zalezność ma isc
w jedna strone: modele/ importuja domena/, nigdy odwrotnie.

Wszystkie to StrEnum, wiec w bazie leza jako czytelny tekst, a nie jako liczba,
ktorej nikt nie rozszyfruje przy zagladaniu do bazy przez psql.
"""

from enum import StrEnum


class RolaUzytkownika(StrEnum):
    """Koncepcja, sekcja 7.9. Kolejnosc od najmniejszych uprawnien."""

    PODGLAD = "podglad"
    OPERATOR = "operator"
    ZARZADCA = "zarzadca"
    ADMINISTRATOR = "administrator"


class TypLokalu(StrEnum):
    HANDLOWY = "handlowy"
    BIUROWY = "biurowy"
    MAGAZYN = "magazyn"
    MIEJSCE_POSTOJOWE = "miejsce_postojowe"
    INNY = "inny"


class StatusLokalu(StrEnum):
    WOLNY = "wolny"
    WYNAJETY = "wynajety"
    W_TRAKCIE_WYDANIA = "w_trakcie_wydania"


class StatusOkresuNajmu(StrEnum):
    """Koncepcja, sekcja 3.2. Dozwolone przejscia sa w domena/stany.py."""

    PRZYGOTOWANIE = "przygotowanie"
    AKTYWNA = "aktywna"
    WYPOWIEDZIANA = "wypowiedziana"
    ZAKONCZONA = "zakonczona"


class BazaOkresuNajmu(StrEnum):
    """Od ktorej daty liczy sie okres najmu (regula R1)."""

    DATA_ZAWARCIA = "data_zawarcia"
    DATA_PRZEKAZANIA = "data_przekazania"


class TypDokumentu(StrEnum):
    UMOWA = "umowa"
    ANEKS = "aneks"
    PROTOKOL_PRZEKAZANIA = "protokol_przekazania"
    PROTOKOL_ZDAWCZY = "protokol_zdawczy"
    POLISA = "polisa"
    PROTOKOL_PRZEGLADU = "protokol_przegladu"
    WYPOWIEDZENIE = "wypowiedzenie"
    INNE = "inne"


class StatusPrzetworzenia(StrEnum):
    """Stan pipeline'u dokumentu (koncepcja, sekcja 4.3). Ekstrakcja wchodzi w E9."""

    WGRANY = "wgrany"
    W_TRAKCIE = "w_trakcie"
    PRZETWORZONY = "przetworzony"
    BLAD = "blad"
    POMINIETY = "pominiety"


class TypWartosci(StrEnum):
    """Ktora kolumna wartosci w parametr_wartosc jest wypelniona."""

    KWOTA = "kwota"
    LICZBA = "liczba"
    DATA = "data"
    FLAGA = "flaga"
    TEKST = "tekst"


class StatusWeryfikacji(StrEnum):
    """Decyzja D4: czlowiek zatwierdza kazda liczbe, zanim trafi do wynikow.

    Do stanu efektywnego wchodza wylacznie ZATWIERDZONA i POPRAWIONA.
    """

    ZAPROPONOWANA = "zaproponowana"
    ZATWIERDZONA = "zatwierdzona"
    POPRAWIONA = "poprawiona"
    ODRZUCONA = "odrzucona"
    NIEJEDNOZNACZNA = "niejednoznaczna"


#: Statusy, ktore wchodza do stanu efektywnego, alertow i raportow.
STATUSY_OBOWIAZUJACE: frozenset[StatusWeryfikacji] = frozenset(
    {StatusWeryfikacji.ZATWIERDZONA, StatusWeryfikacji.POPRAWIONA}
)


class RodzajKwoty(StrEnum):
    """Kazda kwota musi jawnie mowic, czy jest netto czy brutto (plan, punkt A)."""

    NETTO = "netto"
    BRUTTO = "brutto"


class OkresRozliczeniowy(StrEnum):
    MIESIECZNY = "miesieczny"
    KWARTALNY = "kwartalny"
    POLROCZNY = "polroczny"
    ROCZNY = "roczny"


class RodzajZabezpieczenia(StrEnum):
    KAUCJA = "kaucja"
    WEKSEL = "weksel"
    GWARANCJA_BANKOWA = "gwarancja_bankowa"
    POLISA = "polisa"


class StatusZabezpieczenia(StrEnum):
    """Reguly R4, R5, R6."""

    WYMAGANE = "wymagane"
    DOSTARCZONE = "dostarczone"
    ZWROCONE = "zwrocone"
    ZATRZYMANE = "zatrzymane"
    BRAK = "brak"


class KtoObciazany(StrEnum):
    NAJEMCA = "najemca"
    WYNAJMUJACY = "wynajmujacy"


class StatusPrzegladu(StrEnum):
    AKTUALNY = "aktualny"
    ZBLIZA_SIE = "zbliza_sie"
    PRZETERMINOWANY = "przeterminowany"
    NIEUSTALONY = "nieustalony"


class WagaZdarzenia(StrEnum):
    INFORMACJA = "informacja"
    OSTRZEZENIE = "ostrzezenie"
    KRYTYCZNE = "krytyczne"


class StatusZdarzenia(StrEnum):
    OTWARTE = "otwarte"
    OBSLUZONE = "obsluzone"
    ODROCZONE = "odroczone"


class TypZdarzenia(StrEnum):
    """Katalog z sekcji 6 koncepcji. Generator zdarzen powstaje w etapie E3."""

    KONIEC_UMOWY_SIE_ZBLIZA = "koniec_umowy_sie_zbliza"
    MINAL_TERMIN_WYPOWIEDZENIA = "minal_termin_wypowiedzenia"
    UMOWA_WYGASLA_BRAK_NASTEPCZEJ = "umowa_wygasla_brak_nastepczej"
    WALORYZACJA_SIE_ZBLIZA = "waloryzacja_sie_zbliza"
    WSKAZNIK_GUS_OPUBLIKOWANY = "wskaznik_gus_opublikowany"
    POLISA_NIEDOSTARCZONA = "polisa_niedostarczona"
    POLISA_WYGASA = "polisa_wygasa"
    POLISA_PONIZEJ_KWOTY = "polisa_ponizej_kwoty"
    KAUCJA_NIEWPLACONA = "kaucja_niewplacona"
    KAUCJA_DO_ZWROTU = "kaucja_do_zwrotu"
    WEKSEL_DO_PRZELICZENIA = "weksel_do_przeliczenia"
    PRZEGLAD_SIE_ZBLIZA = "przeglad_sie_zbliza"
    PRZEGLAD_PRZETERMINOWANY = "przeglad_przeterminowany"
    BRAK_PROTOKOLU_PRZEKAZANIA = "brak_protokolu_przekazania"
    PROFIL_NIEKOMPLETNY = "profil_niekompletny"
    DOKUMENT_CZEKA_NA_WERYFIKACJE = "dokument_czeka_na_weryfikacje"
    ZADANIE_WLASNE = "zadanie_wlasne"


class RodzajWskaznika(StrEnum):
    """Regula R2. Pytanie otwarte nr 4 koncepcji: ktory dokladnie GUS."""

    GUS_ROK_DO_ROKU = "gus_rok_do_roku"
    GUS_SREDNIOROCZNY = "gus_srednioroczny"
    STALA_STAWKA = "stala_stawka"


class OperacjaAudytu(StrEnum):
    UTWORZENIE = "utworzenie"
    ZMIANA = "zmiana"
    USUNIECIE = "usuniecie"
    ODCZYT_WRAZLIWY = "odczyt_wrazliwy"

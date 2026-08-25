"""Wartosci parametrow umowy i stan efektywny na dzien.

To jest domenowy odpowiednik tabeli parametr_wartosc i mechanika z decyzji D2.
Warstwa domenowa nie zna SQLAlchemy, wiec repozytorium przepisuje wiersze
na `WartoscParametru`, a wszystkie wyliczenia dzieja sie tutaj, na czystych
strukturach, ktore da sie przetestowac bez bazy.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from najem.domena.pieniadze import Kwota
from najem.domena.slowniki import (
    STATUSY_OBOWIAZUJACE,
    StatusWeryfikacji,
    TypWartosci,
)


@dataclass(frozen=True)
class WartoscParametru:
    """Jedna wersja parametru wraz z okresem, w ktorym obowiazuje.

    Dokladnie jedno z pol wartosci jest wypelnione i musi zgadzac sie z `typ`.
    To samo ograniczenie pilnuje baza, ale dane trafiaja tu takze z importu
    z Excela, ktory bazy jeszcze nie widzial.
    """

    klucz: str
    typ: TypWartosci
    obowiazuje_od: date
    obowiazuje_do: date | None
    status: StatusWeryfikacji

    kwota: Kwota | None = None
    liczba: Decimal | None = None
    data: date | None = None
    flaga: bool | None = None
    tekst: str | None = None

    #: Identyfikator wiersza w bazie. Rozstrzyga remis, gdy dwie wartosci
    #: zaczynaja obowiazywac tego samego dnia.
    identyfikator: int | None = None
    dokument_zrodlowy_id: int | None = None

    def __post_init__(self) -> None:
        if self.obowiazuje_do is not None and self.obowiazuje_do < self.obowiazuje_od:
            raise ValueError(
                f"Okres obowiązywania parametru {self.klucz!r} kończy się "
                f"({self.obowiazuje_do}) przed swoim początkiem ({self.obowiazuje_od})."
            )

        wypelnione = {
            TypWartosci.KWOTA: self.kwota is not None,
            TypWartosci.LICZBA: self.liczba is not None,
            TypWartosci.DATA: self.data is not None,
            TypWartosci.FLAGA: self.flaga is not None,
            TypWartosci.TEKST: self.tekst is not None,
        }
        if not wypelnione[self.typ]:
            raise ValueError(
                f"Parametr {self.klucz!r} ma typ {self.typ.value}, "
                f"ale pole {self.typ.value} jest puste."
            )
        nadmiarowe = [typ.value for typ, jest in wypelnione.items() if jest and typ is not self.typ]
        if nadmiarowe:
            raise ValueError(
                f"Parametr {self.klucz!r} ma typ {self.typ.value}, "
                f"ale wypełniono także: {', '.join(sorted(nadmiarowe))}."
            )

    @property
    def obowiazujaca(self) -> bool:
        """Czy wartosc przeszla decyzje czlowieka (decyzja D4)."""
        return self.status in STATUSY_OBOWIAZUJACE

    def czy_dotyczy(self, dzien: date) -> bool:
        """Czy wartosc obejmuje podany dzien. Granice okresu sa domkniete."""
        if dzien < self.obowiazuje_od:
            return False
        return self.obowiazuje_do is None or dzien <= self.obowiazuje_do


def _pierwszenstwo(wartosc: WartoscParametru) -> tuple[date, int]:
    """Klucz sortowania: pozniejsza data wygrywa, a przy remisie wiekszy
    identyfikator, czyli wartosc wprowadzona pozniej.

    Regula musi byc deterministyczna. Bez rozstrzygniecia remisu ten sam stan
    raz pokazywalby jedno, raz drugie, zaleznie od kolejnosci wierszy z bazy.
    """
    return (wartosc.obowiazuje_od, wartosc.identyfikator or 0)


def wartosc_na_dzien(
    wartosci: Iterable[WartoscParametru],
    klucz: str,
    na_dzien: date,
) -> WartoscParametru | None:
    """Wartosc parametru obowiazujaca podanego dnia albo None.

    None znaczy "nieustalone" i jest poprawnym wynikiem, a nie awaria (D5).
    Wartosci niezatwierdzone sa pomijane, wiec nowsza propozycja nie przesloni
    starszej wartosci zatwierdzonej.
    """
    pasujace = [
        w for w in wartosci if w.klucz == klucz and w.obowiazujaca and w.czy_dotyczy(na_dzien)
    ]
    if not pasujace:
        return None
    return max(pasujace, key=_pierwszenstwo)


def stan_efektywny(
    wartosci: Iterable[WartoscParametru],
    na_dzien: date,
) -> dict[str, WartoscParametru]:
    """Komplet parametrow obowiazujacych podanego dnia, po jednym na klucz.

    Klucze bez obowiazujacej wartosci w ogole nie pojawiaja sie w wyniku.
    Pozycja o wartosci None bylaby nieodrozalna od wartosci pustej.
    """
    lista = list(wartosci)
    wynik: dict[str, WartoscParametru] = {}
    for klucz in {w.klucz for w in lista}:
        wybrana = wartosc_na_dzien(lista, klucz, na_dzien)
        if wybrana is not None:
            wynik[klucz] = wybrana
    return wynik


def historia_klucza(
    wartosci: Iterable[WartoscParametru],
    klucz: str,
) -> list[WartoscParametru]:
    """Wszystkie wersje parametru w kolejnosci chronologicznej.

    Celowo bez filtrowania po statusie: zakladka historii na karcie lokalu ma
    pokazywac takze propozycje czekajace na decyzje, wyroznione wizualnie.
    Ukrycie ich tutaj ukryloby prace do zrobienia.
    """
    return sorted((w for w in wartosci if w.klucz == klucz), key=_pierwszenstwo)


def klucze_bez_wartosci(
    wartosci: Iterable[WartoscParametru],
    wymagane: Sequence[str] | set[str] | frozenset[str],
    na_dzien: date,
) -> set[str]:
    """Ktorych wymaganych parametrow brakuje podanego dnia.

    Podstawa wskaznika kompletnosci profilu (decyzja D6, regula R9).
    Wartosc niezatwierdzona liczy sie jako brak, bo profil oparty na samych
    propozycjach nie jest kompletny, tylko czeka na czlowieka.
    """
    lista = list(wartosci)
    return {klucz for klucz in wymagane if wartosc_na_dzien(lista, klucz, na_dzien) is None}

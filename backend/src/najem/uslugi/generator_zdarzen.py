"""Uruchomienie generatora zdarzen i zapis wyniku do bazy.

Idempotencja stoi na dwoch nogach:

1. Generator w `domena/zdarzenia.py` jest czysta funkcja i dla tych samych
   danych zwraca dokladnie te sama liste.
2. Zapis uzywa ON CONFLICT DO NOTHING na kluczu naturalnym
   (typ, encja_typ, encja_id, data_zdarzenia).

Druga noga jest wazniejsza, bo pilnuje takze przypadku dwoch procesow
uruchomionych rownolegle. Konwencja w kodzie by tego nie zalatwila.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from najem.domena.zdarzenia import ProponowaneZdarzenie, zdarzenia_dla_portfela
from najem.modele import Zdarzenie
from najem.repozytoria.stan_umowy import wczytaj_stany_portfela


@dataclass(frozen=True)
class WynikGeneratora:
    """Co generator zrobil. Trafia do logow i do odpowiedzi endpointu."""

    data_odniesienia: date
    umow_sprawdzonych: int
    zdarzen_wyliczonych: int
    zdarzen_dodanych: int

    @property
    def zdarzen_pominietych(self) -> int:
        """Te, ktore juz byly w bazie. Przy powtornym przebiegu to komplet."""
        return self.zdarzen_wyliczonych - self.zdarzen_dodanych


def zapisz_zdarzenia(sesja: Session, proponowane: list[ProponowaneZdarzenie]) -> int:
    """Zapisuje zdarzenia, pomijajac te, ktore juz istnieja. Zwraca liczbe dodanych."""
    if not proponowane:
        return 0

    wiersze = [
        {
            "typ": z.typ,
            "encja_typ": z.encja_typ,
            "encja_id": z.encja_id,
            "lokal_id": z.lokal_id,
            "data_zdarzenia": z.data_zdarzenia,
            "waga": z.waga,
            "tresc": z.tresc,
        }
        for z in proponowane
    ]

    polecenie = (
        insert(Zdarzenie)
        .values(wiersze)
        .on_conflict_do_nothing(
            index_elements=["typ", "encja_typ", "encja_id", "data_zdarzenia"],
        )
        .returning(Zdarzenie.id)
    )
    return len(sesja.execute(polecenie).scalars().all())


def uruchom_generator(sesja: Session, dzis: date) -> WynikGeneratora:
    """Pelny przebieg: wczytaj stan, wylicz zdarzenia, zapisz nowe.

    Date odniesienia podaje wolajacy, a nie funkcja. Dzieki temu da sie
    przeliczyc zdarzenia na dowolny dzien, a testy sa deterministyczne.
    """
    stany = wczytaj_stany_portfela(sesja, dzis)
    proponowane = zdarzenia_dla_portfela(stany, dzis)
    dodane = zapisz_zdarzenia(sesja, proponowane)

    return WynikGeneratora(
        data_odniesienia=dzis,
        umow_sprawdzonych=len(stany),
        zdarzen_wyliczonych=len(proponowane),
        zdarzen_dodanych=dodane,
    )

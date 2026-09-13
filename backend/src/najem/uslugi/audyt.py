"""Zapis do logu audytu.

Kazda zmiana danych zostawia slad: kiedy, co, z jakiej wartosci na jaka.
Bez wyjatkow, takze dla zmian recznych.

Kolumny "kto" tu nie ma: logowanie zostalo usuniete z systemu, wiec nie ma
czego zapisac. Odstepstwo od sekcji 8.1 punkt 6 koncepcji, ADR 009.

Tabela `log_audytu` jest chroniona wyzwalaczem przed UPDATE i DELETE, wiec
zapis jest jednokierunkowy takze dla nas.
"""

from collections.abc import Iterable
from typing import Protocol, cast

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.state import InstanceState

from najem.domena.slowniki import OperacjaAudytu
from najem.modele import LogAudytu

#: Pola techniczne, ktorych zmiany nie zapisujemy: to szum, nie informacja.
POLA_POMIJANE: frozenset[str] = frozenset({"utworzono", "zmodyfikowano", "wersja"})


class MaIdentyfikator(Protocol):
    id: int


def _na_tekst(wartosc: object) -> str | None:
    if wartosc is None:
        return None
    return str(wartosc)


def zapisz_zmiane(
    sesja: Session,
    obiekt: object,
    *,
    operacja: OperacjaAudytu,
    id_zadania: str | None = None,
    adres_ip: str | None = None,
    pola: Iterable[str] | None = None,
) -> int:
    """Zapisuje zmiany obiektu do logu. Zwraca liczbe dopisanych wierszy.

    Zmienione pola odczytujemy z historii sesji SQLAlchemy, wiec wolajacy
    nie musi ich wyliczac ani pamietac starych wartosci.
    """
    stan = cast(InstanceState[object], inspect(obiekt))
    tabela = obiekt.__class__.__tablename__  # type: ignore[attr-defined]
    rekord_id = getattr(obiekt, "id", None)

    if operacja is OperacjaAudytu.UTWORZENIE:
        sesja.add(
            LogAudytu(
                operacja=operacja,
                tabela=tabela,
                rekord_id=rekord_id,
                id_zadania=id_zadania,
                adres_ip=adres_ip,
            )
        )
        return 1

    dopisane = 0
    do_sprawdzenia = set(pola) if pola is not None else None

    for atrybut in stan.attrs:
        nazwa = atrybut.key
        if nazwa in POLA_POMIJANE:
            continue
        if do_sprawdzenia is not None and nazwa not in do_sprawdzenia:
            continue

        historia = atrybut.load_history()
        if not historia.has_changes():
            continue
        # Relacje zapisujemy przez klucze obce, nie przez kolekcje obiektow.
        if atrybut.key not in {kolumna.key for kolumna in stan.mapper.column_attrs}:
            continue

        stara = historia.deleted[0] if historia.deleted else None
        nowa = historia.added[0] if historia.added else None
        if stara == nowa:
            continue

        wartosc_stara, wartosc_nowa = _na_tekst(stara), _na_tekst(nowa)

        sesja.add(
            LogAudytu(
                operacja=operacja,
                tabela=tabela,
                rekord_id=rekord_id,
                pole=nazwa,
                wartosc_stara=wartosc_stara,
                wartosc_nowa=wartosc_nowa,
                id_zadania=id_zadania,
                adres_ip=adres_ip,
            )
        )
        dopisane += 1

    return dopisane


def zapisz_odczyt_wrazliwy(
    sesja: Session,
    *,
    tabela: str,
    rekord_id: int | None,
    id_zadania: str | None = None,
    adres_ip: str | None = None,
) -> None:
    """Slad odczytu danych wrazliwych (koncepcja, sekcja 8.1 punkt 6).

    Uzywane przy pobieraniu dokumentow i przy podgladzie danych najemcy.
    """
    sesja.add(
        LogAudytu(
            operacja=OperacjaAudytu.ODCZYT_WRAZLIWY,
            tabela=tabela,
            rekord_id=rekord_id,
            id_zadania=id_zadania,
            adres_ip=adres_ip,
        )
    )

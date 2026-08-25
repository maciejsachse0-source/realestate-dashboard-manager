"""Waloryzacja roczna: wyliczenie propozycji i ich zbiorcze zatwierdzenie.

Regula R2 opisuje mechanike, a `domena/reguly/waloryzacja.py` ja liczy.
Ten modul tylko wyciaga dane z bazy, wola regule i zapisuje wynik.

Rzecz, dla ktorej ten ekran w ogole powstaje: wskaznik wprowadza sie **raz**,
a efekt jest na wszystkich umowach. Dzis to kilkanascie godzin pracy recznej
raz do roku.

Dwa kroki sa rozdzielone celowo. Pierwszy niczego nie zapisuje, wiec da sie
obejrzec propozycje i wycofac. Drugi zapisuje wszystko w jednej transakcji.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from najem.domena.parametry import stan_efektywny
from najem.domena.pieniadze import Kwota
from najem.domena.reguly.data_zakonczenia import data_zakonczenia
from najem.domena.reguly.waloryzacja import (
    PropozycjaWaloryzacji,
    propozycja_waloryzacji,
    wskaznik_dla_umowy,
)
from najem.domena.slowniki import (
    STATUSY_OBOWIAZUJACE,
    BazaOkresuNajmu,
    OperacjaAudytu,
    RodzajWskaznika,
    StatusOkresuNajmu,
    StatusWeryfikacji,
    TypWartosci,
    TypZdarzenia,
    WagaZdarzenia,
)
from najem.domena.zdarzenia import ProponowaneZdarzenie
from najem.modele import (
    OkresNajmu,
    ParametrWartosc,
    WskaznikWaloryzacji,
    Zabezpieczenie,
)
from najem.repozytoria.stan_umowy import na_wartosc_domenowa
from najem.uslugi.audyt import zapisz_zmiane
from najem.uslugi.generator_zdarzen import zapisz_zdarzenia

KLUCZ_CZYNSZU = "czynsz_podstawowy"

JEDEN_DZIEN = timedelta(days=1)

#: Statusy, przy ktorych umowa w ogole wchodzi do przebiegu waloryzacji.
#: Zakonczonej umowy nie waloryzujemy.
STATUSY_CZYNNE = (
    StatusOkresuNajmu.PRZYGOTOWANIE,
    StatusOkresuNajmu.AKTYWNA,
    StatusOkresuNajmu.WYPOWIEDZIANA,
)


@dataclass(frozen=True)
class PozycjaWaloryzacji:
    """Jedna umowa w przebiegu: albo propozycja, albo powod wylaczenia."""

    okres_najmu_id: int
    lokal_id: int
    oznaczenie_lokalu: str
    najemca: str

    propozycja: PropozycjaWaloryzacji | None = None
    powod_wylaczenia: str | None = None


@dataclass
class SumaWaluty:
    """Suma propozycji w jednej walucie."""

    waluta: str
    umow: int = 0
    przed: Decimal = Decimal("0.00")
    po: Decimal = Decimal("0.00")

    @property
    def roznica(self) -> Decimal:
        return self.po - self.przed


@dataclass
class PrzebiegWaloryzacji:
    """Co system proponuje na dany rok."""

    rok: int
    objete: list[PozycjaWaloryzacji] = field(default_factory=list)
    wylaczone: list[PozycjaWaloryzacji] = field(default_factory=list)

    def podsumowanie(self, tylko: set[int] | None = None) -> list["SumaWaluty"]:
        """Sumy w rozbiciu na waluty, opcjonalnie dla wybranych umow.

        Rozbicie na waluty nie jest ozdoba. Umowa w EUR i umowa w PLN nie maja
        wspolnej sumy, a dodanie ich do siebie dawaloby liczbe, ktora wyglada
        na pieniadze i nie znaczy nic. Lepiej pokazac dwie linie.

        `tylko` sluzy podgladowi przed zatwierdzeniem: uzytkownik moze odznaczyc
        czesc propozycji i musi zobaczyc sume tego, co faktycznie zatwierdza.
        """
        po_walucie: dict[str, SumaWaluty] = {}
        for pozycja in self.objete:
            if pozycja.propozycja is None:
                continue
            if tylko is not None and pozycja.okres_najmu_id not in tylko:
                continue

            p = pozycja.propozycja
            suma = po_walucie.setdefault(p.kwota_nowa.waluta, SumaWaluty(p.kwota_nowa.waluta))
            suma.umow += 1
            suma.przed += p.kwota_stara.wartosc
            suma.po += p.kwota_nowa.wartosc

        return sorted(po_walucie.values(), key=lambda s: s.waluta)


@dataclass
class WynikZatwierdzenia:
    """Co zostalo zapisane."""

    rok: int
    umow_zwaloryzowanych: int = 0
    zdarzen_o_wekslach: int = 0


class BladWaloryzacji(Exception):
    """Przebieg nie moze sie odbyc."""


def wskazniki_na_rok(sesja: Session, rok: int) -> dict[RodzajWskaznika, Decimal]:
    """Wskazniki wprowadzone dla danego roku, po rodzaju."""
    wiersze = sesja.scalars(select(WskaznikWaloryzacji).where(WskaznikWaloryzacji.rok == rok)).all()
    return {w.rodzaj: w.wartosc_procent for w in wiersze}


def _czynsz_przed_waloryzacja(okres: OkresNajmu, dzien: date) -> Kwota | None:
    """Czynsz obowiazujacy dzien przed wejsciem waloryzacji.

    Bierzemy dzien wczesniejszy, a nie sam dzien wejscia: gdyby ktos uruchomil
    przebieg drugi raz, na dzien wejscia obowiazywalby juz nowy czynsz
    i waloryzacja naliczylaby sie od niego po raz drugi.
    """
    wartosci = [
        w
        for w in (na_wartosc_domenowa(p) for p in okres.parametry if p.usunieto_dnia is None)
        if w is not None
    ]
    stan = stan_efektywny(wartosci, dzien)
    pozycja = stan.get(KLUCZ_CZYNSZU)
    return pozycja.kwota if pozycja is not None else None


def _juz_zwaloryzowana(okres: OkresNajmu, rok: int) -> bool:
    """Czy przebieg waloryzacji tego roku juz raz przeszedl po tej umowie.

    Pytamy o znacznik, a nie o date wejscia. Rozpoznawanie po dacie mylilo
    aneks wchodzacy 1 stycznia z waloryzacja, a niezatwierdzona propozycja
    czynszu w tym dniu wykluczala umowe z komunikatem, ze podwyzka juz byla.
    """
    return any(
        p.klucz == KLUCZ_CZYNSZU and p.waloryzacja_rok == rok and p.usunieto_dnia is None
        for p in okres.parametry
    )


def _poczatek_umowy(okres: OkresNajmu) -> date | None:
    """Dzien, od ktorego liczy sie najem (regula R1: zwykle data przekazania)."""
    if okres.bazuje_na_dacie is BazaOkresuNajmu.DATA_PRZEKAZANIA:
        return okres.data_przekazania
    return okres.data_zawarcia


def _koniec_umowy(okres: OkresNajmu) -> date | None:
    """Dzien, w ktorym umowa sie konczy, albo None jesli nie da sie go ustalic."""
    if okres.data_zakonczenia_faktyczna is not None:
        return okres.data_zakonczenia_faktyczna
    return data_zakonczenia(
        bazuje_na=okres.bazuje_na_dacie,
        okres_miesiace=okres.okres_zawarcia_miesiace,
        data_zawarcia=okres.data_zawarcia,
        data_przekazania=okres.data_przekazania,
    ).wartosc


def przygotuj_przebieg(sesja: Session, rok: int) -> PrzebiegWaloryzacji:
    """Wylicza propozycje dla wszystkich umow. **Niczego nie zapisuje.**"""
    wskazniki = wskazniki_na_rok(sesja, rok)

    okresy = sesja.scalars(
        select(OkresNajmu)
        .where(OkresNajmu.usunieto_dnia.is_(None), OkresNajmu.status.in_(STATUSY_CZYNNE))
        .options(
            selectinload(OkresNajmu.parametry),
            selectinload(OkresNajmu.lokal),
            selectinload(OkresNajmu.najemca),
        )
        .order_by(OkresNajmu.id)
    ).all()

    przebieg = PrzebiegWaloryzacji(rok=rok)

    for okres in okresy:
        opis = PozycjaWaloryzacji(
            okres_najmu_id=okres.id,
            lokal_id=okres.lokal_id,
            oznaczenie_lokalu=okres.lokal.oznaczenie,
            najemca=okres.najemca.nazwa_pelna,
        )

        if not okres.waloryzacja_podlega:
            przebieg.wylaczone.append(_z_powodem(opis, "Umowa nie podlega waloryzacji."))
            continue
        if okres.waloryzacja_miesiac is None:
            przebieg.wylaczone.append(_z_powodem(opis, "Umowa nie określa miesiąca waloryzacji."))
            continue

        obowiazuje_od = date(rok, okres.waloryzacja_miesiac, 1)
        if _juz_zwaloryzowana(okres, rok):
            przebieg.wylaczone.append(
                _z_powodem(opis, f"Ta umowa była już waloryzowana w przebiegu {rok}.")
            )
            continue

        # Status okresu najmu zmienia czlowiek, wiec umowa, ktora skonczyla sie
        # w czerwcu, potrafi wisiec w bazie jako aktywna. Podwyzka czynszu dla
        # najmu, ktory juz nie trwa, trafilaby do pisma dla bylego najemcy.
        koniec = _koniec_umowy(okres)
        if koniec is not None and koniec < obowiazuje_od:
            przebieg.wylaczone.append(
                _z_powodem(
                    opis,
                    f"Umowa kończy się {koniec.strftime('%d.%m.%Y')}, "
                    f"czyli przed wejściem waloryzacji {obowiazuje_od.strftime('%d.%m.%Y')}.",
                )
            )
            continue

        poczatek = _poczatek_umowy(okres)
        if poczatek is not None and poczatek > obowiazuje_od:
            przebieg.wylaczone.append(
                _z_powodem(
                    opis,
                    f"Umowa zaczyna się {poczatek.strftime('%d.%m.%Y')}, "
                    f"czyli po wejściu waloryzacji {obowiazuje_od.strftime('%d.%m.%Y')}.",
                )
            )
            continue

        wskaznik = wskaznik_dla_umowy(
            rodzaj=okres.waloryzacja_rodzaj_wskaznika,
            stala_stawka_procent=okres.waloryzacja_stala_stawka,
            wskazniki_gus=wskazniki,
        )
        if not wskaznik.ustalone:
            przebieg.wylaczone.append(_z_powodem(opis, wskaznik.powod_braku or ""))
            continue

        czynsz = _czynsz_przed_waloryzacja(okres, obowiazuje_od - JEDEN_DZIEN)
        propozycja = propozycja_waloryzacji(
            czynsz=czynsz,
            podlega=True,
            miesiac_waloryzacji=okres.waloryzacja_miesiac,
            rok=rok,
            wskaznik_procent=wskaznik.wymagaj(),
            data_pierwszej_waloryzacji=okres.waloryzacja_pierwsza_data,
        )

        if propozycja.ustalone:
            przebieg.objete.append(
                PozycjaWaloryzacji(
                    okres_najmu_id=opis.okres_najmu_id,
                    lokal_id=opis.lokal_id,
                    oznaczenie_lokalu=opis.oznaczenie_lokalu,
                    najemca=opis.najemca,
                    propozycja=propozycja.wymagaj(),
                )
            )
        else:
            przebieg.wylaczone.append(_z_powodem(opis, propozycja.powod_braku or ""))

    return przebieg


def zmiany_zapisane(sesja: Session, rok: int) -> list[PozycjaWaloryzacji]:
    """Waloryzacje **juz zapisane** w danym roku, odczytane ze znacznika.

    Potrzebne, bo pisma do najemcow pisze sie po zatwierdzeniu, a wtedy lista
    propozycji jest juz pusta.

    Wiersze rozpoznajemy po `waloryzacja_rok`, a nie po dacie wejscia. Aneks
    wchodzacy 1 stycznia wygladalby identycznie, a wyliczony z niego „wskaznik"
    trafilby do pisma jako procent, ktorego nigdy nie bylo.
    """
    wiersze = sesja.scalars(
        select(ParametrWartosc)
        .where(
            ParametrWartosc.klucz == KLUCZ_CZYNSZU,
            ParametrWartosc.waloryzacja_rok == rok,
            ParametrWartosc.usunieto_dnia.is_(None),
            ParametrWartosc.status_weryfikacji.in_(STATUSY_OBOWIAZUJACE),
        )
        .options(
            selectinload(ParametrWartosc.okres_najmu).selectinload(OkresNajmu.parametry),
            selectinload(ParametrWartosc.okres_najmu).selectinload(OkresNajmu.lokal),
            selectinload(ParametrWartosc.okres_najmu).selectinload(OkresNajmu.najemca),
        )
        .order_by(ParametrWartosc.okres_najmu_id)
    ).all()

    zapisane: list[PozycjaWaloryzacji] = []
    for wiersz in wiersze:
        okres = wiersz.okres_najmu
        if okres.usunieto_dnia is not None:
            continue

        wartosc = na_wartosc_domenowa(wiersz)
        nowa_kwota = wartosc.kwota if wartosc is not None else None
        stara_kwota = _czynsz_przed_waloryzacja(okres, wiersz.obowiazuje_od - JEDEN_DZIEN)
        if nowa_kwota is None or stara_kwota is None:
            continue

        assert wiersz.waloryzacja_wskaznik_procent is not None
        zapisane.append(
            PozycjaWaloryzacji(
                okres_najmu_id=okres.id,
                lokal_id=okres.lokal_id,
                oznaczenie_lokalu=okres.lokal.oznaczenie,
                najemca=okres.najemca.nazwa_pelna,
                propozycja=PropozycjaWaloryzacji(
                    kwota_stara=stara_kwota,
                    kwota_nowa=nowa_kwota,
                    # Wskaznik zapisany w chwili zatwierdzania, nie odtworzony
                    # z pary kwot. Z pisma do najemcy ma wynikac ten procent,
                    # ktory faktycznie zastosowano.
                    wskaznik_procent=wiersz.waloryzacja_wskaznik_procent,
                    obowiazuje_od=wiersz.obowiazuje_od,
                ),
            )
        )

    return zapisane


def _z_powodem(pozycja: PozycjaWaloryzacji, powod: str) -> PozycjaWaloryzacji:
    return PozycjaWaloryzacji(
        okres_najmu_id=pozycja.okres_najmu_id,
        lokal_id=pozycja.lokal_id,
        oznaczenie_lokalu=pozycja.oznaczenie_lokalu,
        najemca=pozycja.najemca,
        powod_wylaczenia=powod,
    )


def zatwierdz(
    sesja: Session,
    rok: int,
    okresy_do_zatwierdzenia: set[int],
    *,
    uzytkownik_id: int,
    adres_ip: str | None = None,
) -> WynikZatwierdzenia:
    """Zapisuje wybrane propozycje. Wywolujacy odpowiada za `commit()`.

    Cala operacja jest jedna transakcja: przerwanie w polowie nie zostawia
    czesci umow zwaloryzowanych, a czesci nie.
    """
    przebieg = przygotuj_przebieg(sesja, rok)
    wynik = WynikZatwierdzenia(rok=rok)

    objete_po_id = {p.okres_najmu_id: p for p in przebieg.objete}
    nieznane = okresy_do_zatwierdzenia - set(objete_po_id)
    if nieznane:
        # Operator zna lokale, nie identyfikatory wierszy. Komunikat z liczbami
        # z bazy nie mowi mu nic o tym, co ma sprawdzic.
        opisy = {p.okres_najmu_id: p.oznaczenie_lokalu for p in przebieg.wylaczone}
        lokale = sorted(opisy.get(i, f"umowa nr {i}") for i in nieznane)
        raise BladWaloryzacji(
            "Te umowy nie są już objęte waloryzacją w tym przebiegu: "
            + ", ".join(lokale)
            + ". Odśwież listę propozycji."
        )

    teraz = datetime.now(UTC)
    do_zdarzen: list[ProponowaneZdarzenie] = []
    # Jedno zapytanie na caly przebieg, a nie jedno na umowe. Zbiorcze
    # zatwierdzenie potrafi objac kilkaset umow w jednej transakcji.
    zabezpieczenia = _zabezpieczenia_z_wyliczeniem(sesja, okresy_do_zatwierdzenia)

    for okres_id in sorted(okresy_do_zatwierdzenia):
        pozycja = objete_po_id[okres_id]
        assert pozycja.propozycja is not None
        propozycja = pozycja.propozycja

        parametr = ParametrWartosc(
            okres_najmu_id=okres_id,
            klucz=KLUCZ_CZYNSZU,
            typ_wartosci=TypWartosci.KWOTA,
            wartosc_kwota=propozycja.kwota_nowa.wartosc,
            wartosc_waluta=propozycja.kwota_nowa.waluta,
            wartosc_rodzaj_kwoty=propozycja.kwota_nowa.rodzaj,
            wartosc_stawka_vat=propozycja.kwota_nowa.stawka_vat,
            obowiazuje_od=propozycja.obowiazuje_od,
            waloryzacja_rok=rok,
            waloryzacja_wskaznik_procent=propozycja.wskaznik_procent,
            # Czlowiek wlasnie zatwierdzil te wartosc na ekranie, ogladajac
            # kwote przed i po. To jest ta sama decyzja, co przy pojedynczym
            # zatwierdzeniu, tylko wykonana hurtowo (decyzja D4).
            status_weryfikacji=StatusWeryfikacji.ZATWIERDZONA,
            zatwierdzil_uzytkownik_id=uzytkownik_id,
            zatwierdzono_dnia=teraz,
            uwagi=(
                f"Waloryzacja {rok}: {propozycja.kwota_stara.wartosc} razy "
                f"(1 + {propozycja.wskaznik_procent}%)."
            ),
        )
        sesja.add(parametr)
        sesja.flush()
        zapisz_zmiane(
            sesja,
            parametr,
            operacja=OperacjaAudytu.UTWORZENIE,
            uzytkownik_id=uzytkownik_id,
            adres_ip=adres_ip,
        )
        wynik.umow_zwaloryzowanych += 1

        # Przy wskazniku 0% czynsz sie nie zmienil, wiec zabezpieczenie nadal
        # pokrywa te sama ekspozycje. Alarm bez pokrycia w danych uczy ludzi
        # ignorowania alarmow.
        if propozycja.roznica.wartosc != 0:
            do_zdarzen.extend(
                _zdarzenia_o_wekslach(
                    zabezpieczenia.get(okres_id, ()), pozycja, propozycja.obowiazuje_od
                )
            )

    wynik.zdarzen_o_wekslach = zapisz_zdarzenia(sesja, do_zdarzen)
    return wynik


def _zabezpieczenia_z_wyliczeniem(
    sesja: Session, okresy: set[int]
) -> dict[int, list[Zabezpieczenie]]:
    """Zabezpieczenia liczone od czynszu, pogrupowane po umowie."""
    if not okresy:
        return {}

    wiersze = sesja.scalars(
        select(Zabezpieczenie).where(
            Zabezpieczenie.okres_najmu_id.in_(okresy),
            Zabezpieczenie.usunieto_dnia.is_(None),
            Zabezpieczenie.sposob_wyliczenia.is_not(None),
        )
    ).all()

    pogrupowane: dict[int, list[Zabezpieczenie]] = {}
    for wiersz in wiersze:
        pogrupowane.setdefault(wiersz.okres_najmu_id, []).append(wiersz)
    return pogrupowane


def _zdarzenia_o_wekslach(
    zabezpieczenia: Iterable[Zabezpieczenie],
    pozycja: PozycjaWaloryzacji,
    obowiazuje_od: date,
) -> list[ProponowaneZdarzenie]:
    """Regula R5: zabezpieczenie wyliczane z czynszu trzeba przeliczyc.

    Nie znamy krotnosci jako liczby — umowa mowi „czterokrotność czynszu"
    slowami, a my trzymamy to jako tekst w `sposob_wyliczenia`. Dlatego nie
    liczymy nowej wartosci za czlowieka, tylko przypominamy, ze trzeba ja
    ustalic. Zabezpieczenie, ktore po kilku latach przestaje pokrywac
    ekspozycje, to typowe miejsce, o ktorym nikt nie pamieta.
    """
    return [
        ProponowaneZdarzenie(
            typ=TypZdarzenia.WEKSEL_DO_PRZELICZENIA,
            encja_typ="zabezpieczenie",
            encja_id=zab.id,
            lokal_id=pozycja.lokal_id,
            data_zdarzenia=obowiazuje_od,
            waga=WagaZdarzenia.INFORMACJA,
            tresc=(
                f"Po waloryzacji przelicz {zab.rodzaj.value} w lokalu "
                f"{pozycja.oznaczenie_lokalu} (wyliczane jako: {zab.sposob_wyliczenia})."
            ),
        )
        for zab in zabezpieczenia
        if zab.sposob_wyliczenia
    ]

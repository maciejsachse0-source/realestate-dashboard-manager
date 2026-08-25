"""Regula R2: waloryzacja roczna."""

from datetime import date
from decimal import Decimal

from najem.domena.pieniadze import Kwota
from najem.domena.reguly.waloryzacja import (
    propozycja_waloryzacji,
    wskaznik_dla_umowy,
)
from najem.domena.slowniki import RodzajKwoty, RodzajWskaznika

VAT23 = Decimal("23")
GUS_RR = RodzajWskaznika.GUS_ROK_DO_ROKU
GUS_SR = RodzajWskaznika.GUS_SREDNIOROCZNY


def czynsz_netto(wartosc: str) -> Kwota:
    return Kwota(Decimal(wartosc), "PLN", RodzajKwoty.NETTO, VAT23)


def czynsz_brutto(wartosc: str) -> Kwota:
    return Kwota(Decimal(wartosc), "PLN", RodzajKwoty.BRUTTO, VAT23)


class TestWyborWskaznika:
    def test_wskaznik_gus_rok_do_roku(self) -> None:
        wynik = wskaznik_dla_umowy(
            rodzaj=GUS_RR,
            stala_stawka_procent=None,
            wskazniki_gus={GUS_RR: Decimal("3.7")},
        )
        assert wynik.wartosc == Decimal("3.7")

    def test_rozne_umowy_moga_uzywac_roznych_wskaznikow(self) -> None:
        """Pytanie otwarte nr 4 koncepcji: umowy definiuja to roznie."""
        wskazniki = {GUS_RR: Decimal("3.7"), GUS_SR: Decimal("4.2")}
        a = wskaznik_dla_umowy(rodzaj=GUS_RR, stala_stawka_procent=None, wskazniki_gus=wskazniki)
        b = wskaznik_dla_umowy(rodzaj=GUS_SR, stala_stawka_procent=None, wskazniki_gus=wskazniki)
        assert a.wartosc == Decimal("3.7")
        assert b.wartosc == Decimal("4.2")

    def test_stala_stawka_z_umowy(self) -> None:
        wynik = wskaznik_dla_umowy(
            rodzaj=RodzajWskaznika.STALA_STAWKA,
            stala_stawka_procent=Decimal("5"),
            wskazniki_gus={},
        )
        assert wynik.wartosc == Decimal("5")

    def test_stala_stawka_bez_wysokosci(self) -> None:
        wynik = wskaznik_dla_umowy(
            rodzaj=RodzajWskaznika.STALA_STAWKA, stala_stawka_procent=None, wskazniki_gus={}
        )
        assert not wynik.ustalone

    def test_brak_wprowadzonego_wskaznika_gus(self) -> None:
        wynik = wskaznik_dla_umowy(rodzaj=GUS_RR, stala_stawka_procent=None, wskazniki_gus={})
        assert not wynik.ustalone
        assert wynik.powod_braku is not None
        assert "wskaźnika" in wynik.powod_braku

    def test_umowa_bez_okreslonego_rodzaju(self) -> None:
        wynik = wskaznik_dla_umowy(
            rodzaj=None, stala_stawka_procent=None, wskazniki_gus={GUS_RR: Decimal("3.7")}
        )
        assert not wynik.ustalone


class TestPropozycjaWaloryzacji:
    def test_typowa_podwyzka(self) -> None:
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("12500.00"),
            podlega=True,
            miesiac_waloryzacji=1,
            rok=2027,
            wskaznik_procent=Decimal("3.7"),
        )
        propozycja = wynik.wymagaj()
        assert propozycja.kwota_nowa.wartosc == Decimal("12962.50")
        assert propozycja.obowiazuje_od == date(2027, 1, 1)
        assert propozycja.roznica.wartosc == Decimal("462.50")

    def test_waloryzacja_zachowuje_postac_kwoty(self) -> None:
        """Czynsz netto podnosi sie jako netto, brutto jako brutto.

        Typ Kwota niesie te informacje, wiec regula nie zgaduje. To odpowiedz
        na punkt A z planu: dopoki kwota wie, czym jest, waloryzacja jest poprawna.
        """
        z_netto = propozycja_waloryzacji(
            czynsz=czynsz_netto("1000.00"),
            podlega=True,
            miesiac_waloryzacji=1,
            rok=2027,
            wskaznik_procent=Decimal("10"),
        ).wymagaj()
        z_brutto = propozycja_waloryzacji(
            czynsz=czynsz_brutto("1000.00"),
            podlega=True,
            miesiac_waloryzacji=1,
            rok=2027,
            wskaznik_procent=Decimal("10"),
        ).wymagaj()
        assert z_netto.kwota_nowa.rodzaj is RodzajKwoty.NETTO
        assert z_brutto.kwota_nowa.rodzaj is RodzajKwoty.BRUTTO
        assert z_netto.kwota_nowa.wartosc == z_brutto.kwota_nowa.wartosc == Decimal("1100.00")

    def test_umowa_niepodlegajaca_jest_pomijana_z_powodem(self) -> None:
        """Ekran waloryzacji pokazuje wylaczone umowy razem z powodem wylaczenia."""
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("12500.00"),
            podlega=False,
            miesiac_waloryzacji=1,
            rok=2027,
            wskaznik_procent=Decimal("3.7"),
        )
        assert not wynik.ustalone
        assert wynik.powod_braku is not None
        assert "nie podlega" in wynik.powod_braku

    def test_brak_czynszu_nie_daje_zera_tylko_powod(self) -> None:
        """Decyzja D5. Umowa bez zatwierdzonego czynszu nie waloryzuje sie do zera."""
        wynik = propozycja_waloryzacji(
            czynsz=None,
            podlega=True,
            miesiac_waloryzacji=1,
            rok=2027,
            wskaznik_procent=Decimal("3.7"),
        )
        assert not wynik.ustalone

    def test_umowa_przed_pierwsza_waloryzacja_jest_pomijana(self) -> None:
        """Umowa z 2026 z pierwsza waloryzacja w 2028 nie wchodzi do przebiegu 2027."""
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("12500.00"),
            podlega=True,
            miesiac_waloryzacji=1,
            rok=2027,
            wskaznik_procent=Decimal("3.7"),
            data_pierwszej_waloryzacji=date(2028, 1, 1),
        )
        assert not wynik.ustalone
        assert wynik.powod_braku is not None
        assert "2028" in wynik.powod_braku

    def test_umowa_w_roku_pierwszej_waloryzacji_wchodzi(self) -> None:
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("12500.00"),
            podlega=True,
            miesiac_waloryzacji=1,
            rok=2028,
            wskaznik_procent=Decimal("3.7"),
            data_pierwszej_waloryzacji=date(2028, 1, 1),
        )
        assert wynik.ustalone

    def test_wskaznik_ujemny_obniza_czynsz(self) -> None:
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("1000.00"),
            podlega=True,
            miesiac_waloryzacji=3,
            rok=2027,
            wskaznik_procent=Decimal("-1.5"),
        )
        assert wynik.wymagaj().kwota_nowa.wartosc == Decimal("985.00")

    def test_grosze_przy_waloryzacji(self) -> None:
        # 4321,99 razy 1,037 = 4481,90363... czyli 4481,90
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("4321.99"),
            podlega=True,
            miesiac_waloryzacji=1,
            rok=2027,
            wskaznik_procent=Decimal("3.7"),
        )
        assert wynik.wymagaj().kwota_nowa.wartosc == Decimal("4481.90")

    def test_brak_miesiaca_waloryzacji(self) -> None:
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("1000.00"),
            podlega=True,
            miesiac_waloryzacji=None,
            rok=2027,
            wskaznik_procent=Decimal("3.7"),
        )
        assert not wynik.ustalone

    def test_miesiac_poza_zakresem(self) -> None:
        wynik = propozycja_waloryzacji(
            czynsz=czynsz_netto("1000.00"),
            podlega=True,
            miesiac_waloryzacji=13,
            rok=2027,
            wskaznik_procent=Decimal("3.7"),
        )
        assert not wynik.ustalone

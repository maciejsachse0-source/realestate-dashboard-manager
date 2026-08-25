"""Maszyna stanow: dozwolone przejscia i te, ktore musza byc zablokowane."""

import pytest

from najem.domena.slowniki import (
    StatusOkresuNajmu,
    StatusZabezpieczenia,
    StatusZdarzenia,
)
from najem.domena.stany import (
    PRZEJSCIA_OKRESU_NAJMU,
    PRZEJSCIA_ZABEZPIECZENIA,
    PRZEJSCIA_ZDARZENIA,
    NiedozwolonePrzejscie,
    czy_przejscie_dozwolone,
    sprawdz_przejscie,
    stany_koncowe,
)


class TestOkresNajmu:
    def test_typowa_sciezka_umowy(self) -> None:
        assert czy_przejscie_dozwolone(
            PRZEJSCIA_OKRESU_NAJMU, StatusOkresuNajmu.PRZYGOTOWANIE, StatusOkresuNajmu.AKTYWNA
        )
        assert czy_przejscie_dozwolone(
            PRZEJSCIA_OKRESU_NAJMU, StatusOkresuNajmu.AKTYWNA, StatusOkresuNajmu.WYPOWIEDZIANA
        )
        assert czy_przejscie_dozwolone(
            PRZEJSCIA_OKRESU_NAJMU, StatusOkresuNajmu.WYPOWIEDZIANA, StatusOkresuNajmu.ZAKONCZONA
        )

    def test_zakonczonej_umowy_nie_da_sie_wskrzesic(self) -> None:
        """To jest ten przypadek, dla ktorego ta maszyna w ogole istnieje."""
        for docelowy in StatusOkresuNajmu:
            if docelowy is StatusOkresuNajmu.ZAKONCZONA:
                continue
            assert not czy_przejscie_dozwolone(
                PRZEJSCIA_OKRESU_NAJMU, StatusOkresuNajmu.ZAKONCZONA, docelowy
            )

    def test_umowa_nie_wraca_z_aktywnej_do_przygotowania(self) -> None:
        assert not czy_przejscie_dozwolone(
            PRZEJSCIA_OKRESU_NAJMU, StatusOkresuNajmu.AKTYWNA, StatusOkresuNajmu.PRZYGOTOWANIE
        )

    def test_cofniecie_wypowiedzenia_jest_dozwolone(self) -> None:
        """Wypowiedzenie bywa cofane za zgoda stron, wiec to nie jest slepa uliczka."""
        assert czy_przejscie_dozwolone(
            PRZEJSCIA_OKRESU_NAJMU, StatusOkresuNajmu.WYPOWIEDZIANA, StatusOkresuNajmu.AKTYWNA
        )

    def test_zakonczona_to_jedyny_stan_koncowy(self) -> None:
        assert stany_koncowe(PRZEJSCIA_OKRESU_NAJMU) == frozenset({StatusOkresuNajmu.ZAKONCZONA})


class TestZabezpieczenie:
    def test_kaucja_wplacona_i_zwrocona(self) -> None:
        assert czy_przejscie_dozwolone(
            PRZEJSCIA_ZABEZPIECZENIA,
            StatusZabezpieczenia.WYMAGANE,
            StatusZabezpieczenia.DOSTARCZONE,
        )
        assert czy_przejscie_dozwolone(
            PRZEJSCIA_ZABEZPIECZENIA,
            StatusZabezpieczenia.DOSTARCZONE,
            StatusZabezpieczenia.ZWROCONE,
        )

    def test_nie_da_sie_zwrocic_czegos_czego_nie_dostarczono(self) -> None:
        assert not czy_przejscie_dozwolone(
            PRZEJSCIA_ZABEZPIECZENIA,
            StatusZabezpieczenia.WYMAGANE,
            StatusZabezpieczenia.ZWROCONE,
        )


class TestZdarzenie:
    def test_obsluzone_zdarzenie_mozna_otworzyc_ponownie(self) -> None:
        """Pracownik moze sie pomylic, klikajac 'obsluzone'. To musi byc odwracalne."""
        assert czy_przejscie_dozwolone(
            PRZEJSCIA_ZDARZENIA, StatusZdarzenia.OBSLUZONE, StatusZdarzenia.OTWARTE
        )

    def test_zdarzenia_nie_maja_stanow_koncowych(self) -> None:
        assert stany_koncowe(PRZEJSCIA_ZDARZENIA) == frozenset()


class TestWspolne:
    def test_pozostanie_w_tym_samym_stanie_jest_dozwolone(self) -> None:
        """Zapis formularza bez zmiany statusu nie moze wywalac bledu."""
        for stan in StatusOkresuNajmu:
            assert czy_przejscie_dozwolone(PRZEJSCIA_OKRESU_NAJMU, stan, stan)

    def test_kazdy_stan_ma_wpis_w_mapie(self) -> None:
        """Brak wpisu wyglada jak stan koncowy i po cichu blokuje przejscia."""
        assert set(PRZEJSCIA_OKRESU_NAJMU) == set(StatusOkresuNajmu)
        assert set(PRZEJSCIA_ZABEZPIECZENIA) == set(StatusZabezpieczenia)
        assert set(PRZEJSCIA_ZDARZENIA) == set(StatusZdarzenia)

    def test_komunikat_bledu_wymienia_dozwolone_stany(self) -> None:
        with pytest.raises(NiedozwolonePrzejscie) as info:
            sprawdz_przejscie(
                PRZEJSCIA_OKRESU_NAJMU,
                StatusOkresuNajmu.ZAKONCZONA,
                StatusOkresuNajmu.AKTYWNA,
            )
        assert "zakonczona" in str(info.value)
        assert "stan koncowy" in str(info.value)

    def test_mapy_wskazuja_wylacznie_na_znane_stany(self) -> None:
        for mapa, typ in (
            (PRZEJSCIA_OKRESU_NAJMU, StatusOkresuNajmu),
            (PRZEJSCIA_ZABEZPIECZENIA, StatusZabezpieczenia),
            (PRZEJSCIA_ZDARZENIA, StatusZdarzenia),
        ):
            for docelowe in mapa.values():
                assert all(stan in set(typ) for stan in docelowe)

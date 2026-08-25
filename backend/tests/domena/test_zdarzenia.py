"""Generator zdarzen: katalog z sekcji 6 koncepcji i idempotencja.

Najwazniejszy test w tym pliku to ten, ktory sprawdza, ze generator uruchomiony
trzy razy tego samego dnia daje dokladnie ten sam wynik co jedno uruchomienie.
"""

from datetime import date, timedelta
from decimal import Decimal

from najem.domena.pieniadze import Kwota
from najem.domena.slowniki import (
    RodzajKwoty,
    RodzajZabezpieczenia,
    StatusOkresuNajmu,
    StatusZabezpieczenia,
    TypZdarzenia,
    WagaZdarzenia,
)
from najem.domena.zdarzenia import (
    StanPrzegladu,
    StanUmowy,
    StanZabezpieczenia,
    kotwica_miesieczna,
    najblizszy_miesiac,
    zdarzenia_dla_portfela,
    zdarzenia_dla_umowy,
)

DZIS = date(2026, 8, 25)
KONIEC = date(2028, 1, 31)


def pln(wartosc: str) -> Kwota:
    return Kwota(Decimal(wartosc), "PLN", RodzajKwoty.BRUTTO, None)


def umowa(**zmiany: object) -> StanUmowy:
    podstawa: dict[str, object] = {
        "okres_najmu_id": 1,
        "lokal_id": 10,
        "oznaczenie_lokalu": "18A/12",
        "status": StatusOkresuNajmu.AKTYWNA,
        "data_rozpoczecia": date(2026, 2, 1),
        "data_przekazania": date(2026, 2, 1),
        "data_zakonczenia": KONIEC,
    }
    podstawa.update(zmiany)
    return StanUmowy(**podstawa)  # type: ignore[arg-type]


def typy(zdarzenia: list) -> set[TypZdarzenia]:  # type: ignore[type-arg]
    return {z.typ for z in zdarzenia}


class TestIdempotencja:
    def test_trzy_uruchomienia_daja_ten_sam_wynik(self) -> None:
        """Kryterium akceptacji etapu E3.

        Generator jest czysta funkcja, wiec idempotencja wynika z konstrukcji,
        a nie z odsiewania duplikatow po fakcie.
        """
        stan = umowa(
            data_zakonczenia=DZIS + timedelta(days=30),
            profil_kompletny=False,
            brakujace_pola=("status_polisy",),
        )
        przebiegi = [zdarzenia_dla_umowy(stan, DZIS) for _ in range(3)]
        assert przebiegi[0] == przebiegi[1] == przebiegi[2]
        assert len(przebiegi[0]) > 0

    def test_data_zdarzenia_nie_zalezy_od_dnia_uruchomienia(self) -> None:
        """To jest powod, dla ktorego caly ten modul jest zbudowany tak, a nie inaczej.

        Gdyby data_zdarzenia byla dniem uruchomienia, generator tworzylby nowe
        zdarzenie kazdego dnia i kokpit zamienilby sie w liste duplikatow.
        """
        stan = umowa(data_zakonczenia=DZIS + timedelta(days=30))
        dzis = zdarzenia_dla_umowy(stan, DZIS)
        tydzien_pozniej = zdarzenia_dla_umowy(stan, DZIS + timedelta(days=7))

        klucze_dzis = {z.klucz_naturalny for z in dzis}
        klucze_pozniej = {z.klucz_naturalny for z in tydzien_pozniej}
        assert klucze_dzis <= klucze_pozniej

    def test_portfel_nie_powiela_kluczy(self) -> None:
        stan = umowa(data_zakonczenia=DZIS + timedelta(days=30))
        wynik = zdarzenia_dla_portfela([stan, stan, stan], DZIS)
        klucze = [z.klucz_naturalny for z in wynik]
        assert len(klucze) == len(set(klucze))


class TestKoniecUmowy:
    def test_progi_180_90_60_30(self) -> None:
        for dni in (180, 90, 60, 30):
            stan = umowa(data_zakonczenia=DZIS + timedelta(days=dni))
            zdarzenia = [
                z
                for z in zdarzenia_dla_umowy(stan, DZIS)
                if z.typ is TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA
            ]
            assert zdarzenia, f"brak zdarzenia dla progu {dni}"

    def test_waga_rosnie_wraz_ze_zblizaniem_terminu(self) -> None:
        odlegla = umowa(data_zakonczenia=DZIS + timedelta(days=180))
        bliska = umowa(data_zakonczenia=DZIS + timedelta(days=30))

        waga_odlegla = next(
            z.waga
            for z in zdarzenia_dla_umowy(odlegla, DZIS)
            if z.typ is TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA
        )
        wagi_bliskie = {
            z.waga
            for z in zdarzenia_dla_umowy(bliska, DZIS)
            if z.typ is TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA
        }
        assert waga_odlegla is WagaZdarzenia.INFORMACJA
        assert WagaZdarzenia.KRYTYCZNE in wagi_bliskie

    def test_kilka_progow_naraz_gdy_termin_blisko(self) -> None:
        """Umowa konczaca sie za 20 dni przekroczyla juz wszystkie cztery progi."""
        stan = umowa(data_zakonczenia=DZIS + timedelta(days=20))
        zdarzenia = [
            z
            for z in zdarzenia_dla_umowy(stan, DZIS)
            if z.typ is TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA
        ]
        assert len(zdarzenia) == 4
        assert len({z.data_zdarzenia for z in zdarzenia}) == 4

    def test_odlegly_koniec_nie_generuje_nic(self) -> None:
        stan = umowa(data_zakonczenia=DZIS + timedelta(days=400))
        assert TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_nieustalona_data_konca_nie_generuje_ostrzezen(self) -> None:
        """Umowa bez protokolu przekazania nie ma konca, wiec nie ma o czym ostrzegac.

        Zamiast tego powstaje zdarzenie o braku protokolu.
        """
        stan = umowa(data_zakonczenia=None, data_przekazania=None)
        wynik = typy(zdarzenia_dla_umowy(stan, DZIS))
        assert TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA not in wynik
        assert TypZdarzenia.BRAK_PROTOKOLU_PRZEKAZANIA in wynik

    def test_zakonczona_umowa_nie_dostaje_ostrzezen_o_koncu(self) -> None:
        stan = umowa(
            status=StatusOkresuNajmu.ZAKONCZONA, data_zakonczenia=DZIS + timedelta(days=30)
        )
        assert TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA not in typy(zdarzenia_dla_umowy(stan, DZIS))


class TestWypowiedzenieIWygasniecie:
    def test_minal_termin_wypowiedzenia(self) -> None:
        stan = umowa(termin_wypowiedzenia=DZIS - timedelta(days=1))
        zdarzenia = [
            z
            for z in zdarzenia_dla_umowy(stan, DZIS)
            if z.typ is TypZdarzenia.MINAL_TERMIN_WYPOWIEDZENIA
        ]
        assert len(zdarzenia) == 1
        assert zdarzenia[0].waga is WagaZdarzenia.KRYTYCZNE

    def test_termin_wypowiedzenia_jeszcze_nie_minal(self) -> None:
        stan = umowa(termin_wypowiedzenia=DZIS + timedelta(days=10))
        assert TypZdarzenia.MINAL_TERMIN_WYPOWIEDZENIA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_wypowiedziana_umowa_nie_dostaje_alertu_o_braku_decyzji(self) -> None:
        """Decyzja zapadla, wiec alert o jej braku byłby szumem."""
        stan = umowa(
            status=StatusOkresuNajmu.WYPOWIEDZIANA, termin_wypowiedzenia=DZIS - timedelta(days=1)
        )
        assert TypZdarzenia.MINAL_TERMIN_WYPOWIEDZENIA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_umowa_wygasla_bez_nastepczej(self) -> None:
        stan = umowa(data_zakonczenia=DZIS - timedelta(days=1), ma_nastepczy_okres=False)
        zdarzenia = [
            z
            for z in zdarzenia_dla_umowy(stan, DZIS)
            if z.typ is TypZdarzenia.UMOWA_WYGASLA_BRAK_NASTEPCZEJ
        ]
        assert len(zdarzenia) == 1

    def test_umowa_z_nastepczym_okresem_nie_alarmuje(self) -> None:
        stan = umowa(data_zakonczenia=DZIS - timedelta(days=1), ma_nastepczy_okres=True)
        assert TypZdarzenia.UMOWA_WYGASLA_BRAK_NASTEPCZEJ not in typy(
            zdarzenia_dla_umowy(stan, DZIS)
        )


class TestWaloryzacja:
    def test_zbliza_sie_waloryzacja(self) -> None:
        """Waloryzacja w styczniu, patrzymy 10 grudnia."""
        stan = umowa(waloryzacja_podlega=True, waloryzacja_miesiac=1)
        zdarzenia = [
            z
            for z in zdarzenia_dla_umowy(stan, date(2026, 12, 10))
            if z.typ is TypZdarzenia.WALORYZACJA_SIE_ZBLIZA
        ]
        assert len(zdarzenia) == 1
        assert zdarzenia[0].data_zdarzenia == date(2027, 1, 1) - timedelta(days=30)

    def test_za_wczesnie_na_przypomnienie(self) -> None:
        stan = umowa(waloryzacja_podlega=True, waloryzacja_miesiac=1)
        assert TypZdarzenia.WALORYZACJA_SIE_ZBLIZA not in typy(
            zdarzenia_dla_umowy(stan, date(2026, 6, 1))
        )

    def test_umowa_bez_waloryzacji(self) -> None:
        stan = umowa(waloryzacja_podlega=False, waloryzacja_miesiac=1)
        assert TypZdarzenia.WALORYZACJA_SIE_ZBLIZA not in typy(
            zdarzenia_dla_umowy(stan, date(2026, 12, 10))
        )

    def test_najblizszy_miesiac_w_tym_roku(self) -> None:
        assert najblizszy_miesiac(12, date(2026, 8, 25)) == date(2026, 12, 1)

    def test_najblizszy_miesiac_w_nastepnym_roku(self) -> None:
        assert najblizszy_miesiac(1, date(2026, 8, 25)) == date(2027, 1, 1)

    def test_biezacy_miesiac_liczy_sie_od_pierwszego(self) -> None:
        assert najblizszy_miesiac(8, date(2026, 8, 1)) == date(2026, 8, 1)
        assert najblizszy_miesiac(8, date(2026, 8, 2)) == date(2027, 8, 1)


class TestProtokolIKompletnosc:
    def test_brak_protokolu_po_14_dniach(self) -> None:
        stan = umowa(data_rozpoczecia=DZIS - timedelta(days=15), data_przekazania=None)
        assert TypZdarzenia.BRAK_PROTOKOLU_PRZEKAZANIA in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_przed_uplywem_14_dni_jeszcze_nie_alarmujemy(self) -> None:
        stan = umowa(data_rozpoczecia=DZIS - timedelta(days=5), data_przekazania=None)
        assert TypZdarzenia.BRAK_PROTOKOLU_PRZEKAZANIA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_protokol_jest_wiec_brak_alarmu(self) -> None:
        stan = umowa(data_rozpoczecia=DZIS - timedelta(days=100))
        assert TypZdarzenia.BRAK_PROTOKOLU_PRZEKAZANIA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_niekompletny_profil_wraca_raz_w_miesiacu(self) -> None:
        """Stan trwaly nie ma naturalnej daty, wiec kotwiczymy na pierwszym dniu
        miesiaca. Inaczej generator tworzylby nowe zdarzenie kazdego dnia.
        """
        stan = umowa(profil_kompletny=False, brakujace_pola=("status_polisy", "czynsz_podstawowy"))
        w_sierpniu = [
            z for z in zdarzenia_dla_umowy(stan, DZIS) if z.typ is TypZdarzenia.PROFIL_NIEKOMPLETNY
        ]
        pozniej_w_sierpniu = [
            z
            for z in zdarzenia_dla_umowy(stan, date(2026, 8, 30))
            if z.typ is TypZdarzenia.PROFIL_NIEKOMPLETNY
        ]
        we_wrzesniu = [
            z
            for z in zdarzenia_dla_umowy(stan, date(2026, 9, 3))
            if z.typ is TypZdarzenia.PROFIL_NIEKOMPLETNY
        ]
        assert w_sierpniu[0].klucz_naturalny == pozniej_w_sierpniu[0].klucz_naturalny
        assert w_sierpniu[0].klucz_naturalny != we_wrzesniu[0].klucz_naturalny

    def test_tresc_wymienia_brakujace_pola(self) -> None:
        stan = umowa(profil_kompletny=False, brakujace_pola=("status_polisy",))
        zdarzenie = next(
            z for z in zdarzenia_dla_umowy(stan, DZIS) if z.typ is TypZdarzenia.PROFIL_NIEKOMPLETNY
        )
        assert "status_polisy" in zdarzenie.tresc

    def test_kotwica_miesieczna(self) -> None:
        assert kotwica_miesieczna(date(2026, 8, 25)) == date(2026, 8, 1)


class TestZabezpieczenia:
    def test_kaucja_niewplacona_po_terminie(self) -> None:
        stan = umowa(
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=5,
                    rodzaj=RodzajZabezpieczenia.KAUCJA,
                    status=StatusZabezpieczenia.WYMAGANE,
                    data_wymagalnosci=DZIS - timedelta(days=1),
                ),
            )
        )
        zdarzenia = [
            z for z in zdarzenia_dla_umowy(stan, DZIS) if z.typ is TypZdarzenia.KAUCJA_NIEWPLACONA
        ]
        assert len(zdarzenia) == 1
        assert zdarzenia[0].encja_typ == "zabezpieczenie"
        assert zdarzenia[0].encja_id == 5

    def test_kaucja_wplacona_nie_alarmuje(self) -> None:
        stan = umowa(
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=5,
                    rodzaj=RodzajZabezpieczenia.KAUCJA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                    data_wymagalnosci=DZIS - timedelta(days=100),
                ),
            )
        )
        assert TypZdarzenia.KAUCJA_NIEWPLACONA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_polisa_niedostarczona(self) -> None:
        stan = umowa(
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=6,
                    rodzaj=RodzajZabezpieczenia.POLISA,
                    status=StatusZabezpieczenia.WYMAGANE,
                    data_wymagalnosci=DZIS - timedelta(days=1),
                ),
            )
        )
        assert TypZdarzenia.POLISA_NIEDOSTARCZONA in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_polisa_wygasa_za_mniej_niz_30_dni(self) -> None:
        stan = umowa(
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=6,
                    rodzaj=RodzajZabezpieczenia.POLISA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                    data_waznosci=DZIS + timedelta(days=10),
                ),
            )
        )
        assert TypZdarzenia.POLISA_WYGASA in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_polisa_juz_wygasla_nie_jest_wkrotce_wygasajaca(self) -> None:
        stan = umowa(
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=6,
                    rodzaj=RodzajZabezpieczenia.POLISA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                    data_waznosci=DZIS - timedelta(days=5),
                ),
            )
        )
        assert TypZdarzenia.POLISA_WYGASA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_polisa_ponizej_wymaganej_kwoty(self) -> None:
        stan = umowa(
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=6,
                    rodzaj=RodzajZabezpieczenia.POLISA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                    suma_ubezpieczenia=pln("500000.00"),
                    wymagana_kwota=pln("1000000.00"),
                ),
            )
        )
        assert TypZdarzenia.POLISA_PONIZEJ_KWOTY in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_polisa_w_innej_walucie_nie_generuje_alarmu(self) -> None:
        """Porownanie wymaga decyzji czlowieka, wiec system nie zgaduje."""
        euro = Kwota(Decimal("250000"), "EUR", RodzajKwoty.BRUTTO, None)
        stan = umowa(
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=6,
                    rodzaj=RodzajZabezpieczenia.POLISA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                    suma_ubezpieczenia=euro,
                    wymagana_kwota=pln("1000000.00"),
                ),
            )
        )
        assert TypZdarzenia.POLISA_PONIZEJ_KWOTY not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_kaucja_do_zwrotu_po_zakonczeniu(self) -> None:
        stan = umowa(
            status=StatusOkresuNajmu.ZAKONCZONA,
            data_zakonczenia=DZIS - timedelta(days=1),
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=5,
                    rodzaj=RodzajZabezpieczenia.KAUCJA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                ),
            ),
        )
        assert TypZdarzenia.KAUCJA_DO_ZWROTU in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_zabezpieczenia_licza_sie_takze_po_zakonczeniu_umowy(self) -> None:
        """Zakonczona umowa nadal wymaga rozliczenia kaucji. To jest ten termin,
        o ktorym latwo zapomniec i ktory generuje roszczenia (regula R4).
        """
        stan = umowa(
            status=StatusOkresuNajmu.ZAKONCZONA,
            data_zakonczenia=DZIS - timedelta(days=1),
            zabezpieczenia=(
                StanZabezpieczenia(
                    zabezpieczenie_id=5,
                    rodzaj=RodzajZabezpieczenia.KAUCJA,
                    status=StatusZabezpieczenia.DOSTARCZONE,
                ),
            ),
        )
        assert zdarzenia_dla_umowy(stan, DZIS)


class TestPrzeglady:
    def test_przeglad_sie_zbliza(self) -> None:
        stan = umowa(
            przeglady=(
                StanPrzegladu(
                    obowiazek_id=9, element="gaśnice", nastepny_termin=DZIS + timedelta(days=20)
                ),
            )
        )
        zdarzenia = [
            z for z in zdarzenia_dla_umowy(stan, DZIS) if z.typ is TypZdarzenia.PRZEGLAD_SIE_ZBLIZA
        ]
        assert len(zdarzenia) == 1
        assert "gaśnice" in zdarzenia[0].tresc

    def test_przeglad_przeterminowany(self) -> None:
        stan = umowa(
            przeglady=(
                StanPrzegladu(
                    obowiazek_id=9, element="brama", nastepny_termin=DZIS - timedelta(days=1)
                ),
            )
        )
        zdarzenia = [
            z
            for z in zdarzenia_dla_umowy(stan, DZIS)
            if z.typ is TypZdarzenia.PRZEGLAD_PRZETERMINOWANY
        ]
        assert len(zdarzenia) == 1
        assert zdarzenia[0].waga is WagaZdarzenia.KRYTYCZNE

    def test_przeterminowany_wyklucza_zblizajacy_sie(self) -> None:
        """Jeden przeglad nie moze byc jednoczesnie zblizajacy sie i przeterminowany."""
        stan = umowa(
            przeglady=(
                StanPrzegladu(
                    obowiazek_id=9, element="brama", nastepny_termin=DZIS - timedelta(days=1)
                ),
            )
        )
        wynik = typy(zdarzenia_dla_umowy(stan, DZIS))
        assert TypZdarzenia.PRZEGLAD_SIE_ZBLIZA not in wynik

    def test_przeglad_bez_terminu_nie_generuje_zdarzenia(self) -> None:
        """Brak terminu to luka w danych, ktora lapie wskaznik kompletnosci,
        a nie alert terminowy o nieznanym terminie.
        """
        stan = umowa(przeglady=(StanPrzegladu(obowiazek_id=9, element="brama"),))
        wynik = typy(zdarzenia_dla_umowy(stan, DZIS))
        assert TypZdarzenia.PRZEGLAD_SIE_ZBLIZA not in wynik
        assert TypZdarzenia.PRZEGLAD_PRZETERMINOWANY not in wynik

    def test_odlegly_przeglad_nie_generuje_nic(self) -> None:
        stan = umowa(
            przeglady=(
                StanPrzegladu(
                    obowiazek_id=9, element="brama", nastepny_termin=DZIS + timedelta(days=200)
                ),
            )
        )
        assert TypZdarzenia.PRZEGLAD_SIE_ZBLIZA not in typy(zdarzenia_dla_umowy(stan, DZIS))

    def test_wiele_elementow_daje_osobne_zdarzenia(self) -> None:
        """Element jest osobnym bytem, wiec i alert jest osobny (regula R7)."""
        stan = umowa(
            przeglady=(
                StanPrzegladu(
                    obowiazek_id=9, element="gaśnice", nastepny_termin=DZIS + timedelta(days=20)
                ),
                StanPrzegladu(
                    obowiazek_id=10, element="hydranty", nastepny_termin=DZIS + timedelta(days=20)
                ),
            )
        )
        zdarzenia = [
            z for z in zdarzenia_dla_umowy(stan, DZIS) if z.typ is TypZdarzenia.PRZEGLAD_SIE_ZBLIZA
        ]
        assert len(zdarzenia) == 2
        assert {z.encja_id for z in zdarzenia} == {9, 10}


class TestPortfel:
    def test_zdarzenia_z_wielu_umow(self) -> None:
        a = umowa(okres_najmu_id=1, lokal_id=10, data_zakonczenia=DZIS + timedelta(days=30))
        b = umowa(
            okres_najmu_id=2,
            lokal_id=11,
            oznaczenie_lokalu="18A/13",
            data_zakonczenia=DZIS + timedelta(days=30),
        )
        wynik = zdarzenia_dla_portfela([a, b], DZIS)
        assert {z.encja_id for z in wynik if z.encja_typ == "okres_najmu"} == {1, 2}

    def test_pusty_portfel(self) -> None:
        assert zdarzenia_dla_portfela([], DZIS) == []

    def test_kazde_zdarzenie_niesie_lokal_do_filtrowania(self) -> None:
        """Kokpit terminow filtruje po budynku i lokalu (koncepcja, sekcja 7.3)."""
        stan = umowa(data_zakonczenia=DZIS + timedelta(days=30))
        for zdarzenie in zdarzenia_dla_umowy(stan, DZIS):
            assert zdarzenie.lokal_id == 10

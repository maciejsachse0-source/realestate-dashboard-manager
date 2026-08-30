"""Normalizacja tekstu dokumentu.

Wszystko tutaj służy jednemu: żeby ten sam zapis w umowie wyglądał tak samo
niezależnie od tego, czy przyszedł z Worda, z PDF-a, i gdzie akurat wypadł
koniec wiersza. Wzorzec, który trafia albo nie trafia zależnie od szerokości
marginesu, jest bezużyteczny.
"""

import pytest

from najem.domena.ekstrakcja.tekst import (
    StronaTekstu,
    TekstDokumentu,
    WarstwaTekstu,
    normalizuj,
    polacz_przeniesienia,
)


class TestNormalizacji:
    def test_odmiany_spacji_staja_sie_zwykla_spacja(self) -> None:
        """Word wstawia spację niełamiącą, PDF bywa, że wąską. W kwocie to ten
        sam separator tysięcy i musi wyglądać tak samo."""
        assert normalizuj("czynsz 6 960,00 zl") == "czynsz 6 960,00 zl"
        assert normalizuj("czynsz 6 960,00 zl") == "czynsz 6 960,00 zl"
        assert normalizuj("czynsz 6 960,00 zl") == "czynsz 6 960,00 zl"

    def test_metr_kwadratowy_traci_gorny_indeks(self) -> None:
        """Skutek NFKC, o którym musi wiedzieć wzorzec powierzchni:
        szuka „m2", nie „m²"."""
        assert normalizuj("powierzchnia 124,50 m²") == "powierzchnia 124,50 m2"

    def test_ligatura_jest_rozwijana(self) -> None:
        assert normalizuj("oﬁcjalny") == "oficjalny"

    def test_miekki_dywiz_znika(self) -> None:
        """Niewidoczny w tekście, ale rozbija dopasowanie w środku słowa."""
        assert normalizuj("powierzch­nia") == "powierzchnia"

    def test_ciagi_spacji_sie_zwijaja(self) -> None:
        assert normalizuj("czynsz     wynosi") == "czynsz wynosi"

    def test_akapity_zostaja_ale_nadmiar_znika(self) -> None:
        assert normalizuj("A\n\n\n\nB") == "A\n\nB"

    def test_konce_wierszy_windows_i_mac(self) -> None:
        assert normalizuj("A\r\nB") == "A\nB"
        assert normalizuj("A\rB") == "A\nB"

    def test_nie_rusza_zapisu_liczby(self) -> None:
        """Normalizacja, która „poprawia" kwoty, to najprostszy sposób
        na zgubienie trzech rzędów wielkości. Interpretacja należy do liczby.py."""
        assert normalizuj("kwota 6.960,00 zl") == "kwota 6.960,00 zl"

    def test_pusty_tekst(self) -> None:
        assert normalizuj("") == ""
        assert normalizuj("   \n\n  ") == ""


class TestPrzeniesienWyrazow:
    def test_sklejenie_wyrazu_z_konca_wiersza(self) -> None:
        assert polacz_przeniesienia("o powierzch-\nni 124 m2") == "o powierzchni 124 m2"

    def test_nazwa_wlasna_z_lacznikiem_zostaje(self) -> None:
        """„Warszawa-\\nMokotów" to nazwa z łącznikiem, nie przeniesienie.
        Rozstrzyga wielkość litery po łączniku."""
        assert polacz_przeniesienia("Warszawa-\nMokotow") == "Warszawa-\nMokotow"

    def test_polska_litera_po_lacznika(self) -> None:
        assert polacz_przeniesienia("wypowie-\ndzenia") == "wypowiedzenia"
        assert polacz_przeniesienia("mie-\nsięcy") == "miesięcy"

    def test_bez_przeniesienia_nic_sie_nie_zmienia(self) -> None:
        assert polacz_przeniesienia("zwykly tekst") == "zwykly tekst"


class TestStronyTekstu:
    def test_numeracja_od_jedynki(self) -> None:
        assert StronaTekstu(1, "tresc").numer == 1

    @pytest.mark.parametrize("numer", [0, -1])
    def test_numer_mniejszy_od_jedynki_jest_bledem(self, numer: int) -> None:
        with pytest.raises(ValueError, match="od jedynki"):
            StronaTekstu(numer, "tresc")


class TestDokumentu:
    def test_liczba_stron_i_dostep_po_numerze(self) -> None:
        dokument = TekstDokumentu(
            strony=(StronaTekstu(1, "pierwsza"), StronaTekstu(2, "druga")),
            warstwa=WarstwaTekstu.PDF_TEKST,
        )
        assert dokument.liczba_stron == 2
        strona = dokument.strona(2)
        assert strona is not None and strona.tekst == "druga"
        assert dokument.strona(3) is None

    def test_skan_bez_warstwy_tekstowej_jest_pusty_a_nie_bledny(self) -> None:
        """Pusty wynik to poprawna odpowiedź: tak wygląda skan. Woła o OCR,
        nie o wyjątek."""
        dokument = TekstDokumentu(
            strony=(StronaTekstu(1, ""), StronaTekstu(2, "   ")),
            warstwa=WarstwaTekstu.PDF_TEKST,
        )
        assert dokument.pusty is True

    def test_dokument_z_trescia_nie_jest_pusty(self) -> None:
        dokument = TekstDokumentu(
            strony=(StronaTekstu(1, ""), StronaTekstu(2, "czynsz")),
            warstwa=WarstwaTekstu.PDF_TEKST,
        )
        assert dokument.pusty is False

    @pytest.mark.parametrize(
        "numery",
        [(2, 1), (1, 1)],
        ids=["nie po kolei", "powtorzony numer"],
    )
    def test_strony_musza_byc_kolejne_i_niepowtarzalne(self, numery: tuple[int, int]) -> None:
        with pytest.raises(ValueError, match="kolejne i niepowtarzalne"):
            TekstDokumentu(
                strony=tuple(StronaTekstu(n, "x") for n in numery),
                warstwa=WarstwaTekstu.PDF_TEKST,
            )

    def test_ocr_nie_jest_warstwa_dokladna(self) -> None:
        """OCR myli 0 z O i 6 z 8, a to są cyfry w kwocie. Rozróżnienie
        wpływa na pewność propozycji, nie na jej treść."""
        from najem.domena.ekstrakcja.tekst import WARSTWY_DOKLADNE

        assert WarstwaTekstu.OCR not in WARSTWY_DOKLADNE
        assert WarstwaTekstu.PDF_TEKST in WARSTWY_DOKLADNE
        assert WarstwaTekstu.DOCX in WARSTWY_DOKLADNE

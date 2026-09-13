"""Odczyt tekstu z prawdziwych plików PDF i DOCX.

Pliki budujemy w kodzie, bo test opierający się o załączony plik binarny
przestaje cokolwiek mówić w dniu, w którym ktoś ten plik podmieni.

Treść w PDF-ach jest celowo bez polskich znaków: kodowanie WinAnsi, którego
używa Helvetica, nie ma „ł" ani „ą", a walka z tym w teście sprawdzałaby
budowanie PDF-a, a nie nasz czytnik. Obsługę polskich znaków sprawdza
`tests/domena/test_ekstrakcja_tekst.py` na poziomie normalizacji.
"""

import io
import zipfile
from pathlib import Path

import pytest

from najem.dokumenty.tekst_z_pliku import (
    BladOdczytuTekstu,
    CzytnikDocx,
    CzytnikPdf,
    czytaj_tekst,
)
from najem.domena.ekstrakcja.tekst import WarstwaTekstu

PRZESTRZEN = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def zbuduj_pdf(teksty_stron: list[str]) -> bytes:
    """Poprawny PDF z tablicą xref. Pusty tekst strony daje stronę bez tekstu,
    czyli odpowiednik skanu."""
    obiekty: list[bytes] = []
    ile = len(teksty_stron)
    numer_fontu = 3
    pierwsza_strona = 4

    kids = " ".join(f"{pierwsza_strona + 2 * i} 0 R" for i in range(ile))
    obiekty.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    obiekty.append(f"<< /Type /Pages /Count {ile} /Kids [{kids}] >>".encode())
    obiekty.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i, tekst in enumerate(teksty_stron):
        numer_strony = pierwsza_strona + 2 * i
        numer_tresci = numer_strony + 1
        obiekty.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {numer_fontu} 0 R >> >> "
            f"/Contents {numer_tresci} 0 R >>".encode()
        )
        strumien = f"BT /F1 12 Tf 50 800 Td ({tekst}) Tj ET".encode() if tekst else b"q Q"
        obiekty.append(
            f"<< /Length {len(strumien)} >>".encode() + b"\nstream\n" + strumien + b"\nendstream"
        )

    wynik = bytearray(b"%PDF-1.4\n")
    offsety: list[int] = []
    for numer, obiekt in enumerate(obiekty, start=1):
        offsety.append(len(wynik))
        wynik += f"{numer} 0 obj\n".encode() + obiekt + b"\nendobj\n"

    pozycja_xref = len(wynik)
    wynik += f"xref\n0 {len(obiekty) + 1}\n".encode()
    wynik += b"0000000000 65535 f \n"
    for offset in offsety:
        wynik += f"{offset:010d} 00000 n \n".encode()
    wynik += (
        f"trailer\n<< /Size {len(obiekty) + 1} /Root 1 0 R >>\n"
        f"startxref\n{pozycja_xref}\n%%EOF\n".encode()
    )
    return bytes(wynik)


def zbuduj_docx(akapity: list[str]) -> bytes:
    """DOCX z jednym fragmentem na akapit."""
    czesci = "".join(f"<w:p><w:r><w:t>{tresc}</w:t></w:r></w:p>" for tresc in akapity)
    xml = (
        f'<?xml version="1.0"?><w:document xmlns:w="{PRZESTRZEN}">'
        f"<w:body>{czesci}</w:body></w:document>"
    )
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w") as archiwum:
        archiwum.writestr("word/document.xml", xml)
        archiwum.writestr("[Content_Types].xml", "<Types/>")
    return bufor.getvalue()


class TestCzytnikaPdf:
    def test_czyta_tekst_ze_wszystkich_stron(self, tmp_path: Path) -> None:
        plik = tmp_path / "umowa.pdf"
        plik.write_bytes(zbuduj_pdf(["Czynsz najmu wynosi 6 960,00 zl", "Kaucja 20 880,00 zl"]))

        dokument = CzytnikPdf().czytaj(plik)

        assert dokument.warstwa is WarstwaTekstu.PDF_TEKST
        assert dokument.liczba_stron == 2
        assert "6 960,00" in dokument.strony[0].tekst
        assert "Kaucja" in dokument.strony[1].tekst

    def test_numeracja_stron_od_jedynki(self, tmp_path: Path) -> None:
        """Numer trafia do zrodlo_strona i ma prowadzić człowieka do właściwej
        kartki, więc liczy się tak, jak liczy ją on."""
        plik = tmp_path / "umowa.pdf"
        plik.write_bytes(zbuduj_pdf(["pierwsza", "druga", "trzecia"]))

        dokument = CzytnikPdf().czytaj(plik)

        assert [s.numer for s in dokument.strony] == [1, 2, 3]

    def test_skan_bez_warstwy_tekstowej_daje_pusty_dokument(self, tmp_path: Path) -> None:
        """Nie wyjątek. Pusty wynik to poprawna informacja: ten plik wymaga OCR-a."""
        plik = tmp_path / "skan.pdf"
        plik.write_bytes(zbuduj_pdf(["", ""]))

        dokument = CzytnikPdf().czytaj(plik)

        assert dokument.pusty is True
        assert dokument.liczba_stron == 2

    def test_uszkodzony_plik_daje_blad_po_polsku(self, tmp_path: Path) -> None:
        plik = tmp_path / "uszkodzony.pdf"
        plik.write_bytes(b"to nie jest PDF")

        with pytest.raises(BladOdczytuTekstu, match="PDF"):
            CzytnikPdf().czytaj(plik)

    def test_pdf_bez_ani_jednej_strony(self, tmp_path: Path) -> None:
        """Plik, który jest poprawnym PDF-em, ale nie ma stron. Nie mamy z czego
        czytać, więc mówimy to wprost zamiast zwracać dokument bez treści."""
        plik = tmp_path / "pusty.pdf"
        plik.write_bytes(zbuduj_pdf([]))

        with pytest.raises(BladOdczytuTekstu, match="żadnej strony"):
            CzytnikPdf().czytaj(plik)

    def test_obsluguje_tylko_pdf(self) -> None:
        assert CzytnikPdf().obsluguje(Path("a.pdf")) is True
        assert CzytnikPdf().obsluguje(Path("a.PDF")) is True
        assert CzytnikPdf().obsluguje(Path("a.docx")) is False


class TestCzytnikaDocx:
    def test_czyta_akapity(self, tmp_path: Path) -> None:
        plik = tmp_path / "aneks.docx"
        plik.write_bytes(zbuduj_docx(["Aneks nr 1", "Czynsz wynosi 7 218,00 zl"]))

        dokument = CzytnikDocx().czytaj(plik)

        assert dokument.warstwa is WarstwaTekstu.DOCX
        assert "Aneks nr 1" in dokument.strony[0].tekst
        assert "7 218,00" in dokument.strony[0].tekst

    def test_docx_ma_jedna_strone(self, tmp_path: Path) -> None:
        """DOCX nie niesie podziału na strony. Zmyślony podział byłby
        informacją, której w pliku nie ma."""
        plik = tmp_path / "aneks.docx"
        plik.write_bytes(zbuduj_docx(["a"] * 50))

        assert CzytnikDocx().czytaj(plik).liczba_stron == 1

    def test_akapit_pociety_formatowaniem_jest_sklejany(self, tmp_path: Path) -> None:
        """Word tnie akapit przy każdej zmianie formatowania. Pogrubienie kwoty
        rozbija zdanie na trzy fragmenty i bez sklejenia żaden wzorzec
        nie zobaczy całego zapisu."""
        xml = (
            f'<?xml version="1.0"?><w:document xmlns:w="{PRZESTRZEN}"><w:body>'
            "<w:p>"
            "<w:r><w:t>Czynsz wynosi </w:t></w:r>"
            "<w:r><w:t>6 960,00 zl</w:t></w:r>"
            "<w:r><w:t> netto.</w:t></w:r>"
            "</w:p></w:body></w:document>"
        )
        bufor = io.BytesIO()
        with zipfile.ZipFile(bufor, "w") as archiwum:
            archiwum.writestr("word/document.xml", xml)
        plik = tmp_path / "umowa.docx"
        plik.write_bytes(bufor.getvalue())

        assert "Czynsz wynosi 6 960,00 zl netto." in CzytnikDocx().czytaj(plik).strony[0].tekst

    def test_archiwum_bez_tresci(self, tmp_path: Path) -> None:
        bufor = io.BytesIO()
        with zipfile.ZipFile(bufor, "w") as archiwum:
            archiwum.writestr("inne.xml", "<a/>")
        plik = tmp_path / "puste.docx"
        plik.write_bytes(bufor.getvalue())

        with pytest.raises(BladOdczytuTekstu, match="nie zawiera treści dokumentu"):
            CzytnikDocx().czytaj(plik)

    def test_plik_ktory_nie_jest_archiwum(self, tmp_path: Path) -> None:
        plik = tmp_path / "niby.docx"
        plik.write_bytes(b"zwykly tekst")

        with pytest.raises(BladOdczytuTekstu, match="DOCX"):
            CzytnikDocx().czytaj(plik)

    def test_uszkodzony_xml(self, tmp_path: Path) -> None:
        bufor = io.BytesIO()
        with zipfile.ZipFile(bufor, "w") as archiwum:
            archiwum.writestr("word/document.xml", "<w:document><nie zamkniete")
        plik = tmp_path / "zepsuty.docx"
        plik.write_bytes(bufor.getvalue())

        with pytest.raises(BladOdczytuTekstu, match="uszkodzona"):
            CzytnikDocx().czytaj(plik)

    def test_zlamanie_wiersza_i_tabulator_daja_odstep(self, tmp_path: Path) -> None:
        """Adres do korespondencji bywa wpisany złamaniami wiersza w jednym
        akapicie. Bez odstępu skleiłby się w jeden ciąg („ul.Polna1")
        i przestałby przypominać adres."""
        xml = (
            f'<?xml version="1.0"?><w:document xmlns:w="{PRZESTRZEN}"><w:body>'
            "<w:p>"
            "<w:r><w:t>ul. Polna 1</w:t></w:r>"
            "<w:r><w:br/></w:r>"
            "<w:r><w:t>00-001 Warszawa</w:t></w:r>"
            "<w:r><w:tab/></w:r>"
            "<w:r><w:t>NIP 1234563218</w:t></w:r>"
            "</w:p></w:body></w:document>"
        )
        bufor = io.BytesIO()
        with zipfile.ZipFile(bufor, "w") as archiwum:
            archiwum.writestr("word/document.xml", xml)
        plik = tmp_path / "adres.docx"
        plik.write_bytes(bufor.getvalue())

        tekst = CzytnikDocx().czytaj(plik).strony[0].tekst

        assert tekst == "ul. Polna 1 00-001 Warszawa NIP 1234563218"


class TestWyboruCzytnika:
    def test_pdf_i_docx_trafiaja_do_wlasciwego_czytnika(self, tmp_path: Path) -> None:
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(zbuduj_pdf(["tresc"]))
        docx = tmp_path / "b.docx"
        docx.write_bytes(zbuduj_docx(["tresc"]))

        assert czytaj_tekst(pdf).warstwa is WarstwaTekstu.PDF_TEKST
        assert czytaj_tekst(docx).warstwa is WarstwaTekstu.DOCX

    def test_stary_doc_mowi_co_zrobic(self, tmp_path: Path) -> None:
        """Milczące zwrócenie pustki byłoby nie do odróżnienia od skanu
        i wysłałoby człowieka szukać OCR-a zamiast zapisać plik ponownie."""
        plik = tmp_path / "stara.doc"
        plik.write_bytes(b"cokolwiek")

        with pytest.raises(BladOdczytuTekstu, match="zapisz go jako PDF albo DOCX"):
            czytaj_tekst(plik)

    def test_nieznane_rozszerzenie(self, tmp_path: Path) -> None:
        plik = tmp_path / "obrazek.jpg"
        plik.write_bytes(b"cokolwiek")

        with pytest.raises(BladOdczytuTekstu, match="Obsługiwane formaty"):
            czytaj_tekst(plik)

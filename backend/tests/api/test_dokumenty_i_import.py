"""Dokumenty i import z arkusza przez HTTP.

Kryterium akceptacji etapu E7: import arkusza z celowo wprowadzonymi błędami
daje czytelny raport i **nie zapisuje niczego połowicznie**.
"""

import json
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from najem.domena.slowniki import RolaUzytkownika
from najem.modele import Budynek, Lokal, Najemca, OkresNajmu, ParametrWartosc
from tests.api.conftest import zaloguj_jako

pytestmark = pytest.mark.integracja

#: Najmniejszy poprawny PDF, jaki da się napisać ręcznie.
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32

NAGLOWKI = [
    "Budynek",
    "Lokal",
    "Typ",
    "Powierzchnia",
    "Najemca",
    "NIP",
    "Przekazanie",
    "Okres",
    "Czynsz",
    "Netto/brutto",
    "VAT",
    "Płatne do",
]

#: Mapowanie kolumn arkusza na pola systemu, tak jak zrobiłby to człowiek
#: w kreatorze importu.
MAPOWANIE = json.dumps(
    {
        "Budynek": "budynek",
        "Lokal": "lokal",
        "Typ": "typ_lokalu",
        "Powierzchnia": "powierzchnia",
        "Najemca": "najemca",
        "NIP": "nip",
        "Przekazanie": "data_przekazania",
        "Okres": "okres_miesiace",
        "Czynsz": "czynsz",
        "Netto/brutto": "czynsz_rodzaj",
        "VAT": "stawka_vat",
        "Płatne do": "dzien_platnosci",
    }
)


def arkusz(wiersze: list[list[object]]) -> bytes:
    """Prawdziwy plik XLSX w pamięci."""
    skoroszyt = Workbook()
    arkusz_roboczy = skoroszyt.active
    assert arkusz_roboczy is not None
    arkusz_roboczy.append(NAGLOWKI)
    for wiersz in wiersze:
        arkusz_roboczy.append(wiersz)
    bufor = BytesIO()
    skoroszyt.save(bufor)
    return bufor.getvalue()


def wiersz_poprawny(lokal: str = "18A/12", budynek: str = "18A") -> list[object]:
    return [
        budynek,
        lokal,
        "handlowy",
        "128,50",
        "Piekarnia Złoty Kłos",
        "5842746735",
        "01.03.2024",
        36,
        "9 500,00",
        "netto",
        23,
        10,
    ]


class TestWgrywanieDokumentu:
    def test_pdf_przechodzi(self, klient_zarzadca: TestClient) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa",
            files={"plik": ("umowa.pdf", PDF, "application/pdf")},
        )
        assert odpowiedz.status_code == 201
        assert odpowiedz.json()["typ_mime"] == "application/pdf"
        assert len(odpowiedz.json()["hash_sha256"]) == 64

    def test_typ_rozpoznawany_po_zawartosci_a_nie_po_rozszerzeniu(
        self, klient_zarzadca: TestClient
    ) -> None:
        """Rozszerzenie jest deklaracją nadawcy. Liczy się, co jest w pliku."""
        odpowiedz = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=polisa",
            files={"plik": ("skan-bez-rozszerzenia", PNG, "application/pdf")},
        )
        assert odpowiedz.status_code == 201
        assert odpowiedz.json()["typ_mime"] == "image/png"

    def test_plik_wykonywalny_udajacy_pdf_jest_odrzucany(self, klient_zarzadca: TestClient) -> None:
        """`umowa.pdf` bywa plikiem wykonywalnym. Nagłówek MZ to Windows PE."""
        odpowiedz = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa",
            files={"plik": ("umowa.pdf", b"MZ\x90\x00" + b"\x00" * 64, "application/pdf")},
        )
        assert odpowiedz.status_code == 422
        assert "zawartość pliku" in odpowiedz.json()["detail"]

    def test_pusty_plik_jest_odrzucany(self, klient_zarzadca: TestClient) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa", files={"plik": ("pusty.pdf", b"", "application/pdf")}
        )
        assert odpowiedz.status_code == 422

    def test_arkusz_nie_jest_dokumentem_umowy(self, klient_zarzadca: TestClient) -> None:
        """XLSX idzie ścieżką importu, a nie do repozytorium dokumentów."""
        odpowiedz = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa",
            files={"plik": ("dane.xlsx", arkusz([]), "application/vnd.ms-excel")},
        )
        assert odpowiedz.status_code == 422

    def test_ten_sam_plik_drugi_raz_jest_rozpoznawany(self, klient_zarzadca: TestClient) -> None:
        pierwszy = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa", files={"plik": ("a.pdf", PDF, "application/pdf")}
        )
        assert pierwszy.status_code == 201

        drugi = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=aneks",
            files={"plik": ("inna-nazwa.pdf", PDF, "application/pdf")},
        )
        assert drugi.status_code == 409
        assert "już jest w systemie" in drugi.json()["detail"]
        assert drugi.headers["X-Dokument-Id"] == str(pierwszy.json()["id"])

    def test_podglad_nie_moze_wgrywac(self, klient_podglad: TestClient) -> None:
        assert (
            klient_podglad.post(
                "/api/v1/dokumenty?typ=umowa",
                files={"plik": ("a.pdf", PDF, "application/pdf")},
            ).status_code
            == 403
        )

    def test_pobranie_zwraca_ten_sam_plik(self, klient_zarzadca: TestClient) -> None:
        dokument = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa", files={"plik": ("a.pdf", JPEG, "image/jpeg")}
        ).json()

        pobrany = klient_zarzadca.get(f"/api/v1/dokumenty/{dokument['id']}/plik")
        assert pobrany.status_code == 200
        assert pobrany.content == JPEG
        assert pobrany.headers["X-Content-Type-Options"] == "nosniff"

    def test_pobranie_zostawia_slad_w_audycie(
        self, klient_zarzadca: TestClient, baza: Session
    ) -> None:
        """Każdy odczyt danych wrażliwych jest logowany (koncepcja, sekcja 8.1)."""
        from najem.domena.slowniki import OperacjaAudytu
        from najem.modele import LogAudytu

        dokument = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa", files={"plik": ("a.pdf", PDF, "application/pdf")}
        ).json()
        klient_zarzadca.get(f"/api/v1/dokumenty/{dokument['id']}/plik")

        odczyty = baza.scalars(
            select(LogAudytu).where(
                LogAudytu.operacja == OperacjaAudytu.ODCZYT_WRAZLIWY,
                LogAudytu.tabela == "dokument",
            )
        ).all()
        assert len(odczyty) == 1
        assert odczyty[0].rekord_id == dokument["id"]

    def test_aneks_wskazuje_na_umowe(self, klient_zarzadca: TestClient) -> None:
        umowa = klient_zarzadca.post(
            "/api/v1/dokumenty?typ=umowa", files={"plik": ("u.pdf", PDF, "application/pdf")}
        ).json()

        inny_pdf = PDF.replace(b"1.4", b"1.7")
        aneks = klient_zarzadca.post(
            f"/api/v1/dokumenty?typ=aneks&dokument_nadrzedny_id={umowa['id']}",
            files={"plik": ("a.pdf", inny_pdf, "application/pdf")},
        )
        assert aneks.status_code == 201
        assert aneks.json()["dokument_nadrzedny_id"] == umowa["id"]


class TestPodgladImportu:
    def test_pokazuje_naglowki_i_liczbe_wierszy(self, klient_zarzadca: TestClient) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/import/podglad",
            files={"plik": ("dane.xlsx", arkusz([wiersz_poprawny()]), "application/xlsx")},
            data={"mapowanie": MAPOWANIE},
        )
        assert odpowiedz.status_code == 200
        dane = odpowiedz.json()
        assert dane["naglowki"][:2] == ["Budynek", "Lokal"]
        assert dane["wierszy_w_pliku"] == 1
        assert dane["wierszy_poprawnych"] == 1
        assert dane["bledy"] == []

    def test_podglad_niczego_nie_zapisuje(self, klient_zarzadca: TestClient, baza: Session) -> None:
        klient_zarzadca.post(
            "/api/v1/import/podglad",
            files={"plik": ("dane.xlsx", arkusz([wiersz_poprawny()]), "application/xlsx")},
            data={"mapowanie": MAPOWANIE},
        )
        assert baza.scalar(select(func.count()).select_from(Budynek)) == 0

    def test_bledy_maja_numery_wierszy(self, klient_zarzadca: TestClient) -> None:
        bledny = wiersz_poprawny()
        bledny[4] = ""  # brak najemcy
        odpowiedz = klient_zarzadca.post(
            "/api/v1/import/podglad",
            files={
                "plik": (
                    "dane.xlsx",
                    arkusz([wiersz_poprawny(), bledny]),
                    "application/xlsx",
                )
            },
            data={"mapowanie": MAPOWANIE},
        )
        bledy = odpowiedz.json()["bledy"]
        assert len(bledy) == 1
        assert bledy[0]["wiersz"] == 3
        assert "Wiersz 3" in bledy[0]["opis"]

    def test_plik_ktory_nie_jest_arkuszem(self, klient_zarzadca: TestClient) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/import/podglad",
            files={"plik": ("dane.xlsx", PDF, "application/xlsx")},
            data={"mapowanie": MAPOWANIE},
        )
        assert odpowiedz.status_code == 422
        assert "XLSX" in odpowiedz.json()["detail"]

    def test_nieznane_pole_w_mapowaniu(self, klient_zarzadca: TestClient) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/import/podglad",
            files={"plik": ("d.xlsx", arkusz([]), "application/xlsx")},
            data={"mapowanie": '{"Budynek":"kolor_sciany"}'},
        )
        assert odpowiedz.status_code == 422
        assert "kolor_sciany" in odpowiedz.json()["detail"]


class TestWykonanieImportu:
    def test_import_tworzy_komplet_danych(self, klient_zarzadca: TestClient, baza: Session) -> None:
        odpowiedz = klient_zarzadca.post(
            "/api/v1/import/wykonaj",
            files={"plik": ("d.xlsx", arkusz([wiersz_poprawny()]), "application/xlsx")},
            data={"mapowanie": MAPOWANIE},
        )
        assert odpowiedz.status_code == 200
        wynik = odpowiedz.json()
        assert wynik["budynkow_dodanych"] == 1
        assert wynik["lokali_dodanych"] == 1
        assert wynik["najemcow_dodanych"] == 1
        assert wynik["umow_dodanych"] == 1
        assert wynik["warunkow_dodanych"] == 1
        assert wynik["skladnikow_dodanych"] == 1

        okres = baza.scalars(select(OkresNajmu)).one()
        assert okres.data_zakonczenia_planowana is not None

        czynsz = baza.scalars(select(ParametrWartosc)).one()
        assert str(czynsz.wartosc_kwota) == "9500.00"
        assert czynsz.status_weryfikacji.value == "zatwierdzona"

    def test_arkusz_z_bledem_nie_zapisuje_niczego(
        self, klient_zarzadca: TestClient, baza: Session
    ) -> None:
        """Kryterium akceptacji E7. Albo cały plik, albo nic."""
        bledny = wiersz_poprawny(lokal="18A/13")
        bledny[4] = ""  # brak najemcy

        odpowiedz = klient_zarzadca.post(
            "/api/v1/import/wykonaj",
            files={
                "plik": (
                    "d.xlsx",
                    arkusz([wiersz_poprawny(), bledny, wiersz_poprawny(lokal="18A/14")]),
                    "application/xlsx",
                )
            },
            data={"mapowanie": MAPOWANIE},
        )
        assert odpowiedz.status_code == 422
        tresc = odpowiedz.json()["detail"]
        assert "Nie zapisano niczego" in tresc["komunikat"]
        assert any("Wiersz 3" in b for b in tresc["bledy"])

        # Dwa poprawne wiersze też nie weszły. To jest sedno kryterium.
        assert baza.scalar(select(func.count()).select_from(Budynek)) == 0
        assert baza.scalar(select(func.count()).select_from(Lokal)) == 0
        assert baza.scalar(select(func.count()).select_from(Najemca)) == 0

    def test_powtorzony_import_nie_duplikuje(
        self, klient_zarzadca: TestClient, baza: Session
    ) -> None:
        """Poprawiony arkusz można wgrać ponownie bez sprzątania po pierwszym."""
        plik = arkusz([wiersz_poprawny()])

        pierwszy = klient_zarzadca.post(
            "/api/v1/import/wykonaj",
            files={"plik": ("d.xlsx", plik, "application/xlsx")},
            data={"mapowanie": MAPOWANIE},
        ).json()
        assert pierwszy["umow_dodanych"] == 1

        drugi = klient_zarzadca.post(
            "/api/v1/import/wykonaj",
            files={"plik": ("d.xlsx", plik, "application/xlsx")},
            data={"mapowanie": MAPOWANIE},
        ).json()
        assert drugi["budynkow_dodanych"] == 0
        assert drugi["lokali_dodanych"] == 0
        assert drugi["najemcow_dodanych"] == 0
        assert drugi["umow_dodanych"] == 0
        assert drugi["wierszy_pominietych"] == 1
        assert "ma już umowę" in drugi["pominiecia"][0]

        assert baza.scalar(select(func.count()).select_from(Budynek)) == 1
        assert baza.scalar(select(func.count()).select_from(OkresNajmu)) == 1

    def test_kilka_lokali_w_jednym_budynku(
        self, klient_zarzadca: TestClient, baza: Session
    ) -> None:
        wynik = klient_zarzadca.post(
            "/api/v1/import/wykonaj",
            files={
                "plik": (
                    "d.xlsx",
                    arkusz(
                        [
                            wiersz_poprawny(lokal="18A/12"),
                            wiersz_poprawny(lokal="18A/13"),
                            wiersz_poprawny(lokal="20C/01", budynek="20C"),
                        ]
                    ),
                    "application/xlsx",
                )
            },
            data={"mapowanie": MAPOWANIE},
        ).json()
        assert wynik["budynkow_dodanych"] == 2
        assert wynik["lokali_dodanych"] == 3
        # Ten sam najemca we wszystkich wierszach: dodany raz.
        assert wynik["najemcow_dodanych"] == 1

    def test_podglad_nie_moze_importowac(self, klient_podglad: TestClient) -> None:
        assert (
            klient_podglad.post(
                "/api/v1/import/wykonaj",
                files={"plik": ("d.xlsx", arkusz([]), "application/xlsx")},
                data={"mapowanie": MAPOWANIE},
            ).status_code
            == 403
        )


class TestRozpoznawanieTypu:
    """Sprawdzenie sygnatur bez ruszania HTTP."""

    def test_docx_odrozniany_od_xlsx(self) -> None:
        from najem.dokumenty.przechowalnia import TypPliku, rozpoznaj_typ

        bufor = BytesIO()
        with zipfile.ZipFile(bufor, "w") as archiwum:
            archiwum.writestr("word/document.xml", "<w:document/>")
        assert rozpoznaj_typ(bufor.getvalue()) is TypPliku.DOCX

        bufor = BytesIO()
        with zipfile.ZipFile(bufor, "w") as archiwum:
            archiwum.writestr("xl/workbook.xml", "<workbook/>")
        assert rozpoznaj_typ(bufor.getvalue()) is TypPliku.XLSX

    def test_zwykly_zip_jest_odrzucany(self) -> None:
        from najem.dokumenty.przechowalnia import BladPliku, rozpoznaj_typ

        bufor = BytesIO()
        with zipfile.ZipFile(bufor, "w") as archiwum:
            archiwum.writestr("cokolwiek.txt", "tekst")
        with pytest.raises(BladPliku, match="Worda ani arkuszem"):
            rozpoznaj_typ(bufor.getvalue())

    def test_sciezka_wychodzaca_poza_katalog(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Jedna pomyłka w danych nie może pozwolić na czytanie dysku."""
        from najem.dokumenty.przechowalnia import BladPliku, wczytaj_plik

        with pytest.raises(BladPliku, match="poza katalog"):
            wczytaj_plik("../../../etc/passwd", katalog=tmp_path)


class TestUprawnieniaDokumentow:
    def test_operator_moze_wgrywac(self, klient: TestClient, baza: Session) -> None:
        zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        assert (
            klient.post(
                "/api/v1/dokumenty?typ=umowa",
                files={"plik": ("a.pdf", PDF, "application/pdf")},
            ).status_code
            == 201
        )

    def test_operator_nie_moze_importowac_arkusza(self, klient: TestClient, baza: Session) -> None:
        """Import zakłada budynki i umowy hurtowo. To praca zarządcy."""
        zaloguj_jako(klient, baza, RolaUzytkownika.OPERATOR)
        assert (
            klient.post(
                "/api/v1/import/wykonaj",
                files={"plik": ("d.xlsx", arkusz([]), "application/xlsx")},
                data={"mapowanie": MAPOWANIE},
            ).status_code
            == 403
        )

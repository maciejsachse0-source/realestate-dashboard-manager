"""Skan folderow z dokumentami na dysku.

Testy pracuja na prawdziwym drzewie katalogow w katalogu tymczasowym pytesta.
Nigdy na katalogu uzytkownika: to jest dokladnie ten rodzaj testu, ktory
kusi, zeby wskazac "prawdziwy folder z umowami", i dokladnie ten, w ktorym
tego robic nie wolno.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from najem.config import ustawienia
from najem.domena.slowniki import (
    BazaOkresuNajmu,
    StatusOkresuNajmu,
    TrybPrzechowywania,
)
from najem.modele import Budynek, Dokument, Lokal, Najemca, OkresNajmu

pytestmark = pytest.mark.integracja

#: Najkrotszy plik, ktory rozpoznawanie typu po zawartosci uzna za PDF.
PDF = b"%PDF-1.4\ntresc umowy\n%%EOF\n"
INNY_PDF = b"%PDF-1.4\ntresc aneksu\n%%EOF\n"


@pytest.fixture
def katalog_skanu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Katalog udajacy drzewo dokumentow uzytkownika, wskazany przez .env."""
    monkeypatch.setenv("KATALOG_SKANU", str(tmp_path))
    ustawienia.cache_clear()
    yield tmp_path
    ustawienia.cache_clear()


@pytest.fixture
def bez_katalogu(monkeypatch: pytest.MonkeyPatch) -> None:
    """Program bez wskazanego katalogu skanu.

    Podmieniamy funkcje, a nie zmienna srodowiskowa: katalog moze byc ustawiony
    w bazie albo w pliku .env, a wtedy samo `delenv` niczego by nie zdjelo
    i test przechodzilby albo nie w zaleznosci od konfiguracji maszyny.
    """
    monkeypatch.setattr("najem.api.v1.skan.katalog_skanu", lambda _baza: None)


@pytest.fixture
def umowa(baza: Session, lokal_api: Lokal, najemca_api: Najemca) -> OkresNajmu:
    okres = OkresNajmu(
        lokal_id=lokal_api.id,
        najemca_id=najemca_api.id,
        data_zawarcia=date(2026, 1, 15),
        bazuje_na_dacie=BazaOkresuNajmu.DATA_ZAWARCIA,
        okres_zawarcia_miesiace=24,
        status=StatusOkresuNajmu.AKTYWNA,
    )
    baza.add(okres)
    baza.flush()
    return okres


def zbuduj_drzewo(korzen: Path, budynek: str = "18A", lokal: str = "Lokal nr 12_Kowalski") -> Path:
    """Struktura z dysku uzytkownika: budynek, "Umowy najmu", folder lokalu."""
    folder = korzen / budynek / "Umowy najmu" / lokal
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def operator(klient: TestClient, baza: Session) -> TestClient:
    return klient


class TestSkanowanie:
    def test_bez_ustawionego_katalogu_mowi_co_zrobic(
        self, operator: TestClient, bez_katalogu: None
    ) -> None:
        """Brak konfiguracji to nie jest blad programu, tylko brakujaca decyzja.
        Ekran ma powiedziec, co ustawic, a nie wyrzucic 500."""
        odpowiedz = operator.get("/api/v1/skan")
        assert odpowiedz.status_code == 200
        tresc = odpowiedz.json()
        assert tresc["dostepny"] is False
        assert "KATALOG_SKANU" in tresc["komunikat"]

    def test_wskazany_katalog_nie_istnieje(
        self, operator: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KATALOG_SKANU", str(tmp_path / "nie ma takiego"))
        ustawienia.cache_clear()
        try:
            tresc = operator.get("/api/v1/skan").json()
        finally:
            ustawienia.cache_clear()
        assert tresc["dostepny"] is False
        assert "nie istnieje" in tresc["komunikat"]

    def test_znajduje_pliki_i_proponuje_typ(
        self, operator: TestClient, katalog_skanu: Path, budynek_api: Budynek
    ) -> None:
        folder = zbuduj_drzewo(katalog_skanu, budynek=budynek_api.nazwa)
        (folder / "Umowa najmu.pdf").write_bytes(PDF)
        (folder / "Aneks nr 2.pdf").write_bytes(INNY_PDF)

        tresc = operator.get("/api/v1/skan").json()

        assert tresc["dostepny"] is True
        assert tresc["nowych"] == 2
        budynek = tresc["budynki"][0]
        assert budynek["budynek_id"] == budynek_api.id, "budynek dopasowany po nazwie folderu"
        pliki = {p["nazwa"]: p for p in budynek["foldery"][0]["pliki"]}
        assert pliki["Umowa najmu.pdf"]["typ_proponowany"] == "umowa"
        assert pliki["Aneks nr 2.pdf"]["typ_proponowany"] == "aneks"
        assert pliki["Aneks nr 2.pdf"]["numer_proponowany"] == "2"
        assert all(p["status"] == "nowy" for p in pliki.values())

    def test_nierozpoznana_nazwa_nie_dostaje_typu(
        self, operator: TestClient, katalog_skanu: Path
    ) -> None:
        """Decyzja D5: system nie podstawia "inne" za brak wiedzy."""
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "skan0012.pdf").write_bytes(PDF)

        plik = operator.get("/api/v1/skan").json()["budynki"][0]["foldery"][0]["pliki"][0]
        assert plik["typ_proponowany"] is None

    def test_nieznany_budynek_widac_mimo_braku_dopasowania(
        self, operator: TestClient, katalog_skanu: Path
    ) -> None:
        """Folder budynku, ktorego nie ma w kartotece, tez ma byc widoczny.
        Inaczej czlowiek nie wie, ze system go pomija."""
        zbuduj_drzewo(katalog_skanu, budynek="Nowatorow")

        budynek = operator.get("/api/v1/skan").json()["budynki"][0]
        assert budynek["nazwa_folderu"] == "Nowatorow"
        assert budynek["budynek_id"] is None

    def test_smieci_nie_wchodza_na_liste(self, operator: TestClient, katalog_skanu: Path) -> None:
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(PDF)
        (folder / "~$Umowa.docx").write_bytes(b"tymczasowy plik Worda")
        (folder / "notatki.txt").write_bytes(b"cokolwiek")

        pliki = operator.get("/api/v1/skan").json()["budynki"][0]["foldery"][0]["pliki"]
        assert [p["nazwa"] for p in pliki] == ["Umowa.pdf"]


class TestParowanieFolderu:
    def test_sparowany_folder_pokazuje_umowe(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(PDF)
        sciezka = "18A/Umowy najmu/Lokal nr 12_Kowalski"

        odpowiedz = operator.post(
            "/api/v1/skan/powiazania",
            json={"sciezka_wzgledna": sciezka, "okres_najmu_id": umowa.id},
        )
        assert odpowiedz.status_code == 201

        folder_wynik = operator.get("/api/v1/skan").json()["budynki"][0]["foldery"][0]
        assert folder_wynik["okres_najmu_id"] == umowa.id
        assert "18A/12" in folder_wynik["opis_umowy"]

    def test_powiazanie_do_nieistniejacej_umowy(
        self, operator: TestClient, katalog_skanu: Path
    ) -> None:
        odpowiedz = operator.post(
            "/api/v1/skan/powiazania",
            json={"sciezka_wzgledna": "cokolwiek", "okres_najmu_id": 999_999},
        )
        assert odpowiedz.status_code == 422

    def test_przepiecie_folderu_na_inna_umowe(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu, baza: Session
    ) -> None:
        """Pomylka przy parowaniu ma byc odwracalna jednym klikiem, a nie
        wymagac grzebania w bazie."""
        druga = OkresNajmu(
            lokal_id=umowa.lokal_id,
            najemca_id=umowa.najemca_id,
            data_zawarcia=date(2027, 1, 1),
            bazuje_na_dacie=BazaOkresuNajmu.DATA_ZAWARCIA,
            status=StatusOkresuNajmu.PRZYGOTOWANIE,
        )
        baza.add(druga)
        baza.flush()

        sciezka = "18A/Umowy najmu/Lokal nr 12_Kowalski"
        operator.post(
            "/api/v1/skan/powiazania",
            json={"sciezka_wzgledna": sciezka, "okres_najmu_id": umowa.id},
        )
        odpowiedz = operator.post(
            "/api/v1/skan/powiazania",
            json={"sciezka_wzgledna": sciezka, "okres_najmu_id": druga.id},
        )
        assert odpowiedz.status_code == 201
        assert odpowiedz.json()["okres_najmu_id"] == druga.id


class TestImportPrzezOdnosnik:
    def test_dokument_wskazuje_plik_i_go_nie_kopiuje(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu, baza: Session
    ) -> None:
        """Sedno calej funkcji: plik zostaje tam, gdzie lezy."""
        folder = zbuduj_drzewo(katalog_skanu)
        plik = folder / "Umowa najmu.pdf"
        plik.write_bytes(PDF)
        sciezka = "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa najmu.pdf"

        odpowiedz = operator.post(
            "/api/v1/skan/importuj",
            json={"sciezka_wzgledna": sciezka, "typ": "umowa", "okres_najmu_id": umowa.id},
        )
        assert odpowiedz.status_code == 201, odpowiedz.text

        dokument = baza.get(Dokument, odpowiedz.json()["id"])
        assert dokument is not None
        assert dokument.przechowywanie == TrybPrzechowywania.LINK
        assert dokument.plik_sciezka == sciezka
        assert plik.read_bytes() == PDF, "plik zrodlowy nie moze byc ruszony"

        w_przechowalni = list(ustawienia().katalog_dokumentow.rglob("*.pdf"))
        assert not any(p.read_bytes() == PDF for p in w_przechowalni), "kopia nie powstaje"

    def test_data_zostaje_pusta_gdy_nikt_jej_nie_poda(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu, baza: Session
    ) -> None:
        """Do E9 system nie czyta tresci. Brak daty to brak daty, nie "dzis"."""
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(PDF)

        odpowiedz = operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )
        dokument = baza.get(Dokument, odpowiedz.json()["id"])
        assert dokument is not None
        assert dokument.data_dokumentu is None

    def test_zaimportowany_plik_nie_jest_juz_nowy(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(PDF)
        operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )

        tresc = operator.get("/api/v1/skan").json()
        assert tresc["nowych"] == 0
        assert tresc["budynki"][0]["foldery"][0]["pliki"][0]["status"] == "w_systemie"

    def test_ten_sam_plik_dwa_razy(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(PDF)
        (folder / "Umowa kopia.pdf").write_bytes(PDF)
        podstawa = "18A/Umowy najmu/Lokal nr 12_Kowalski"

        operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": f"{podstawa}/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )
        druga = operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": f"{podstawa}/Umowa kopia.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )
        assert druga.status_code == 422
        assert "już w systemie" in druga.json()["detail"]

    def test_plik_znikniety_miedzy_skanem_a_importem(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        zbuduj_drzewo(katalog_skanu)
        odpowiedz = operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Nie ma.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )
        assert odpowiedz.status_code == 404

    def test_sciezka_wychodzaca_poza_katalog(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        """Sciezka przychodzi z zewnatrz, wiec nie moze prowadzic gdziekolwiek."""
        odpowiedz = operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "../../../Windows/System32/drivers/etc/hosts",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )
        assert odpowiedz.status_code in (404, 422)

    def test_plik_udajacy_pdf_odrzucony(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        """Rozszerzenie to deklaracja, nie fakt. Liczy sie zawartosc pliku."""
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(b"MZ\x90\x00program wykonywalny")

        odpowiedz = operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )
        assert odpowiedz.status_code == 422

    def test_zlinkowany_plik_da_sie_pobrac(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(PDF)
        utworzony = operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        ).json()

        odpowiedz = operator.get(f"/api/v1/dokumenty/{utworzony['id']}/plik")
        assert odpowiedz.status_code == 200
        assert odpowiedz.content == PDF


class TestPomijanie:
    def test_pominiety_plik_nie_wraca(self, operator: TestClient, katalog_skanu: Path) -> None:
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Zdjecie drzwi.pdf").write_bytes(PDF)
        sciezka = "18A/Umowy najmu/Lokal nr 12_Kowalski/Zdjecie drzwi.pdf"

        odpowiedz = operator.post("/api/v1/skan/pominiecia", json={"sciezka_wzgledna": sciezka})
        assert odpowiedz.status_code == 201

        tresc = operator.get("/api/v1/skan").json()
        assert tresc["nowych"] == 0
        assert tresc["budynki"][0]["foldery"][0]["pliki"][0]["status"] == "pominiety"

    def test_pominiecie_przezywa_przemianowanie(
        self, operator: TestClient, katalog_skanu: Path
    ) -> None:
        """Pamietamy skrot tresci, nie sciezke. Przemianowany plik to nadal
        ten sam plik i nadal ma sie nie pokazywac."""
        folder = zbuduj_drzewo(katalog_skanu)
        plik = folder / "Zdjecie.pdf"
        plik.write_bytes(PDF)
        operator.post(
            "/api/v1/skan/pominiecia",
            json={"sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Zdjecie.pdf"},
        )

        plik.rename(folder / "Zdjecie drzwi wejsciowych.pdf")

        pliki = operator.get("/api/v1/skan").json()["budynki"][0]["foldery"][0]["pliki"]
        assert pliki[0]["nazwa"] == "Zdjecie drzwi wejsciowych.pdf"
        assert pliki[0]["status"] == "pominiety"

    def test_cofniecie_pominiecia(self, operator: TestClient, katalog_skanu: Path) -> None:
        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Zdjecie.pdf").write_bytes(PDF)
        utworzone = operator.post(
            "/api/v1/skan/pominiecia",
            json={"sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Zdjecie.pdf"},
        ).json()

        odpowiedz = operator.delete(f"/api/v1/skan/pominiecia/{utworzone['id']}")
        assert odpowiedz.status_code == 204
        assert operator.get("/api/v1/skan").json()["nowych"] == 1


class TestPrzegladOdnosnikow:
    def test_przeniesiony_plik_zglasza_sie_jako_zerwany(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        """Cena za brak kopiowania. Ma byc widoczna, a nie odkrywana przy sporze."""
        folder = zbuduj_drzewo(katalog_skanu)
        plik = folder / "Umowa.pdf"
        plik.write_bytes(PDF)
        operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )
        assert operator.get("/api/v1/skan/sprawdz").json()["zerwane"] == []

        plik.unlink()

        wynik = operator.get("/api/v1/skan/sprawdz").json()
        assert wynik["sprawdzonych"] == 1
        assert len(wynik["zerwane"]) == 1
        assert "przeniesiony" in wynik["zerwane"][0]["powod"]

    def test_podmieniona_tresc_tez_jest_zerwaniem(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu
    ) -> None:
        """Dokument ma byc dowodem. Plik o tej samej nazwie, ale innej tresci,
        dowodem juz nie jest."""
        folder = zbuduj_drzewo(katalog_skanu)
        plik = folder / "Umowa.pdf"
        plik.write_bytes(PDF)
        operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        )

        plik.write_bytes(INNY_PDF)

        zerwane = operator.get("/api/v1/skan/sprawdz").json()["zerwane"]
        assert len(zerwane) == 1
        assert "inną treść" in zerwane[0]["powod"]


class TestSladWAudycie:
    def test_import_zostawia_slad(
        self, operator: TestClient, katalog_skanu: Path, umowa: OkresNajmu, baza: Session
    ) -> None:
        from najem.modele import LogAudytu

        folder = zbuduj_drzewo(katalog_skanu)
        (folder / "Umowa.pdf").write_bytes(PDF)
        utworzony = operator.post(
            "/api/v1/skan/importuj",
            json={
                "sciezka_wzgledna": "18A/Umowy najmu/Lokal nr 12_Kowalski/Umowa.pdf",
                "typ": "umowa",
                "okres_najmu_id": umowa.id,
            },
        ).json()

        wpisy = baza.scalars(
            select(LogAudytu).where(
                LogAudytu.tabela == "dokument", LogAudytu.rekord_id == utworzony["id"]
            )
        ).all()
        assert len(wpisy) == 1


class TestOdpornoscNaDysk:
    """Skan chodzi po prawdziwym dysku, wiec trafi na katalog bez uprawnien,
    na sciezke dluzsza niz limit Windowsa albo na odlaczony dysk sieciowy."""

    def test_nieczytelny_folder_nie_konczy_calego_skanu(
        self, operator: TestClient, katalog_skanu: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dobry = zbuduj_drzewo(katalog_skanu, budynek="18A")
        (dobry / "Umowa.pdf").write_bytes(PDF)
        zamkniety = katalog_skanu / "Zamkniety"
        zamkniety.mkdir()

        prawdziwy = Path.iterdir

        def udawaj_brak_dostepu(self: Path):  # type: ignore[no-untyped-def]
            if self.name == "Zamkniety":
                raise PermissionError(13, "Odmowa dostepu")
            return prawdziwy(self)

        monkeypatch.setattr(Path, "iterdir", udawaj_brak_dostepu)

        odpowiedz = operator.get("/api/v1/skan")

        assert odpowiedz.status_code == 200, "jeden zly katalog nie moze zabrac reszty"
        tresc = odpowiedz.json()
        assert tresc["niedostepnych"] >= 1, "pominiecie ma byc policzone, nie przemilczane"
        assert tresc["nowych"] == 1, "dokumenty z czytelnych folderow maja byc widoczne"


class TestUstawianieKatalogu:
    """Katalog wskazuje sie w interfejsie, nie w pliku .env.

    Wymaganie edycji pliku tekstowego od osoby, ktora ma obslugiwac umowy,
    bylo przerzucaniem na nia pracy administratora.
    """

    def test_administrator_ustawia_katalog(
        self, klient: TestClient, baza: Session, tmp_path: Path
    ) -> None:
        docelowy = tmp_path / "Budynki"
        docelowy.mkdir()

        odpowiedz = klient.put("/api/v1/skan/katalog", json={"sciezka": str(docelowy)})

        assert odpowiedz.status_code == 200, odpowiedz.text
        tresc = odpowiedz.json()
        assert tresc["zrodlo"] == "baza"
        assert tresc["istnieje"] is True
        assert Path(tresc["sciezka"]) == docelowy

    def test_ustawienie_z_bazy_wygrywa_z_plikiem(
        self, klient: TestClient, baza: Session, katalog_skanu: Path, tmp_path: Path
    ) -> None:
        """Fixture ustawia KATALOG_SKANU w srodowisku; wpis w bazie ma go przykryc."""
        inny = tmp_path / "Inne budynki"
        inny.mkdir()
        zbuduj_drzewo(inny, budynek="Rycerska")

        klient.put("/api/v1/skan/katalog", json={"sciezka": str(inny)})

        skan = klient.get("/api/v1/skan").json()
        assert Path(skan["katalog"]) == inny
        assert skan["budynki"][0]["nazwa_folderu"] == "Rycerska"

    def test_literowka_w_sciezce_wykryta_od_razu(
        self, klient: TestClient, baza: Session, tmp_path: Path
    ) -> None:
        """Najczestszy blad przy tym polu. Wykryty przy zapisie kosztuje poprawke
        jednego znaku zamiast szukania, czemu skan nic nie znajduje."""

        odpowiedz = klient.put(
            "/api/v1/skan/katalog", json={"sciezka": str(tmp_path / "nie ma takiego")}
        )

        assert odpowiedz.status_code == 422
        assert "nie istnieje" in odpowiedz.json()["detail"]

    def test_sciezka_wzgledna_odrzucona(self, klient: TestClient, baza: Session) -> None:

        odpowiedz = klient.put("/api/v1/skan/katalog", json={"sciezka": "Dokumenty/Budynki"})

        assert odpowiedz.status_code == 422
        assert "pełną ścieżkę" in odpowiedz.json()["detail"]

    def test_plik_zamiast_katalogu(self, klient: TestClient, baza: Session, tmp_path: Path) -> None:
        plik = tmp_path / "umowa.pdf"
        plik.write_bytes(PDF)

        odpowiedz = klient.put("/api/v1/skan/katalog", json={"sciezka": str(plik)})

        assert odpowiedz.status_code == 422
        assert "katalog" in odpowiedz.json()["detail"]

    def test_operator_widzi_ktory_katalog_jest_ustawiony(
        self, klient: TestClient, baza: Session, katalog_skanu: Path
    ) -> None:
        """Odczyt tak, zapis nie: operator musi wiedziec, gdzie program szuka."""

        odpowiedz = klient.get("/api/v1/skan/katalog")

        assert odpowiedz.status_code == 200
        assert Path(odpowiedz.json()["sciezka"]) == katalog_skanu

    def test_wyczyszczenie_wraca_do_pliku(
        self, klient: TestClient, baza: Session, katalog_skanu: Path, tmp_path: Path
    ) -> None:
        inny = tmp_path / "Inne"
        inny.mkdir()
        klient.put("/api/v1/skan/katalog", json={"sciezka": str(inny)})

        odpowiedz = klient.delete("/api/v1/skan/katalog")

        assert odpowiedz.status_code == 200
        tresc = odpowiedz.json()
        assert tresc["zrodlo"] == "plik"
        assert Path(tresc["sciezka"]) == katalog_skanu

"""Zapis zaimportowanego arkusza do bazy.

Dwie zasady, obie z planu budowy (sekcja E7):

**Albo cały plik, albo nic.** Sprawdzamy wszystko przed zapisaniem czegokolwiek.
Import, który zapisuje trzydzieści wierszy i wywala się na trzydziestym pierwszym,
zostawia bazę w stanie, którego nikt nie umie posprzątać.

**Powtórzenie importu nie duplikuje danych.** Budynek, lokal i najemca są
odnajdywani po naturalnych cechach; umowa nie powstaje drugi raz dla lokalu,
który już ją ma. Dzięki temu poprawiony arkusz można wgrać ponownie.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from najem.domena.import_arkusza import BladWiersza, WierszImportu
from najem.domena.reguly.data_zakonczenia import data_zakonczenia
from najem.domena.slowniki import (
    BazaOkresuNajmu,
    OperacjaAudytu,
    RodzajKwoty,
    StatusLokalu,
    StatusOkresuNajmu,
    StatusWeryfikacji,
    TypLokalu,
    TypWartosci,
)
from najem.modele import (
    Budynek,
    Lokal,
    Najemca,
    OkresNajmu,
    ParametrWartosc,
    SkladnikOplaty,
)
from najem.uslugi.audyt import zapisz_zmiane

KLUCZ_CZYNSZU = "czynsz_podstawowy"

#: Statusy, przy których uznajemy, że lokal ma już bieżącą umowę.
STATUSY_BIEZACE = (
    StatusOkresuNajmu.PRZYGOTOWANIE,
    StatusOkresuNajmu.AKTYWNA,
    StatusOkresuNajmu.WYPOWIEDZIANA,
)


@dataclass
class WynikImportu:
    """Co import zrobił. Trafia wprost na ekran po zakończeniu."""

    budynkow_dodanych: int = 0
    lokali_dodanych: int = 0
    najemcow_dodanych: int = 0
    umow_dodanych: int = 0
    warunkow_dodanych: int = 0
    skladnikow_dodanych: int = 0
    wierszy_pominietych: int = 0
    pominiecia: list[str] = field(default_factory=list)

    @property
    def cokolwiek_dodano(self) -> bool:
        return any(
            (
                self.budynkow_dodanych,
                self.lokali_dodanych,
                self.najemcow_dodanych,
                self.umow_dodanych,
                self.warunkow_dodanych,
                self.skladnikow_dodanych,
            )
        )


class ImportPrzerwany(Exception):
    """Arkusz ma błędy. Nic nie zostało zapisane."""

    def __init__(self, bledy: list[BladWiersza]) -> None:
        self.bledy = bledy
        super().__init__(f"Arkusz ma {len(bledy)} błędów. Nie zapisano niczego.")


def _znajdz_lub_dodaj_budynek(sesja: Session, nazwa: str, wynik: WynikImportu) -> Budynek:
    istniejacy = sesja.scalars(
        select(Budynek).where(
            func.lower(Budynek.nazwa) == nazwa.lower(),
            Budynek.usunieto_dnia.is_(None),
        )
    ).first()
    if istniejacy is not None:
        return istniejacy

    budynek = Budynek(nazwa=nazwa)
    sesja.add(budynek)
    sesja.flush()
    zapisz_zmiane(sesja, budynek, operacja=OperacjaAudytu.UTWORZENIE)
    wynik.budynkow_dodanych += 1
    return budynek


def _znajdz_lub_dodaj_najemce(
    sesja: Session, wiersz: WierszImportu, wynik: WynikImportu
) -> Najemca:
    """Najemca odnajdywany po NIP, a gdy go nie ma — po nazwie.

    NIP jest pewniejszy: ta sama firma bywa wpisywana raz z „sp. z o.o.",
    raz ze „Sp. z o. o.".
    """
    if wiersz.nip:
        po_nipie = sesja.scalars(
            select(Najemca).where(Najemca.nip == wiersz.nip, Najemca.usunieto_dnia.is_(None))
        ).first()
        if po_nipie is not None:
            return po_nipie

    po_nazwie = sesja.scalars(
        select(Najemca).where(
            func.lower(Najemca.nazwa_pelna) == wiersz.najemca.lower(),
            Najemca.usunieto_dnia.is_(None),
        )
    ).first()
    if po_nazwie is not None:
        return po_nazwie

    najemca = Najemca(nazwa_pelna=wiersz.najemca, nip=wiersz.nip)
    sesja.add(najemca)
    sesja.flush()
    zapisz_zmiane(sesja, najemca, operacja=OperacjaAudytu.UTWORZENIE)
    wynik.najemcow_dodanych += 1
    return najemca


def _znajdz_lub_dodaj_lokal(
    sesja: Session,
    budynek: Budynek,
    wiersz: WierszImportu,
    wynik: WynikImportu,
) -> Lokal:
    istniejacy = sesja.scalars(
        select(Lokal).where(
            Lokal.budynek_id == budynek.id,
            func.lower(Lokal.oznaczenie) == wiersz.lokal.lower(),
            Lokal.usunieto_dnia.is_(None),
        )
    ).first()
    if istniejacy is not None:
        return istniejacy

    lokal = Lokal(
        budynek_id=budynek.id,
        oznaczenie=wiersz.lokal,
        typ=TypLokalu(wiersz.typ_lokalu),
        status=StatusLokalu.WYNAJETY,
        powierzchnia_ewidencyjna=wiersz.powierzchnia,
    )
    sesja.add(lokal)
    sesja.flush()
    zapisz_zmiane(sesja, lokal, operacja=OperacjaAudytu.UTWORZENIE)
    wynik.lokali_dodanych += 1
    return lokal


def _zaimportuj_wiersz(sesja: Session, wiersz: WierszImportu, wynik: WynikImportu) -> None:
    budynek = _znajdz_lub_dodaj_budynek(sesja, wiersz.budynek, wynik)
    najemca = _znajdz_lub_dodaj_najemce(sesja, wiersz, wynik)
    lokal = _znajdz_lub_dodaj_lokal(sesja, budynek, wiersz, wynik)

    biezaca = sesja.scalars(
        select(OkresNajmu).where(
            OkresNajmu.lokal_id == lokal.id,
            OkresNajmu.status.in_(STATUSY_BIEZACE),
            OkresNajmu.usunieto_dnia.is_(None),
        )
    ).first()

    if biezaca is not None:
        # Lokal ma już bieżącą umowę. Nie nadpisujemy jej danymi z arkusza:
        # to arkusz jest zwykle mniej aktualny niż system, a nie odwrotnie.
        wynik.wierszy_pominietych += 1
        wynik.pominiecia.append(
            f"Wiersz {wiersz.numer}: lokal {wiersz.lokal} ma już umowę w systemie, pominięto."
        )
        return

    okres = OkresNajmu(
        lokal_id=lokal.id,
        najemca_id=najemca.id,
        data_zawarcia=wiersz.data_zawarcia,
        data_przekazania=wiersz.data_przekazania,
        bazuje_na_dacie=(
            BazaOkresuNajmu.DATA_PRZEKAZANIA
            if wiersz.data_przekazania is not None
            else BazaOkresuNajmu.DATA_ZAWARCIA
        ),
        okres_zawarcia_miesiace=wiersz.okres_miesiace,
        status=StatusOkresuNajmu.AKTYWNA,
    )
    okres.data_zakonczenia_planowana = data_zakonczenia(
        bazuje_na=okres.bazuje_na_dacie,
        okres_miesiace=okres.okres_zawarcia_miesiace,
        data_zawarcia=okres.data_zawarcia,
        data_przekazania=okres.data_przekazania,
    ).wartosc
    sesja.add(okres)
    sesja.flush()
    zapisz_zmiane(sesja, okres, operacja=OperacjaAudytu.UTWORZENIE)
    wynik.umow_dodanych += 1

    if wiersz.czynsz is None:
        return

    obowiazuje_od = wiersz.data_przekazania or wiersz.data_zawarcia
    if obowiazuje_od is None:
        wynik.pominiecia.append(
            f"Wiersz {wiersz.numer}: czynsz podano, ale bez żadnej daty, "
            "więc nie wiadomo, od kiedy obowiązuje. Warunek pominięto."
        )
        return

    # Wartość z arkusza wchodzi jako ZATWIERDZONA, i to jest świadome odstępstwo
    # od domyślnej ścieżki: arkusz wypełnia człowiek, a import uruchamia człowiek,
    # który przed chwilą oglądał podgląd. To jest ta sama decyzja, co przy
    # ręcznym wpisaniu z zatwierdzeniem, tylko wykonana hurtowo.
    sesja.add(
        ParametrWartosc(
            okres_najmu_id=okres.id,
            klucz=KLUCZ_CZYNSZU,
            typ_wartosci=TypWartosci.KWOTA,
            wartosc_kwota=wiersz.czynsz,
            wartosc_waluta="PLN",
            wartosc_rodzaj_kwoty=RodzajKwoty(wiersz.czynsz_rodzaj),
            wartosc_stawka_vat=wiersz.stawka_vat,
            obowiazuje_od=obowiazuje_od,
            status_weryfikacji=StatusWeryfikacji.ZATWIERDZONA,
            zatwierdzono_dnia=datetime.now(UTC),
            uwagi="Wprowadzone importem z arkusza.",
        )
    )
    wynik.warunkow_dodanych += 1

    if wiersz.dzien_platnosci is not None:
        sesja.add(
            SkladnikOplaty(
                okres_najmu_id=okres.id,
                nazwa="Czynsz podstawowy",
                klucz_parametru=KLUCZ_CZYNSZU,
                dzien_platnosci_miesiaca=wiersz.dzien_platnosci,
            )
        )
        wynik.skladnikow_dodanych += 1

    sesja.flush()


def zaimportuj(
    sesja: Session,
    wiersze: list[WierszImportu],
    bledy: list[BladWiersza],
) -> WynikImportu:
    """Zapisuje arkusz. Przy jakimkolwiek błędzie nie zapisuje niczego.

    Wywołujący odpowiada za `commit()`. Dzięki temu cały import jest jedną
    transakcją, a przerwanie w środku nie zostawia połowy danych.
    """
    if bledy:
        raise ImportPrzerwany(bledy)

    wynik = WynikImportu()
    for wiersz in wiersze:
        _zaimportuj_wiersz(sesja, wiersz, wynik)
    return wynik

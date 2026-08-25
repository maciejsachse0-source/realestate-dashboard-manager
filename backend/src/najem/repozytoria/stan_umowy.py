"""Sklada domenowe zdjecie stanu umowy z tego, co lezy w bazie.

To jedyne miejsce, ktore tlumaczy wiersze SQLAlchemy na struktury z `domena/`.
Dzieki temu generator zdarzen i reguly nie wiedza o istnieniu bazy.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from najem.domena.parametry import WartoscParametru, stan_efektywny
from najem.domena.pieniadze import Kwota
from najem.domena.reguly.data_zakonczenia import data_wypowiedzenia, data_zakonczenia
from najem.domena.reguly.kompletnosc import POLA_KRYTYCZNE, ocen_kompletnosc
from najem.domena.slowniki import (
    RodzajZabezpieczenia,
    StatusOkresuNajmu,
    TypWartosci,
)
from najem.domena.zdarzenia import StanPrzegladu, StanUmowy, StanZabezpieczenia
from najem.modele import (
    ObowiazekPrzegladu,
    OkresNajmu,
    ParametrWartosc,
    Zabezpieczenie,
)

#: Klucz parametru niosacego czynsz podstawowy.
KLUCZ_CZYNSZU = "czynsz_podstawowy"
KLUCZ_POWIERZCHNI = "powierzchnia"


def na_wartosc_domenowa(wiersz: ParametrWartosc) -> WartoscParametru | None:
    """Przepisuje wiersz na strukture domenowa. None, gdy wiersz jest niespojny.

    Niespojny wiersz pomijamy zamiast wywracac caly przebieg generatora:
    jedna uszkodzona wartosc nie moze zablokowac alertow dla calego portfela.
    """
    kwota: Kwota | None = None
    if wiersz.typ_wartosci is TypWartosci.KWOTA and wiersz.wartosc_kwota is not None:
        if wiersz.wartosc_waluta is None or wiersz.wartosc_rodzaj_kwoty is None:
            return None
        kwota = Kwota(
            wiersz.wartosc_kwota,
            wiersz.wartosc_waluta,
            wiersz.wartosc_rodzaj_kwoty,
            wiersz.wartosc_stawka_vat,
        )

    try:
        return WartoscParametru(
            klucz=wiersz.klucz,
            typ=wiersz.typ_wartosci,
            obowiazuje_od=wiersz.obowiazuje_od,
            obowiazuje_do=wiersz.obowiazuje_do,
            status=wiersz.status_weryfikacji,
            kwota=kwota,
            liczba=wiersz.wartosc_liczba,
            data=wiersz.wartosc_data,
            flaga=wiersz.wartosc_flaga,
            tekst=wiersz.wartosc_tekst,
            identyfikator=wiersz.id,
            dokument_zrodlowy_id=wiersz.dokument_zrodlowy_id,
        )
    except ValueError:
        return None


def czynsz_na_dzien(okres: OkresNajmu, na_dzien: date) -> Kwota | None:
    """Czynsz obowiazujacy danego dnia albo None, gdy nieustalony."""
    wartosci = [
        w
        for w in (na_wartosc_domenowa(p) for p in okres.parametry if p.usunieto_dnia is None)
        if w is not None
    ]
    stan = stan_efektywny(wartosci, na_dzien)
    pozycja = stan.get(KLUCZ_CZYNSZU)
    return pozycja.kwota if pozycja is not None else None


def wypelnione_pola(okres: OkresNajmu, na_dzien: date, koniec: date | None) -> set[str]:
    """Ktore z pol krytycznych reguly R9 sa wypelnione i zatwierdzone."""
    wartosci = [
        w
        for w in (na_wartosc_domenowa(p) for p in okres.parametry if p.usunieto_dnia is None)
        if w is not None
    ]
    stan = stan_efektywny(wartosci, na_dzien)
    zywe_zabezpieczenia = [z for z in okres.zabezpieczenia if z.usunieto_dnia is None]

    wypelnione: set[str] = {"najemca"}  # najemca_id jest obowiazkowy w schemacie

    if KLUCZ_POWIERZCHNI in stan:
        wypelnione.add("powierzchnia")
    if KLUCZ_CZYNSZU in stan:
        wypelnione.add(KLUCZ_CZYNSZU)
    if okres.data_przekazania is not None:
        wypelnione.add("data_przekazania")
    if koniec is not None:
        wypelnione.add("data_zakonczenia")
    if any(
        s.dzien_platnosci_miesiaca is not None
        for s in okres.skladniki_oplat
        if s.usunieto_dnia is None
    ):
        wypelnione.add("terminy_platnosci")
    if any(z.rodzaj is RodzajZabezpieczenia.KAUCJA for z in zywe_zabezpieczenia):
        wypelnione.add("status_kaucji")
    if any(z.rodzaj is RodzajZabezpieczenia.POLISA for z in zywe_zabezpieczenia):
        wypelnione.add("status_polisy")

    return wypelnione


def zabezpieczenie_domenowe(zab: Zabezpieczenie) -> StanZabezpieczenia:
    wymagana: Kwota | None = None
    if (
        zab.wymagana_wartosc is not None
        and zab.wymagana_waluta is not None
        and zab.wymagana_rodzaj_kwoty is not None
    ):
        wymagana = Kwota(
            zab.wymagana_wartosc,
            zab.wymagana_waluta,
            zab.wymagana_rodzaj_kwoty,
            zab.wymagana_stawka_vat,
        )

    return StanZabezpieczenia(
        zabezpieczenie_id=zab.id,
        rodzaj=zab.rodzaj,
        status=zab.status,
        data_wymagalnosci=zab.data_wymagalnosci,
        data_waznosci=zab.data_waznosci,
        # Suma z polisy bedzie osobnym parametrem po etapie E9. Do tego czasu
        # porownanie kwot nie ma wejscia i regula sama zwraca "nieustalone".
        suma_ubezpieczenia=None,
        wymagana_kwota=wymagana,
    )


def zbuduj_stan_umowy(
    sesja: Session,
    okres: OkresNajmu,
    na_dzien: date,
    *,
    ma_nastepczy: bool = False,
) -> StanUmowy:
    """Zdjecie stanu jednej umowy dla generatora zdarzen."""
    koniec = okres.data_zakonczenia_faktyczna
    if koniec is None:
        wyliczony = data_zakonczenia(
            bazuje_na=okres.bazuje_na_dacie,
            okres_miesiace=okres.okres_zawarcia_miesiace,
            data_zawarcia=okres.data_zawarcia,
            data_przekazania=okres.data_przekazania,
        )
        koniec = wyliczony.wartosc

    termin_wypowiedzenia = data_wypowiedzenia(
        data_zakonczenia_umowy=koniec,
        okres_wypowiedzenia_miesiace=okres.okres_wypowiedzenia_miesiace,
    ).wartosc

    wypelnione = wypelnione_pola(okres, na_dzien, koniec)
    ocena = ocen_kompletnosc(wypelnione, POLA_KRYTYCZNE)

    przeglady = sesja.scalars(
        select(ObowiazekPrzegladu).where(
            ObowiazekPrzegladu.lokal_id == okres.lokal_id,
            ObowiazekPrzegladu.usunieto_dnia.is_(None),
        )
    ).all()

    return StanUmowy(
        okres_najmu_id=okres.id,
        lokal_id=okres.lokal_id,
        oznaczenie_lokalu=okres.lokal.oznaczenie,
        status=okres.status,
        data_rozpoczecia=okres.data_przekazania or okres.data_zawarcia,
        data_przekazania=okres.data_przekazania,
        data_zakonczenia=koniec,
        termin_wypowiedzenia=termin_wypowiedzenia,
        ma_nastepczy_okres=ma_nastepczy,
        waloryzacja_podlega=okres.waloryzacja_podlega,
        waloryzacja_miesiac=okres.waloryzacja_miesiac,
        profil_kompletny=ocena.kompletny,
        brakujace_pola=tuple(sorted(ocena.brakujace)),
        zabezpieczenia=tuple(
            zabezpieczenie_domenowe(z) for z in okres.zabezpieczenia if z.usunieto_dnia is None
        ),
        przeglady=tuple(
            StanPrzegladu(
                obowiazek_id=p.id,
                element=p.element,
                nastepny_termin=p.nastepny_przeglad_data,
            )
            for p in przeglady
        ),
    )


def wczytaj_stany_portfela(sesja: Session, na_dzien: date) -> list[StanUmowy]:
    """Zdjecia stanu wszystkich nieusuniętych okresow najmu."""
    okresy = sesja.scalars(
        select(OkresNajmu)
        .where(OkresNajmu.usunieto_dnia.is_(None))
        .options(
            selectinload(OkresNajmu.lokal),
            selectinload(OkresNajmu.parametry),
            selectinload(OkresNajmu.zabezpieczenia),
            selectinload(OkresNajmu.skladniki_oplat),
        )
        .order_by(OkresNajmu.id)
    ).all()

    # Lokal ma umowe nastepcza, gdy istnieje inny okres zaczynajacy sie pozniej.
    # Liczymy to raz dla calego portfela, zeby nie robic zapytania na umowe.
    czynne_po_lokalu: dict[int, list[OkresNajmu]] = {}
    for okres in okresy:
        czynne_po_lokalu.setdefault(okres.lokal_id, []).append(okres)

    stany: list[StanUmowy] = []
    for okres in okresy:
        rodzenstwo = czynne_po_lokalu[okres.lokal_id]
        ma_nastepczy = any(
            inny.id != okres.id
            and inny.status is not StatusOkresuNajmu.ZAKONCZONA
            and (inny.data_zawarcia or date.min) >= (okres.data_zawarcia or date.min)
            for inny in rodzenstwo
        )
        stany.append(zbuduj_stan_umowy(sesja, okres, na_dzien, ma_nastepczy=ma_nastepczy))

    return stany

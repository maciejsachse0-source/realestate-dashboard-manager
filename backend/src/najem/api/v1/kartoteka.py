"""Kartoteka: budynki, lokale i najemcy.

Wzorzec powtarza sie swiadomie zamiast chowac sie za generyczna warstwa CRUD.
Czytelnosc endpointu jest wazniejsza niz oszczednosc kilkudziesieciu linii,
a kazda encja ma wlasne reguly uprawnien.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import ColumnElement, func, or_, select

from najem.auth.sesje import ZalogowanySesja
from najem.auth.zaleznosci import Administrator, Podglad, Zarzadca
from najem.baza import SesjaBazy
from najem.domena.slowniki import OperacjaAudytu
from najem.modele import Budynek, Lokal, Najemca
from najem.schematy.kartoteka import (
    BudynekWejscie,
    BudynekWyjscie,
    BudynekZmiana,
    LokalWejscie,
    LokalWyjscie,
    LokalZmiana,
    NajemcaWejscie,
    NajemcaWyjscie,
    NajemcaZmiana,
)
from najem.schematy.wspolne import LIMIT_DOMYSLNY, LIMIT_MAKSYMALNY, Strona
from najem.uslugi.audyt import zapisz_zmiane

router = APIRouter(tags=["kartoteka"])

Limit = Annotated[int, Query(ge=1, le=LIMIT_MAKSYMALNY)]
Offset = Annotated[int, Query(ge=0)]


def _adres(request: Request) -> str | None:
    return request.client.host if request.client else None


def _teraz() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ budynki


@router.get("/budynki", response_model=Strona[BudynekWyjscie], summary="Lista budynków")
def lista_budynkow(
    baza: SesjaBazy,
    _: Podglad,
    limit: Limit = LIMIT_DOMYSLNY,
    offset: Offset = 0,
    tylko_aktywne: bool = True,
) -> Strona[BudynekWyjscie]:
    warunki: list[ColumnElement[bool]] = [Budynek.usunieto_dnia.is_(None)]
    if tylko_aktywne:
        warunki.append(Budynek.aktywny.is_(True))

    wszystkich = baza.scalar(select(func.count()).select_from(Budynek).where(*warunki)) or 0
    pozycje = baza.scalars(
        select(Budynek).where(*warunki).order_by(Budynek.nazwa).limit(limit).offset(offset)
    ).all()

    return Strona(
        pozycje=[BudynekWyjscie.model_validate(b) for b in pozycje],
        wszystkich=wszystkich,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/budynki",
    response_model=BudynekWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje budynek",
)
def dodaj_budynek(
    dane: BudynekWejscie, baza: SesjaBazy, kto: Administrator, request: Request
) -> BudynekWyjscie:
    budynek = Budynek(**dane.model_dump())
    baza.add(budynek)
    baza.flush()
    zapisz_zmiane(
        baza,
        budynek,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return BudynekWyjscie.model_validate(budynek)


@router.put("/budynki/{budynek_id}", response_model=BudynekWyjscie, summary="Zmienia budynek")
def zmien_budynek(
    budynek_id: int,
    dane: BudynekZmiana,
    baza: SesjaBazy,
    kto: Administrator,
    request: Request,
) -> BudynekWyjscie:
    budynek = _pobierz(baza, Budynek, budynek_id, "Budynek")
    _sprawdz_wersje(budynek, dane.wersja, "Budynek")
    for pole, wartosc in dane.model_dump(exclude={"wersja"}).items():
        setattr(budynek, pole, wartosc)
    zapisz_zmiane(
        baza,
        budynek,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return BudynekWyjscie.model_validate(budynek)


@router.delete(
    "/budynki/{budynek_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Usuwa budynek (miękko)",
)
def usun_budynek(budynek_id: int, baza: SesjaBazy, kto: Administrator, request: Request) -> None:
    budynek = _pobierz(baza, Budynek, budynek_id, "Budynek")
    _usun_miekko(baza, budynek, kto, _adres(request))
    baza.commit()


# ------------------------------------------------------------------- lokale


@router.post(
    "/lokale",
    response_model=LokalWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje lokal",
)
def dodaj_lokal(
    dane: LokalWejscie, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> LokalWyjscie:
    if baza.get(Budynek, dane.budynek_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazany budynek nie istnieje.")

    lokal = Lokal(**dane.model_dump())
    baza.add(lokal)
    baza.flush()
    zapisz_zmiane(
        baza,
        lokal,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return LokalWyjscie.model_validate(lokal)


@router.get("/lokale/{lokal_id}", response_model=LokalWyjscie, summary="Szczegóły lokalu")
def pobierz_lokal(lokal_id: int, baza: SesjaBazy, _: Podglad) -> LokalWyjscie:
    return LokalWyjscie.model_validate(_pobierz(baza, Lokal, lokal_id, "Lokal"))


@router.put("/lokale/{lokal_id}", response_model=LokalWyjscie, summary="Zmienia lokal")
def zmien_lokal(
    lokal_id: int, dane: LokalZmiana, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> LokalWyjscie:
    lokal = _pobierz(baza, Lokal, lokal_id, "Lokal")
    _sprawdz_wersje(lokal, dane.wersja, "Lokal")
    for pole, wartosc in dane.model_dump(exclude={"wersja"}).items():
        setattr(lokal, pole, wartosc)
    zapisz_zmiane(
        baza,
        lokal,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return LokalWyjscie.model_validate(lokal)


@router.delete(
    "/lokale/{lokal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Usuwa lokal (miękko)",
)
def usun_lokal(lokal_id: int, baza: SesjaBazy, kto: Zarzadca, request: Request) -> None:
    lokal = _pobierz(baza, Lokal, lokal_id, "Lokal")
    _usun_miekko(baza, lokal, kto, _adres(request))
    baza.commit()


# ------------------------------------------------------------------ najemcy


@router.get("/najemcy", response_model=Strona[NajemcaWyjscie], summary="Lista najemców")
def lista_najemcow(
    baza: SesjaBazy,
    _: Podglad,
    limit: Limit = LIMIT_DOMYSLNY,
    offset: Offset = 0,
    szukaj: Annotated[str | None, Query(max_length=200)] = None,
) -> Strona[NajemcaWyjscie]:
    warunki: list[ColumnElement[bool]] = [Najemca.usunieto_dnia.is_(None)]
    if szukaj:
        wzorzec = f"%{szukaj.strip()}%"
        warunki.append(or_(Najemca.nazwa_pelna.ilike(wzorzec), Najemca.nip.ilike(wzorzec)))

    wszystkich = baza.scalar(select(func.count()).select_from(Najemca).where(*warunki)) or 0
    pozycje = baza.scalars(
        select(Najemca).where(*warunki).order_by(Najemca.nazwa_pelna).limit(limit).offset(offset)
    ).all()

    return Strona(
        pozycje=[NajemcaWyjscie.model_validate(n) for n in pozycje],
        wszystkich=wszystkich,
        limit=limit,
        offset=offset,
    )


@router.get("/najemcy/{najemca_id}", response_model=NajemcaWyjscie, summary="Szczegóły najemcy")
def pobierz_najemce(najemca_id: int, baza: SesjaBazy, _: Podglad) -> NajemcaWyjscie:
    return NajemcaWyjscie.model_validate(_pobierz(baza, Najemca, najemca_id, "Najemca"))


@router.post(
    "/najemcy",
    response_model=NajemcaWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaje najemcę",
)
def dodaj_najemce(
    dane: NajemcaWejscie, baza: SesjaBazy, kto: Zarzadca, request: Request
) -> NajemcaWyjscie:
    najemca = Najemca(**dane.model_dump())
    baza.add(najemca)
    baza.flush()
    zapisz_zmiane(
        baza,
        najemca,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return NajemcaWyjscie.model_validate(najemca)


@router.put("/najemcy/{najemca_id}", response_model=NajemcaWyjscie, summary="Zmienia najemcę")
def zmien_najemce(
    najemca_id: int,
    dane: NajemcaZmiana,
    baza: SesjaBazy,
    kto: Zarzadca,
    request: Request,
) -> NajemcaWyjscie:
    najemca = _pobierz(baza, Najemca, najemca_id, "Najemca")
    _sprawdz_wersje(najemca, dane.wersja, "Najemca")
    for pole, wartosc in dane.model_dump(exclude={"wersja"}).items():
        setattr(najemca, pole, wartosc)
    zapisz_zmiane(
        baza,
        najemca,
        operacja=OperacjaAudytu.ZMIANA,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return NajemcaWyjscie.model_validate(najemca)


@router.delete(
    "/najemcy/{najemca_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Usuwa najemcę (miękko)",
)
def usun_najemce(najemca_id: int, baza: SesjaBazy, kto: Zarzadca, request: Request) -> None:
    najemca = _pobierz(baza, Najemca, najemca_id, "Najemca")
    _usun_miekko(baza, najemca, kto, _adres(request))
    baza.commit()


# ----------------------------------------------------------------- pomocnicze


def _sprawdz_wersje(obiekt: object, wersja_klienta: int, nazwa: str) -> None:
    """Optimistic locking. Dwie osoby otwieraja ten sam profil i zapisuja:
    druga dostaje 409 z aktualna wersja, zamiast po cichu nadpisac zmiany pierwszej.

    Odpowiedz niesie wersje biezaca, zeby front mogl pokazac roznice,
    a nie tylko komunikat "sprobuj jeszcze raz".
    """
    wersja_biezaca = getattr(obiekt, "wersja", None)
    if wersja_biezaca is not None and wersja_biezaca != wersja_klienta:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"{nazwa} został w międzyczasie zmieniony przez kogoś innego "
                f"(twoja wersja: {wersja_klienta}, aktualna: {wersja_biezaca}). "
                "Odśwież widok i wprowadź zmiany ponownie."
            ),
            headers={"X-Wersja-Biezaca": str(wersja_biezaca)},
        )


def _pobierz[T](baza: SesjaBazy, model: type[T], identyfikator: int, nazwa: str) -> T:
    """Rekord albo 404. Rekordy usuniete miekko sa dla API nieistniejace."""
    obiekt = baza.get(model, identyfikator)
    if obiekt is None or getattr(obiekt, "usunieto_dnia", None) is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"{nazwa} o numerze {identyfikator} nie istnieje."
        )
    return obiekt


def _usun_miekko(baza: SesjaBazy, obiekt: object, kto: ZalogowanySesja, adres: str | None) -> None:
    """Nic nie kasujemy fizycznie (CLAUDE.md, zasady twarde)."""
    obiekt.usunieto_dnia = _teraz()  # type: ignore[attr-defined]
    obiekt.usunal_uzytkownik_id = kto.uzytkownik.id  # type: ignore[attr-defined]
    zapisz_zmiane(
        baza,
        obiekt,
        operacja=OperacjaAudytu.USUNIECIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=adres,
    )

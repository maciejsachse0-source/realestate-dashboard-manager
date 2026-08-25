"""Wgrywanie, pobieranie i przeglądanie dokumentów.

Dokument to źródło dowodu, nie źródło prawdy (koncepcja, sekcja 1.2). Prawda
leży w bazie i linkuje do fragmentu dokumentu — stąd hierarchia umowa → aneks
i ślad w `parametr_wartosc`.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import ColumnElement, select

from najem.auth.zaleznosci import Operator, Podglad, Zarzadca
from najem.baza import SesjaBazy
from najem.config import ustawienia
from najem.dokumenty.przechowalnia import BladPliku, przyjmij_plik, wczytaj_plik
from najem.domena.slowniki import OperacjaAudytu, StatusPrzetworzenia, TypDokumentu
from najem.modele import Dokument, OkresNajmu
from najem.uslugi.audyt import zapisz_odczyt_wrazliwy, zapisz_zmiane

router = APIRouter(prefix="/dokumenty", tags=["dokumenty"])


class DokumentWyjscie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    okres_najmu_id: int | None
    typ: TypDokumentu
    numer: str | None
    data_dokumentu: date | None
    data_obowiazywania_od: date | None
    plik_nazwa_oryginalna: str | None
    hash_sha256: str | None
    rozmiar_bajty: int | None
    typ_mime: str | None
    dokument_nadrzedny_id: int | None
    status_przetworzenia: StatusPrzetworzenia
    wgral_uzytkownik_id: int | None
    utworzono: datetime
    uwagi: str | None
    wersja: int


class DuplikatDokumentu(BaseModel):
    """Odpowiedź 409 przy wgraniu pliku, który już jest w systemie."""

    detail: str
    dokument_id: int
    okres_najmu_id: int | None


def _adres(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "",
    response_model=DokumentWyjscie,
    status_code=status.HTTP_201_CREATED,
    summary="Wgrywa dokument",
    responses={409: {"model": DuplikatDokumentu, "description": "Plik już jest w systemie"}},
)
async def wgraj(
    baza: SesjaBazy,
    kto: Operator,
    request: Request,
    plik: Annotated[UploadFile, File(description="PDF, DOCX, JPEG albo PNG")],
    typ: Annotated[TypDokumentu, Query(description="Rodzaj dokumentu")],
    okres_najmu_id: Annotated[int | None, Query()] = None,
    dokument_nadrzedny_id: Annotated[
        int | None, Query(description="Umowa, do której należy ten aneks")
    ] = None,
    numer: Annotated[str | None, Query(max_length=80)] = None,
    data_dokumentu: date | None = None,
    data_obowiazywania_od: Annotated[
        date | None, Query(description="Od kiedy obowiązują postanowienia. Aneks bywa wsteczny.")
    ] = None,
) -> DokumentWyjscie:
    zawartosc = await plik.read()

    try:
        zapisany = przyjmij_plik(zawartosc, katalog=ustawienia().katalog_dokumentow)
    except BladPliku as blad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(blad)) from blad

    # Deduplikacja po skrócie treści. Ten sam skan wgrany drugi raz ma zostać
    # rozpoznany, a nie zdublowany — razem z informacją, gdzie już jest.
    istniejacy = baza.scalars(
        select(Dokument).where(
            Dokument.hash_sha256 == zapisany.hash_sha256,
            Dokument.usunieto_dnia.is_(None),
        )
    ).one_or_none()
    if istniejacy is not None:
        gdzie = (
            f" przy umowie numer {istniejacy.okres_najmu_id}" if istniejacy.okres_najmu_id else ""
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Ten dokument już jest w systemie{gdzie} (pozycja {istniejacy.id}).",
            headers={"X-Dokument-Id": str(istniejacy.id)},
        )

    if okres_najmu_id is not None and baza.get(OkresNajmu, okres_najmu_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazany okres najmu nie istnieje."
        )
    if dokument_nadrzedny_id is not None and baza.get(Dokument, dokument_nadrzedny_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Wskazany dokument nadrzędny nie istnieje."
        )

    dokument = Dokument(
        okres_najmu_id=okres_najmu_id,
        typ=typ,
        numer=numer,
        data_dokumentu=data_dokumentu,
        data_obowiazywania_od=data_obowiazywania_od,
        plik_sciezka=zapisany.sciezka_wzgledna,
        # Nazwę z uploadu zapamiętujemy wyłącznie po to, żeby człowiek poznał
        # swój plik na liście. Do niczego innego nie jest używana.
        plik_nazwa_oryginalna=(plik.filename or "")[:300] or None,
        hash_sha256=zapisany.hash_sha256,
        rozmiar_bajty=zapisany.rozmiar_bajty,
        typ_mime=zapisany.typ.value,
        dokument_nadrzedny_id=dokument_nadrzedny_id,
        status_przetworzenia=StatusPrzetworzenia.WGRANY,
        wgral_uzytkownik_id=kto.uzytkownik.id,
    )
    baza.add(dokument)
    baza.flush()
    zapisz_zmiane(
        baza,
        dokument,
        operacja=OperacjaAudytu.UTWORZENIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()
    return DokumentWyjscie.model_validate(dokument)


@router.get("", response_model=list[DokumentWyjscie], summary="Dokumenty umowy albo lokalu")
def lista(
    baza: SesjaBazy,
    _: Podglad,
    okres_najmu_id: Annotated[int | None, Query()] = None,
) -> list[DokumentWyjscie]:
    warunki: list[ColumnElement[bool]] = [Dokument.usunieto_dnia.is_(None)]
    if okres_najmu_id is not None:
        warunki.append(Dokument.okres_najmu_id == okres_najmu_id)

    wiersze = baza.scalars(
        select(Dokument).where(*warunki).order_by(Dokument.data_dokumentu, Dokument.id)
    ).all()
    return [DokumentWyjscie.model_validate(d) for d in wiersze]


@router.get(
    "/{dokument_id}/plik",
    summary="Pobiera plik dokumentu",
    response_class=Response,
)
def pobierz(dokument_id: int, baza: SesjaBazy, kto: Podglad, request: Request) -> Response:
    """Pobranie zostawia ślad w audycie (koncepcja, sekcja 8.1 punkt 6).

    Plik idzie z nagłówkiem `inline`, żeby przeglądarka mogła go pokazać
    zamiast od razu ściągać — ekran weryfikacji będzie tego potrzebował.
    """
    dokument = baza.get(Dokument, dokument_id)
    if dokument is None or dokument.usunieto_dnia is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Dokument o numerze {dokument_id} nie istnieje."
        )
    if dokument.plik_sciezka is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ten dokument nie ma wgranego pliku.")

    try:
        zawartosc = wczytaj_plik(dokument.plik_sciezka, katalog=ustawienia().katalog_dokumentow)
    except BladPliku as blad:
        raise HTTPException(status.HTTP_410_GONE, str(blad)) from blad

    zapisz_odczyt_wrazliwy(
        baza,
        tabela="dokument",
        rekord_id=dokument.id,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()

    nazwa = dokument.plik_nazwa_oryginalna or f"dokument-{dokument.id}"
    return Response(
        content=zawartosc,
        media_type=dokument.typ_mime or "application/octet-stream",
        headers={
            # filename* z kodowaniem UTF-8: nazwy plików bywają po polsku.
            "Content-Disposition": f"inline; filename*=UTF-8''{nazwa}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/{dokument_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Usuwa dokument (miękko)",
)
def usun(dokument_id: int, baza: SesjaBazy, kto: Zarzadca, request: Request) -> None:
    """Sam plik zostaje w przechowalni. W systemie, który ma rozstrzygać spory,
    skasowanie dowodu jest problemem prawnym, nie technicznym.
    """
    dokument = baza.get(Dokument, dokument_id)
    if dokument is None or dokument.usunieto_dnia is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Dokument o numerze {dokument_id} nie istnieje."
        )

    dokument.usunieto_dnia = datetime.now(UTC)
    dokument.usunal_uzytkownik_id = kto.uzytkownik.id
    zapisz_zmiane(
        baza,
        dokument,
        operacja=OperacjaAudytu.USUNIECIE,
        uzytkownik_id=kto.uzytkownik.id,
        adres_ip=_adres(request),
    )
    baza.commit()

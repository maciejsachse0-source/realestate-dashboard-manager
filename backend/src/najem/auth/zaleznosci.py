"""Zaleznosci FastAPI: kto jest zalogowany i czy wolno mu to, o co prosi.

Role sa hierarchiczne (koncepcja, sekcja 7.9): kazda wyzsza umie wszystko,
co nizsza. Dzieki temu endpoint deklaruje minimalna role, a nie liste rol.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from najem.auth.sesje import NAZWA_CIASTECZKA, ZalogowanySesja, odczytaj_sesje, teraz_utc
from najem.baza import SesjaBazy
from najem.domena.slowniki import RolaUzytkownika

#: Hierarchia uprawnien. Wieksza liczba to szersze uprawnienia.
POZIOM_ROLI: dict[RolaUzytkownika, int] = {
    RolaUzytkownika.PODGLAD: 1,
    RolaUzytkownika.OPERATOR: 2,
    RolaUzytkownika.ZARZADCA: 3,
    RolaUzytkownika.ADMINISTRATOR: 4,
}


def biezaca_sesja(request: Request, baza: SesjaBazy) -> ZalogowanySesja:
    """Zalogowany uzytkownik albo 401."""
    token = request.cookies.get(NAZWA_CIASTECZKA)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nie jesteś zalogowany.",
        )

    zalogowany = odczytaj_sesje(baza, token, teraz_utc())
    if zalogowany is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesja wygasła. Zaloguj się ponownie.",
        )
    return zalogowany


Zalogowany = Annotated[ZalogowanySesja, Depends(biezaca_sesja)]


def wymagaj_roli(minimalna: RolaUzytkownika):  # type: ignore[no-untyped-def]
    """Zaleznosc sprawdzajaca, czy uzytkownik ma co najmniej podana role.

    Uzycie: `def endpoint(kto: Annotated[ZalogowanySesja, Depends(wymagaj_roli(ZARZADCA))])`.
    """

    def sprawdz(zalogowany: Zalogowany) -> ZalogowanySesja:
        if POZIOM_ROLI[zalogowany.uzytkownik.rola] < POZIOM_ROLI[minimalna]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Ta operacja wymaga roli {minimalna.value} lub wyższej. "
                    f"Twoja rola to {zalogowany.uzytkownik.rola.value}."
                ),
            )
        return zalogowany

    return sprawdz


#: Skroty do najczestszych progow uprawnien.
Podglad = Annotated[ZalogowanySesja, Depends(wymagaj_roli(RolaUzytkownika.PODGLAD))]
Operator = Annotated[ZalogowanySesja, Depends(wymagaj_roli(RolaUzytkownika.OPERATOR))]
Zarzadca = Annotated[ZalogowanySesja, Depends(wymagaj_roli(RolaUzytkownika.ZARZADCA))]
Administrator = Annotated[ZalogowanySesja, Depends(wymagaj_roli(RolaUzytkownika.ADMINISTRATOR))]

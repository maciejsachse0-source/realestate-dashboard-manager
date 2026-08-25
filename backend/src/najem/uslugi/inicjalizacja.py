"""Pierwsze uruchomienie: konto administratora.

Program ma uruchamiac osoba, ktora nie programuje. Nie moze wiec zaczynac
od komendy w terminalu tworzacej pierwsze konto. Przy pustej tabeli uzytkownikow
zakladamy administratora i pokazujemy haslo raz, w oknie startowym.

Haslo jest losowe i wymaga zmiany przy pierwszym logowaniu (punkt K planu).
Nie ma tu zadnego domyslnego hasla wpisanego w kod: takie haslo zostaje
na produkcji na zawsze.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from najem.auth.haslo import wygeneruj_haslo, zahaszuj
from najem.domena.slowniki import RolaUzytkownika
from najem.modele import Uzytkownik

LOGIN_ADMINISTRATORA = "administrator"


@dataclass(frozen=True)
class KontoPoczatkowe:
    login: str
    haslo: str


def zapewnij_konto_administratora(sesja: Session) -> KontoPoczatkowe | None:
    """Zaklada konto administratora, gdy w bazie nie ma zadnego uzytkownika.

    Zwraca dane do pokazania raz albo None, gdy konta juz istnieja.
    Funkcja jest idempotentna: drugie uruchomienie nie tworzy niczego.
    """
    ilu = sesja.scalar(select(func.count()).select_from(Uzytkownik)) or 0
    if ilu > 0:
        return None

    haslo = wygeneruj_haslo()
    sesja.add(
        Uzytkownik(
            login=LOGIN_ADMINISTRATORA,
            imie_nazwisko="Administrator systemu",
            rola=RolaUzytkownika.ADMINISTRATOR,
            hash_hasla=zahaszuj(haslo),
            wymaga_zmiany_hasla=True,
            aktywny=True,
        )
    )
    sesja.flush()
    return KontoPoczatkowe(login=LOGIN_ADMINISTRATORA, haslo=haslo)

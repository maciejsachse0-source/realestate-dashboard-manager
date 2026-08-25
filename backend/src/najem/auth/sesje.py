"""Zakladanie, weryfikacja i uniewaznianie sesji.

Sesja zyje w bazie, a w ciasteczku leci sam token. Ciasteczko jest HttpOnly
i SameSite=Lax (punkt K planu budowy), wiec skrypt na stronie go nie odczyta,
a przegladarka nie wysle go przy zadaniach z innych witryn.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from najem.modele import Uzytkownik
from najem.modele.sesje import SesjaUzytkownika

#: Nazwa ciasteczka sesyjnego.
NAZWA_CIASTECZKA = "najem_sesja"

#: Jak dlugo zyje sesja bez ponownego logowania.
CZAS_ZYCIA = timedelta(hours=12)

#: Po ilu nieudanych probach blokujemy konto i na jak dlugo (punkt K planu).
LIMIT_NIEUDANYCH_LOGOWAN = 5
CZAS_BLOKADY = timedelta(minutes=15)


class BladLogowania(Exception):
    """Logowanie odrzucone. Komunikat jest celowo ogolny."""


class KontoZablokowane(BladLogowania):
    def __init__(self, do_kiedy: datetime) -> None:
        self.do_kiedy = do_kiedy
        super().__init__(
            "Konto jest tymczasowo zablokowane po nieudanych próbach logowania. "
            f"Spróbuj po {do_kiedy.astimezone().strftime('%H:%M')}."
        )


@dataclass(frozen=True)
class ZalogowanySesja:
    """Kto jest zalogowany i w ramach ktorej sesji."""

    uzytkownik: Uzytkownik
    sesja_id: int


def _skrot(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def zaloguj(
    sesja: Session,
    *,
    login: str,
    haslo: str,
    teraz: datetime,
    adres_ip: str | None = None,
) -> tuple[Uzytkownik, str]:
    """Sprawdza dane logowania i zaklada sesje. Zwraca uzytkownika i token.

    Token jest jedynym momentem, w ktorym istnieje w postaci jawnej. Do bazy
    trafia tylko jego skrot.
    """
    # Import lokalny, zeby modul hasel nie byl potrzebny przy samym odczycie sesji.
    from najem.auth.haslo import zweryfikuj

    uzytkownik = sesja.scalars(select(Uzytkownik).where(Uzytkownik.login == login)).one_or_none()

    if uzytkownik is None:
        # Liczymy skrot mimo braku uzytkownika, zeby czas odpowiedzi nie zdradzal,
        # ktore loginy istnieja.
        zweryfikuj(None, haslo)
        raise BladLogowania("Nieprawidłowy login lub hasło.")

    if uzytkownik.zablokowany_do is not None and uzytkownik.zablokowany_do > teraz:
        raise KontoZablokowane(uzytkownik.zablokowany_do)

    if not uzytkownik.aktywny:
        raise BladLogowania("Konto jest nieaktywne. Skontaktuj się z administratorem.")

    if not zweryfikuj(uzytkownik.hash_hasla, haslo):
        uzytkownik.nieudane_logowania += 1
        if uzytkownik.nieudane_logowania >= LIMIT_NIEUDANYCH_LOGOWAN:
            uzytkownik.zablokowany_do = teraz + CZAS_BLOKADY
            uzytkownik.nieudane_logowania = 0
            sesja.flush()
            raise KontoZablokowane(teraz + CZAS_BLOKADY)
        sesja.flush()
        raise BladLogowania("Nieprawidłowy login lub hasło.")

    uzytkownik.nieudane_logowania = 0
    uzytkownik.zablokowany_do = None
    uzytkownik.ostatnie_logowanie = teraz

    token = secrets.token_urlsafe(48)
    sesja.add(
        SesjaUzytkownika(
            uzytkownik_id=uzytkownik.id,
            token_hash=_skrot(token),
            wygasa=teraz + CZAS_ZYCIA,
            ostatnia_aktywnosc=teraz,
            adres_ip=adres_ip,
        )
    )
    sesja.flush()
    return uzytkownik, token


def odczytaj_sesje(sesja: Session, token: str, teraz: datetime) -> ZalogowanySesja | None:
    """Kto stoi za tokenem albo None, gdy sesja jest nieważna."""
    wpis = sesja.scalars(
        select(SesjaUzytkownika).where(SesjaUzytkownika.token_hash == _skrot(token))
    ).one_or_none()

    if wpis is None or wpis.uniewazniona_dnia is not None or wpis.wygasa <= teraz:
        return None

    uzytkownik = sesja.get(Uzytkownik, wpis.uzytkownik_id)
    if uzytkownik is None or not uzytkownik.aktywny:
        return None

    wpis.ostatnia_aktywnosc = teraz
    return ZalogowanySesja(uzytkownik=uzytkownik, sesja_id=wpis.id)


def wyloguj(sesja: Session, token: str, teraz: datetime) -> None:
    wpis = sesja.scalars(
        select(SesjaUzytkownika).where(SesjaUzytkownika.token_hash == _skrot(token))
    ).one_or_none()
    if wpis is not None and wpis.uniewazniona_dnia is None:
        wpis.uniewazniona_dnia = teraz


def uniewaznij_wszystkie(sesja: Session, uzytkownik_id: int, teraz: datetime) -> int:
    """Wylogowuje uzytkownika ze wszystkich urzadzen.

    Wolane po zmianie hasla i przy dezaktywacji konta.
    """
    wpisy = sesja.scalars(
        select(SesjaUzytkownika).where(
            SesjaUzytkownika.uzytkownik_id == uzytkownik_id,
            SesjaUzytkownika.uniewazniona_dnia.is_(None),
        )
    ).all()
    for wpis in wpisy:
        wpis.uniewazniona_dnia = teraz
    return len(wpisy)


def teraz_utc() -> datetime:
    """Jedno miejsce, w ktorym aplikacja pyta o biezacy czas."""
    return datetime.now(UTC)

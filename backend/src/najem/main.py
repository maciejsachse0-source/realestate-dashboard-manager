"""Punkt wejscia aplikacji."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from najem.api.bledy import zarejestruj_handlery
from najem.api.v1 import router as router_v1
from najem.baza import TworzSesje
from najem.config import KATALOG_REPO, ustawienia
from najem.uslugi.inicjalizacja import zapewnij_konto_administratora
from najem.zadania.harmonogram import uruchom_harmonogram, zatrzymaj_harmonogram

log = structlog.get_logger(__name__)


@asynccontextmanager
async def cykl_zycia(_: FastAPI) -> AsyncIterator[None]:
    """Harmonogram zyje tak dlugo, jak aplikacja.

    Generator zdarzen jest idempotentny, wiec restart aplikacji w srodku dnia
    niczego nie dubluje ani nie gubi.
    """
    _zaloz_konto_poczatkowe()
    uruchom_harmonogram()
    try:
        yield
    finally:
        zatrzymaj_harmonogram()


def _zaloz_konto_poczatkowe() -> None:
    """Przy pustej bazie zaklada administratora i pokazuje haslo raz.

    Bledu nie podnosimy dalej: aplikacja ma wstac takze wtedy, gdy baza jeszcze
    nie odpowiada, zeby endpoint /health mogl powiedziec, co jest nie tak.
    """
    try:
        with TworzSesje() as sesja:
            konto = zapewnij_konto_administratora(sesja)
            sesja.commit()
    except Exception:
        log.warning("konto_poczatkowe_nieutworzone", powod="baza niedostępna przy starcie")
        return

    if konto is None:
        return

    ramka = "=" * 64
    print("")
    print(ramka)
    print("  PIERWSZE URUCHOMIENIE: utworzono konto administratora")
    print(ramka)
    print(f"  Login:  {konto.login}")
    print(f"  Hasło:  {konto.haslo}")
    print("")
    print("  Zapisz je teraz. Ten komunikat nie pojawi się ponownie.")
    print("  Program poprosi o zmianę hasła przy pierwszym logowaniu.")
    print(ramka)
    print("")


app = FastAPI(
    title="System Zarzadzania Umowami Najmu",
    version="0.1.0",
    description="Wewnetrzna aplikacja on-prem. Rejestr stanu umow najmu.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=cykl_zycia,
)

zarejestruj_handlery(app)
app.include_router(router_v1)


@app.get("/api", include_in_schema=False)
def korzen_api() -> dict[str, str]:
    return {"aplikacja": app.title, "wersja": app.version, "srodowisko": ustawienia().srodowisko}


# Zbudowany interfejs serwujemy z tego samego procesu i tego samego portu.
# Dzieki temu uzytkownik ma jeden adres i jedno okno, a nie dwa serwery
# do pilnowania. W trybie deweloperskim katalogu dist jeszcze nie ma i ten
# fragment sie nie wykonuje - wtedy front chodzi na Vite z proxy do /api.
KATALOG_INTERFEJSU: Path = KATALOG_REPO / "frontend" / "dist"

if KATALOG_INTERFEJSU.is_dir():
    app.mount("/", StaticFiles(directory=KATALOG_INTERFEJSU, html=True), name="interfejs")

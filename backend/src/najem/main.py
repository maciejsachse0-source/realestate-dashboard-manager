"""Punkt wejscia aplikacji."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as BladHTTP
from starlette.responses import Response
from starlette.types import Scope

from najem.api.bledy import zarejestruj_handlery
from najem.api.v1 import router as router_v1
from najem.config import KATALOG_REPO, ustawienia
from najem.zadania.harmonogram import uruchom_harmonogram, zatrzymaj_harmonogram

log = structlog.get_logger(__name__)


@asynccontextmanager
async def cykl_zycia(_: FastAPI) -> AsyncIterator[None]:
    """Harmonogram zyje tak dlugo, jak aplikacja.

    Generator zdarzen jest idempotentny, wiec restart aplikacji w srodku dnia
    niczego nie dubluje ani nie gubi.
    """
    uruchom_harmonogram()
    try:
        yield
    finally:
        zatrzymaj_harmonogram()


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


def czy_adres_ekranu(sciezka: str) -> bool:
    """Czy ten adres jest ekranem interfejsu, a nie plikiem ani API.

    Rozstrzyga o tym, komu nalezy sie `index.html`, gdy pliku o takiej nazwie
    nie ma na dysku. Dwa wyjatki sa konieczne:

    * `api/...` -- nieistniejacy endpoint ma zwrocic 404 z JSON-em, a nie
      strone HTML, bo inaczej front dostanie w odpowiedzi na zapytanie
      o dane kawalek HTML-a i zglosi blad parsowania zamiast czytelnego 404;
    * nazwa z kropka (`favicon.ico`, mapa zrodel) -- to prosba o konkretny
      plik. Brak pliku jest brakiem pliku i ma tak wygladac.

    Separatory ujednolicamy, bo `StaticFiles` podaje sciezke przepuszczona
    przez `os.path.normpath` -- na Windowsie `api/v1/cos` przychodzi tu jako
    `api\\v1\\cos` i porownanie z `api/` nie trafia.
    """
    znormalizowana = sciezka.replace("\\", "/")
    if znormalizowana.startswith(("api/", "assets/")):
        return False
    return "." not in znormalizowana.rsplit("/", 1)[-1]


class InterfejsSPA(StaticFiles):
    """Serwowanie zbudowanego interfejsu: przekierowanie adresow i naglowki cache.

    **Adresy.** Sciezki w rodzaju `/kartoteka` czy `/lokale/12` istnieja
    wylacznie w routerze dzialajacym w przegladarce. Na dysku nie ma takich
    plikow, wiec `StaticFiles` odpowiadal na nie 404. Dzialalo to dopoki
    uzytkownik klikal w menu, ale kazde odswiezenie podstrony, wpisanie adresu
    z reki i kazda zakladka w przegladarce konczyly sie strona bledu.
    Dlatego nieznany adres ekranu dostaje `index.html`, a router w przegladarce
    decyduje, co pokazac.

    **Cache.** Pliki z `assets/` maja w nazwie skrot tresci, wiec moga lezec
    w pamieci podrecznej dowolnie dlugo. `index.html` skrotu nie ma i to on
    wskazuje na aktualne pliki -- podany z pamieci podrecznej bez pytania
    serwera pokazuje poprzednia wersje programu mimo zaktualizowanego serwera.
    `no-cache` nie zabrania cache'owania, tylko wymusza sprawdzenie: przy
    niezmienionym pliku przegladarka i tak dostaje 304 i nie pobiera go ponownie.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            odpowiedz = await super().get_response(path, scope)
        except BladHTTP as blad:
            # StaticFiles zglasza brak pliku wyjatkiem, a nie odpowiedzia 404,
            # wiec sprawdzanie `status_code` na zwroconym obiekcie nigdy by
            # tu nie zadzialalo.
            if blad.status_code != 404 or not czy_adres_ekranu(path):
                raise
            odpowiedz = await super().get_response("index.html", scope)

        # Katalog glowny trafia tu jako "." albo pusty tekst, bo html=True
        # podstawia index.html dopiero nizej.
        if path.endswith(".html") or path in {"", ".", "/"} or czy_adres_ekranu(path):
            odpowiedz.headers["Cache-Control"] = "no-cache, must-revalidate"
        return odpowiedz


if KATALOG_INTERFEJSU.is_dir():
    app.mount("/", InterfejsSPA(directory=KATALOG_INTERFEJSU, html=True), name="interfejs")

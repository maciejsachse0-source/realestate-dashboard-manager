"""Punkt wejscia aplikacji."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from najem.api.v1 import router as router_v1
from najem.config import KATALOG_REPO, ustawienia

app = FastAPI(
    title="System Zarzadzania Umowami Najmu",
    version="0.1.0",
    description="Wewnetrzna aplikacja on-prem. Rejestr stanu umow najmu.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

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

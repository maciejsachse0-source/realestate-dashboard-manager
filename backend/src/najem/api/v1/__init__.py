"""Wersja 1 API. Prefiks /api/v1 od poczatku (plan, sekcja 1.3)."""

from fastapi import APIRouter

from najem.api.v1 import zdarzenia, zdrowie

router = APIRouter(prefix="/api/v1")
router.include_router(zdrowie.router)
router.include_router(zdarzenia.router)

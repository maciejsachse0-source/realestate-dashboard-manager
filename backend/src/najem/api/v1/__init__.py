"""Wersja 1 API. Prefiks /api/v1 od poczatku (plan, sekcja 1.3)."""

from fastapi import APIRouter

from najem.api.v1 import (
    auth,
    dashboard,
    dokumenty,
    import_danych,
    kartoteka,
    umowy,
    waloryzacja,
    zdarzenia,
    zdrowie,
)

router = APIRouter(prefix="/api/v1")
router.include_router(zdrowie.router)
router.include_router(auth.router)
router.include_router(kartoteka.router)
router.include_router(dashboard.router)
router.include_router(umowy.router)
router.include_router(dokumenty.router)
router.include_router(import_danych.router)
router.include_router(waloryzacja.router)
router.include_router(zdarzenia.router)

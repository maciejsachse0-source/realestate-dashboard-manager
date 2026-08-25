"""Harmonogram zadan cyklicznych.

Generator zdarzen chodzi raz na dobe o 6:00 czasu lokalnego, zeby alerty czekaly
na pracownika, gdy przychodzi rano do pracy.

APScheduler w procesie aplikacji wystarcza: zadanie jest jedno, trwa sekundy
i jest idempotentne, wiec pominiety albo powtorzony przebieg niczego nie psuje.
Osobny worker wchodzi dopiero z przetwarzaniem dokumentow w etapie E9.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from najem.baza import TworzSesje
from najem.config import ustawienia
from najem.uslugi.generator_zdarzen import uruchom_generator

log = structlog.get_logger(__name__)

#: O ktorej godzinie czasu lokalnego rusza generator.
GODZINA_GENERATORA = 6

_harmonogram: BackgroundScheduler | None = None


def dzis_lokalnie() -> date:
    """Dzisiejsza data w strefie prezentacji.

    W bazie i w logice trzymamy UTC, ale "dzis" dla alertow to dzis w Warszawie.
    O drugiej w nocy czasu polskiego UTC pokazuje jeszcze dzien poprzedni,
    a alert o wygasajacej dzis polisie musi dotyczyc polskiego dnia.
    """
    strefa = ZoneInfo(ustawienia().strefa_prezentacji)
    return datetime.now(UTC).astimezone(strefa).date()


def przebieg_generatora() -> None:
    """Jedno uruchomienie generatora. Bledy sa logowane, nie wywalaja procesu."""
    dzis = dzis_lokalnie()
    try:
        with TworzSesje() as sesja:
            wynik = uruchom_generator(sesja, dzis)
            sesja.commit()
        log.info(
            "generator_zdarzen_zakonczony",
            data=wynik.data_odniesienia.isoformat(),
            umow=wynik.umow_sprawdzonych,
            wyliczonych=wynik.zdarzen_wyliczonych,
            dodanych=wynik.zdarzen_dodanych,
            pominietych=wynik.zdarzen_pominietych,
        )
    except Exception:
        # Zadanie cykliczne, ktore wywala watek, przestaje chodzic po cichu.
        # Lepiej zalogowac i sprobowac jutro.
        log.exception("generator_zdarzen_blad", data=dzis.isoformat())


def uruchom_harmonogram() -> BackgroundScheduler:
    """Startuje harmonogram. Wolane raz, przy starcie aplikacji."""
    global _harmonogram
    if _harmonogram is not None:
        return _harmonogram

    strefa = ZoneInfo(ustawienia().strefa_prezentacji)
    harmonogram = BackgroundScheduler(timezone=strefa)
    harmonogram.add_job(
        przebieg_generatora,
        trigger=CronTrigger(hour=GODZINA_GENERATORA, minute=0, timezone=strefa),
        id="generator_zdarzen",
        name="Generator zdarzeń terminowych",
        # Po przestoju maszyny nadrabiamy jeden przebieg, a nie wszystkie zalegle.
        # Zadanie jest idempotentne, wiec jeden przebieg wystarczy.
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600 * 6,
    )
    harmonogram.start()
    _harmonogram = harmonogram
    log.info("harmonogram_uruchomiony", godzina=GODZINA_GENERATORA, strefa=str(strefa))
    return harmonogram


def zatrzymaj_harmonogram() -> None:
    global _harmonogram
    if _harmonogram is not None:
        _harmonogram.shutdown(wait=False)
        _harmonogram = None
        log.info("harmonogram_zatrzymany")

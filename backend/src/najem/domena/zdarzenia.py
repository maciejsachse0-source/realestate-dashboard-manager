"""Generator zdarzen terminowych. Katalog z sekcji 6 koncepcji.

Czysta funkcja: dostaje zdjecie stanu umowy i date odniesienia, zwraca liste
zdarzen do wygenerowania. Nie zna bazy, nie zna dzisiejszej daty, niczego
nie zapisuje.

Kluczowa decyzja projektowa: `data_zdarzenia` to data, KTOREJ zdarzenie DOTYCZY,
a nie dzien, w ktorym generator sie uruchomil. Umowa konczaca sie 31.01.2028
ma zdarzenie "90 dni do konca" z data 02.11.2027, niezaleznie od tego, czy
generator odpali sie tego dnia, czy tydzien pozniej.

Bez tego klucz naturalny (typ, encja, data) nie dawalby idempotencji: kazdy
kolejny dzien tworzylby nowe zdarzenie o tej samej tresci i kokpit terminow
zamienilby sie w listę duplikatow.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from najem.domena.pieniadze import Kwota
from najem.domena.reguly.zabezpieczenia import (
    PROG_OSTRZEZENIA_POLISA_DNI,
    czy_polisa_ponizej_wymaganej,
)
from najem.domena.slowniki import (
    RodzajZabezpieczenia,
    StatusOkresuNajmu,
    StatusZabezpieczenia,
    TypZdarzenia,
    WagaZdarzenia,
)

#: Progi ostrzegania o koncu umowy i waga kazdego z nich.
#: Katalog mowi "ostrzezenie, rosnaca", wiec waga rosnie wraz ze zblizaniem sie terminu.
PROGI_KONCA_UMOWY: tuple[tuple[int, WagaZdarzenia], ...] = (
    (180, WagaZdarzenia.INFORMACJA),
    (90, WagaZdarzenia.OSTRZEZENIE),
    (60, WagaZdarzenia.OSTRZEZENIE),
    (30, WagaZdarzenia.KRYTYCZNE),
)

#: Ile dni przed miesiacem waloryzacji przypominamy.
PROG_WALORYZACJI_DNI = 30

#: Po ilu dniach od startu umowy brak protokolu przekazania staje sie problemem.
PROG_BRAKU_PROTOKOLU_DNI = 14

#: Ile dni przed terminem przypominamy o przegladzie.
PROG_PRZEGLADU_DNI = 30

#: Statusy okresu najmu, dla ktorych generujemy zdarzenia terminowe.
#: Umowa zakonczona nie potrzebuje juz ostrzezen o zblizajacym sie koncu.
STATUSY_CZYNNE: frozenset[StatusOkresuNajmu] = frozenset(
    {
        StatusOkresuNajmu.PRZYGOTOWANIE,
        StatusOkresuNajmu.AKTYWNA,
        StatusOkresuNajmu.WYPOWIEDZIANA,
    }
)


@dataclass(frozen=True)
class ProponowaneZdarzenie:
    """Zdarzenie do zapisania. Klucz naturalny to (typ, encja_typ, encja_id, data)."""

    typ: TypZdarzenia
    encja_typ: str
    encja_id: int
    data_zdarzenia: date
    waga: WagaZdarzenia
    tresc: str
    lokal_id: int | None = None

    @property
    def klucz_naturalny(self) -> tuple[str, str, int, date]:
        return (self.typ.value, self.encja_typ, self.encja_id, self.data_zdarzenia)


@dataclass(frozen=True)
class StanZabezpieczenia:
    zabezpieczenie_id: int
    rodzaj: RodzajZabezpieczenia
    status: StatusZabezpieczenia
    data_wymagalnosci: date | None = None
    data_waznosci: date | None = None
    suma_ubezpieczenia: Kwota | None = None
    wymagana_kwota: Kwota | None = None


@dataclass(frozen=True)
class StanPrzegladu:
    obowiazek_id: int
    element: str
    nastepny_termin: date | None = None


@dataclass(frozen=True)
class StanUmowy:
    """Zdjecie stanu jednej umowy, wystarczajace do wygenerowania zdarzen.

    Warstwa uslug sklada to z bazy i ze stanu efektywnego parametrow.
    """

    okres_najmu_id: int
    lokal_id: int
    oznaczenie_lokalu: str
    status: StatusOkresuNajmu

    data_rozpoczecia: date | None = None
    data_przekazania: date | None = None
    data_zakonczenia: date | None = None
    termin_wypowiedzenia: date | None = None
    ma_nastepczy_okres: bool = False

    waloryzacja_podlega: bool = False
    waloryzacja_miesiac: int | None = None

    profil_kompletny: bool = True
    brakujace_pola: tuple[str, ...] = field(default_factory=tuple)

    zabezpieczenia: tuple[StanZabezpieczenia, ...] = field(default_factory=tuple)
    przeglady: tuple[StanPrzegladu, ...] = field(default_factory=tuple)


def kotwica_miesieczna(dzis: date) -> date:
    """Data odniesienia dla stanow trwalych, np. niekompletnego profilu.

    Stan trwaly nie ma naturalnej daty. Gdyby uzyc dzisiejszej, generator
    tworzylby nowe zdarzenie kazdego dnia. Kotwiczenie na pierwszym dniu
    miesiaca sprawia, ze przypomnienie wraca raz w miesiacu, dopoki stan trwa.
    """
    return date(dzis.year, dzis.month, 1)


def najblizszy_miesiac(miesiac: int, dzis: date) -> date:
    """Pierwszy dzien najblizszego wystapienia podanego miesiaca, liczac od dzis."""
    w_tym_roku = date(dzis.year, miesiac, 1)
    if w_tym_roku >= dzis:
        return w_tym_roku
    return date(dzis.year + 1, miesiac, 1)


def _koniec_umowy(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    if stan.data_zakonczenia is None:
        return []

    zdarzenia: list[ProponowaneZdarzenie] = []
    for dni, waga in PROGI_KONCA_UMOWY:
        wyzwalacz = stan.data_zakonczenia - timedelta(days=dni)
        # Prog juz minal, ale umowa jeszcze trwa: zdarzenie ma prawo powstac
        # takze wtedy, gdy generator nie chodzil przez kilka dni.
        if wyzwalacz <= dzis <= stan.data_zakonczenia:
            zdarzenia.append(
                ProponowaneZdarzenie(
                    typ=TypZdarzenia.KONIEC_UMOWY_SIE_ZBLIZA,
                    encja_typ="okres_najmu",
                    encja_id=stan.okres_najmu_id,
                    lokal_id=stan.lokal_id,
                    data_zdarzenia=wyzwalacz,
                    waga=waga,
                    tresc=(
                        f"Umowa w lokalu {stan.oznaczenie_lokalu} kończy się za {dni} dni "
                        f"({stan.data_zakonczenia.isoformat()})."
                    ),
                )
            )
    return zdarzenia


def _wypowiedzenie(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    if stan.termin_wypowiedzenia is None or stan.status is not StatusOkresuNajmu.AKTYWNA:
        return []
    if dzis <= stan.termin_wypowiedzenia:
        return []

    return [
        ProponowaneZdarzenie(
            typ=TypZdarzenia.MINAL_TERMIN_WYPOWIEDZENIA,
            encja_typ="okres_najmu",
            encja_id=stan.okres_najmu_id,
            lokal_id=stan.lokal_id,
            data_zdarzenia=stan.termin_wypowiedzenia + timedelta(days=1),
            waga=WagaZdarzenia.KRYTYCZNE,
            tresc=(
                f"Minął termin wypowiedzenia umowy w lokalu {stan.oznaczenie_lokalu} "
                f"({stan.termin_wypowiedzenia.isoformat()}) bez decyzji."
            ),
        )
    ]


def _wygasniecie(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    if stan.data_zakonczenia is None or stan.ma_nastepczy_okres:
        return []
    dzien_po = stan.data_zakonczenia + timedelta(days=1)
    if dzis < dzien_po:
        return []

    return [
        ProponowaneZdarzenie(
            typ=TypZdarzenia.UMOWA_WYGASLA_BRAK_NASTEPCZEJ,
            encja_typ="okres_najmu",
            encja_id=stan.okres_najmu_id,
            lokal_id=stan.lokal_id,
            data_zdarzenia=dzien_po,
            waga=WagaZdarzenia.KRYTYCZNE,
            tresc=(
                f"Umowa w lokalu {stan.oznaczenie_lokalu} wygasła "
                f"{stan.data_zakonczenia.isoformat()} i nie ma umowy następczej."
            ),
        )
    ]


def _waloryzacja(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    if not stan.waloryzacja_podlega or stan.waloryzacja_miesiac is None:
        return []

    poczatek = najblizszy_miesiac(stan.waloryzacja_miesiac, dzis)
    wyzwalacz = poczatek - timedelta(days=PROG_WALORYZACJI_DNI)
    if dzis < wyzwalacz:
        return []

    return [
        ProponowaneZdarzenie(
            typ=TypZdarzenia.WALORYZACJA_SIE_ZBLIZA,
            encja_typ="okres_najmu",
            encja_id=stan.okres_najmu_id,
            lokal_id=stan.lokal_id,
            data_zdarzenia=wyzwalacz,
            waga=WagaZdarzenia.INFORMACJA,
            tresc=(
                f"Waloryzacja umowy w lokalu {stan.oznaczenie_lokalu} przypada "
                f"{poczatek.isoformat()}."
            ),
        )
    ]


def _brak_protokolu(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    if stan.data_przekazania is not None or stan.data_rozpoczecia is None:
        return []
    wyzwalacz = stan.data_rozpoczecia + timedelta(days=PROG_BRAKU_PROTOKOLU_DNI)
    if dzis < wyzwalacz:
        return []

    return [
        ProponowaneZdarzenie(
            typ=TypZdarzenia.BRAK_PROTOKOLU_PRZEKAZANIA,
            encja_typ="okres_najmu",
            encja_id=stan.okres_najmu_id,
            lokal_id=stan.lokal_id,
            data_zdarzenia=wyzwalacz,
            waga=WagaZdarzenia.OSTRZEZENIE,
            tresc=(
                f"Brak protokołu przekazania lokalu {stan.oznaczenie_lokalu} "
                f"{PROG_BRAKU_PROTOKOLU_DNI} dni po rozpoczęciu umowy. "
                "Bez niego data zakończenia pozostaje nieustalona."
            ),
        )
    ]


def _niekompletny_profil(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    if stan.profil_kompletny:
        return []

    braki = ", ".join(sorted(stan.brakujace_pola)) if stan.brakujace_pola else "dane krytyczne"
    return [
        ProponowaneZdarzenie(
            typ=TypZdarzenia.PROFIL_NIEKOMPLETNY,
            encja_typ="okres_najmu",
            encja_id=stan.okres_najmu_id,
            lokal_id=stan.lokal_id,
            data_zdarzenia=kotwica_miesieczna(dzis),
            waga=WagaZdarzenia.INFORMACJA,
            tresc=f"Profil lokalu {stan.oznaczenie_lokalu} jest niekompletny. Brakuje: {braki}.",
        )
    ]


def _zabezpieczenia(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    zdarzenia: list[ProponowaneZdarzenie] = []

    for zab in stan.zabezpieczenia:
        dostarczone = zab.status in {
            StatusZabezpieczenia.DOSTARCZONE,
            StatusZabezpieczenia.ZWROCONE,
            StatusZabezpieczenia.ZATRZYMANE,
        }

        # Zaleglosc: termin minal, a zabezpieczenia nadal nie ma.
        if not dostarczone and zab.data_wymagalnosci is not None and dzis > zab.data_wymagalnosci:
            typ = (
                TypZdarzenia.KAUCJA_NIEWPLACONA
                if zab.rodzaj is RodzajZabezpieczenia.KAUCJA
                else TypZdarzenia.POLISA_NIEDOSTARCZONA
            )
            zdarzenia.append(
                ProponowaneZdarzenie(
                    typ=typ,
                    encja_typ="zabezpieczenie",
                    encja_id=zab.zabezpieczenie_id,
                    lokal_id=stan.lokal_id,
                    data_zdarzenia=zab.data_wymagalnosci + timedelta(days=1),
                    waga=WagaZdarzenia.KRYTYCZNE,
                    tresc=(
                        f"{zab.rodzaj.value.capitalize()} w lokalu {stan.oznaczenie_lokalu} "
                        f"nie została dostarczona w terminie "
                        f"({zab.data_wymagalnosci.isoformat()})."
                    ),
                )
            )

        # Kaucja do zwrotu po zakonczeniu najmu.
        if (
            zab.rodzaj is RodzajZabezpieczenia.KAUCJA
            and zab.status is StatusZabezpieczenia.DOSTARCZONE
            and stan.status is StatusOkresuNajmu.ZAKONCZONA
            and stan.data_zakonczenia is not None
            and dzis > stan.data_zakonczenia
        ):
            zdarzenia.append(
                ProponowaneZdarzenie(
                    typ=TypZdarzenia.KAUCJA_DO_ZWROTU,
                    encja_typ="zabezpieczenie",
                    encja_id=zab.zabezpieczenie_id,
                    lokal_id=stan.lokal_id,
                    data_zdarzenia=stan.data_zakonczenia + timedelta(days=1),
                    waga=WagaZdarzenia.OSTRZEZENIE,
                    tresc=(
                        f"Kaucja z lokalu {stan.oznaczenie_lokalu} czeka na rozliczenie "
                        "po zakończeniu najmu."
                    ),
                )
            )

        if zab.rodzaj is not RodzajZabezpieczenia.POLISA:
            continue

        # Polisa wygasa. Warunek celowo nie obejmuje polis juz wygaslych:
        # to inne zdarzenie i inna waga.
        if zab.data_waznosci is not None and dzis <= zab.data_waznosci:
            wyzwalacz = zab.data_waznosci - timedelta(days=PROG_OSTRZEZENIA_POLISA_DNI)
            if dzis >= wyzwalacz:
                zdarzenia.append(
                    ProponowaneZdarzenie(
                        typ=TypZdarzenia.POLISA_WYGASA,
                        encja_typ="zabezpieczenie",
                        encja_id=zab.zabezpieczenie_id,
                        lokal_id=stan.lokal_id,
                        data_zdarzenia=wyzwalacz,
                        waga=WagaZdarzenia.OSTRZEZENIE,
                        tresc=(
                            f"Polisa w lokalu {stan.oznaczenie_lokalu} wygasa "
                            f"{zab.data_waznosci.isoformat()}."
                        ),
                    )
                )

        # Polisa na kwote nizsza niz wymagana. Stan trwaly, wiec kotwica miesieczna.
        ocena = czy_polisa_ponizej_wymaganej(
            suma_ubezpieczenia=zab.suma_ubezpieczenia,
            wymagana_kwota=zab.wymagana_kwota,
        )
        if ocena.ustalone and ocena.wymagaj():
            zdarzenia.append(
                ProponowaneZdarzenie(
                    typ=TypZdarzenia.POLISA_PONIZEJ_KWOTY,
                    encja_typ="zabezpieczenie",
                    encja_id=zab.zabezpieczenie_id,
                    lokal_id=stan.lokal_id,
                    data_zdarzenia=kotwica_miesieczna(dzis),
                    waga=WagaZdarzenia.OSTRZEZENIE,
                    tresc=(
                        f"Polisa w lokalu {stan.oznaczenie_lokalu} opiewa na kwotę niższą "
                        "niż wymagana umową."
                    ),
                )
            )

    return zdarzenia


def _przeglady(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    zdarzenia: list[ProponowaneZdarzenie] = []

    for przeglad in stan.przeglady:
        if przeglad.nastepny_termin is None:
            continue

        if dzis > przeglad.nastepny_termin:
            zdarzenia.append(
                ProponowaneZdarzenie(
                    typ=TypZdarzenia.PRZEGLAD_PRZETERMINOWANY,
                    encja_typ="obowiazek_przegladu",
                    encja_id=przeglad.obowiazek_id,
                    lokal_id=stan.lokal_id,
                    data_zdarzenia=przeglad.nastepny_termin + timedelta(days=1),
                    waga=WagaZdarzenia.KRYTYCZNE,
                    tresc=(
                        f"Przegląd: {przeglad.element}, lokal {stan.oznaczenie_lokalu}. "
                        f"Termin minął {przeglad.nastepny_termin.isoformat()}."
                    ),
                )
            )
            continue

        wyzwalacz = przeglad.nastepny_termin - timedelta(days=PROG_PRZEGLADU_DNI)
        if dzis >= wyzwalacz:
            zdarzenia.append(
                ProponowaneZdarzenie(
                    typ=TypZdarzenia.PRZEGLAD_SIE_ZBLIZA,
                    encja_typ="obowiazek_przegladu",
                    encja_id=przeglad.obowiazek_id,
                    lokal_id=stan.lokal_id,
                    data_zdarzenia=wyzwalacz,
                    waga=WagaZdarzenia.OSTRZEZENIE,
                    tresc=(
                        f"Przegląd: {przeglad.element}, lokal {stan.oznaczenie_lokalu}. "
                        f"Termin {przeglad.nastepny_termin.isoformat()}."
                    ),
                )
            )

    return zdarzenia


def zdarzenia_dla_umowy(stan: StanUmowy, dzis: date) -> list[ProponowaneZdarzenie]:
    """Wszystkie zdarzenia, ktore powinny istniec dla tej umowy na dany dzien.

    Funkcja jest deterministyczna i idempotentna: dwa wywolania z tymi samymi
    argumentami daja identyczna liste. Odsianie tych, ktore juz sa w bazie,
    nalezy do warstwy uslug i opiera sie na kluczu naturalnym.
    """
    zdarzenia: list[ProponowaneZdarzenie] = []

    # Zabezpieczenia po zakonczonej umowie nadal wymagaja rozliczenia,
    # wiec ta grupa liczy sie takze poza statusami czynnymi.
    zdarzenia.extend(_zabezpieczenia(stan, dzis))

    if stan.status in STATUSY_CZYNNE:
        zdarzenia.extend(_koniec_umowy(stan, dzis))
        zdarzenia.extend(_wypowiedzenie(stan, dzis))
        zdarzenia.extend(_wygasniecie(stan, dzis))
        zdarzenia.extend(_waloryzacja(stan, dzis))
        zdarzenia.extend(_brak_protokolu(stan, dzis))
        zdarzenia.extend(_niekompletny_profil(stan, dzis))
        zdarzenia.extend(_przeglady(stan, dzis))

    return zdarzenia


def zdarzenia_dla_portfela(
    stany: list[StanUmowy],
    dzis: date,
) -> list[ProponowaneZdarzenie]:
    """Zdarzenia dla wszystkich umow, bez duplikatow klucza naturalnego."""
    widziane: set[tuple[str, str, int, date]] = set()
    wynik: list[ProponowaneZdarzenie] = []

    for stan in stany:
        for zdarzenie in zdarzenia_dla_umowy(stan, dzis):
            if zdarzenie.klucz_naturalny in widziane:
                continue
            widziane.add(zdarzenie.klucz_naturalny)
            wynik.append(zdarzenie)

    return wynik

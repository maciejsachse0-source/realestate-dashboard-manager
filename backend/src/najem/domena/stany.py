"""Maszyny stanow. Plan budowy, sekcja 1.1 punkt F.

Status nie jest polem tekstowym, tylko zbiorem stanow i dozwolonych przejsc
wymuszonym w kodzie. Bez tego po pol roku w bazie beda umowy jednoczesnie
zakonczone i aktywne.

Wszystko tutaj to czyste funkcje: bez bazy, bez daty biezacej, bez I/O.
"""

from collections.abc import Mapping

from najem.domena.slowniki import (
    StatusLokalu,
    StatusOkresuNajmu,
    StatusZabezpieczenia,
    StatusZdarzenia,
)


class NiedozwolonePrzejscie(Exception):
    """Proba zmiany statusu na taki, ktory nie wynika z biezacego."""

    def __init__(self, z_stanu: str, do_stanu: str, dozwolone: frozenset[str]) -> None:
        self.z_stanu = z_stanu
        self.do_stanu = do_stanu
        self.dozwolone = dozwolone
        czytelne = ", ".join(sorted(dozwolone)) if dozwolone else "brak (stan koncowy)"
        super().__init__(
            f"Nie można przejść ze stanu '{z_stanu}' do '{do_stanu}'. Dozwolone: {czytelne}."
        )


# Okres najmu. Regula R8 opisuje sciezke zmiany najemcy:
# aktywna -> zakonczona, a nowy najemca to nowy okres najmu, nie zmiana tego.
PRZEJSCIA_OKRESU_NAJMU: Mapping[StatusOkresuNajmu, frozenset[StatusOkresuNajmu]] = {
    StatusOkresuNajmu.PRZYGOTOWANIE: frozenset(
        {StatusOkresuNajmu.AKTYWNA, StatusOkresuNajmu.ZAKONCZONA}
    ),
    StatusOkresuNajmu.AKTYWNA: frozenset(
        {StatusOkresuNajmu.WYPOWIEDZIANA, StatusOkresuNajmu.ZAKONCZONA}
    ),
    # Wypowiedziana umowa nadal trwa do konca okresu wypowiedzenia. Powrot do
    # stanu aktywnego jest mozliwy, bo wypowiedzenie bywa cofane za zgoda stron.
    StatusOkresuNajmu.WYPOWIEDZIANA: frozenset(
        {StatusOkresuNajmu.ZAKONCZONA, StatusOkresuNajmu.AKTYWNA}
    ),
    # Stan koncowy. Pomylke prostuje sie nowym okresem najmu, nie cofnieciem.
    StatusOkresuNajmu.ZAKONCZONA: frozenset(),
}

PRZEJSCIA_LOKALU: Mapping[StatusLokalu, frozenset[StatusLokalu]] = {
    StatusLokalu.WOLNY: frozenset({StatusLokalu.WYNAJETY}),
    StatusLokalu.WYNAJETY: frozenset({StatusLokalu.W_TRAKCIE_WYDANIA, StatusLokalu.WOLNY}),
    StatusLokalu.W_TRAKCIE_WYDANIA: frozenset({StatusLokalu.WOLNY, StatusLokalu.WYNAJETY}),
}

# Regula R4: wymagane -> dostarczone -> zwrocone albo zatrzymane.
PRZEJSCIA_ZABEZPIECZENIA: Mapping[StatusZabezpieczenia, frozenset[StatusZabezpieczenia]] = {
    StatusZabezpieczenia.BRAK: frozenset({StatusZabezpieczenia.WYMAGANE}),
    StatusZabezpieczenia.WYMAGANE: frozenset(
        {StatusZabezpieczenia.DOSTARCZONE, StatusZabezpieczenia.BRAK}
    ),
    StatusZabezpieczenia.DOSTARCZONE: frozenset(
        {StatusZabezpieczenia.ZWROCONE, StatusZabezpieczenia.ZATRZYMANE}
    ),
    # Zwrot i zatrzymanie sa odwracalne, bo to jeden klik od pomylki, a kaucja
    # zwrocona omylkowo znikala z widoku bez sposobu na cofniecie. Powrot idzie
    # do stanu "dostarczone", czyli tam, skad przejscie wyszlo. Slad zostaje
    # w audycie.
    StatusZabezpieczenia.ZWROCONE: frozenset({StatusZabezpieczenia.DOSTARCZONE}),
    StatusZabezpieczenia.ZATRZYMANE: frozenset({StatusZabezpieczenia.DOSTARCZONE}),
}

# Zdarzenie odroczone wraca do otwartych, gdy minie termin odroczenia.
PRZEJSCIA_ZDARZENIA: Mapping[StatusZdarzenia, frozenset[StatusZdarzenia]] = {
    StatusZdarzenia.OTWARTE: frozenset({StatusZdarzenia.OBSLUZONE, StatusZdarzenia.ODROCZONE}),
    StatusZdarzenia.ODROCZONE: frozenset({StatusZdarzenia.OTWARTE, StatusZdarzenia.OBSLUZONE}),
    StatusZdarzenia.OBSLUZONE: frozenset({StatusZdarzenia.OTWARTE}),
}


def czy_przejscie_dozwolone[S](
    mapa: Mapping[S, frozenset[S]],
    z_stanu: S,
    do_stanu: S,
) -> bool:
    """Czy zmiana stanu jest dozwolona. Pozostanie w tym samym stanie jest zawsze OK."""
    if z_stanu == do_stanu:
        return True
    return do_stanu in mapa.get(z_stanu, frozenset())


def sprawdz_przejscie[S](
    mapa: Mapping[S, frozenset[S]],
    z_stanu: S,
    do_stanu: S,
) -> None:
    """Jak wyzej, ale rzuca wyjatkiem z czytelnym komunikatem po polsku."""
    if not czy_przejscie_dozwolone(mapa, z_stanu, do_stanu):
        raise NiedozwolonePrzejscie(
            str(z_stanu),
            str(do_stanu),
            frozenset(str(s) for s in mapa.get(z_stanu, frozenset())),
        )


def stany_koncowe[S](mapa: Mapping[S, frozenset[S]]) -> frozenset[S]:
    """Stany, z ktorych nie ma wyjscia."""
    return frozenset(stan for stan, dalej in mapa.items() if not dalej)

"""Wspolny ksztalt wyniku reguly biznesowej.

Regula nigdy nie zwraca samej liczby. Zwraca strukture, z ktorej widac takze,
dlaczego wynik jest taki, a jesli go nie ma, to dlaczego go nie ma.

To bezposrednio realizuje decyzje D5: brak danych jest informacja, nie pusta
komorka. "Nieustalona" z powodem to uzyteczna odpowiedz, ktora da sie pokazac
uzytkownikowi i z ktorej da sie wygenerowac zadanie.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Wynik[T]:
    """Wynik reguly wraz z uzasadnieniem.

    Albo `wartosc` jest ustalona, albo `powod_braku` mowi, czego zabraklo.
    Nigdy oba naraz i nigdy zadne z nich.
    """

    wartosc: T | None = None
    powod_braku: str | None = None
    wyjasnienie: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (self.wartosc is None) == (self.powod_braku is None):
            raise ValueError(
                "Wynik musi mieć albo wartość, albo powód jej braku. "
                f"Otrzymano wartość={self.wartosc!r}, powód={self.powod_braku!r}."
            )

    @property
    def ustalone(self) -> bool:
        return self.wartosc is not None

    def wymagaj(self) -> T:
        """Wartosc albo wyjatek. Do uzycia tam, gdzie brak jest naprawde bledem."""
        if self.wartosc is None:
            raise ValueError(self.powod_braku or "Wartość nieustalona.")
        return self.wartosc


def ustalony[T](wartosc: T, *wyjasnienie: str) -> Wynik[T]:
    return Wynik(wartosc=wartosc, wyjasnienie=tuple(wyjasnienie))


def nieustalony[T](powod: str, *wyjasnienie: str) -> Wynik[T]:
    return Wynik(powod_braku=powod, wyjasnienie=tuple(wyjasnienie))

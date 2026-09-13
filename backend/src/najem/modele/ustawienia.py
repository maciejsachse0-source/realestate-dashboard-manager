"""Ustawienia systemu zmieniane z interfejsu, a nie z pliku .env.

Plik .env jest dobry dla adresu bazy: ustawia go raz osoba, ktora program
instaluje. Zla dla katalogu z dokumentami: to decyzja uzytkownika, ktora
potrafi sie zmienic, a wymaganie edycji pliku tekstowego od kogos, kto ma
obslugiwac umowy, jest przerzucaniem na niego pracy administratora.

Wartosci trzymamy jako tekst i interpretujemy w warstwie uslug. Tabela jest
celowo prosta -- nie jest to poczatek "systemu konfiguracji", tylko miejsce
na kilka ustawien, ktore musi dac sie zmienic bez restartu programu.
"""

from sqlalchemy import Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from najem.baza import Baza
from najem.modele.wspolne import KluczGlowny, MiekkieUsuwanie, Wersjonowanie, ZnacznikiCzasu

#: Katalog z dokumentami uzytkownika przeszukiwany przez ekran "Dokumenty z dysku".
KLUCZ_KATALOG_SKANU = "katalog_skanu"


class UstawienieSystemu(Baza, ZnacznikiCzasu, MiekkieUsuwanie, Wersjonowanie):
    """Jedno ustawienie: klucz, wartosc, kto ja ostatnio zmienil."""

    __tablename__ = "ustawienie_systemu"

    id: Mapped[KluczGlowny]
    klucz: Mapped[str] = mapped_column(String(80), nullable=False)
    #: NULL znaczy "wyczyszczone", czyli wracamy do wartosci z .env.
    #: To nie to samo, co brak wiersza, i oba stany sa poprawne.
    wartosc: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (
        Index(
            "uq_ustawienie_klucz",
            "klucz",
            unique=True,
            postgresql_where=text("usunieto_dnia IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<UstawienieSystemu {self.klucz!r}>"

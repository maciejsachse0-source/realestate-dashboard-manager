"""Haszowanie i weryfikacja hasel.

Argon2id, zgodnie z punktem K planu budowy. Parametry z domyslnych ustawien
biblioteki argon2-cffi, ktore odpowiadaja rekomendacjom OWASP.
"""

import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

#: Jedna instancja na proces. Trzyma parametry kosztu.
_haszer = PasswordHasher()

#: Minimalna dlugosc hasla. Aplikacja jest wewnetrzna, za logowaniem imiennym,
#: wiec stawiamy na dlugosc zamiast na wymuszanie znakow specjalnych, ktore
#: w praktyce konczy sie haslem zapisanym na karteczce.
MINIMALNA_DLUGOSC = 12


class SlabeHaslo(Exception):
    """Haslo nie spelnia minimalnych wymagan."""


def zahaszuj(haslo: str) -> str:
    sprawdz_sile(haslo)
    return _haszer.hash(haslo)


def sprawdz_sile(haslo: str) -> None:
    if len(haslo) < MINIMALNA_DLUGOSC:
        raise SlabeHaslo(f"Hasło musi mieć co najmniej {MINIMALNA_DLUGOSC} znaków.")
    if haslo.strip() != haslo:
        raise SlabeHaslo("Hasło nie może zaczynać się ani kończyć spacją.")


def zweryfikuj(hash_hasla: str | None, haslo: str) -> bool:
    """Czy haslo pasuje do skrotu.

    Dla uzytkownika bez ustawionego hasla i tak liczymy skrot na wartosci
    zastepczej. Bez tego czas odpowiedzi zdradzalby, ktore loginy istnieja.
    """
    if hash_hasla is None:
        _haszer.hash(haslo)
        return False
    try:
        return _haszer.verify(hash_hasla, haslo)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def wymaga_przehaszowania(hash_hasla: str) -> bool:
    """Czy skrot powstal przy slabszych parametrach niz obecne."""
    try:
        return _haszer.check_needs_rehash(hash_hasla)
    except InvalidHashError:
        return True


def wygeneruj_haslo(dlugosc: int = 16) -> str:
    """Haslo poczatkowe dla nowego konta. Uzytkownik zmienia je przy pierwszym logowaniu."""
    alfabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabet) for _ in range(dlugosc))

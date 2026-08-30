"""Ekstrakcja danych z tekstu dokumentu (etap E9).

Cały ten podpakiet jest czystym Pythonem: wejściem jest napis, wyjściem
propozycja wartości wraz z uzasadnieniem i pozycją w tekście. Zero I/O,
zero bazy, zero bibliotek do czytania PDF-ów — te mieszkają w `dokumenty/`
i podają tutaj gotowy tekst.

Granica jest celowa. Wzorce będą się zmieniać co tydzień przez pierwsze pół
roku pracy na realnym archiwum, więc muszą dać się testować na napisie,
w milisekundach, bez pliku i bez uruchomionej bazy.

Plan etapu: `docs/plan-e9-ekstrakcja.md`.
"""

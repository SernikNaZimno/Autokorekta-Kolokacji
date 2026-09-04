"""Testy filtra slownikowego opartego na Morfeuszu."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.slownik import WalidatorSlownikowy  # noqa: E402


@pytest.fixture(scope="module")
def walidator():
    return WalidatorSlownikowy()


@pytest.mark.parametrize(
    "lemat", ["decyzja", "podjąć", "porażka", "koszyk", "zielony", "ubezpieczenie"]
)
def test_prawdziwe_slowa_przechodza(walidator, lemat):
    assert walidator.znane(lemat)


@pytest.mark.parametrize("lemat", ["złdo", "xyzqw", "abcdefgh"])
def test_niesłowa_odrzucone(walidator, lemat):
    """`złdo` to sklejka z „100,00 zł do koszyka" — miala f=18 na probce
    50 tys. tokenow i regula na ksztalcie napisu jej nie lapie."""
    assert not walidator.znane(lemat)


def test_filtruje_trojki_po_obu_lematach(walidator):
    krotki = [
        ("złdo", "nmod:gen", "koszyk", "web"),      # zly head
        ("cena", "nmod:gen", "złdo", "web"),        # zly dep
        ("podjąć", "obj:acc", "decyzja", "wiki"),   # oba dobre
    ]
    assert list(walidator.filtruj(krotki)) == [
        ("podjąć", "obj:acc", "decyzja", "wiki")
    ]


def test_cache_dziala(walidator):
    walidator.znane("decyzja")
    przed = len(walidator._cache)
    for _ in range(50):
        walidator.znane("decyzja")
    assert len(walidator._cache) == przed

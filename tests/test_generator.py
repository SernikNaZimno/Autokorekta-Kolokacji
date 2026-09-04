"""Testy generowania form sugestii."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.generator import GeneratorForm  # noqa: E402


@pytest.fixture(scope="module")
def gen():
    return GeneratorForm()


def test_formy_aglutynacyjne_sa_odfiltrowane(gen):
    """Dla 'ponieść' Morfeusz zwraca 'poniósł' (nagl) i 'poniosł' (agl).
    Ta druga to czlon 'poniosłem', nie samodzielne slowo — podsunieta
    czytelnikowi wyglada jak literowka."""
    teksty = {f.tekst for f in gen.formy("ponieść")}
    assert "poniósł" in teksty
    assert "poniosł" not in teksty


def test_odmiana_czasownika_do_formy_wzorcowej(gen):
    """*odniósł -> doznał: ta sama osoba, liczba, rodzaj i czas."""
    f = gen.odmien_jak("doznać", "odniósł")
    assert f is not None and f.tekst == "doznał"


def test_odmiana_zachowuje_rodzaj_zenski(gen):
    f = gen.odmien_jak("doznać", "odniosła")
    assert f is not None and f.tekst == "doznała"


def test_odmiana_zachowuje_liczbe_mnoga(gen):
    f = gen.odmien_jak("podjąć", "zrobili")
    assert f is not None and f.tekst == "podjęli"


def test_zmiana_przypadku_rzeczownika(gen):
    """'doznać' rzadzi dopelniaczem, wiec 'porażkę' musi stac sie 'porażki'."""
    f = gen.odmien_jak("porażka", "porażkę", przypadek="gen")
    assert f is not None and f.tekst == "porażki"


def test_zmiana_przypadku_zachowuje_liczbe(gen):
    f = gen.odmien_jak("decyzja", "decyzje", przypadek="gen")
    assert f is not None and f.tekst == "decyzji"


def test_klasa_fleksyjna_musi_sie_zgadzac(gen):
    """Nie podsuwamy bezokolicznika w miejsce formy osobowej."""
    f = gen.odmien_jak("podjąć", "zrobił")
    assert f is not None and f.tekst != "podjąć"


def test_nieznany_lemat_zwraca_none(gen):
    assert gen.odmien_jak("xyzqw", "zrobił") is None


def test_nieznana_forma_wzorcowa_zwraca_none(gen):
    assert gen.odmien_jak("podjąć", "qwerty") is None


def test_pelny_obieg_z_planu(gen):
    """*odniósł porażkę  ->  doznał porażki"""
    czasownik = gen.odmien_jak("doznać", "odniósł")
    rzeczownik = gen.odmien_jak("porażka", "porażkę", przypadek="gen")
    assert f"{czasownik.tekst} {rzeczownik.tekst}" == "doznał porażki"

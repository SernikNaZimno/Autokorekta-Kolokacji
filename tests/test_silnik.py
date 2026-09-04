"""Testy reguly detekcji.

Wiekszosc z nich sprawdza, kiedy silnik ma MILCZEC. To nie jest przesada:
90,9% par kolokacyjnych w korpusie wystepuje raz, wiec narzedzie, ktore chetnie
sie odzywa, bedzie sie mylic na poprawnej polszczyznie. Kazdy falszywy alarm
kosztuje wiecej niz przeoczony blad — po kilku uzytkownik wylacza dodatek.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.baza import BazaKolokacji, zbuduj  # noqa: E402
from backend.ekstraktor import Trojka, z_conllu  # noqa: E402
from backend.generator import GeneratorForm  # noqa: E402
from backend.silnik import SilnikKolokacji  # noqa: E402


def obj(head: str, dep: str, n: int, przypadek: str = "acc") -> list[Trojka]:
    return [Trojka(head, "obj", przypadek, None, dep)] * n


@pytest.fixture(scope="module")
def baza(tmp_path_factory):
    trojki = (
        # 'decyzja' dobrze zbadana: 55 obserwacji w obj:acc
        obj("podjąć", "decyzja", 30)
        + obj("podejmować", "decyzja", 20)
        + obj("przyjąć", "decyzja", 5)
        # 'racja' zbadana i mocno zwiazana z 'mieć' — czasownikiem lekkim
        + obj("mieć", "racja", 60)
        # 'porażka' NIEzbadana: tylko 5 obserwacji
        + obj("ponieść", "porażka", 5)
        # 'klęska' zbadana, rzadzona dopelniaczem przez 'doznać'
        + obj("ponieść", "klęska", 55)
        + obj("doznać", "klęska", 40, przypadek="gen")
        # tlo, zeby profile dystrybucyjne mialy sie na czym oprzec
        + obj("podjąć", "próba", 25)
        + obj("podejmować", "próba", 18)
        + obj("jeść", "obiad", 40)
        + obj("jeść", "kolacja", 30)
    )
    sciezka = tmp_path_factory.mktemp("db") / "test.sqlite"
    zbuduj(trojki, sciezka, min_pary=3)
    with BazaKolokacji(sciezka) as db:
        yield db


@pytest.fixture(scope="module")
def silnik(baza):
    return SilnikKolokacji(baza, generator=GeneratorForm())


def zdanie(forma_czasownika, lemat_czasownika, forma_rzecz, lemat_rzecz, przyp="Acc"):
    return z_conllu(
        f"1\tZarząd\tzarząd\tNOUN\t_\tCase=Nom|Number=Sing\t2\tnsubj\t_\t_\n"
        f"2\t{forma_czasownika}\t{lemat_czasownika}\tVERB\t_\tAspect=Perf\t0\troot\t_\t_\n"
        f"3\t{forma_rzecz}\t{lemat_rzecz}\tNOUN\t_\tCase={przyp}|Number=Sing\t2\tobj\t_\t_\n"
    )


# --- kiedy silnik MA sie odezwac ---------------------------------------------


def test_wykrywa_czasownik_lekki(silnik):
    """*zrobić decyzję -> podjąć. Sztandarowy przypadek."""
    s = silnik.sprawdz(zdanie("zrobił", "zrobić", "decyzję", "decyzja"))
    assert len(s) == 1
    assert s[0].lemat_propozycji == "podjąć"


def test_sugestia_jest_odmieniona(silnik):
    """Propozycja w bezokoliczniku byla by bezuzyteczna w tekscie."""
    s = silnik.sprawdz(zdanie("zrobił", "zrobić", "decyzję", "decyzja"))
    assert s[0].propozycja == "podjął"


def test_sugestia_zachowuje_rodzaj(silnik):
    s = silnik.sprawdz(zdanie("zrobiła", "zrobić", "decyzję", "decyzja"))
    assert s[0].propozycja == "podjęła"


def test_uzasadnienie_podaje_liczby(silnik):
    s = silnik.sprawdz(zdanie("zrobił", "zrobić", "decyzję", "decyzja"))
    assert "podjąć" in s[0].uzasadnienie and "logDice" in s[0].uzasadnienie


# --- kiedy silnik MA milczec -------------------------------------------------


def test_milczy_gdy_slot_niezbadany(silnik):
    """'porażka' ma 5 obserwacji. Nie wiemy o niej nic, wiec sie nie odzywamy —
    nawet jesli para wyglada na rzadka. To warunek trzymajacy precyzje."""
    s = silnik.sprawdz(zdanie("zrobił", "zrobić", "porażkę", "porażka"))
    assert s == []


def test_milczy_gdy_para_dobrze_poswiadczona(silnik):
    """'mieć rację' to poprawna polszczyzna. 'mieć' JEST czasownikiem lekkim,
    ale warunek 2 zatrzymuje alarm wczesniej — dlatego lista czasownikow
    lekkich sama w sobie niczego nie zglasza."""
    s = silnik.sprawdz(zdanie("miał", "mieć", "rację", "racja"))
    assert s == []


def test_milczy_gdy_alternatywa_semantycznie_odlegla(silnik):
    """'jeść' nie jest czasownikiem lekkim i nie dzieli kolokatow z 'podjąć'.
    Bez tego warunku podpowiadalibysmy przy kazdym rzeczowniku po prostu
    najczestszy czasownik."""
    s = silnik.sprawdz(zdanie("jadł", "jeść", "decyzję", "decyzja"))
    assert s == []


def test_milczy_na_poprawnej_kolokacji(silnik):
    s = silnik.sprawdz(zdanie("podjął", "podjąć", "decyzję", "decyzja"))
    assert s == []


def test_milczy_na_poprawnym_wariancie_aspektowym(silnik):
    """'podejmował' to inny aspekt, ale nadal poprawna kolokacja."""
    s = silnik.sprawdz(zdanie("podejmował", "podejmować", "decyzję", "decyzja"))
    assert s == []


def test_milczy_gdy_brak_dopelnienia(silnik):
    tokeny = z_conllu(
        "1\tZarząd\tzarząd\tNOUN\t_\tCase=Nom|Number=Sing\t2\tnsubj\t_\t_\n"
        "2\tobradował\tobradować\tVERB\t_\tAspect=Imp\t0\troot\t_\t_\n"
    )
    assert silnik.sprawdz(tokeny) == []


# --- rzad przypadka ----------------------------------------------------------


def test_rozpoznaje_przypadek_rzadzony(silnik):
    """'doznać' laczy sie z 'klęska' w dopelniaczu, 'ponieść' w bierniku."""
    assert silnik._przypadek_rzadzony("doznać", "klęska") == "gen"
    assert silnik._przypadek_rzadzony("ponieść", "klęska") == "acc"


def test_bez_generatora_zwraca_lemat(baza):
    """Silnik musi dzialac takze bez Morfeusza — do testow i diagnostyki."""
    s = SilnikKolokacji(baza, generator=None).sprawdz(
        zdanie("zrobił", "zrobić", "decyzję", "decyzja")
    )
    assert len(s) == 1 and s[0].propozycja == "podjąć"

"""Testy warstwy bazy — glownie na pulapki kolejnosci operacji."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.baza import BazaKolokacji, zbuduj  # noqa: E402
from backend.ekstraktor import Trojka  # noqa: E402


def t(head: str, dep: str, n: int = 1) -> list[Trojka]:
    return [Trojka(head, "obj", "acc", None, dep)] * n


@pytest.fixture
def baza(tmp_path):
    trojki = (
        t("podjąć", "decyzja", 10)
        + t("podejmować", "decyzja", 6)
        + t("podjąć", "próba", 5)
        + t("podejmować", "próba", 4)
        + t("zrobić", "zdjęcie", 8)
        # pary rzadkie — maja zniknac po przycieciu, ale ZOSTAC w brzegowych
        + t("unieważnić", "decyzja", 1)
        + t("skomentować", "decyzja", 1)
        + t("zignorować", "decyzja", 1)
    )
    sciezka = tmp_path / "test.sqlite"
    zbuduj(trojki, sciezka, min_pary=3)
    with BazaKolokacji(sciezka) as db:
        yield db


def test_przyciecie_usuwa_pary_rzadkie(baza):
    assert baza.logdice("unieważnić", "obj:acc", "decyzja") == 0.0
    assert baza.logdice("podjąć", "obj:acc", "decyzja") > 0


def test_brzegowe_licza_sie_przed_przycieciem(baza):
    """Pulapka: gdyby brzegowe liczyly sie po odrzuceniu rzadkich par,
    mianownik logDice bylby zanizony, a wszystkie wyniki zawyzone."""
    # decyzja jako obj: 10+6+1+1+1 = 19, mimo ze trzy pary wypadly
    assert baza.czestosc_slotu_dep("obj:acc", "decyzja") == 19


def test_logdice_zgodny_ze_wzorem(baza):
    """14 + log2(2*f(xy) / (f(x)+f(y)))."""
    f_xy = 10                                    # podjąć+decyzja
    f_x = baza.czestosc_slotu_head("podjąć", "obj:acc")   # 10+5 = 15
    f_y = baza.czestosc_slotu_dep("obj:acc", "decyzja")   # 19
    oczekiwany = 14 + math.log2(2 * f_xy / (f_x + f_y))
    assert baza.logdice("podjąć", "obj:acc", "decyzja") == pytest.approx(oczekiwany)


def test_nieobecne_daje_zero_a_nie_wyjatek(baza):
    """0.0 znaczy 'nie wiem', nie 'blad' — rozroznienie kluczowe dla silnika."""
    assert baza.logdice("jeść", "obj:acc", "decyzja") == 0.0
    assert baza.czestosc_slotu_dep("obj:acc", "kosmos") == 0


def test_slot_zbadany_respektuje_prog(baza):
    assert baza.slot_zbadany("obj:acc", "decyzja", prog=15)
    assert not baza.slot_zbadany("obj:acc", "decyzja", prog=20)
    assert not baza.slot_zbadany("obj:acc", "zdjęcie", prog=20)


def test_alternatywy_sortowane_malejaco(baza):
    alt = baza.alternatywy("obj:acc", "decyzja")
    assert [k.lemat for k in alt] == ["podjąć", "podejmować"]
    assert alt[0].logdice >= alt[1].logdice


def test_podobienstwo_wykrywa_pare_aspektowa(baza):
    """podjąć i podejmować dziela oba kolokaty — powinny byc bliskie."""
    assert baza.podobienstwo("podjąć", "podejmować", "obj:acc") > 0.9
    assert baza.podobienstwo("podjąć", "zrobić", "obj:acc") == 0.0


def test_baza_jest_tylko_do_odczytu(baza):
    with pytest.raises(Exception):
        baza.con.execute("DELETE FROM pary")

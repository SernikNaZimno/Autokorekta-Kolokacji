"""Testy regul budowy klucza kolokacyjnego.

Fixture'y sa recznie zapisane w CoNLL-U, zeby testy chodzily bez modelu Stanzy
(szybko i deterministycznie). Rozbior zgodny z tym, co Stanza faktycznie zwraca
dla tych zdan — sprawdzone w scripts/spike_stanza.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ekstraktor import Trojka, wyciagnij_trojki, z_conllu  # noqa: E402


def klucze(conllu: str) -> set[str]:
    return {t.klucz() for t in wyciagnij_trojki(z_conllu(conllu))}


# ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC
TWIERDZACE = """\
1\tZarząd\tzarząd\tNOUN\t_\tCase=Nom|Number=Sing\t2\tnsubj\t_\t_
2\tpodjął\tpodjąć\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
3\tdecyzję\tdecyzja\tNOUN\t_\tCase=Acc|Number=Sing\t2\tobj\t_\t_
"""

PRZECZACE = """\
1\tZarząd\tzarząd\tNOUN\t_\tCase=Nom|Number=Sing\t3\tnsubj\t_\t_
2\tnie\tnie\tPART\t_\t_\t3\tadvmod\t_\t_
3\tpodjął\tpodjąć\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
4\tdecyzji\tdecyzja\tNOUN\t_\tCase=Gen|Number=Sing\t3\tobj\t_\t_
"""


def test_dopelniacz_negacji_daje_ten_sam_klucz():
    """„podjął decyzję" i „nie podjął decyzji" to jedna kolokacja.

    Bez normalizacji zliczenia rozdzielaja sie na dwa klucze, oba wychodza
    rzadsze niz sa naprawde i silnik zglasza falszywy alarm na kazdym zdaniu
    przeczacym.
    """
    assert "podjąć|obj|acc|decyzja" in klucze(TWIERDZACE)
    assert "podjąć|obj|acc|decyzja" in klucze(PRZECZACE)


def test_dopelniacz_bez_negacji_zostaje_dopelniaczem():
    """Normalizacja nie moze byc bezwarunkowa — sa czasowniki rzadzace gen."""
    doznal = """\
1\tFirma\tfirma\tNOUN\t_\tCase=Nom|Number=Sing\t2\tnsubj\t_\t_
2\tdoznała\tdoznać\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
3\tporażki\tporażka\tNOUN\t_\tCase=Gen|Number=Sing\t2\tobj\t_\t_
"""
    assert "doznać|obj|gen|porażka" in klucze(doznal)


def test_amod_pomija_przypadek():
    """Przymiotnik tylko uzgadnia sie z rzeczownikiem — przypadek nie niesie
    informacji kolokacyjnej i rozbilby „ważna decyzja" na 7 wpisow."""
    mianownik = """\
1\tważna\tważny\tADJ\t_\tCase=Nom|Number=Sing\t2\tamod\t_\t_
2\tdecyzja\tdecyzja\tNOUN\t_\tCase=Nom|Number=Sing\t0\troot\t_\t_
"""
    biernik = """\
1\tważną\tważny\tADJ\t_\tCase=Acc|Number=Sing\t2\tamod\t_\t_
2\tdecyzję\tdecyzja\tNOUN\t_\tCase=Acc|Number=Sing\t0\troot\t_\t_
"""
    assert klucze(mianownik) == klucze(biernik) == {"decyzja|amod|ważny"}


def test_nsubj_pomija_przypadek():
    assert "podjąć|nsubj|zarząd" in klucze(TWIERDZACE)


def test_obl_zachowuje_przyimek_i_przypadek():
    zdanie = """\
1\tponiosła\tponieść\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
2\tporażkę\tporażka\tNOUN\t_\tCase=Acc|Number=Sing\t1\tobj\t_\t_
3\tna\tna\tADP\t_\t_\t4\tcase\t_\t_
4\trynku\trynek\tNOUN\t_\tCase=Loc|Number=Sing\t1\tobl\t_\t_
"""
    k = klucze(zdanie)
    assert "ponieść|obj|acc|porażka" in k
    assert "ponieść|obl|na|loc|rynek" in k


def test_podtyp_relacji_jest_normalizowany():
    """'obl:arg' i 'nsubj:pass' musza trafic pod relacje bazowa."""
    zdanie = """\
1\tdecyzja\tdecyzja\tNOUN\t_\tCase=Nom|Number=Sing\t2\tnsubj:pass\t_\t_
2\tpodjęta\tpodjąć\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
"""
    assert "podjąć|nsubj|decyzja" in klucze(zdanie)


def test_slowa_funkcyjne_sa_odrzucane():
    """Zaimki, przyimki i interpunkcja nie sa kolokatami."""
    zdanie = """\
1\tOn\ton\tPRON\t_\tCase=Nom|Number=Sing\t2\tnsubj\t_\t_
2\tzrobił\tzrobić\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
3\tto\tto\tPRON\t_\tCase=Acc|Number=Sing\t2\tobj\t_\t_
4\t.\t.\tPUNCT\t_\t_\t2\tpunct\t_\t_
"""
    assert klucze(zdanie) == set()


def test_wielowyrazowce_i_wezly_puste_sa_pomijane():
    """CoNLL-U dopuszcza zakresy '3-4' i wezly '5.1' — nie sa tokenami."""
    zdanie = """\
1\tZarząd\tzarząd\tNOUN\t_\tCase=Nom|Number=Sing\t2\tnsubj\t_\t_
2\tpodjął\tpodjąć\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
3-4\tdecyzję\t_\t_\t_\t_\t_\t_\t_\t_
3\tdecyzję\tdecyzja\tNOUN\t_\tCase=Acc|Number=Sing\t2\tobj\t_\t_
4.1\t_\t_\t_\t_\t_\t_\t_\t_\t_
"""
    assert "podjąć|obj|acc|decyzja" in klucze(zdanie)


def test_klucz_jest_odwracalny_wzgledem_str():
    t = Trojka("ponieść", "obl", "loc", "na", "rynek")
    assert t.klucz() == "ponieść|obl|na|loc|rynek"
    assert str(t) == "ponieść --obl+na:loc--> rynek"

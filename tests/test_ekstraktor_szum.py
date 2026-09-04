"""Testy odsiewania szumu — przypadki z realnego przebiegu na Wikipedii i C4.

Kazdy z nich trafil do bazy podczas przebiegu probnego (scripts/probny_przebieg.py)
i mial wysoka czestosc mimo tylko 50 tys. tokenow. Takie wpisy sa gorsze niz
zwykly szum: wystepuja w jednym powtarzanym szablonie, wiec maja waskie profile
brzegowe i wychodza wysoko w logDice.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ekstraktor import wyciagnij_trojki, z_conllu  # noqa: E402


def klucze(conllu: str) -> set[str]:
    return {t.klucz() for t in wyciagnij_trojki(z_conllu(conllu))}


def test_liczba_nie_jest_kolokatem():
    """Regres: 'rok --amod--> 2017' (f=11)."""
    zdanie = """\
1\tW\tw\tADP\t_\t_\t3\tcase\t_\t_
2\t2017\t2017\tADJ\t_\tCase=Loc|Number=Sing\t3\tamod\t_\t_
3\troku\trok\tNOUN\t_\tCase=Loc|Number=Sing\t0\troot\t_\t_
"""
    assert klucze(zdanie) == set()


def test_liczebnik_nie_jest_kolokatem():
    zdanie = """\
1\ttrzy\ttrzy\tNUM\t_\tCase=Acc\t2\tamod\t_\t_
2\tdecyzje\tdecyzja\tNOUN\t_\tCase=Acc|Number=Plur\t0\troot\t_\t_
"""
    assert klucze(zdanie) == set()


def test_lemat_z_cyfra_odrzucony():
    zdanie = """\
1\tmodel\tmodel\tNOUN\t_\tCase=Nom|Number=Sing\t0\troot\t_\t_
2\tX200\tx200\tADJ\t_\tCase=Nom|Number=Sing\t1\tamod\t_\t_
"""
    assert klucze(zdanie) == set()


# Uwaga: sklejki alfabetyczne w rodzaju `złdo` (f=18 na probce) NIE sa lapane
# tutaj — maja poprawny ksztalt napisu. Odsiewa je filtr slownikowy oparty
# na Morfeuszu, patrz tests/test_slownik.py.


def test_nazwa_wlasna_nie_jest_kolokacja():
    """Regres: 'góra --amod--> zielony' (f=13) z 'Zielona Góra'."""
    zdanie = """\
1\tMieszkam\tmieszkać\tVERB\t_\tAspect=Imp\t0\troot\t_\t_
2\tw\tw\tADP\t_\t_\t4\tcase\t_\t_
3\tZielonej\tzielony\tADJ\t_\tCase=Loc|Number=Sing\t4\tamod\t_\t_
4\tGórze\tgóra\tNOUN\t_\tCase=Loc|Number=Sing\t1\tobl\t_\t_
"""
    assert "góra|amod|zielony" not in klucze(zdanie)


def test_przymiotnik_na_poczatku_zdania_nie_jest_odrzucany():
    """Straz przed nadgorliwoscia: 'Zielona trawa rosła' to poprawna kolokacja,
    a wielka litera wynika tylko z pozycji na poczatku zdania."""
    zdanie = """\
1\tZielona\tzielony\tADJ\t_\tCase=Nom|Number=Sing\t2\tamod\t_\t_
2\ttrawa\ttrawa\tNOUN\t_\tCase=Nom|Number=Sing\t3\tnsubj\t_\t_
3\trosła\trosnąć\tVERB\t_\tAspect=Imp\t0\troot\t_\t_
"""
    assert "trawa|amod|zielony" in klucze(zdanie)


def test_zwykla_kolokacja_przechodzi_mimo_nowych_filtrow():
    zdanie = """\
1\tZarząd\tzarząd\tNOUN\t_\tCase=Nom|Number=Sing\t2\tnsubj\t_\t_
2\tpodjął\tpodjąć\tVERB\t_\tAspect=Perf\t0\troot\t_\t_
3\tważną\tważny\tADJ\t_\tCase=Acc|Number=Sing\t4\tamod\t_\t_
4\tdecyzję\tdecyzja\tNOUN\t_\tCase=Acc|Number=Sing\t2\tobj\t_\t_
"""
    k = klucze(zdanie)
    assert "podjąć|obj|acc|decyzja" in k
    assert "decyzja|amod|ważny" in k

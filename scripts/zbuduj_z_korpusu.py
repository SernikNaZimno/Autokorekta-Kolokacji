"""Buduje baze z trojek zebranych w Colabie i od razu ocenia sygnal.

Ten krok NIE potrzebuje GPU ani sesji Colaba — to czysty SQLite. Robimy go
lokalnie, zeby dalo sie iterowac (zmienic prog, odrzucic zrodlo) bez ogladania
sie na limity czasu sesji.

Uzycie:
    python scripts/zbuduj_z_korpusu.py data/trojki_5M.tsv.gz [prog_par]
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.baza import BazaKolokacji, zbuduj  # noqa: E402
from backend.pipeline import czytaj_trojki  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)

ZRODLO = Path(sys.argv[1])
MIN_PARY = int(sys.argv[2]) if len(sys.argv) > 2 else 3
BAZA = ZRODLO.parent / (ZRODLO.name.split(".")[0] + ".sqlite")

if not ZRODLO.exists():
    sys.exit(f"Brak pliku: {ZRODLO}")

print("=" * 72)
print(f"BUDOWA BAZY z {ZRODLO.name} ({ZRODLO.stat().st_size / 1024**2:.1f} MB)")
print(f"prog przyciecia: pary o czestosci < {MIN_PARY} odpadaja")
print("=" * 72)

t0 = time.perf_counter()
stat = zbuduj(czytaj_trojki(ZRODLO), BAZA, min_pary=MIN_PARY, postep=print)
czas = time.perf_counter() - t0

print(f"\nGotowe w {czas:.1f} s -> {BAZA.name} "
      f"({BAZA.stat().st_size / 1024**2:.1f} MB)")
for k, v in stat.items():
    print(f"  {k:<26} {v:>12,}")

with BazaKolokacji(BAZA) as db:
    print("\n" + "=" * 72)
    print("PYTANIE 1: czy slot `decyzja` jest juz zbadany")
    print("=" * 72)
    print("To liczba rozstrzygajaca budzet korpusu. W PDB (350 tys. tokenow)")
    print("wynosila 34 przy progu 50 — czyli silnik milczal.\n")
    for dep in ["decyzja", "porażka", "uwaga", "funkcja", "klęska", "próba"]:
        f = db.czestosc_slotu_dep("obj:acc", dep)
        status = "ZBADANY" if db.slot_zbadany("obj:acc", dep) else "za malo — milczymy"
        print(f"  {dep:<12} f_brzegowa = {f:<7,} {status}")

    print("\n" + "=" * 72)
    print("PYTANIE 2: czy sygnal przetrwal przejscie z treebanku na web")
    print("=" * 72)
    for dep in ["decyzja", "porażka"]:
        print(f"\n  Czasowniki laczace sie z '{dep}' (obj:acc):")
        alt = db.alternatywy("obj:acc", dep, limit=10)
        if not alt:
            print("    (brak — slot pusty)")
        for k in alt:
            print(f"    {k.lemat:<18} f={k.f:<6,} logDice={k.logdice:.2f}")
    print("\n  Kontrola bledu sztandarowego:")
    for head in ["podjąć", "podejmować", "przyjąć", "zrobić"]:
        ld = db.logdice(head, "obj:acc", "decyzja")
        print(f"    logDice({head:<12} + decyzja) = {ld:>6.2f}")

    print("\n" + "=" * 72)
    print("PYTANIE 3: czy lista czasownikow lekkich jest jeszcze potrzebna")
    print("=" * 72)
    print("Na PDB podobienstwo podjac~zrobic wynosilo 0,000, co zmusilo nas do")
    print("recznej listy czasownikow lekkich w silniku. Przy wiekszym korpusie")
    print("profile moga sie zazebic i lista stanie sie zbedna.\n")
    for a, b in [
        ("podjąć", "podejmować"),
        ("podjąć", "zrobić"),
        ("ponieść", "doznać"),
        ("podjąć", "jeść"),
    ]:
        print(f"  {a:<10} ~ {b:<12} = {db.podobienstwo(a, b, 'obj:acc'):.3f}")

    print("\n" + "=" * 72)
    print("KONTROLA SKAZENIA DOMENOWEGO")
    print("=" * 72)
    try:
        print(f"udzial wiki {db.udzial_zrodla('wiki'):.1%}, "
              f"web {db.udzial_zrodla('web'):.1%}\n")
        print("Pary czeste, ale obecne WYLACZNIE w webie (kandydaci na boilerplate):")
        wiersze = db.con.execute(
            """SELECT p.head, p.slot, p.dep, p.f FROM pary p
               WHERE p.f >= 10 AND NOT EXISTS (
                 SELECT 1 FROM pary_zrodlo z WHERE z.head=p.head AND z.slot=p.slot
                 AND z.dep=p.dep AND z.zrodlo='wiki')
               ORDER BY p.f DESC LIMIT 20"""
        ).fetchall()
        if not wiersze:
            print("  (zadnych — web nie wprowadzil wlasnych szablonow)")
        for h, s, d, f in wiersze:
            print(f"  {h} --{s}--> {d}   f={f:,}")
    except Exception as e:
        print(f"  pominieto: {e}")

    print("\n" + "=" * 72)
    print("NAJCZESTSZE KOLOKACJE obj:acc — kontrola wzrokowa jakosci")
    print("=" * 72)
    for h, d, f, ld in db.con.execute(
        """SELECT head, dep, f, logdice FROM pary
           WHERE slot='obj:acc' ORDER BY f DESC LIMIT 25"""
    ):
        print(f"  {h + ' ' + d:<34} f={f:<7,} logDice={ld:.2f}")

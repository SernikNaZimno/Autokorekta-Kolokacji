"""Buduje baze kolokacji z plikow CoNLL-U znalezionych w data/.

Na razie zrodlem jest UD Polish-PDB (350 tys. tokenow) — za maly na produkcje,
ale wystarczajacy, zeby zwalidowac warstwe bazy i regule detekcji, zanim
zainwestujemy godziny w pipeline korpusowy.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.baza import BazaKolokacji, trojki_z_conllu, zbuduj  # noqa: E402

KORZEN = Path(__file__).resolve().parents[1]
PLIKI = sorted((KORZEN / "data").glob("*.conllu"))
BAZA = KORZEN / "data" / "kolokacje.sqlite"

if not PLIKI:
    sys.exit("Brak plikow .conllu w data/")

print(f"Zrodla: {', '.join(p.name for p in PLIKI)}")
t0 = time.perf_counter()
stat = zbuduj(trojki_z_conllu(PLIKI), BAZA)
czas = time.perf_counter() - t0

print(f"\nZbudowano w {czas:.1f} s -> {BAZA.name} "
      f"({BAZA.stat().st_size / 1024 / 1024:.1f} MB)")
for k, v in stat.items():
    print(f"  {k:<24} {v:>9,}")

print()
print("=" * 68)
print("KONTROLA — czy baza zwraca to samo, co liczyl skrypt jednorazowy")
print("=" * 68)
with BazaKolokacji(BAZA) as db:
    print(f"  {db.statystyki()}")
    print()
    for head in ["podjąć", "podejmować", "zrobić"]:
        ld = db.logdice(head, "obj:acc", "decyzja")
        print(f"  logDice({head:<12} obj:acc decyzja) = {ld:.2f}")

    print()
    print("  Alternatywy dla slotu (?, obj:acc, decyzja):")
    for k in db.alternatywy("obj:acc", "decyzja", limit=6):
        print(f"    {k.lemat:<14} f={k.f:<4} logDice={k.logdice:.2f}")

    print()
    print("  Czy sloty sa zbadane (prog 50):")
    for dep in ["decyzja", "porażka", "uwaga"]:
        f = db.czestosc_slotu_dep("obj:acc", dep)
        print(f"    {dep:<10} f_brzegowa={f:<5} "
              f"{'ZBADANY' if db.slot_zbadany('obj:acc', dep) else 'za malo danych — milczymy'}")

    print()
    print("  Podobienstwo dystrybucyjne (cosinus na obj:acc):")
    for a, b in [("podjąć", "podejmować"), ("podjąć", "zrobić"), ("podjąć", "jeść")]:
        print(f"    {a} ~ {b:<12} = {db.podobienstwo(a, b, 'obj:acc'):.3f}")

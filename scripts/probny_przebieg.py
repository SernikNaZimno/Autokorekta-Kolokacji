"""Maly przebieg pipeline'u na CPU — kontrola przed uruchomieniem na GPU.

Cel: udowodnic, ze cala sciezka (strumien -> filtr -> Stanza bulk -> trojki ->
TSV.gz -> baza) dziala od konca do konca. Blad wykryty tutaj kosztuje minuty;
ten sam blad wykryty po godzinie parsowania w Colabie kosztuje godzine.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.baza import BazaKolokacji, zbuduj  # noqa: E402
from backend.pipeline import czytaj_trojki, zbierz  # noqa: E402

KORZEN = Path(__file__).resolve().parents[1]
TSV = KORZEN / "data" / "trojki_probne.tsv.gz"
BAZA = KORZEN / "data" / "kolokacje_probne.sqlite"

BUDZET = {"wiki": 25_000, "web": 25_000}

print("=" * 70)
print("PRZEBIEG PROBNY — CPU, maly budzet")
print("=" * 70)
stat = zbierz(BUDZET, TSV, gpu=False, partia=32)

print()
print("=" * 70)
print("WYNIK ZBIERANIA")
print("=" * 70)
for k in ("trojek", "na_zrodlo", "sekund"):
    print(f"  {k:<18} {stat[k]}")
print(f"  plik               {TSV.stat().st_size / 1024:.0f} KB")
print("\n  Najczestsze powody odrzucenia zdan:")
for powod, n in sorted(stat["odrzucone_zdania"].items(), key=lambda x: -x[1])[:6]:
    print(f"    {powod:<24} {n:>6}")

print()
print("=" * 70)
print("BUDOWA BAZY Z TSV")
print("=" * 70)
# prog 2 zamiast 3 — przy 50 tys. tokenow prawie nic nie przezylo by progu 3
info = zbuduj(czytaj_trojki(TSV), BAZA, min_pary=2)
for k, v in info.items():
    print(f"  {k:<24} {v:>9,}")

print()
print("=" * 70)
print("KONTROLA TRESCI — czy to wyglada na polskie kolokacje")
print("=" * 70)
with BazaKolokacji(BAZA) as db:
    print(f"  {db.statystyki()}")
    print(f"  udzial wiki: {db.udzial_zrodla('wiki'):.1%}   "
          f"udzial web: {db.udzial_zrodla('web'):.1%}")

    print("\n  Najlepsze pary obj:acc wg logDice (f>=3):")
    wiersze = db.con.execute(
        "SELECT head, dep, f, logdice FROM pary WHERE slot='obj:acc' AND f>=3 "
        "ORDER BY logdice DESC LIMIT 12"
    ).fetchall()
    for h, d, f, ld in wiersze:
        zrodla = db.zrodla_pary(h, "obj:acc", d)
        opis = " ".join(f"{k}={v}" for k, v in sorted(zrodla.items()))
        print(f"    {h} + {d:<18} f={f:<3} logDice={ld:.1f}   [{opis}]")

    print("\n  Kontrola skazenia — pary wylacznie z webu, f>=4:")
    wiersze = db.con.execute(
        """SELECT p.head, p.slot, p.dep, p.f FROM pary p
           WHERE p.f >= 4 AND NOT EXISTS (
             SELECT 1 FROM pary_zrodlo z WHERE z.head=p.head AND z.slot=p.slot
             AND z.dep=p.dep AND z.zrodlo='wiki')
           ORDER BY p.f DESC LIMIT 8"""
    ).fetchall()
    for h, s, d, f in wiersze:
        print(f"    {h} --{s}--> {d}   f={f}")
    if not wiersze:
        print("    (brak — za maly przebieg)")

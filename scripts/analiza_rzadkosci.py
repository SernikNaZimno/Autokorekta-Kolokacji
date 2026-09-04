"""Ile korpusu naprawde potrzeba — pomiar rzadkosci par.

Bramka sygnalu przeszla, ale „porażka jako obj" ma w calym PDB dwa wystapienia.
Regula „para rzadka => alarm" przy takim pokryciu zglasza poprawna polszczyzne.
Ten skrypt mierzy, jaka czesc par to hapaksy i jak pokrycie rosnie z rozmiarem
korpusu — czyli ile tokenow trzeba zebrac w Etapie 3.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ekstraktor import czytaj_conllu, wyciagnij_trojki  # noqa: E402

KATALOG = Path(__file__).resolve().parents[1] / "data"

# Zbieramy trojki w kolejnosci wystepowania, zeby moc symulowac mniejsze korpusy.
strumien: list[tuple[str, str, str]] = []
tokenow = 0
for plik in sorted(KATALOG.glob("pl_pdb-ud-*.conllu")):
    for tokeny in czytaj_conllu(str(plik)):
        tokenow += len(tokeny)
        for t in wyciagnij_trojki(tokeny):
            slot = t.relacja
            if t.przyimek:
                slot += f"+{t.przyimek}"
            if t.przypadek:
                slot += f":{t.przypadek}"
            strumien.append((t.head, slot, t.dep))

pary = Counter(strumien)
n_par = len(pary)

print("=" * 70)
print("ROZKLAD CZESTOSCI PAR")
print("=" * 70)
rozklad = Counter(pary.values())
skum = 0
for f in sorted(rozklad)[:8]:
    skum += rozklad[f]
    print(
        f"  f={f:<3} {rozklad[f]:>7,} par  "
        f"({100 * rozklad[f] / n_par:>5.1f}%)   skumulowane {100 * skum / n_par:>5.1f}%"
    )
powyzej = n_par - skum
print(f"  f>8  {powyzej:>7,} par  ({100 * powyzej / n_par:>5.1f}%)")

hapaks = rozklad[1]
print()
print(f"  HAPAKSY (f=1): {hapaks:,} z {n_par:,} = {100 * hapaks / n_par:.1f}%")
print(f"  Par przezywajacych prog f>=3: {sum(v for k, v in rozklad.items() if k >= 3):,}")

print()
print("=" * 70)
print("KRZYWA POKRYCIA - jak rosnie liczba par przy progu f>=3")
print("=" * 70)
print(f"{'% korpusu':>10} {'tokenow':>10} {'par f>=3':>10} {'przyrost':>10}")
print("-" * 70)
poprzednio = 0
for udzial in [0.125, 0.25, 0.5, 0.75, 1.0]:
    wycinek = Counter(strumien[: int(len(strumien) * udzial)])
    solidne = sum(1 for v in wycinek.values() if v >= 3)
    print(
        f"{100 * udzial:>9.1f}% {int(tokenow * udzial):>10,} "
        f"{solidne:>10,} {solidne - poprzednio:>+10,}"
    )
    poprzednio = solidne

print()
print("=" * 70)
print("WNIOSEK")
print("=" * 70)
solidne = sum(1 for v in pary.values() if v >= 3)
na_milion = solidne / (tokenow / 1_000_000)
print(f"  Przy {tokenow:,} tokenach mamy {solidne:,} par o f>=3.")
print(f"  To {na_milion:.0f} solidnych par na milion tokenow.")
print()
print("  Krzywa jest wklesla (przyrosty rosna), wiec ekstrapolacja liniowa")
print("  zanizza wynik — ale nawet liniowo:")
for cel in [10, 100, 500]:
    print(f"    {cel:>4} mln tokenow  ->  co najmniej {int(na_milion * cel):>9,} par f>=3")

"""Walidacja ekstraktora na skale + pierwszy pomiar sygnalu kolokacyjnego.

Na 3 zdaniach wszystko wyglada dobrze. Ten skrypt puszcza ekstraktor przez caly
treebank UD Polish-PDB i sprawdza rzecz, od ktorej zalezy sens calego projektu:
czy z czestosci wychodzi roznica miedzy kolokacja poprawna a bledna.

Bramka: podjąć+decyzja musi wyraznie bic zrobić+decyzja w logDice.
"""

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ekstraktor import czytaj_conllu, wyciagnij_trojki  # noqa: E402

KATALOG = Path(__file__).resolve().parents[1] / "data"
PLIKI = sorted(KATALOG.glob("pl_pdb-ud-*.conllu"))

pary: Counter[tuple[str, str, str]] = Counter()   # (head, relacja+przyp, dep)
head_marg: Counter[tuple[str, str]] = Counter()
dep_marg: Counter[tuple[str, str]] = Counter()
wg_relacji: Counter[str] = Counter()
liczba_zdan = liczba_tokenow = 0

print(f"Przetwarzam {len(PLIKI)} plikow z {KATALOG}...")
for plik in PLIKI:
    for tokeny in czytaj_conllu(str(plik)):
        liczba_zdan += 1
        liczba_tokenow += len(tokeny)
        for t in wyciagnij_trojki(tokeny):
            slot = t.relacja
            if t.przyimek:
                slot += f"+{t.przyimek}"
            if t.przypadek:
                slot += f":{t.przypadek}"
            pary[(t.head, slot, t.dep)] += 1
            head_marg[(t.head, slot)] += 1
            dep_marg[(slot, t.dep)] += 1
            wg_relacji[t.relacja] += 1

print(f"  zdan:     {liczba_zdan:>9,}")
print(f"  tokenow:  {liczba_tokenow:>9,}")
print(f"  trojek:   {sum(pary.values()):>9,}")
print(f"  unikalnych par: {len(pary):>9,}")


def log_dice(head: str, slot: str, dep: str) -> float:
    """logDice = 14 + log2(2*f(xy) / (f(x) + f(y))). Skala ~0-14, niezalezna
    od rozmiaru korpusu, wiec progi przenosza sie miedzy korpusami."""
    fxy = pary.get((head, slot, dep), 0)
    if fxy == 0:
        return 0.0
    fx = head_marg[(head, slot)]
    fy = dep_marg[(slot, dep)]
    return 14 + math.log2(2 * fxy / (fx + fy))


print()
print("=" * 72)
print("ROZKLAD WG RELACJI")
print("=" * 72)
for rel, n in wg_relacji.most_common():
    print(f"  {rel:<10} {n:>8,}  {100 * n / sum(wg_relacji.values()):>5.1f}%")

print()
print("=" * 72)
print("NAJCZESTSZE DOPELNIENIA BLIZSZE (obj:acc)")
print("=" * 72)
obj = [(k, v) for k, v in pary.items() if k[1] == "obj:acc"]
for (h, slot, d), n in sorted(obj, key=lambda x: -x[1])[:12]:
    print(f"  {n:>4}x  {h} + {d}   (logDice {log_dice(h, slot, d):.1f})")

print()
print("=" * 72)
print("BRAMKA: jakie czasowniki lacza sie z 'decyzja' jako obj")
print("=" * 72)
kandydaci = [(k[0], v) for k, v in pary.items() if k[1] == "obj:acc" and k[2] == "decyzja"]
if kandydaci:
    for h, n in sorted(kandydaci, key=lambda x: -log_dice(x[0], "obj:acc", "decyzja")):
        print(f"  {h:<16} f={n:<4} logDice={log_dice(h, 'obj:acc', 'decyzja'):.2f}")
else:
    print("  BRAK — korpus za maly")

print()
print("=" * 72)
print("BRAMKA: 'porażka' jako obj")
print("=" * 72)
kandydaci = [(k[0], v) for k, v in pary.items() if k[1] in ("obj:acc", "obj:gen") and k[2] == "porażka"]
if kandydaci:
    for h, n in sorted(kandydaci, key=lambda x: -x[1]):
        slot = "obj:acc" if (h, "obj:acc", "porażka") in pary else "obj:gen"
        print(f"  {h:<16} f={n:<4} logDice={log_dice(h, slot, 'porażka'):.2f}")
else:
    print("  BRAK — korpus za maly")

print()
print("=" * 72)
print("WERDYKT BRAMKI")
print("=" * 72)
dobry = log_dice("podjąć", "obj:acc", "decyzja")
zly = log_dice("zrobić", "obj:acc", "decyzja")
print(f"  podjąć + decyzja : logDice {dobry:.2f}  (f={pary.get(('podjąć','obj:acc','decyzja'),0)})")
print(f"  zrobić + decyzja : logDice {zly:.2f}  (f={pary.get(('zrobić','obj:acc','decyzja'),0)})")
roznica = dobry - zly
print(f"  roznica: {roznica:.2f}")
print(f"  {'SYGNAL JEST' if roznica > 3 else 'SYGNAL ZA SLABY — sprawdz ekstraktor'}")

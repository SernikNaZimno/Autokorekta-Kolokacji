"""Ocena filtra zdaniowego na C4 i Wikipedii.

Poprzednia proba (filtr dokumentowy) przepuszczala 4 smieci na 5 przyjetych.
Ten skrypt pokazuje surowe probki wejscia i wyjscia, zeby ocenic je okiem —
liczba przezywalnosci sama w sobie nic nie mowi o jakosci.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datasets import load_dataset  # noqa: E402

from backend.czyszczenie import na_zdania, powod_odrzucenia  # noqa: E402

N_DOK = 300


def oceń(nazwa: str, **kw) -> None:
    ds = load_dataset(split="train", streaming=True, **kw)
    dokumenty = [r["text"] for _, r in zip(range(N_DOK), ds)]

    powody: Counter[str] = Counter()
    przyjete: list[str] = []
    wszystkich = 0
    for tekst in dokumenty:
        for z in na_zdania(tekst):
            wszystkich += 1
            p = powod_odrzucenia(z)
            if p is None:
                przyjete.append(z)
            else:
                powody[p] += 1

    print()
    print("=" * 78)
    print(f"{nazwa}  —  {N_DOK} dokumentow, {wszystkich:,} zdan-kandydatow")
    print("=" * 78)
    print(f"  przyjete: {len(przyjete):,} ({100*len(przyjete)/max(wszystkich,1):.1f}%)")
    slow = sum(len(z.split()) for z in przyjete)
    print(f"  slow uzytecznych: {slow:,} "
          f"({slow/N_DOK:.0f} na dokument)")
    print("\n  Powody odrzucenia:")
    for powod, n in powody.most_common():
        print(f"    {powod:<24} {n:>6}  ({100*n/max(wszystkich,1):>4.1f}%)")

    print("\n  PRZYJETE (co trafi do parsera):")
    for z in przyjete[:8]:
        print(f"    · {z[:150]}")

    print("\n  ODRZUCONE (kontrola falszywych odrzucen):")
    pokazane: set[str] = set()
    for tekst in dokumenty:
        for z in na_zdania(tekst):
            p = powod_odrzucenia(z)
            if p and p not in pokazane and len(z) > 40:
                pokazane.add(p)
                print(f"    [{p}] {z[:130]}")
    print()


oceń("C4 pl (web)", path="allenai/c4", name="pl")
oceń("Wikipedia pl", path="wikimedia/wikipedia", name="20231101.pl")

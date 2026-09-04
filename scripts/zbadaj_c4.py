"""Rozpoznanie jakosci C4 pl — na czym kalibrowac filtr.

Pierwszy rekord C4 okazal sie spamem SEO. Zanim napisze heurystyki, chce
zobaczyc rozklad: ile jest smieci, jak wygladaja i ktore sygnaly je odrozniaja
od zwyklej prozy. Filtr strojony na przeczuciu albo przepusci spam (skazi normy
kolokacyjne), albo wytnie poprawny tekst (zmarnuje korpus).
"""

import re
import statistics
import sys
from collections import Counter

from datasets import load_dataset

N = 400

DIAKRYTYKI = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
POLSKIE_STOP = {"i", "w", "na", "się", "z", "do", "nie", "że", "jest", "to", "o", "a"}


def cechy(tekst: str) -> dict:
    slowa = re.findall(r"\w+", tekst.lower())
    linie = [l.strip() for l in tekst.splitlines() if l.strip()]
    n_slow = len(slowa) or 1
    znaki = len(tekst) or 1
    return {
        "slow": len(slowa),
        "linii": len(linie),
        # udzial polskich diakrytykow — spam obcojezyczny/maszynowy ich nie ma
        "diakrytyki": sum(1 for c in tekst if c in DIAKRYTYKI) / znaki,
        # udzial slow funkcyjnych — proza ma duzo, listy produktow prawie wcale
        "stopwords": sum(1 for s in slowa if s in POLSKIE_STOP) / n_slow,
        # udzial cyfr — cenniki, ISBN, numery katalogowe
        "cyfry": sum(1 for c in tekst if c.isdigit()) / znaki,
        # srednia dlugosc linii — spam to krotkie urwane linijki
        "sr_linia": statistics.mean(len(l) for l in linie) if linie else 0,
        # udzial linii konczacych sie kropka — zdania vs naglowki/listy
        "linie_zdaniowe": (
            sum(1 for l in linie if l.rstrip().endswith((".", "!", "?", "…")))
            / len(linie)
            if linie
            else 0
        ),
        "unikalnosc_linii": len(set(linie)) / len(linie) if linie else 0,
    }


print(f"Pobieram {N} dokumentow C4 pl...")
ds = load_dataset("allenai/c4", "pl", split="train", streaming=True)
dokumenty = [r["text"] for _, r in zip(range(N), ds)]
wektory = [cechy(t) for t in dokumenty]

print()
print("=" * 76)
print("ROZKLAD CECH (percentyle)")
print("=" * 76)
print(f"{'cecha':<18} {'p10':>9} {'mediana':>9} {'p90':>9}")
print("-" * 76)
for k in wektory[0]:
    v = sorted(x[k] for x in wektory)
    p = lambda q: v[int(len(v) * q)]  # noqa: E731
    print(f"{k:<18} {p(0.10):>9.3f} {p(0.50):>9.3f} {p(0.90):>9.3f}")

# Heurystyka wstepna, do kalibracji ponizej
def podejrzany(c: dict) -> list[str]:
    powody = []
    if c["slow"] < 40:
        powody.append("za krotki")
    if c["diakrytyki"] < 0.015:
        powody.append("brak diakrytykow")
    if c["stopwords"] < 0.12:
        powody.append("malo slow funkcyjnych")
    if c["cyfry"] > 0.06:
        powody.append("duzo cyfr")
    if c["linie_zdaniowe"] < 0.35:
        powody.append("linie niezdaniowe")
    if c["unikalnosc_linii"] < 0.75:
        powody.append("powtorzone linie")
    return powody


odrzucone = [(t, c, p) for t, c in zip(dokumenty, wektory) if (p := podejrzany(c))]
print()
print("=" * 76)
print(f"ODRZUCONE PRZEZ HEURYSTYKE: {len(odrzucone)}/{N} = {100*len(odrzucone)/N:.0f}%")
print("=" * 76)
licznik = Counter(r for _, _, powody in odrzucone for r in powody)
for powod, n in licznik.most_common():
    print(f"  {powod:<24} {n:>4}")

print()
print("=" * 76)
print("PROBKA ODRZUCONYCH — czy slusznie?")
print("=" * 76)
for t, c, powody in odrzucone[:5]:
    print(f"\n  [{', '.join(powody)}]  ({c['slow']} slow)")
    print(f"    {t[:200].replace(chr(10), ' | ')!r}")

print()
print("=" * 76)
print("PROBKA PRZYJETYCH — czy to zdatna proza?")
print("=" * 76)
przyjete = [(t, c) for t, c in zip(dokumenty, wektory) if not podejrzany(c)]
for t, c in przyjete[:5]:
    print(f"\n  ({c['slow']} slow, diakr {c['diakrytyki']:.3f}, "
          f"stop {c['stopwords']:.2f})")
    print(f"    {t[:200].replace(chr(10), ' | ')!r}")

sys.stdout.flush()

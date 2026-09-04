"""Oszacowanie rozmiaru docelowej bazy ze 100 mln tokenow.

Mierzy faktyczne zuzycie miejsca w bazie zbudowanej z PDB (350 tys. tokenow),
a potem ekstrapoluje. Kluczowe rozroznienie: tabela `pary` jest PRZYCIETA do
f>=3, ale tabele brzegowe NIE SA — rosna z liczba typow, wiec przy duzej skali
moga zdominowac rozmiar. Wspolczynnik liczony wylacznie z tabeli par by to
przeoczyl.

Uzycie: python scripts/oszacuj_rozmiar.py [sciezka.sqlite] [tokenow_zrodla]
"""

import sqlite3
import sys
from pathlib import Path

SCIEZKA = Path(sys.argv[1] if len(sys.argv) > 1 else "data/kolokacje.sqlite")
TOKENY = int(sys.argv[2]) if len(sys.argv) > 2 else 349_978
CEL = 100_000_000

con = sqlite3.connect(SCIEZKA)
calosc = SCIEZKA.stat().st_size

print("=" * 72)
print(f"POMIAR: {SCIEZKA.name}   {calosc / 1024 / 1024:.2f} MB")
print(f"zrodlo: {TOKENY:,} tokenow".replace(",", " "))
print("=" * 72)

try:
    uzycie = dict(
        con.execute("SELECT name, SUM(pgsize) FROM dbstat GROUP BY name").fetchall()
    )
except sqlite3.OperationalError:
    uzycie = {}

# Baza z Etapu 4 powstala przed dodaniem sledzenia zrodel, wiec nie ma
# tabeli `pary_zrodlo` — pomijamy brakujace zamiast sie wywracac.
ISTNIEJACE = {
    r[0]
    for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
}
TABELE = [
    t for t in ["pary", "pary_zrodlo", "brzeg_head", "brzeg_dep"] if t in ISTNIEJACE
]
wiersze = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABELE}
if "pary_zrodlo" not in ISTNIEJACE:
    print("\n(brak tabeli pary_zrodlo — baza sprzed sledzenia zrodel;")
    print(" docelowa bedzie o nia wieksza, korekta nizej)")

print(f"\n{'tabela':<14} {'wierszy':>10} {'MB':>8} {'B/wiersz':>9}")
print("-" * 72)
for t in TABELE:
    n = wiersze[t]
    b = uzycie.get(t, 0)
    print(f"{t:<14} {n:>10,} {b / 1024 / 1024:>8.2f} {b / max(n, 1):>9.0f}")

if uzycie:
    indeksy = sum(v for k, v in uzycie.items() if k.startswith("idx_"))
    print(f"{'(indeksy)':<14} {'':>10} {indeksy / 1024 / 1024:>8.2f}")
    print(f"\nindeksy stanowia {indeksy / calosc:.0%} pliku")

print("\n" + "=" * 72)
print(f"EKSTRAPOLACJA NA {CEL:,} TOKENOW".replace(",", " "))
print("=" * 72)

skala = CEL / TOKENY
razem_wierszy = sum(wiersze.values())
b_na_wiersz = calosc / razem_wierszy

print(f"skala tokenow: {skala:.0f}x")
print(f"wierszy razem: {razem_wierszy:,}".replace(",", " "))
print(f"bajtow na wiersz (z indeksami): {b_na_wiersz:.0f}\n")

# Kazda tabela rosnie inaczej i trzeba je modelowac OSOBNO:
#
#  * brzeg_head / brzeg_dep to liczba TYPOW (head,slot) i (slot,dep). Rosna
#    jak slownictwo, czyli prawem Heapsa z wykladnikiem ~0,6.
#  * pary sa przyciete do f>=3. Przy malym korpusie prog odcina prawie
#    wszystko, wiec krzywa wewnatrz PDB wyglada na nadliniowa (b=1,31) — to
#    artefakt progu, nie realny wzrost. Przy duzej skali efekt zanika.
#
# Ekstrapolacja z samej tabeli par zawyzalaby kilkukrotnie, bo w zmierzonej
# bazie pary to tylko 4% wierszy.

brzegowe = wiersze.get("brzeg_head", 0) + wiersze.get("brzeg_dep", 0)
par_teraz = wiersze["pary"]

print(f"{'wariant':<24} {'par':>12} {'brzegowych':>12} {'rozmiar':>11}")
print("-" * 72)
wyniki = []
for nazwa, b_par, b_brzeg in [
    ("ostrozny", 0.75, 0.55),
    ("srodkowy", 0.85, 0.60),
    ("hojny", 1.00, 0.65),
]:
    par = par_teraz * (skala**b_par)
    brz = brzegowe * (skala**b_brzeg)
    # pary_zrodlo w docelowej bazie: kazda para razy liczba zrodel, w ktorych
    # wystapila (1-2 przy Wikipedii + C4), z grubsza 1,5x liczba par
    wierszy = par * 2.5 + brz
    rozmiar = wierszy * b_na_wiersz
    wyniki.append(rozmiar)
    print(
        f"{nazwa:<24} {par:>12,.0f} {brz:>12,.0f} {rozmiar / 1024**2:>8.0f} MB"
    )

print()
print(f"WIDELKI: {min(wyniki) / 1024**2:.0f} - {max(wyniki) / 1024**2:.0f} MB")
print()
print("Przebieg na 5 mln da trzeci punkt pomiarowy (350 tys. -> 5 mln -> 100 mln)")
print("i pozwoli wybrac wlasciwy wykladnik zamiast zgadywac miedzy wariantami.")

con.close()

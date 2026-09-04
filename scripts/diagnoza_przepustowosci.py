"""Gdzie naprawde idzie czas w pipelinie korpusowym.

Przebieg w Colabie dal 227 trojek/s (~740 tokenow/s) na T4, przy zakladanych
3-8 tys. Dwie hipotezy juz obalone pomiarem: grupowanie zdan w dokumenty nie
daje nic, a `use_gpu=True` jest przez Stanze honorowany.

Zostaje pytanie, ktorego dotad nikt nie zadal: ile z tego czasu to w ogole
parsowanie? W `zbierz` pobieranie z HuggingFace, filtr zdaniowy, Stanza,
Morfeusz i gzip chodza SZEREGOWO w jednym watku, przeplecione przez leniwe
generatory. Raportowane tempo obejmuje je wszystkie razem.

Ten skrypt rozdziela etapy i mierzy kazdy osobno.

Uzycie: python scripts/diagnoza_przepustowosci.py [zrodlo] [tokenow]
"""

import sys
import time

sys.path.insert(0, ".")

ZRODLO = sys.argv[1] if len(sys.argv) > 1 else "wiki"
BUDZET = int(sys.argv[2]) if len(sys.argv) > 2 else 20_000


def sekcja(tytul):
    print("\n" + "=" * 70)
    print(tytul)
    print("=" * 70)


sekcja(f"ETAP 1: pobieranie + filtr zdaniowy  ({ZRODLO}, {BUDZET:,} tokenow)")

from collections import Counter  # noqa: E402

from backend.pipeline import zdania_ze_zrodla  # noqa: E402

powody: Counter[str] = Counter()
t = time.perf_counter()
zdania = list(zdania_ze_zrodla(ZRODLO, BUDZET, powody))
czas_pobrania = time.perf_counter() - t

tokenow = sum(len(z.split()) for z in zdania)
odrzuconych = sum(powody.values())
print(f"zdan przyjetych:   {len(zdania):,}")
print(f"tokenow:           {tokenow:,}")
print(f"czas:              {czas_pobrania:.1f} s   -> {tokenow / czas_pobrania:,.0f} tok/s")
print(f"zdan odrzuconych:  {odrzuconych:,}", end="")
if odrzuconych + len(zdania):
    print(f"  ({odrzuconych / (odrzuconych + len(zdania)):.0%} materialu)")
else:
    print()
if powody:
    print("powody odrzucenia:")
    for p, n in powody.most_common(8):
        print(f"   {p:<28} {n:>8,}")

sekcja("ETAP 2: parsowanie Stanza")

from backend.pipeline import parsuj_do_trojek, utworz_pipeline  # noqa: E402

t = time.perf_counter()
nlp = utworz_pipeline(gpu=False, partia=256)
print(f"zaladowanie modelu: {time.perf_counter() - t:.1f} s")
print(f"urzadzenie: {getattr(nlp, 'device', '?')}")

t = time.perf_counter()
trojki = list(parsuj_do_trojek(zdania, nlp, ZRODLO, partia=256))
czas_parsowania = time.perf_counter() - t
print(f"trojek:            {len(trojki):,}")
print(f"czas:              {czas_parsowania:.1f} s   -> {tokenow / czas_parsowania:,.0f} tok/s")
print(f"                              -> {len(trojki) / czas_parsowania:,.0f} trojek/s")

sekcja("ETAP 3: filtr slownikowy Morfeusza")

from backend.slownik import WalidatorSlownikowy  # noqa: E402

walidator = WalidatorSlownikowy()
t = time.perf_counter()
przefiltrowane = list(walidator.filtruj(trojki))
czas_filtra = time.perf_counter() - t
print(f"przepuszczonych:   {len(przefiltrowane):,}")
print(f"czas:              {czas_filtra:.2f} s")
print(f"statystyki:        {walidator.statystyki}")

sekcja("PODSUMOWANIE")

calosc = czas_pobrania + czas_parsowania + czas_filtra
print(f"{'etap':<34} {'czas':>9} {'udzial':>9}")
print("-" * 70)
for nazwa, ile in [
    ("pobieranie + filtr zdaniowy", czas_pobrania),
    ("parsowanie Stanza", czas_parsowania),
    ("filtr slownikowy", czas_filtra),
]:
    print(f"{nazwa:<34} {ile:>7.1f} s {ile / calosc:>8.0%}")
print("-" * 70)
print(f"{'RAZEM':<34} {calosc:>7.1f} s")
print(f"\nlacznie {len(przefiltrowane) / calosc:,.0f} trojek/s "
      f"(Colab na T4 raportowal 227/s)")
print()
print("Jesli pobieranie zajmuje znaczacy udzial, to GPU nie jest waskim gardlem")
print("i szybsza karta niczego nie zmieni — trzeba rozdzielic pobieranie od")
print("parsowania na osobne watki, zeby chodzily rownolegle.")

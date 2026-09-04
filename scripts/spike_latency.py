"""Spike 0.3b - jak opoznienie Stanzy skaluje sie z dlugoscia akapitu.

580 ms na 31 slow to ~19 ms/slowo. Jesli skalowanie jest liniowe, akapit
100-slowny da ~1,9 s i wywali budzet dodatku. Mierzymy, zanim zbudujemy
architekture na blednym zalozeniu.
"""

import time

import torch

import stanza

print(f"torch threads (domyslnie): {torch.get_num_threads()}")
torch.set_num_threads(8)
print(f"torch threads (ustawione): {torch.get_num_threads()}\n")

nlp = stanza.Pipeline("pl", processors="tokenize,pos,lemma,depparse", verbose=False)

ZDANIE = (
    "Zarząd spółki podjął wczoraj ważną decyzję o zmianie strategii rynkowej. "
)


def zmierz(tekst, powtorzenia=3):
    nlp(tekst)  # rozgrzewka
    czasy = []
    for _ in range(powtorzenia):
        t = time.perf_counter()
        nlp(tekst)
        czasy.append((time.perf_counter() - t) * 1000)
    return min(czasy)


print("=" * 68)
print("SKALOWANIE - jeden akapit rosnacej dlugosci")
print("=" * 68)
print(f"{'zdan':>5} {'slow':>6} {'czas ms':>9} {'ms/slowo':>10}  budzet")
print("-" * 68)
for n in [1, 2, 4, 8, 16]:
    tekst = ZDANIE * n
    slow = len(tekst.split())
    ms = zmierz(tekst)
    status = "OK" if ms < 750 else "PRZEKROCZONY"
    print(f"{n:>5} {slow:>6} {ms:>9.0f} {ms / slow:>10.1f}  {status}")

print()
print("=" * 68)
print("ZDANIE POJEDYNCZE - jednostka cache'owania")
print("=" * 68)
ms = zmierz(ZDANIE)
print(f"  Jedno zdanie ({len(ZDANIE.split())} slow): {ms:.0f} ms")
print("  Przy cache'owaniu po zdaniu przeparsowujemy tylko zdanie zmienione,")
print("  wiec to jest realny koszt jednego nacisniecia klawisza.")

"""Ile realnie da sie wycisnac z lokalnego CPU przy parsowaniu korpusu.

Maszyna nie ma CUDA (AMD zintegrowana, torch w wersji +cpu), wiec jedyne
dostepne dzwignie to liczba watkow i rozmiar partii sieci. Mierzymy je, zeby
odpowiedziec na konkretne pytanie: czy zbieranie 30 mln tokenow lokalnie jest
realne, czy Colab pozostaje jedyna sensowna droga.

Zdania bierzemy z PDB, a nie ze strumienia HuggingFace — chcemy zmierzyc samo
parsowanie, bez wahan sieci.
"""

import sys
import time
from pathlib import Path

import torch

import stanza

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CEL = 30_000_000  # budzet, o ktory pytamy


def zdania_z_pdb(ile: int) -> list[str]:
    plik = next(Path(".").rglob("pl_pdb-ud-train.conllu"), None)
    if plik is None:
        raise SystemExit("nie znaleziono pl_pdb-ud-train.conllu")
    out = []
    with open(plik, encoding="utf-8") as f:
        for linia in f:
            if linia.startswith("# text = "):
                out.append(linia[9:].strip())
                if len(out) >= ile:
                    break
    return out


ZDANIA = zdania_z_pdb(600)
TOKENOW = sum(len(z.split()) for z in ZDANIA)
print(f"materiał: {len(ZDANIA)} zdań, {TOKENOW:,} tokenów")
print(f"rdzeni logicznych: {torch.get_num_threads()} (domyślnie w torch)\n")

from backend.pipeline import parsuj_do_trojek  # noqa: E402


def zmierz(watki: int, partia) -> float:
    torch.set_num_threads(watki)
    nlp = stanza.Pipeline(
        "pl", processors="tokenize,pos,lemma,depparse",
        use_gpu=False, verbose=False,
        **({} if partia is None else {
            "tokenize_batch_size": partia,
            "pos_batch_size": partia,
            "depparse_batch_size": partia,
        }),
    )
    list(parsuj_do_trojek(ZDANIA[:100], nlp, "x", partia=64))  # rozgrzewka
    t = time.perf_counter()
    list(parsuj_do_trojek(ZDANIA, nlp, "x", partia=64))
    return TOKENOW / (time.perf_counter() - t)


print(f"{'wątki':>6} {'partia sieci':>13} {'tok/s':>8} {'30 mln zajmie':>16}")
print("-" * 50)
najlepszy = (0, None, 0.0)
for watki in (4, 8, 16):
    for partia in (None, 1000):
        try:
            tps = zmierz(watki, partia)
            godzin = CEL / tps / 3600
            etyk = "domyślna" if partia is None else str(partia)
            print(f"{watki:>6} {etyk:>13} {tps:>8,.0f} {godzin:>13.1f} h")
            if tps > najlepszy[2]:
                najlepszy = (watki, partia, tps)
        except Exception as e:
            print(f"{watki:>6} {str(partia):>13}   błąd: {str(e)[:30]}")

w, p, tps = najlepszy
print()
print(f"NAJLEPSZY WARIANT: {w} wątków, partia {p}  ->  {tps:,.0f} tok/s")
print()
print("=" * 50)
print("PORÓWNANIE Z COLABEM")
print("=" * 50)
KOLAB = 705  # zmierzone: 5 mln tokenów w 7 087 s na T4
print(f"  ten laptop (CPU):   {tps:>6,.0f} tok/s   ->  {CEL/tps/3600:>5.1f} h")
print(f"  Colab T4:           {KOLAB:>6,.0f} tok/s   ->  {CEL/KOLAB/3600:>5.1f} h")
print(f"  stosunek:           {KOLAB/tps:.1f}x na korzyść Colaba")
print()
print("Zrównoleglenie na 8 rdzeniach dałoby optymistycznie ~4x (pamięć jest")
print("wąskim gardłem, nie liczba rdzeni), czyli wciąż wolniej niż T4 —")
print(f"okolo {CEL/(tps*4)/3600:.1f} h, i wymagałoby napisania obsługi procesów roboczych.")

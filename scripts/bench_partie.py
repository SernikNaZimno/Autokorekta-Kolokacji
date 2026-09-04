"""Pomiar: jak grupowanie zdan w dokumenty wplywa na przepustowosc Stanzy.

Przebieg w Colabie dal ~680 tokenow/s na T4, przy zakladanych 3-8 tys.
Obecny pipeline tworzy JEDEN dokument na zdanie, wiec tokenizator wykonuje
setki przebiegow na kilkunastowyrazowych tekstach. Sprawdzamy, ile kosztuje
to naprawde i czy sklejenie zdan w wieksze dokumenty pomaga.

Mierzone na CPU — liczby bezwzgledne beda nizsze niz na GPU, ale interesuje
nas STOSUNEK miedzy wariantami, ktory na GPU powinien byc jeszcze wiekszy
(karta gorzej znosi male porcje niz procesor).

Uzycie: python scripts/bench_partie.py [ile_zdan]
"""

import sys
import time
from pathlib import Path

import stanza
from stanza.models.common.doc import Document

ILE = int(sys.argv[1]) if len(sys.argv) > 1 else 200


def zdania_z_pdb(ile: int) -> list[str]:
    """Prawdziwe polskie zdania z treebanku — realistyczna dlugosc i sklad."""
    plik = next(Path(".").rglob("pl_pdb-ud-train.conllu"), None)
    if plik is None:
        raise SystemExit("nie znaleziono pl_pdb-ud-train.conllu")
    zdania = []
    with open(plik, encoding="utf-8") as f:
        for linia in f:
            if linia.startswith("# text = "):
                zdania.append(linia[9:].strip())
                if len(zdania) >= ile:
                    break
    return zdania


zdania = zdania_z_pdb(ILE)
tokenow = sum(len(z.split()) for z in zdania)
print(f"materiał: {len(zdania)} zdań, {tokenow} tokenów, "
      f"średnio {tokenow / len(zdania):.1f} tok./zdanie\n")

print("ładowanie modelu...")
nlp = stanza.Pipeline(
    "pl", processors="tokenize,pos,lemma,depparse", use_gpu=False, verbose=False
)
nlp_bez_ssplit = stanza.Pipeline(
    "pl", processors="tokenize,pos,lemma,depparse", use_gpu=False,
    tokenize_no_ssplit=True, verbose=False,
)
print("gotowe\n")


def zmierz(nazwa, funkcja, powtorzenia=2):
    funkcja()  # rozgrzewka
    czasy = []
    for _ in range(powtorzenia):
        t = time.perf_counter()
        n = funkcja()
        czasy.append(time.perf_counter() - t)
    naj = min(czasy)
    print(f"{nazwa:<44} {naj:>7.2f} s  {tokenow / naj:>8.0f} tok/s  ({n} zdań)")
    return tokenow / naj


def wariant_obecny():
    """Jak teraz: jeden Document na zdanie."""
    docs = nlp.bulk_process([Document([], text=z) for z in zdania])
    return sum(len(d.sentences) for d in docs)


def wariant_jeden_dokument():
    """Wszystkie zdania sklejone w jeden tekst; Stanza sama dzieli na zdania."""
    doc = nlp(" ".join(zdania))
    return len(doc.sentences)


def wariant_bez_ssplit():
    """Jeden dokument, zdania rozdzielone pustą linią, podział wyłączony.

    Zdania mamy już podzielone przez filtr, więc ponowne dzielenie jest
    zbędną pracą — a przy okazji ryzykiem rozjazdu granic zdań.
    """
    doc = nlp_bez_ssplit("\n\n".join(zdania))
    return len(doc.sentences)


def wariant_grupy(n):
    """Kompromis: kilka średnich dokumentów zamiast setek malutkich."""
    def f():
        grupy = ["\n\n".join(zdania[i:i + n]) for i in range(0, len(zdania), n)]
        docs = nlp_bez_ssplit.bulk_process([Document([], text=g) for g in grupy])
        return sum(len(d.sentences) for d in docs)
    return f


print(f"{'wariant':<44} {'czas':>9} {'przepustowość':>16}")
print("-" * 78)
podstawa = zmierz("obecny: 1 dokument na zdanie", wariant_obecny)
zmierz("1 wielki dokument, podział przez Stanzę", wariant_jeden_dokument)
najlepszy = zmierz("1 wielki dokument, bez podziału", wariant_bez_ssplit)
for n in (25, 50):
    zmierz(f"grupy po {n} zdań, bez podziału", wariant_grupy(n))

print()
print(f"PRZYSPIESZENIE względem obecnego: {najlepszy / podstawa:.1f}x")
print()
print("Na GPU różnica powinna być WIĘKSZA — karta traci więcej niż procesor")
print("na przełączaniu między drobnymi porcjami pracy.")

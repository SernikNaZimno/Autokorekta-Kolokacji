"""Walidacja ekstraktora na prawdziwym rozbiorze Stanzy.

Testy jednostkowe chodza na recznych fixture'ach CoNLL-U, wiec moga byc zielone
mimo ze regula nie odpala sie na realnych danych — jesli zalozylem zla etykiete.
Ten skrypt sprawdza zalozenia na wyjsciu modelu:

  A. jak Stanza faktycznie znakuje partykule „nie" (od tego zalezy normalizacja
     dopelniacza negacji),
  B. czy sciezka Stanza i sciezka CoNLL-U daja identyczne klucze.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stanza  # noqa: E402

from backend.ekstraktor import (  # noqa: E402
    wyciagnij_trojki,
    z_conllu,
    z_stanzy,
)

nlp = stanza.Pipeline("pl", processors="tokenize,pos,lemma,depparse", verbose=False)

print("=" * 72)
print("A. JAK STANZA ZNAKUJE NEGACJE (zalozenie testu: PART + advmod -> VERB)")
print("=" * 72)
for tekst in ["Zarząd nie podjął decyzji.", "Firma nie poniosła porażki."]:
    print(f'\n  "{tekst}"')
    for sent in nlp(tekst).sentences:
        for w in sent.words:
            gwiazdka = "  <<<" if w.lemma == "nie" else ""
            head = sent.words[w.head - 1].text if w.head > 0 else "ROOT"
            print(
                f"    {w.text:<10} lemat={w.lemma:<10} {w.upos:<6} "
                f"{w.deprel:<10} -> {head}{gwiazdka}"
            )

print()
print("=" * 72)
print("B. CZY NORMALIZACJA ODPALA NA REALNYM ROZBIORZE")
print("=" * 72)
pary = [
    ("Zarząd podjął decyzję.", "Zarząd nie podjął decyzji."),
    ("Firma poniosła porażkę.", "Firma nie poniosła porażki."),
]
wszystko_ok = True
for twierdzace, przeczace in pary:
    k1 = {t.klucz() for t in wyciagnij_trojki(z_stanzy(nlp(twierdzace).sentences[0]))}
    k2 = {t.klucz() for t in wyciagnij_trojki(z_stanzy(nlp(przeczace).sentences[0]))}
    wspolne = {k for k in k1 & k2 if "|obj|" in k}
    ok = bool(wspolne)
    wszystko_ok &= ok
    print(f'\n  "{twierdzace}" vs "{przeczace}"')
    print(f"    twierdzace obj: {sorted(k for k in k1 if '|obj|' in k)}")
    print(f"    przeczace  obj: {sorted(k for k in k2 if '|obj|' in k)}")
    print(f"    {'ZGODNE' if ok else 'ROZJAZD — normalizacja nie zadziala'}")

print()
print("=" * 72)
print("C. TROJKI Z REALNEGO AKAPITU")
print("=" * 72)
akapit = (
    "Zarząd spółki podjął wczoraj ważną decyzję o zmianie strategii. "
    "Firma poniosła dotkliwą porażkę na rynku europejskim. "
    "Nowy plan zakłada głębokie zmiany w strukturze zatrudnienia."
)
for sent in nlp(akapit).sentences:
    print(f"\n  {sent.text}")
    for t in wyciagnij_trojki(z_stanzy(sent)):
        print(f"    {t}")

print()
print("=" * 72)
print("D. ZGODNOSC ADAPTEROW (Stanza vs CoNLL-U na tym samym zdaniu)")
print("=" * 72)
zdanie = "Zarząd podjął ważną decyzję na posiedzeniu."
sent = nlp(zdanie).sentences[0]
przez_stanze = {t.klucz() for t in wyciagnij_trojki(z_stanzy(sent))}

# ten sam rozbior przepuszczony przez serializacje do CoNLL-U
linie = []
for w in sent.words:
    linie.append(
        "\t".join(
            [
                str(w.id),
                w.text,
                w.lemma or "_",
                w.upos or "_",
                "_",
                w.feats or "_",
                str(w.head),
                w.deprel or "_",
                "_",
                "_",
            ]
        )
    )
przez_conllu = {t.klucz() for t in wyciagnij_trojki(z_conllu("\n".join(linie)))}

print(f"  Stanza:  {len(przez_stanze)} kluczy")
print(f"  CoNLL-U: {len(przez_conllu)} kluczy")
if przez_stanze == przez_conllu:
    print("  ZGODNE — ta sama logika klucza w budowie bazy i w runtime")
else:
    wszystko_ok = False
    print(f"  ROZJAZD: {przez_stanze ^ przez_conllu}")

print()
print("=" * 72)
print("WERDYKT:", "wszystko OK" if wszystko_ok else "SA ROZJAZDY — patrz wyzej")
print("=" * 72)
sys.exit(0 if wszystko_ok else 1)

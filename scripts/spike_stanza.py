"""Spike 0.3 - Stanza pl na CPU: poprawnosc rozbioru + opoznienie runtime.

Sprawdzamy dwie rzeczy:
1. Czy parser znajduje luki czasownik->dopelnienie i przymiotnik->rzeczownik,
   z ktorych zbudujemy trojki kolokacyjne.
2. Czy opoznienie na akapicie miesci sie pod debounce'em 750 ms w dodatku.
"""

import time

import stanza

print("Pobieranie/ladowanie modelu pl (PDB)...")
t0 = time.perf_counter()
stanza.download("pl", verbose=False)
nlp = stanza.Pipeline("pl", processors="tokenize,pos,lemma,depparse", verbose=False)
print(f"Model zaladowany w {time.perf_counter() - t0:.1f} s\n")

# Wzorce, ktore chcemy wyciagac (Etap 2 planu)
INTERESUJACE = {"obj", "iobj", "obl", "amod", "nmod", "advmod", "nsubj"}


def przypadek(word):
    """Wyciaga przypadek z kolumny FEATS, np. Case=Acc -> acc."""
    if not word.feats:
        return None
    for kv in word.feats.split("|"):
        if kv.startswith("Case="):
            return kv.split("=")[1].lower()
    return None


def trojki(sent):
    """(lemat_head, relacja, przypadek, lemat_dep) - klucz bazy kolokacji."""
    out = []
    for w in sent.words:
        if w.deprel not in INTERESUJACE or w.head == 0:
            continue
        head = sent.words[w.head - 1]
        out.append((head.lemma, w.deprel, przypadek(w), w.lemma))
    return out


print("=" * 74)
print("1. ROZBIOR - zdania z bledami kolokacyjnymi")
print("=" * 74)
zdania = [
    "Zarzad zrobil wazna decyzje w tej sprawie.",
    "Zarząd zrobił ważną decyzję w tej sprawie.",
    "Firma odniosła porażkę na trudnym rynku.",
]
for tekst in zdania:
    doc = nlp(tekst)
    print(f"\n  \"{tekst}\"")
    for sent in doc.sentences:
        for w in sent.words:
            head = sent.words[w.head - 1].text if w.head > 0 else "ROOT"
            print(
                f"    {w.text:<12} lemat={w.lemma:<14} {w.upos:<6} "
                f"{w.deprel:<10} -> {head}"
            )

print()
print("=" * 74)
print("2. TROJKI KOLOKACYJNE - to trafia do bazy")
print("=" * 74)
for tekst in ["Zarząd zrobił ważną decyzję w tej sprawie.",
              "Firma odniosła porażkę na trudnym rynku."]:
    doc = nlp(tekst)
    print(f"\n  \"{tekst}\"")
    for sent in doc.sentences:
        for h, rel, case, d in trojki(sent):
            kluc = f"{h} --{rel}"
            if case:
                kluc += f":{case}"
            print(f"    {kluc}--> {d}")

print()
print("=" * 74)
print("3. OPOZNIENIE NA CPU - budzet dodatku to 750 ms debounce")
print("=" * 74)
akapit = (
    "Zarząd spółki podjął wczoraj ważną decyzję o zmianie strategii. "
    "Wcześniejsze działania nie przyniosły oczekiwanych rezultatów, "
    "a firma poniosła dotkliwą porażkę na rynku europejskim. "
    "Nowy plan zakłada głębokie zmiany w strukturze zatrudnienia."
)
liczba_slow = len(akapit.split())
nlp(akapit)  # rozgrzewka - pierwszy przebieg alokuje bufory

czasy = []
for _ in range(5):
    t = time.perf_counter()
    nlp(akapit)
    czasy.append((time.perf_counter() - t) * 1000)

sredni = sum(czasy) / len(czasy)
print(f"  Akapit: {liczba_slow} slow, {len(akapit)} znakow")
print(f"  Przebiegi: {', '.join(f'{c:.0f}' for c in czasy)} ms")
print(f"  Sredni:    {sredni:.0f} ms   (min {min(czasy):.0f}, max {max(czasy):.0f})")
print(f"  WERDYKT:   {'OK - miesci sie pod debounce' if sredni < 750 else 'ZA WOLNO'}")

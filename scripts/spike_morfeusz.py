"""Spike 0.2 - czy Morfeusz 2 analizuje i GENERUJE formy na Py 3.12/Windows.

Generacja jest warunkiem koniecznym funkcji podmiany: zeby zaproponowac
"doznal porazki" w miejsce "*odniosl porazke", trzeba odmienic rzeczownik
do przypadka wymaganego przez nowy czasownik i czasownik do formy oryginalu.
"""

import morfeusz2

m = morfeusz2.Morfeusz(generate=True)


def analyse(text):
    """Zwraca liste (forma, lemat, tag) dla kazdej interpretacji."""
    out = []
    for _start, _end, interp in m.analyse(text):
        forma, lemat, tag = interp[0], interp[1], interp[2]
        out.append((forma, lemat, tag))
    return out


def generate(lemat, tag_prefix=None):
    """Generuje formy lematu; opcjonalnie filtruje po prefiksie tagu."""
    try:
        forms = m.generate(lemat)
    except Exception as exc:  # noqa: BLE001 - spike, chcemy zobaczyc blad
        return [("BLAD", str(exc), "")]
    out = []
    for interp in forms:
        forma, lem, tag = interp[0], interp[1], interp[2]
        if tag_prefix is None or tag.startswith(tag_prefix):
            out.append((forma, lem, tag))
    return out


print("=" * 70)
print("1. ANALIZA - rozbior bledneg zdania")
print("=" * 70)
for forma, lemat, tag in analyse("odniosl porazke"):
    print(f"  {forma:<12} -> lemat={lemat:<18} tag={tag}")

print()
print("=" * 70)
print("2. ANALIZA z polskimi znakami")
print("=" * 70)
for forma, lemat, tag in analyse("odniósł porażkę"):
    print(f"  {forma:<12} -> lemat={lemat:<18} tag={tag}")

print()
print("=" * 70)
print("3. GENERACJA - rzeczownik do innego przypadka")
print("=" * 70)
print("  porażka w dopelniaczu l.poj. (wymagany przez 'doznać'):")
for forma, lem, tag in generate("porażka", "subst:sg:gen"):
    print(f"    {forma:<12} tag={tag}")
print("  porażka w bierniku l.poj. (wymagany przez 'ponieść'):")
for forma, lem, tag in generate("porażka", "subst:sg:acc"):
    print(f"    {forma:<12} tag={tag}")

print()
print("=" * 70)
print("4. GENERACJA - czasownik do formy oryginalu (praet sg m)")
print("=" * 70)
for lemat in ["doznać", "ponieść"]:
    formy = generate(lemat, "praet:sg:m1")
    print(f"  {lemat}:")
    for forma, lem, tag in formy[:4]:
        print(f"    {forma:<12} tag={tag}")

print()
print("=" * 70)
print("5. TEST ASPEKTU - czy tag niesie dokonanosc")
print("=" * 70)
for lemat in ["podjąć", "podejmować"]:
    formy = generate(lemat, "praet:sg:m1")
    if formy:
        forma, lem, tag = formy[0]
        aspekt = "perf" if ":perf" in tag else ("imperf" if ":imperf" in tag else "?")
        print(f"  {lemat:<14} -> {forma:<14} aspekt={aspekt:<8} tag={tag}")

print()
print("=" * 70)
print("6. PELNY OBIEG - *odniosl porazke  =>  doznal porazki")
print("=" * 70)
zrodlo_v = generate("doznać", "praet:sg:m1")
zrodlo_n = generate("porażka", "subst:sg:gen")
if zrodlo_v and zrodlo_n:
    print(f"  WYNIK: {zrodlo_v[0][0]} {zrodlo_n[0][0]}")
else:
    print("  NIEPOWODZENIE - brak form")

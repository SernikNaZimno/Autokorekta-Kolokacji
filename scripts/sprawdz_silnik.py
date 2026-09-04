"""Pierwsza proba silnika na PRAWDZIWEJ bazie korpusowej.

Dotad silnik byl testowany wylacznie na danych syntetycznych, gdzie sam
ustawialem zliczenia. To jest moment prawdy: czy regula czterowarunkowa
dziala na zliczeniach z prawdziwego korpusu.

Liczy sie oboje: czy lapie bledy ORAZ czy milczy na poprawnej polszczyznie.
Falszywy alarm kosztuje wiecej niz przeoczenie — po kilku uzytkownik wylacza
dodatek.

Uzycie: python scripts/sprawdz_silnik.py data/trojki_5M.sqlite
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.baza import BazaKolokacji  # noqa: E402
from backend.ekstraktor import z_stanzy  # noqa: E402
from backend.generator import GeneratorForm  # noqa: E402
from backend.silnik import SilnikKolokacji  # noqa: E402

BAZA = Path(sys.argv[1] if len(sys.argv) > 1 else "data/trojki_5M.sqlite")
if not BAZA.exists():
    sys.exit(f"Brak bazy: {BAZA}")

# (zdanie, czy_silnik_POWINIEN_sie_odezwac, komentarz)
PROBKI = [
    # --- bledy kolokacyjne: silnik POWINIEN zareagowac ---
    ("Zarząd zrobił ważną decyzję w tej sprawie.", True, "sztandarowy przypadek"),
    ("Firma zrobiła próbę wejścia na rynek.", True, "podjąć próbę"),
    ("Chciałbym zrobić uwagę do tego projektu.", True, "zwrócić uwagę"),
    ("On robi funkcję prezesa zarządu.", True, "pełnić funkcję"),
    ("Naukowcy zrobili badania nad tym zjawiskiem.", True, "prowadzić badania"),

    # --- poprawna polszczyzna: silnik MUSI milczec ---
    ("Zarząd podjął ważną decyzję w tej sprawie.", False, "poprawne"),
    ("Zarząd podejmował decyzje przez cały rok.", False, "poprawne, inny aspekt"),
    ("Zrobił zdjęcie na wakacjach.", False, "'zrobić zdjęcie' JEST poprawne"),
    ("Firma odniosła sukces na rynku.", False, "poprawne"),
    ("Wziął udział w konferencji naukowej.", False, "poprawne"),
    ("Pełnił funkcję dyrektora przez lata.", False, "poprawne"),
    ("Zarząd nie podjął decyzji w tej sprawie.", False, "NEGACJA — dopełniacz"),
    ("Zwrócił uwagę na ten problem.", False, "poprawne"),
    ("Prowadzi działalność gospodarczą.", False, "poprawne"),
]

print("ładowanie Stanzy i bazy...")
import stanza  # noqa: E402

nlp = stanza.Pipeline("pl", processors="tokenize,pos,lemma,depparse", verbose=False)

with BazaKolokacji(BAZA) as db:
    silnik = SilnikKolokacji(db, generator=GeneratorForm())

    print("\n" + "=" * 76)
    print("PODOBIENSTWA ISTOTNE DLA WARUNKU 4")
    print("=" * 76)
    print("Prog w silniku: 0,15. Ponizej niego alternatywa jest odrzucana jako")
    print("semantycznie odlegla — chyba ze obserwowany czasownik jest lekki.\n")
    for a, b in [
        ("podjąć", "zrobić"),
        ("odnieść", "ponieść"),
        ("zwrócić", "zrobić"),
        ("pełnić", "robić"),
        ("prowadzić", "zrobić"),
    ]:
        s = db.podobienstwo(a, b, "obj:acc")
        print(f"  {a:<10} ~ {b:<10} = {s:.3f}  {'>= prog' if s >= 0.15 else '< prog'}")

    print("\n" + "=" * 76)
    print("SILNIK NA ZDANIACH")
    print("=" * 76)

    trafienia = pudla = falszywe = ciche_ok = 0
    for zdanie, oczekiwany, komentarz in PROBKI:
        doc = nlp(zdanie)
        sugestie = []
        for sent in doc.sentences:
            sugestie.extend(silnik.sprawdz(z_stanzy(sent)))

        odezwal_sie = bool(sugestie)
        if oczekiwany and odezwal_sie:
            ocena, trafienia = "TRAFIONE ", trafienia + 1
        elif oczekiwany and not odezwal_sie:
            ocena, pudla = "PRZEOCZONE", pudla + 1
        elif not oczekiwany and odezwal_sie:
            ocena, falszywe = "FALSZYWY ALARM", falszywe + 1
        else:
            ocena, ciche_ok = "milczy OK ", ciche_ok + 1

        print(f"\n[{ocena}] {zdanie}")
        print(f"           ({komentarz})")
        for s in sugestie:
            zamiana = f"{s.oryginal} -> {s.propozycja}"
            if s.forma_dopelnienia:
                zamiana += f" + {s.forma_dopelnienia}"
            print(f"    {zamiana}   przewaga logDice {s.przewaga:.1f}")
            print(f"    {s.uzasadnienie}")

    print("\n" + "=" * 76)
    print("PODSUMOWANIE")
    print("=" * 76)
    bledne = sum(1 for _, o, _ in PROBKI if o)
    poprawne = len(PROBKI) - bledne
    print(f"  bledy wykryte:        {trafienia}/{bledne}")
    print(f"  bledy przeoczone:     {pudla}/{bledne}")
    print(f"  falszywe alarmy:      {falszywe}/{poprawne}   <- to jest krytyczne")
    print(f"  poprawnie milczy:     {ciche_ok}/{poprawne}")
    print()
    if falszywe:
        print("  Falszywe alarmy sa gorsze niz przeoczenia. Jesli wystapily,")
        print("  progi trzeba zaostrzyc ZANIM cokolwiek trafi do Worda.")
    else:
        print("  Zero falszywych alarmow — warunek 1 (slot zbadany) dziala.")

"""Zbieranie korpusu na wlasnej maszynie z karta NVIDIA — zamiast Colaba.

PRZYGOTOWANIE MASZYNY Z KARTA (jednorazowo):

    git clone https://github.com/SernikNaZimno/Autokorekta-Kolokacji.git
    cd Autokorekta-Kolokacji
    py -3.12 -m venv .venv
    .\\.venv\\Scripts\\pip install -r requirements.txt

    # UWAGA: requirements.txt ciagnie torch w wersji +cpu, ktora IGNORUJE karte.
    # Trzeba go nadpisac wersja CUDA (cu126 to jedyna z torch 2.14 dla Py3.12):
    .\\.venv\\Scripts\\pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu126

URUCHOMIENIE:

    python scripts/zbierz_lokalnie.py proba      # 5 mln tokenow
    python scripts/zbierz_lokalnie.py pelna      # 30 mln tokenow
    python scripts/zbierz_lokalnie.py pelna --pomiar   # tylko zmierz tempo

Skrypt ZAWSZE zaczyna od pomiaru przepustowosci i podaje szacowany czas,
zanim zacznie wielogodzinna prace. Wynik ladue w data/ — ten sam format,
co plik z Colaba, wiec `zbuduj_z_korpusu.py` przyjmie go bez zmian.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

USTAWIENIA = {
    "proba": {"wiki": 3_000_000, "web": 2_000_000, "etykieta": "5M"},
    "pelna": {"wiki": 18_000_000, "web": 12_000_000, "etykieta": "30M"},
}

SKALA = sys.argv[1] if len(sys.argv) > 1 else "proba"
TYLKO_POMIAR = "--pomiar" in sys.argv

if SKALA not in USTAWIENIA:
    sys.exit(f"Nieznana skala: {SKALA}. Dostepne: {', '.join(USTAWIENIA)}")

k = USTAWIENIA[SKALA]
BUDZET = {"wiki": k["wiki"], "web": k["web"]}
CEL = sum(BUDZET.values())
KORZEN = Path(__file__).resolve().parents[1]
WYJSCIE = KORZEN / "data" / f"trojki_{k['etykieta']}.tsv.gz"

# --------------------------------------------------------------- karta

import torch  # noqa: E402

print("=" * 70)
print(f"ZBIERANIE LOKALNE — skala {SKALA} ({CEL:,} tokenow)".replace(",", " "))
print("=" * 70)
print(f"torch {torch.__version__}")

GPU = torch.cuda.is_available()
if GPU:
    print(f"karta: {torch.cuda.get_device_name(0)}")
    print(f"VRAM:  {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
else:
    print("CUDA NIEDOSTEPNA — parsowanie pojdzie na CPU.")
    if "+cpu" in torch.__version__:
        print()
        print("  Masz torch w wersji +cpu, ktora IGNORUJE karte nawet jesli jest.")
        print("  Napraw to poleceniem:")
        print("    pip install --force-reinstall torch \\")
        print("        --index-url https://download.pytorch.org/whl/cu126")
        print()
    print("  Na CPU 30 mln tokenow to ~48 h (zmierzone na Ryzen 7 5825U).")

# --------------------------------------------------------------- pomiar

from backend.pipeline import (  # noqa: E402
    parsuj_do_trojek,
    utworz_pipeline,
    zbierz,
    zdania_ze_zrodla,
)

print("\n" + "=" * 70)
print("POMIAR PRZEPUSTOWOSCI")
print("=" * 70)
print("pobieram probke...")
PROBKA = list(zdania_ze_zrodla("wiki", 25_000))
TOKENOW = sum(len(z.split()) for z in PROBKA)
print(f"{len(PROBKA)} zdan, {TOKENOW:,} tokenow\n".replace(",", " "))

# Na GPU rozmiar partii sieci ma znaczenie; na CPU nie ma (bench_partie.py).
KANDYDACI = [None, 400, 1000, 2000] if GPU else [None, 1000]

print(f"{'partia sieci':>13} {'tok/s':>9} {'caly przebieg':>16}")
print("-" * 44)
wyniki = {}
for partia in KANDYDACI:
    try:
        nlp = utworz_pipeline(gpu=GPU, partia=partia)
        t = time.perf_counter()
        list(parsuj_do_trojek(PROBKA, nlp, "wiki", partia=256))
        tps = TOKENOW / (time.perf_counter() - t)
        wyniki[partia] = tps
        etyk = "domyslna" if partia is None else str(partia)
        print(f"{etyk:>13} {tps:>9,.0f} {CEL / tps / 3600:>13.1f} h")
        del nlp
        if GPU:
            import gc

            gc.collect()
            torch.cuda.empty_cache()
    except Exception as e:
        print(f"{str(partia):>13}   blad: {str(e)[:36]}")

if not wyniki:
    sys.exit("Zaden wariant nie zadzialal — sprawdz instalacje.")

NAJ = max(wyniki, key=wyniki.get)
TPS = wyniki[NAJ]
GODZIN = CEL / TPS / 3600
print(f"\nNAJLEPSZA: partia_modelu={NAJ}  ({TPS:,.0f} tok/s)".replace(",", " "))
print(f"Szacowany czas calego przebiegu: {GODZIN:.1f} h")
print("\nDla porownania: Colab T4 dawal 705 tok/s, czyli 11,8 h dla 30 mln.")
if TPS > 705:
    print(f"Ta maszyna jest {TPS / 705:.1f}x SZYBSZA od T4.")
else:
    print(f"Ta maszyna jest {705 / TPS:.1f}x wolniejsza od T4.")

if TYLKO_POMIAR:
    sys.exit(0)

# --------------------------------------------------------------- zbieranie

print("\n" + "=" * 70)
print("ZBIERANIE")
print("=" * 70)
print(f"wyjscie: {WYJSCIE}")
print(f"Zapis jest opruzniany co 50 000 trojek, wiec przerwanie kosztuje")
print(f"najwyzej ostatnia partie — `czytaj_trojki` toleruje uciety plik.\n")
WYJSCIE.parent.mkdir(parents=True, exist_ok=True)

t0 = time.perf_counter()
stat = zbierz(
    BUDZET,
    WYJSCIE,
    gpu=GPU,
    partia=256,
    partia_modelu=NAJ,
    co_ile_raport=50_000,
)
print(f"\nGOTOWE w {(time.perf_counter() - t0) / 3600:.2f} h")
for klucz, wartosc in stat.items():
    print(f"  {klucz:<22} {wartosc}")
print(f"\nNastepny krok:")
print(f"  python scripts/zbuduj_z_korpusu.py {WYJSCIE.relative_to(KORZEN)}")

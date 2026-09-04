"""Pipeline korpusowy: zrodlo -> filtr zdaniowy -> Stanza -> trojki na dysk.

Ten sam modul chodzi na laptopie (CPU, male probki, rozwoj) i w Colabie
(GPU, pelna skala). Krytyczne jest to, ze uzywa tego samego `ekstraktor.py`,
co silnik w czasie pisania — rozjazd logiki klucza miedzy budowa bazy
a zapytaniem nie objawilby sie zadnym bledem, tylko cicho zerowa skutecznoscia.

Wyjscie to TSV.gz z kolumnami (head, slot, dep, zrodlo). Surowe trojki, nie
zliczenia: agregacje robi `baza.zbuduj`, dzieki czemu mozna zmienic prog
przyciecia albo odrzucic zrodlo bez ponownego parsowania korpusu.
"""

from __future__ import annotations

import gzip
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator

from backend.baza import slot_z_trojki
from backend.czyszczenie import przefiltruj_dokumenty
from backend.ekstraktor import wyciagnij_trojki, z_stanzy

# Zrodla sprawdzone pod katem dostepnosci — patrz docs/USTALENIA-KORPUS.md.
ZRODLA: dict[str, dict] = {
    "wiki": {"path": "wikimedia/wikipedia", "name": "20231101.pl"},
    "web": {"path": "allenai/c4", "name": "pl"},
}


def utworz_pipeline(gpu: bool = False, partia: int = 64):
    """Pipeline Stanzy. Na GPU zwieksz partie — narzut na wywolanie dominuje."""
    import stanza

    return stanza.Pipeline(
        "pl",
        processors="tokenize,pos,lemma,depparse",
        use_gpu=gpu,
        tokenize_batch_size=partia,
        pos_batch_size=partia,
        depparse_batch_size=partia,
        verbose=False,
    )


def dokumenty_ze_zrodla(zrodlo: str) -> Iterator[str]:
    """Strumien surowych tekstow z nazwanego zrodla."""
    from datasets import load_dataset

    if zrodlo not in ZRODLA:
        raise ValueError(f"Nieznane zrodlo: {zrodlo}. Dostepne: {list(ZRODLA)}")
    ds = load_dataset(split="train", streaming=True, **ZRODLA[zrodlo])
    for rekord in ds:
        yield rekord["text"]


def zdania_ze_zrodla(
    zrodlo: str, limit_tokenow: int, powody: Counter | None = None
) -> Iterator[str]:
    """Zdatne, unikalne zdania ze zrodla — do wyczerpania budzetu tokenow."""
    tokenow = 0
    for zdanie in przefiltruj_dokumenty(dokumenty_ze_zrodla(zrodlo), powody):
        yield zdanie
        tokenow += len(zdanie.split())
        if tokenow >= limit_tokenow:
            return


def _partie(strumien: Iterable[str], n: int) -> Iterator[list[str]]:
    bufor: list[str] = []
    for x in strumien:
        bufor.append(x)
        if len(bufor) >= n:
            yield bufor
            bufor = []
    if bufor:
        yield bufor


def parsuj_do_trojek(
    zdania: Iterable[str], nlp, zrodlo: str, partia: int = 64
) -> Iterator[tuple[str, str, str, str]]:
    """Parsuje zdania partiami i wypuszcza trojki ze znacznikiem zrodla."""
    from stanza.models.common.doc import Document

    for grupa in _partie(zdania, partia):
        dokumenty = nlp.bulk_process([Document([], text=z) for z in grupa])
        for doc in dokumenty:
            for sent in doc.sentences:
                for t in wyciagnij_trojki(z_stanzy(sent)):
                    yield (t.head, slot_z_trojki(t), t.dep, zrodlo)


def zbierz(
    zrodla: dict[str, int],
    wyjscie: str | Path,
    gpu: bool = False,
    partia: int = 64,
    co_ile_raport: int = 20_000,
) -> dict:
    """Glowna petla: dla kazdego zrodla parsuje przydzielony budzet tokenow.

    `zrodla` to mapa nazwa -> budzet tokenow, np. {"wiki": 3_000_000,
    "web": 2_000_000}. Budzet jest per zrodlo, zeby jedno nie zdominowalo
    korpusu — Wikipedia jest latwiejsza do strumieniowania niz C4 i bez
    podzialu wypelnilaby caly limit.
    """
    from backend.slownik import WalidatorSlownikowy

    wyjscie = Path(wyjscie)
    wyjscie.parent.mkdir(parents=True, exist_ok=True)
    nlp = utworz_pipeline(gpu=gpu, partia=partia)
    walidator = WalidatorSlownikowy()

    powody: Counter[str] = Counter()
    na_zrodlo: Counter[str] = Counter()
    t0 = time.perf_counter()
    n = 0

    with gzip.open(wyjscie, "wt", encoding="utf-8", newline="\n") as f:
        for zrodlo, budzet in zrodla.items():
            print(f"[{zrodlo}] budzet {budzet:,} tokenow")
            t_zrodlo = time.perf_counter()
            zdania = zdania_ze_zrodla(zrodlo, budzet, powody)
            trojki = parsuj_do_trojek(zdania, nlp, zrodlo, partia)
            for krotka in walidator.filtruj(trojki):
                f.write("\t".join(krotka) + "\n")
                n += 1
                na_zrodlo[zrodlo] += 1
                if n % co_ile_raport == 0:
                    tempo = n / (time.perf_counter() - t0)
                    print(f"  {n:,} trojek  ({tempo:,.0f}/s)")
            print(
                f"[{zrodlo}] gotowe: {na_zrodlo[zrodlo]:,} trojek "
                f"w {time.perf_counter() - t_zrodlo:.0f} s"
            )

    return {
        "trojek": n,
        "na_zrodlo": dict(na_zrodlo),
        "odrzucone_zdania": dict(powody),
        "filtr_slownikowy": walidator.statystyki,
        "sekund": round(time.perf_counter() - t0, 1),
        "plik": str(wyjscie),
    }


def czytaj_trojki(sciezka: str | Path) -> Iterator[tuple[str, str, str, str]]:
    """Czyta TSV.gz z powrotem — wejscie dla `baza.zbuduj`."""
    with gzip.open(sciezka, "rt", encoding="utf-8") as f:
        for linia in f:
            pola = linia.rstrip("\n").split("\t")
            if len(pola) == 4:
                yield (pola[0], pola[1], pola[2], pola[3])

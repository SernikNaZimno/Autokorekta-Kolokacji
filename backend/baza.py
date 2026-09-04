"""Baza zliczen kolokacyjnych — budowa i zapytania.

Budowa idzie przez SQLite, nie przez Counter w RAM: przy docelowych 100 mln
tokenow strumien ma ~30 mln trojek, co w pamieci zajelo by kilka GB. Wstawiamy
surowe trojki na dysk, a agregacje robi silnik bazy.

Kolejnosc operacji jest istotna: **czestosci brzegowe licza sie przed
przycieciem**. Gdyby liczyc je po odrzuceniu rzadkich par, mianownik logDice
bylby zanizony i wszystkie wyniki zawyzone.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from backend.ekstraktor import Trojka

# Ponizej tej czestosci para jest szumem parsera lub literowka.
MIN_CZESTOSC_PARY = 3

# Ponizej tej czestosci brzegowej slot jest niezbadany i silnik ma milczec.
# Uzasadnienie: 90,9% par w PDB to hapaksy — patrz docs/USTALENIA-SPIKE.md.
MIN_CZESTOSC_SLOTU = 50


def slot_z_trojki(t: Trojka) -> str:
    """Kanoniczna etykieta slotu: 'obj:acc', 'obl+na:loc', 'amod'."""
    s = t.relacja
    if t.przyimek:
        s += f"+{t.przyimek}"
    if t.przypadek:
        s += f":{t.przypadek}"
    return s


# ------------------------------------------------------------------- budowa


def _dostroj(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    con.execute("PRAGMA cache_size = -262144")  # 256 MB
    con.execute("PRAGMA temp_store = MEMORY")


def zbuduj(
    trojki: Iterable[Trojka],
    sciezka: str | Path,
    min_pary: int = MIN_CZESTOSC_PARY,
    partia: int = 100_000,
) -> dict[str, int]:
    """Buduje baze z strumienia trojek. Zwraca statystyki."""
    sciezka = Path(sciezka)
    if sciezka.exists():
        sciezka.unlink()

    con = sqlite3.connect(sciezka)
    _dostroj(con)
    con.execute("CREATE TABLE surowe (head TEXT, slot TEXT, dep TEXT)")

    bufor: list[tuple[str, str, str]] = []
    n_surowych = 0
    for t in trojki:
        bufor.append((t.head, slot_z_trojki(t), t.dep))
        if len(bufor) >= partia:
            con.executemany("INSERT INTO surowe VALUES (?,?,?)", bufor)
            n_surowych += len(bufor)
            bufor.clear()
    if bufor:
        con.executemany("INSERT INTO surowe VALUES (?,?,?)", bufor)
        n_surowych += len(bufor)
    con.commit()

    # Agregacja par.
    con.execute(
        """CREATE TABLE pary AS
           SELECT head, slot, dep, COUNT(*) AS f
           FROM surowe GROUP BY head, slot, dep"""
    )
    n_par_przed = con.execute("SELECT COUNT(*) FROM pary").fetchone()[0]

    # Brzegowe PRZED przycieciem — inaczej logDice wyjdzie zawyzony.
    con.execute(
        """CREATE TABLE brzeg_head AS
           SELECT head, slot, SUM(f) AS f FROM pary GROUP BY head, slot"""
    )
    con.execute(
        """CREATE TABLE brzeg_dep AS
           SELECT slot, dep, SUM(f) AS f FROM pary GROUP BY slot, dep"""
    )

    con.execute("DROP TABLE surowe")
    con.execute("DELETE FROM pary WHERE f < ?", (min_pary,))

    # logDice = 14 + log2(2*f(xy) / (f(x)+f(y))). Skala ~0-14 niezalezna od
    # rozmiaru korpusu, wiec progi przenosza sie miedzy wersjami bazy.
    con.create_function("log2", 1, math.log2, deterministic=True)
    con.execute("ALTER TABLE pary ADD COLUMN logdice REAL")
    con.execute(
        """UPDATE pary SET logdice = 14 + log2(
               2.0 * f / (
                   (SELECT f FROM brzeg_head h WHERE h.head=pary.head AND h.slot=pary.slot)
                 + (SELECT f FROM brzeg_dep d WHERE d.slot=pary.slot AND d.dep=pary.dep)
               ))"""
    )

    con.execute("CREATE INDEX idx_para ON pary (head, slot, dep)")
    con.execute("CREATE INDEX idx_slot_dep ON pary (slot, dep, logdice DESC)")
    con.execute("CREATE INDEX idx_slot_head ON pary (slot, head, logdice DESC)")
    con.execute("CREATE UNIQUE INDEX idx_bh ON brzeg_head (head, slot)")
    con.execute("CREATE UNIQUE INDEX idx_bd ON brzeg_dep (slot, dep)")
    con.commit()

    n_par_po = con.execute("SELECT COUNT(*) FROM pary").fetchone()[0]
    con.execute("VACUUM")
    con.commit()
    con.close()

    return {
        "trojek": n_surowych,
        "par_przed_przycieciem": n_par_przed,
        "par_po_przycieciu": n_par_po,
    }


# ----------------------------------------------------------------- zapytania


@dataclass(frozen=True, slots=True)
class Kandydat:
    """Alternatywa dla obserwowanego slowa w danym slocie."""

    lemat: str
    f: int
    logdice: float


class BazaKolokacji:
    """Dostep tylko do odczytu. Bezpieczna do wspoldzielenia miedzy zapytaniami."""

    def __init__(self, sciezka: str | Path) -> None:
        self.con = sqlite3.connect(f"file:{Path(sciezka)}?mode=ro", uri=True)
        self.con.execute("PRAGMA query_only = ON")

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> BazaKolokacji:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def logdice(self, head: str, slot: str, dep: str) -> float:
        """0.0 oznacza 'nieobecne w bazie' — NIE 'bledne'. Patrz USTALENIA."""
        w = self.con.execute(
            "SELECT logdice FROM pary WHERE head=? AND slot=? AND dep=?",
            (head, slot, dep),
        ).fetchone()
        return w[0] if w else 0.0

    def czestosc_slotu_dep(self, slot: str, dep: str) -> int:
        """Ile razy widzielismy ten rzeczownik w tym slocie — miara zbadania."""
        w = self.con.execute(
            "SELECT f FROM brzeg_dep WHERE slot=? AND dep=?", (slot, dep)
        ).fetchone()
        return w[0] if w else 0

    def czestosc_slotu_head(self, head: str, slot: str) -> int:
        w = self.con.execute(
            "SELECT f FROM brzeg_head WHERE head=? AND slot=?", (head, slot)
        ).fetchone()
        return w[0] if w else 0

    def slot_zbadany(self, slot: str, dep: str, prog: int = MIN_CZESTOSC_SLOTU) -> bool:
        """Warunek 1 reguly detekcji: bez tego silnik musi milczec."""
        return self.czestosc_slotu_dep(slot, dep) >= prog

    def alternatywy(self, slot: str, dep: str, limit: int = 20) -> list[Kandydat]:
        """Nadrzedniki laczace sie z tym slowem w tym slocie, wg logDice."""
        return [
            Kandydat(lemat, f, ld)
            for lemat, f, ld in self.con.execute(
                "SELECT head, f, logdice FROM pary WHERE slot=? AND dep=? "
                "ORDER BY logdice DESC LIMIT ?",
                (slot, dep, limit),
            )
        ]

    def kolokaty(self, head: str, slot: str, limit: int = 200) -> dict[str, float]:
        """Profil dystrybucyjny: co dane slowo bierze w tym slocie."""
        return {
            dep: ld
            for dep, ld in self.con.execute(
                "SELECT dep, logdice FROM pary WHERE head=? AND slot=? "
                "ORDER BY logdice DESC LIMIT ?",
                (head, slot, limit),
            )
        }

    def podobienstwo(self, a: str, b: str, slot: str) -> float:
        """Bliskosc dystrybucyjna dwoch nadrzednikow — cosinus na wektorach logDice.

        Zastepuje plWordNet tam, gdzie ten nie siega: liczy sie z samej bazy,
        wiec obejmuje tez slowa spoza slownika. Warunek 4 reguly detekcji.
        """
        va, vb = self.kolokaty(a, slot), self.kolokaty(b, slot)
        wspolne = va.keys() & vb.keys()
        if not wspolne:
            return 0.0
        licznik = sum(va[k] * vb[k] for k in wspolne)
        norma = math.sqrt(sum(v * v for v in va.values())) * math.sqrt(
            sum(v * v for v in vb.values())
        )
        return licznik / norma if norma else 0.0

    def statystyki(self) -> dict[str, int]:
        return {
            "par": self.con.execute("SELECT COUNT(*) FROM pary").fetchone()[0],
            "slotow": self.con.execute(
                "SELECT COUNT(DISTINCT slot) FROM pary"
            ).fetchone()[0],
        }


def trojki_z_conllu(pliki: Iterable[str | Path]) -> Iterator[Trojka]:
    """Pomocnik: strumien trojek z listy plikow CoNLL-U."""
    from backend.ekstraktor import czytaj_conllu, wyciagnij_trojki

    for plik in pliki:
        for tokeny in czytaj_conllu(str(plik)):
            yield from wyciagnij_trojki(tokeny)

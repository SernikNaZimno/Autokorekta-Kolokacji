"""Ekstrakcja trojek kolokacyjnych z rozbioru zaleznosciowego.

Modul jest celowo niezalezny od Stanzy: pracuje na neutralnej reprezentacji
`Token`, do ktorej prowadza dwa adaptery — z obiektu Stanzy (pipeline runtime
i parsowanie Wikipedii) oraz z surowego CoNLL-U (gotowe korpusy, np. NLPre-PL).
Dzieki temu ta sama logika klucza obowiazuje przy budowie bazy i przy zapytaniu
w czasie pisania; rozjazd miedzy nimi bylby cichym zrodlem falszywych alarmow.

Reguly klucza wynikaja z pomiarow ze Sprintu 0 — patrz docs/USTALENIA-SPIKE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

# --------------------------------------------------------------- reprezentacja


@dataclass(frozen=True, slots=True)
class Token:
    """Jeden token rozbioru — wspolny mianownik Stanzy i CoNLL-U."""

    id: int
    text: str
    lemma: str
    upos: str
    feats: str | None
    head: int
    deprel: str

    @property
    def relacja(self) -> str:
        """Relacja bez podtypu: 'obl:arg' -> 'obl', 'nsubj:pass' -> 'nsubj'."""
        return self.deprel.split(":", 1)[0]

    @property
    def przypadek(self) -> str | None:
        """Przypadek z FEATS, np. 'Case=Acc|Number=Sing' -> 'acc'."""
        if not self.feats:
            return None
        for kv in self.feats.split("|"):
            if kv.startswith("Case="):
                return kv.split("=", 1)[1].lower()
        return None


@dataclass(frozen=True, slots=True)
class Trojka:
    """Krotka trafiajaca do bazy zliczen."""

    head: str
    relacja: str
    przypadek: str | None
    przyimek: str | None
    dep: str

    def klucz(self) -> str:
        """Kanoniczny klucz tekstowy — jedyne miejsce, gdzie ustala sie format.

        Baza i zapytanie runtime musza uzywac tej samej funkcji, inaczej
        kolokacja obecna w korpusie nie zostanie znaleziona przy sprawdzaniu.
        """
        czesci = [self.head, self.relacja]
        if self.przyimek:
            czesci.append(self.przyimek)
        if self.przypadek:
            czesci.append(self.przypadek)
        czesci.append(self.dep)
        return "|".join(czesci)

    def __str__(self) -> str:
        etykieta = self.relacja
        if self.przyimek:
            etykieta += f"+{self.przyimek}"
        if self.przypadek:
            etykieta += f":{self.przypadek}"
        return f"{self.head} --{etykieta}--> {self.dep}"


# --------------------------------------------------------------- konfiguracja


@dataclass(frozen=True, slots=True)
class Regula:
    """Jak budowac klucz dla danej relacji."""

    z_przypadkiem: bool
    z_przyimkiem: bool
    upos_head: frozenset[str]
    upos_dep: frozenset[str]


CZASOWNIK = frozenset({"VERB"})
RZECZOWNIK = frozenset({"NOUN", "PROPN"})
CZ_LUB_RZ = CZASOWNIK | RZECZOWNIK
PRZYMIOTNIK = frozenset({"ADJ"})
PRZYSLOWEK = frozenset({"ADV"})

# Przypadek trafia do klucza TYLKO tam, gdzie jest rzadzony przez nadrzednik.
# Przy uzgodnieniu (amod) i przy stalej wartosci (nsubj = zawsze nom) rozbilby
# jedna kolokacje na kilka rzadszych wpisow — patrz USTALENIA-SPIKE.md.
REGULY: dict[str, Regula] = {
    # rzadzone przez czasownik — przypadek niesie informacje
    "obj": Regula(True, False, CZASOWNIK, RZECZOWNIK),
    "iobj": Regula(True, False, CZASOWNIK, RZECZOWNIK),
    # rzadzone przez czasownik I przyimek — potrzebne oba
    "obl": Regula(True, True, CZASOWNIK, RZECZOWNIK),
    # uzgodnienie, nie rzad — przypadek pominiety
    "amod": Regula(False, False, RZECZOWNIK, PRZYMIOTNIK),
    # zawsze mianownik — przypadek redundantny
    "nsubj": Regula(False, False, CZASOWNIK, RZECZOWNIK),
    # dopelniaczowy/przyimkowy przydawek rzeczownika
    "nmod": Regula(True, True, RZECZOWNIK, RZECZOWNIK),
    # przyslowek nieodmienny
    "advmod": Regula(False, False, CZASOWNIK | PRZYMIOTNIK, PRZYSLOWEK),
}

LEMAT_NEGACJI = "nie"


# ----------------------------------------------------------------- ekstrakcja


def _indeksuj(tokeny: list[Token]) -> tuple[dict[int, Token], dict[int, list[Token]]]:
    wg_id = {t.id: t for t in tokeny}
    dzieci: dict[int, list[Token]] = {}
    for t in tokeny:
        dzieci.setdefault(t.head, []).append(t)
    return wg_id, dzieci


def _zanegowany(head: Token, dzieci: dict[int, list[Token]]) -> bool:
    """Czy nadrzednik ma przy sobie partykule 'nie'."""
    return any(
        d.lemma and d.lemma.lower() == LEMAT_NEGACJI
        for d in dzieci.get(head.id, ())
    )


def _przyimek(tok: Token, dzieci: dict[int, list[Token]]) -> str | None:
    """Przyimek podpiety do tokenu relacja 'case' — np. 'na rynku' -> 'na'."""
    for d in dzieci.get(tok.id, ()):
        if d.relacja == "case" and d.lemma:
            return d.lemma.lower()
    return None


def wyciagnij_trojki(tokeny: list[Token]) -> list[Trojka]:
    """Zwraca trojki kolokacyjne dla jednego zdania."""
    wg_id, dzieci = _indeksuj(tokeny)
    wynik: list[Trojka] = []

    for tok in tokeny:
        regula = REGULY.get(tok.relacja)
        if regula is None or tok.head == 0:
            continue
        head = wg_id.get(tok.head)
        if head is None or not head.lemma or not tok.lemma:
            continue
        if head.upos not in regula.upos_head or tok.upos not in regula.upos_dep:
            continue

        przypadek = tok.przypadek if regula.z_przypadkiem else None

        # Dopelniacz negacji: „podjął decyzję" (acc) i „nie podjął decyzji" (gen)
        # to ta sama kolokacja. Bez tego zliczenia rozdzielaja sie na dwa klucze
        # i oba wychodza rzadsze niz sa — czyli falszywy alarm na kazdym
        # zdaniu przeczacym.
        if (
            przypadek == "gen"
            and tok.relacja in ("obj", "iobj")
            and _zanegowany(head, dzieci)
        ):
            przypadek = "acc"

        przyimek = _przyimek(tok, dzieci) if regula.z_przyimkiem else None

        # 'obl' bez przyimka to zwykle okolicznik narzednikowy/czasu; zostawiamy,
        # ale 'nmod' bez przyimka ma sens tylko w dopelniaczu.
        if tok.relacja == "nmod" and not przyimek and przypadek != "gen":
            continue

        wynik.append(
            Trojka(
                head=head.lemma.lower(),
                relacja=tok.relacja,
                przypadek=przypadek,
                przyimek=przyimek,
                dep=tok.lemma.lower(),
            )
        )

    return wynik


# ------------------------------------------------------------------- adaptery


def z_stanzy(sent) -> list[Token]:
    """Adapter z `stanza.models.common.doc.Sentence`."""
    return [
        Token(
            id=w.id if isinstance(w.id, int) else w.id[0],
            text=w.text,
            lemma=w.lemma or "",
            upos=w.upos or "",
            feats=w.feats,
            head=w.head,
            deprel=w.deprel or "",
        )
        for w in sent.words
    ]


def z_conllu(blok: str) -> list[Token]:
    """Adapter z jednego zdania w formacie CoNLL-U (bez linii pustej)."""
    tokeny: list[Token] = []
    for linia in blok.splitlines():
        if not linia or linia.startswith("#"):
            continue
        pola = linia.split("\t")
        if len(pola) < 8:
            continue
        # pomijamy zakresy tokenow wielowyrazowych (np. '3-4') i wezly puste ('5.1')
        if "-" in pola[0] or "." in pola[0]:
            continue
        tokeny.append(
            Token(
                id=int(pola[0]),
                text=pola[1],
                lemma=pola[2] if pola[2] != "_" else "",
                upos=pola[3],
                feats=pola[5] if pola[5] != "_" else None,
                head=int(pola[6]) if pola[6] != "_" else 0,
                deprel=pola[7],
            )
        )
    return tokeny


def czytaj_conllu(sciezka: str) -> Iterator[list[Token]]:
    """Strumieniuje plik CoNLL-U zdanie po zdaniu (nie laduje calosci do RAM)."""
    with open(sciezka, encoding="utf-8") as f:
        blok: list[str] = []
        for linia in f:
            linia = linia.rstrip("\n")
            if linia:
                blok.append(linia)
            elif blok:
                yield z_conllu("\n".join(blok))
                blok = []
        if blok:
            yield z_conllu("\n".join(blok))


def trojki_z_korpusu(zdania: Iterable[list[Token]]) -> Iterator[Trojka]:
    """Splaszcza strumien zdan w strumien trojek."""
    for tokeny in zdania:
        yield from wyciagnij_trojki(tokeny)

"""Testy filtra zdaniowego.

Przypadki pochodza z realnych probek C4 i Wikipedii (scripts/ocen_filtr.py).
Podzial na „musi przejsc" / „musi wypasc" chroni przed dwoma regresami:
przepuszczeniem boilerplate'u i systematycznym wycinaniem rejestru rzeczowego.
"""

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.czyszczenie import (  # noqa: E402
    na_zdania,
    powod_odrzucenia,
    przefiltruj_dokumenty,
)

# Prawdziwe zdania z korpusu — wszystkie musza przejsc.
DOBRE = [
    "Nie da się ukryć, że piękne samochody zawsze przyciągają nasz wzrok.",
    "AWK jest językiem, który w znacznym stopniu wykorzystuje tablice asocjacyjne.",
    "Każda linia jest podzielona na pola, więc można traktować pierwsze pole jako słowo.",
    "Przykładowo protony muszą zderzyć się z energią 3–10 keV, aby się połączyć.",
    "Protokół z posiedzenia Zarządu odbył się w dniu 16 listopada 2016 roku.",
    "Zarząd spółki podjął wczoraj ważną decyzję o zmianie strategii rynkowej.",
]

# Prawdziwe smieci z korpusu — wszystkie musza wypasc.
ZLE = [
    "Listopad 2016 – Strona 2 – PIROL – PODLASKA IZBA ROLNICZA",
    "Rozmiar paczki: 10 * 6,5 * 1 cm / 3,9 * 2,54 * 0,39 cala",
    "O firmieNasi partnerzyOfertaObsługa posprzedażnaDo pobraniaPromocjeKontakt",
    "Artykuły na temat dentysta chorzów - http://dla-stomatologow.karmag.pl/",
    "Home | Oferta | Produkty | Kontakt | O nas",
    "Smartfon 1828 pln 1369 pln 25% 2019-01-18 21:17:07 RM10342",
]


@pytest.mark.parametrize("zdanie", DOBRE)
def test_poprawna_proza_przechodzi(zdanie):
    """Strata systematyczna (liczby, nazwy wlasne, jednostki) przechylalaby
    normy kolokacyjne przeciw rejestrowi rzeczowemu — patrz USTALENIA."""
    assert powod_odrzucenia(zdanie) is None, f"odrzucone jako: {powod_odrzucenia(zdanie)}"


@pytest.mark.parametrize("zdanie", ZLE)
def test_boilerplate_wypada(zdanie):
    assert powod_odrzucenia(zdanie) is not None


def test_jednostki_nie_uchodza_za_sklejony_naglowek():
    """Regres: regex [male][WIELKIE] lapal 'keV', 'mAh', 'iPhone'."""
    assert powod_odrzucenia("Bateria o pojemności 3000 mAh wystarcza na dobę pracy.") is None


def test_deduplikacja_usuwa_powtorzenia():
    dokumenty = [
        "Zarząd podjął ważną decyzję o zmianie strategii firmy.",
        "Zarząd podjął ważną decyzję o zmianie strategii firmy.",   # dokladny duplikat
        "zarząd podjął ważną decyzję o zmianie strategii firmy!!!",  # rozni sie forma
        "Firma poniosła dotkliwą porażkę na rynku europejskim.",
    ]
    powody: Counter[str] = Counter()
    wynik = list(przefiltruj_dokumenty(dokumenty, powody))
    assert len(wynik) == 2
    assert powody["duplikat"] == 2


def test_bez_deduplikacji_powtorzenia_zostaja():
    dokumenty = ["Zarząd podjął ważną decyzję o zmianie strategii firmy."] * 3
    assert len(list(przefiltruj_dokumenty(dokumenty, deduplikuj=False))) == 3


def test_podzial_na_zdania():
    tekst = "Pierwsze zdanie. Drugie zdanie!\nTrzecie w nowej linii?"
    assert len(na_zdania(tekst)) == 3

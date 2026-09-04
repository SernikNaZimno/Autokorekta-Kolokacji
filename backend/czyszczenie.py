"""Filtrowanie tekstu zrodlowego na poziomie ZDANIA.

Rozpoznanie C4 (scripts/zbadaj_c4.py, 400 dokumentow) pokazalo, ze filtrowanie
calych dokumentow nie dziala: mediana udzialu linii zakonczonych znakiem konca
zdania wynosi 0,333, bo typowy dokument webowy to mieszanka menu, stopki,
klauzuli cookie i wlasciwego artykulu. Kazdy prog na poziomie dokumentu albo
wyrzuca dobra proze, albo wpuszcza boilerplate — przy 400 probkach filtr
dokumentowy przepuszczal 4 smieci na 5 przyjetych.

Dlatego tniemy na zdania i oceniamy kazde osobno. Dokument mieszany oddaje
swoje dobre zdania i gubi menu.

Dlaczego to wazne akurat tu: zrzut menu nawigacyjnego („Produkty Eurorubber",
„Fiat Powertrain Technologies") nie zawiera czasownikow, wiec nie wygeneruje
trojek obj — ale wygeneruje amod i nmod, ktore stanowia 48% wszystkich trojek.
Bez filtra nazwy handlowe trafilyby do bazy jako norma kolokacyjna.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DIAKRYTYKI = frozenset("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

# Slowa funkcyjne — proza ma ich duzo, listy produktow i menu prawie wcale.
# Lista musi byc szeroka: przy krotkiej („i w na sie z do…") prog 10% odrzucal
# poprawne zdania w rodzaju „Kazda linia jest podzielona na pola, wiec mozna
# traktowac…", bo jej spojniki i partykuly do niej nie nalezaly.
STOP = frozenset(
    """
    w na do z ze o po za od przez dla przy pod nad bez przed między wśród
    wobec około ku u ponad obok wzdłuż podczas dzięki wraz spod znad
    i a ale oraz lub albo czy że żeby aby gdy gdyby jeśli jeżeli ponieważ
    bo więc zatem jednak choć chociaż niż jak jako lecz ani czyli
    się to ten ta te tego tej tym tych tam ta który która które którego
    której których jego jej ich on ona ono oni one nam nas wam was mu jej
    co kto wszystko wszyscy każdy każda inne innych taki taka takie
    nie już tylko także też bardzo tak można trzeba może właśnie nawet
    jeszcze zawsze nigdy gdzie kiedy dlatego przede wszystkim
    jest są był była było były będzie będą być ma mają mamy miał miała
    zostać został została zostały mogą mógł mogła
    """.split()
)

URL = re.compile(r"https?://|www\.|@[\w.]+\.\w{2,}")
# Separatory typowe dla nawigacji: „Start » Oferta » Produkty", „Home | O nas"
NAWIGACJA = re.compile(r"[|»›→·]|\s>\s|\s-\s\S+\s-\s")
# Sklejone naglowki: „MisjaRozwójWydarzeniaWyróżnienia". Wymagamy DWOCH przejsc
# male->wielkie w obrebie jednego tokenu — pojedyncze wystepuje w zwyklych
# jednostkach i nazwach („keV", „mAh", „iPhone") i wycinalo poprawne zdania.
SKLEJONE = re.compile(r"\S*[a-ząćęłńóśźż][A-ZĄĆĘŁŃÓŚŹŻ]\S*[a-ząćęłńóśźż][A-ZĄĆĘŁŃÓŚŹŻ]")
KONIEC_ZDANIA = re.compile(r"(?<=[.!?…])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„\"])")

MIN_SLOW = 5
MAX_SLOW = 80


@dataclass(frozen=True, slots=True)
class Statystyki:
    zdan_wejscie: int = 0
    zdan_wyjscie: int = 0
    odrzuconych: int = 0

    @property
    def przezywalnosc(self) -> float:
        return self.zdan_wyjscie / self.zdan_wejscie if self.zdan_wejscie else 0.0


def na_zdania(tekst: str) -> list[str]:
    """Wstepny podzial na zdania — tani, przed uruchomieniem parsera.

    Nie zastepuje tokenizatora Stanzy; ma tylko dac jednostki do oceny jakosci,
    zeby nie placic za parsowanie menu nawigacyjnego.
    """
    zdania: list[str] = []
    for linia in tekst.splitlines():
        linia = linia.strip()
        if linia:
            zdania.extend(z.strip() for z in KONIEC_ZDANIA.split(linia) if z.strip())
    return zdania


def powod_odrzucenia(zdanie: str) -> str | None:
    """Zwraca powod odrzucenia albo None, jesli zdanie jest zdatne."""
    slowa = re.findall(r"[^\W\d_]+", zdanie, re.UNICODE)
    n = len(slowa)

    if n < MIN_SLOW:
        return "za krotkie"
    if n > MAX_SLOW:
        return "za dlugie"          # zlepek bez interpunkcji, nie zdanie
    if not zdanie.rstrip().endswith((".", "!", "?", "…")):
        return "brak konca zdania"  # naglowek, pozycja menu, etykieta
    if URL.search(zdanie):
        return "url"
    if NAWIGACJA.search(zdanie):
        return "nawigacja"
    if SKLEJONE.search(zdanie):
        return "sklejone naglowki"

    male = [s.lower() for s in slowa]
    if sum(1 for s in male if s in STOP) / n < 0.10:
        return "malo slow funkcyjnych"

    znaki = len(zdanie)
    if sum(1 for c in zdanie if c in DIAKRYTYKI) / znaki < 0.010:
        return "brak diakrytykow"   # nie po polsku albo bez ogonkow
    # Progi ponizej sa celowo lagodne. Odsiewanie zdan z data albo nazwa wlasna
    # to strata SYSTEMATYCZNA, nie losowa: przechylalaby normy kolokacyjne
    # przeciw rejestrowi rzeczowemu. Korpusu mamy w nadmiarze, wiec wolimy
    # przepuscic zdanie z liczbami niz wyciac cala klase zdan.
    if sum(1 for c in zdanie if c.isdigit()) / znaki > 0.15:
        return "duzo cyfr"          # cennik, specyfikacja, numer katalogowy
    # Wielkie litery w srodku: „Fiat Powertrain Technologies EATON Mecc Alte"
    if sum(1 for s in slowa[1:] if s[:1].isupper()) / n > 0.55:
        return "duzo wielkich liter"

    return None


def zdatne_zdania(tekst: str) -> list[str]:
    """Zdania nadajace sie do ekstrakcji kolokacji."""
    return [z for z in na_zdania(tekst) if powod_odrzucenia(z) is None]


def _odcisk(zdanie: str) -> int:
    """Skrot zdania odporny na roznice interpunkcji i wielkosci liter."""
    rdzen = " ".join(re.findall(r"[^\W\d_]+", zdanie.lower()))
    return hash(rdzen)


def przefiltruj_dokumenty(dokumenty, licznik_powodow=None, deduplikuj=True):
    """Strumien dokumentow -> strumien zdatnych, unikalnych zdan.

    Deduplikacja jest konieczna przy zrodlach webowych: w probce C4 „Protokół
    z posiedzenia Zarządu…" wystapil dwukrotnie w 300 dokumentach. Powtorzony
    boilerplate (stopki, klauzule, szablony ogloszen) zawyzalby zliczenia
    kolokacji proporcjonalnie do tego, jak czesto szablon wystepuje w sieci —
    czyli tworzylby fałszywa norme jezykowa z tekstu jednego autora.
    """
    widziane: set[int] = set()
    for tekst in dokumenty:
        for zdanie in na_zdania(tekst):
            powod = powod_odrzucenia(zdanie)
            if powod is not None:
                if licznik_powodow is not None:
                    licznik_powodow[powod] += 1
                continue
            if deduplikuj:
                odcisk = _odcisk(zdanie)
                if odcisk in widziane:
                    if licznik_powodow is not None:
                        licznik_powodow["duplikat"] += 1
                    continue
                widziane.add(odcisk)
            yield zdanie

"""Filtr slownikowy oparty na Morfeuszu — odsiewa lematy, ktore nie sa slowami.

Przebieg probny wyrzucil `złdo` z czestoscia 18 na zaledwie 50 tys. tokenow.
To sklejka z „100,00 zł do koszyka" ze stron sklepowych. Regula na ksztalcie
napisu jej nie zlapie (jest alfabetyczna i ma sensowna dlugosc), ale Morfeusz
zwraca dla niej `ign` — nie ma takiego slowa w polszczyznie.

Takie wpisy sa gorsze niz zwykly szum. Wystepuja w jednym powtarzanym szablonie,
wiec ich profile brzegowe sa skrajnie waskie, a logDice — wysoki. Trafiaja na
szczyt listy kolokacji, czyli dokladnie tam, gdzie silnik szuka alternatyw.

Filtr siedzi w pipelinie korpusowym, a nie w `ekstraktor.py`, zeby ten drugi
pozostal niezalezny od Morfeusza i dzialal wszedzie tam, gdzie jest tylko rozbior.
"""

from __future__ import annotations

from typing import Iterable, Iterator


class WalidatorSlownikowy:
    """Sprawdza, czy lemat jest slowem polskim. Wyniki sa cache'owane.

    Slownictwo korpusu jest ograniczone (rzedu setek tysiecy lematow), wiec
    cache po pierwszym przebiegu praktycznie eliminuje koszt wywolan Morfeusza.
    """

    def __init__(self) -> None:
        import morfeusz2

        self._morfeusz = morfeusz2.Morfeusz(generate=False)
        self._cache: dict[str, bool] = {}
        self.sprawdzonych = 0
        self.odrzuconych = 0

    def znane(self, lemat: str) -> bool:
        wynik = self._cache.get(lemat)
        if wynik is None:
            try:
                analizy = self._morfeusz.analyse(lemat)
                wynik = not all(i[2][2] == "ign" for i in analizy)
            except Exception:
                wynik = False
            self._cache[lemat] = wynik
        return wynik

    def filtruj(
        self, krotki: Iterable[tuple[str, str, str, str]]
    ) -> Iterator[tuple[str, str, str, str]]:
        """Przepuszcza tylko trojki, ktorych OBA lematy sa slowami."""
        for krotka in krotki:
            self.sprawdzonych += 1
            if self.znane(krotka[0]) and self.znane(krotka[2]):
                yield krotka
            else:
                self.odrzuconych += 1

    @property
    def statystyki(self) -> dict[str, int | float]:
        return {
            "sprawdzonych": self.sprawdzonych,
            "odrzuconych": self.odrzuconych,
            "udzial_odrzuconych": (
                self.odrzuconych / self.sprawdzonych if self.sprawdzonych else 0.0
            ),
            "rozmiar_cache": len(self._cache),
        }

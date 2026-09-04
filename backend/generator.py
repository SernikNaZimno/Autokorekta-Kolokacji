"""Generowanie form fleksyjnych sugestii przez Morfeusza.

Sugestia „podjąć" jest bezuzyteczna, jesli wstawimy ja do zdania w bezokoliczniku.
Trzeba ja odmienic tak, zeby pasowala do zdania — a przy zmianie czasownika
czesto takze przypadek rzeczownika, bo nowy czasownik moze rzadzic innym:

    *odniósł porażkę  ->  doznał porażki      (biernik -> dopelniacz)

Dwie pulapki zmierzone w Sprincie 0 (docs/USTALENIA-SPIKE.md):

1. **Formy aglutynacyjne.** Dla `ponieść` Morfeusz zwraca `poniósł` (`:nagl`)
   ORAZ `poniosł` (`:agl`, czlon form typu „poniosłem"). Bez filtru podsuniemy
   `poniosł`, co czytelnik odbierze jako literowke — czyli gorzej niz brak
   sugestii, bo podwazy zaufanie do calego narzedzia.
2. **Rodzaj to zbior kropkowany**, nie wartosc: `praet:sg:m1.m2.m3:perf`.
   Porownywanie tagow jako napisow nie dziala.
"""

from __future__ import annotations

from dataclasses import dataclass

PRZYPADKI = frozenset({"nom", "gen", "dat", "acc", "inst", "loc", "voc"})


def _wartosci(tag: str) -> set[str]:
    """Wszystkie wartosci tagu jako plaski zbior — rozbija czlony kropkowane.

    'praet:sg:m1.m2.m3:perf' -> {'praet','sg','m1','m2','m3','perf'}
    """
    wartosci: set[str] = set()
    for czlon in tag.split(":"):
        wartosci.update(czlon.split("."))
    return wartosci


def _klasa(tag: str) -> str:
    """Klasa fleksyjna — pierwszy czlon tagu ('subst', 'praet', 'fin'...)."""
    return tag.split(":", 1)[0]


@dataclass(frozen=True, slots=True)
class Forma:
    tekst: str
    tag: str


class GeneratorForm:
    """Odmienia lematy do form pasujacych do kontekstu zdania."""

    def __init__(self) -> None:
        import morfeusz2

        self._m = morfeusz2.Morfeusz(generate=True)
        self._cache: dict[str, list[Forma]] = {}

    def tag_formy(self, forma: str) -> str | None:
        """Tag Morfeusza dla konkretnej formy wyrazowej.

        Istotne: wzorzec do generacji MUSI pochodzic z tagsetu Morfeusza.
        Stanza opisuje formy cechami UD („Aspect=Perf|Gender=Masc"), ktore
        z tagami Morfeusza („praet:sg:m1.m2.m3:perf") nie maja wspolnych
        wartosci — dopasowanie po nich zwracaloby zawsze pustke.
        """
        try:
            analizy = self._m.analyse(forma)
        except Exception:
            return None
        tagi = [i[2][2] for i in analizy if i[2][2] != "ign"]
        return tagi[0] if tagi else None

    def formy(self, lemat: str) -> list[Forma]:
        """Pelny paradygmat lematu, z pominieciem form aglutynacyjnych."""
        wynik = self._cache.get(lemat)
        if wynik is None:
            try:
                surowe = self._m.generate(lemat)
            except Exception:
                surowe = []
            wynik = [
                Forma(i[0], i[2])
                for i in surowe
                # `:agl` to czlon form zlozonych („poniosł" + „em"), nie
                # samodzielne slowo. Podsunieta czytelnikowi wyglada jak blad.
                if ":agl" not in i[2]
            ]
            self._cache[lemat] = wynik
        return wynik

    def dopasuj(
        self, lemat: str, wzor_tag: str, przypadek: str | None = None
    ) -> Forma | None:
        """Forma lematu najlepiej pasujaca do tagu wzorcowego.

        `przypadek` nadpisuje przypadek ze wzorca — uzywane, gdy nowy czasownik
        rzadzi innym przypadkiem niz ten, ktory napisal uzytkownik.
        """
        kandydaci = self.formy(lemat)
        if not kandydaci:
            return None

        oczekiwane = _wartosci(wzor_tag)
        if przypadek:
            oczekiwane = (oczekiwane - PRZYPADKI) | {przypadek}

        klasa_wzorca = _klasa(wzor_tag)
        najlepszy: Forma | None = None
        najlepszy_wynik = -1

        for forma in kandydaci:
            # Klasa fleksyjna musi sie zgadzac: nie podsuwamy bezokolicznika
            # w miejsce formy czasu przeszlego.
            if _klasa(forma.tag) != klasa_wzorca:
                continue
            wartosci = _wartosci(forma.tag)
            if przypadek and przypadek not in wartosci:
                continue
            wynik = len(wartosci & oczekiwane)
            if wynik > najlepszy_wynik:
                najlepszy_wynik, najlepszy = wynik, forma

        return najlepszy

    def odmien_jak(
        self, lemat_docelowy: str, forma_wzorcowa: str, przypadek: str | None = None
    ) -> Forma | None:
        """Odmienia lemat tak, jak odmieniona jest podana forma wzorcowa.

        To jest wejscie uzywane przez silnik: bierze slowo z tekstu uzytkownika
        („odniósł"), odczytuje jego tag Morfeuszem i generuje w tej samej formie
        wyraz zaproponowany („doznał").
        """
        wzor = self.tag_formy(forma_wzorcowa)
        if wzor is None:
            return None
        return self.dopasuj(lemat_docelowy, wzor, przypadek)

    def przypadek_formy(self, tag: str) -> str | None:
        for w in _wartosci(tag):
            if w in PRZYPADKI:
                return w
        return None

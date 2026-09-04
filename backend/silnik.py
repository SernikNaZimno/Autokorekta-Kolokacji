"""Silnik detekcji bledow kolokacyjnych.

Regula NIE brzmi „para rzadka => blad". Pomiar na treebanku PDB pokazal, ze
**90,9% par kolokacyjnych wystepuje dokladnie raz**, wiec przy kazdym realnym
korpusie ogromna czesc poprawnej polszczyzny wyglada na rzadka. Taka regula
bylaby generatorem falszywych alarmow.

Pytamy zamiast tego: *czy w tym samym slocie stoi duzo lepsza alternatywa,
semantycznie bliska temu, co napisano.* Test wzgledny, nie bezwzgledny.

Alarm wymaga czterech warunkow NARAZ:

  1. Slot jest zbadany — inaczej milczymy. Domyslna odpowiedz to „nie wiem",
     nie „blad". To ten warunek trzyma precyzje; bez niego reszta nie ma
     znaczenia, bo alternatywy liczone z dwoch obserwacji sa przypadkowe.
  2. Obserwowana para ma niski logDice.
  3. Istnieje alternatywa o wysoko wyzszym logDice.
  4. Alternatywa jest semantycznie bliska temu, co napisano — inaczej przy
     kazdym rzeczowniku podpowiadalibysmy po prostu najczestszy czasownik.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.baza import BazaKolokacji, slot_z_trojki
from backend.ekstraktor import Token, wyciagnij_trojki

# --- progi -------------------------------------------------------------------
# Kalibrowane wstepnie; Etap 6 ustawi je na krzywej precyzja/pokrycie.

PROG_SLOTU = 50          # ile obserwacji rzeczownika w slocie, zeby sie odezwac
PROG_AKCEPTACJI = 7.0    # powyzej tego para jest uznana za poprawna
PROG_PRZEWAGI = 3.0      # o ile alternatywa musi bic obserwacje
PROG_PODOBIENSTWA = 0.15 # minimalna bliskosc dystrybucyjna alternatywy

# Czasowniki lekkie — semantycznie „wyblakle", nosnikiem znaczenia jest
# rzeczownik. Podstawienie takiego czasownika w miejsce wlasciwego kolokatu to
# najczestszy polski blad kolokacyjny („*zrobić decyzję").
#
# Sa tu z konkretnego powodu: pomiar wykazal podobienstwo dystrybucyjne
# podjąć~zrobić = 0,000, wiec warunek 4 oparty wylacznie na profilach
# odrzucalby wlasnie te klase bledow. Czasownik lekki spelnia warunek 4
# z definicji — ale warunki 1-3 nadal obowiazuja, wiec dobrze poswiadczone
# zwiazki („mieć rację", „dać radę") nie zostana zgloszone, bo maja wysoki
# logDice i wypadaja juz na warunku 2.
#
# UWAGA: to hipoteza do zweryfikowania na pelnym korpusie. Przy 100 mln tokenow
# `zrobić` bedzie mialo setki kolokatow i przeciecie z `podjąć` moze okazac sie
# niezerowe — wtedy ta lista stanie sie zbedna.
CZASOWNIKI_LEKKIE = frozenset(
    {"robić", "zrobić", "mieć", "dać", "dawać", "czynić", "uczynić", "posiadać"}
)


@dataclass(frozen=True, slots=True)
class Sugestia:
    """Jedna propozycja poprawki."""

    id_tokenu: int
    oryginal: str          # slowo z tekstu
    lemat_oryginalu: str
    propozycja: str        # forma do wstawienia, juz odmieniona
    lemat_propozycji: str
    nowy_przypadek_dopelnienia: str | None  # jesli trzeba odmienic tez dopelnienie
    id_dopelnienia: int | None
    forma_dopelnienia: str | None
    logdice_oryginalu: float
    logdice_propozycji: float
    uzasadnienie: str

    @property
    def przewaga(self) -> float:
        return self.logdice_propozycji - self.logdice_oryginalu


class SilnikKolokacji:
    def __init__(
        self,
        baza: BazaKolokacji,
        generator=None,
        prog_slotu: int = PROG_SLOTU,
        prog_akceptacji: float = PROG_AKCEPTACJI,
        prog_przewagi: float = PROG_PRZEWAGI,
        prog_podobienstwa: float = PROG_PODOBIENSTWA,
    ) -> None:
        self.baza = baza
        self.generator = generator
        self.prog_slotu = prog_slotu
        self.prog_akceptacji = prog_akceptacji
        self.prog_przewagi = prog_przewagi
        self.prog_podobienstwa = prog_podobienstwa

    # --- warunek 4 ---
    def _semantycznie_bliskie(self, obserwowany: str, kandydat: str, slot: str) -> bool:
        if obserwowany in CZASOWNIKI_LEKKIE:
            return True
        podobienstwo = self.baza.podobienstwo(obserwowany, kandydat, slot)
        return podobienstwo >= self.prog_podobienstwa

    def sprawdz(self, tokeny: list[Token]) -> list[Sugestia]:
        """Analizuje jedno zdanie i zwraca sugestie (czesto pusta liste)."""
        wg_id = {t.id: t for t in tokeny}
        sugestie: list[Sugestia] = []

        for trojka in wyciagnij_trojki(tokeny):
            # Na razie sprawdzamy tylko czasownik + dopelnienie blizsze; to
            # najlepiej poswiadczony i najbardziej jednoznaczny typ kolokacji.
            if trojka.relacja != "obj":
                continue
            slot = slot_z_trojki(trojka)

            # WARUNEK 1 — bez tego milczymy
            if not self.baza.slot_zbadany(slot, trojka.dep, self.prog_slotu):
                continue

            # WARUNEK 2
            ld_obs = self.baza.logdice(trojka.head, slot, trojka.dep)
            if ld_obs >= self.prog_akceptacji:
                continue

            # WARUNEK 3
            kandydaci = self.baza.alternatywy(slot, trojka.dep, limit=10)
            if not kandydaci:
                continue
            najlepszy = kandydaci[0]
            if najlepszy.lemat == trojka.head:
                continue
            if najlepszy.logdice - ld_obs < self.prog_przewagi:
                continue

            # WARUNEK 4
            if not self._semantycznie_bliskie(trojka.head, najlepszy.lemat, slot):
                continue

            sugestia = self._zbuduj_sugestie(
                tokeny, wg_id, trojka, slot, najlepszy, ld_obs
            )
            if sugestia:
                sugestie.append(sugestia)

        return sugestie

    def _zbuduj_sugestie(self, tokeny, wg_id, trojka, slot, kandydat, ld_obs):
        """Odmienia propozycje do formy pasujacej do zdania."""
        # Odnajdujemy tokeny odpowiadajace trojce.
        tok_head = tok_dep = None
        for t in tokeny:
            if t.relacja == "obj" and t.lemma.lower() == trojka.dep:
                nadrzednik = wg_id.get(t.head)
                if nadrzednik and nadrzednik.lemma.lower() == trojka.head:
                    tok_head, tok_dep = nadrzednik, t
                    break
        if tok_head is None or tok_dep is None:
            return None

        if self.generator is None:
            forma_czasownika, forma_dopelnienia, nowy_przyp = (
                kandydat.lemat,
                None,
                None,
            )
        else:
            # Wzorzec bierzemy z formy napisanej przez uzytkownika, a nie
            # z cech UD — tagsety Stanzy i Morfeusza sa rozlaczne.
            f = self.generator.odmien_jak(kandydat.lemat, tok_head.text)
            forma_czasownika = f.tekst if f else kandydat.lemat

            # Nowy czasownik moze rzadzic innym przypadkiem — sprawdzamy,
            # w jakim przypadku wystepuje z tym rzeczownikiem najczesciej.
            nowy_przyp = self._przypadek_rzadzony(kandydat.lemat, trojka.dep)
            forma_dopelnienia = None
            if nowy_przyp and nowy_przyp != trojka.przypadek:
                fd = self.generator.odmien_jak(
                    tok_dep.lemma, tok_dep.text, przypadek=nowy_przyp
                )
                forma_dopelnienia = fd.tekst if fd else None

        return Sugestia(
            id_tokenu=tok_head.id,
            oryginal=tok_head.text,
            lemat_oryginalu=trojka.head,
            propozycja=forma_czasownika,
            lemat_propozycji=kandydat.lemat,
            nowy_przypadek_dopelnienia=nowy_przyp if forma_dopelnienia else None,
            id_dopelnienia=tok_dep.id if forma_dopelnienia else None,
            forma_dopelnienia=forma_dopelnienia,
            logdice_oryginalu=ld_obs,
            logdice_propozycji=kandydat.logdice,
            uzasadnienie=(
                f"„{trojka.head} {trojka.dep}" + "” jest w korpusie "
                + ("nieobecne" if ld_obs == 0 else f"rzadkie (logDice {ld_obs:.1f})")
                + f"; „{kandydat.lemat} {trojka.dep}” — {kandydat.f} wystąpień, "
                f"logDice {kandydat.logdice:.1f}"
            ),
        )

    def _przypadek_rzadzony(self, czasownik: str, rzeczownik: str) -> str | None:
        """W jakim przypadku ten czasownik laczy sie z tym rzeczownikiem.

        Wybieramy po CZESTOSCI, nie po logDice. To sa odpowiedzi na dwa rozne
        pytania: logDice mierzy sile skojarzenia wzgledem profili brzegowych,
        wiec slot rzadki, ale o waskim profilu, potrafi przebic slot czesty.

        Zmierzone na korpusie 5 mln tokenow dla (podjac, proba):

            obj:acc   f=94   logDice 11,71
            obj:gen   f= 8   logDice 12,09   <- wygrywalo

        Wynikiem bylo „podjela proby" zamiast „podjela probe" — forma
        niegramatyczna, czyli gorsza niz brak sugestii, bo podwaza zaufanie
        do calego narzedzia.

        Osiem wystapien w dopelniaczu to najpewniej resztka po negacji
        („nie podjeto proby") albo blad rozbioru. Slot obj:gen sam w sobie
        jest poprawny — rzadza nim `uzywac`, `dokonac`, `udzielic` — wiec nie
        da sie go po prostu odrzucic.
        """
        najlepszy, najlepsza_f = None, 0
        for przypadek in ("acc", "gen", "dat", "inst"):
            f = self.baza.czestosc_pary(czasownik, f"obj:{przypadek}", rzeczownik)
            if f > najlepsza_f:
                najlepsza_f, najlepszy = f, przypadek
        return najlepszy

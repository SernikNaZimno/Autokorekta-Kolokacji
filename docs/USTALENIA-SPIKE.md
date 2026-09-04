# Ustalenia ze Sprintu 0 (spike derysykujacy)

Wnioski z uruchomionego kodu, nie z zalozen. Wiazace dla Etapow 1-3.

## Wynik bramek

| Test | Wynik | Dowod |
|---|---|---|
| 0.2 Morfeusz analiza + **generacja** | **ZDANY** | `scripts/spike_morfeusz.py` → pelny obieg `*odniosl porazke` ⇒ `doznał porażki` |
| 0.3 Stanza rozbior + opoznienie | **ZDANY** | `scripts/spike_stanza.py`, `scripts/spike_latency.py` |
| 0.1 Critique API w Wordzie | oczekuje | do wykonania recznie w Script Lab |

Wersje: `stanza==1.14.0`, `torch==2.14.0`, `morfeusz2==1.99.15` (kolo `cp310-abi3`,
natywnie na Py 3.12/Windows), model `stanza pl` (PDB).

## Morfeusz 2

- **Generacja dziala** — `Morfeusz(generate=True).generate(lemat)` zwraca pelny paradygmat.
  To byl cichy warunek konieczny funkcji podmiany; jest spelniony.
- **Aspekt jest w tagu**: `podjąć` → `praet:sg:m1.m2.m3:perf`, `podejmować` → `...:imperf`.
  Podmiana musi zachowac aspekt — da sie to sprawdzic bez dodatkowego slownika.
- **Filtrowac na `nagl`.** Dla `ponieść` generator zwraca *dwie* formy praet:
  `poniósł` (`:nagl`) i `poniosł` (`:agl`, do form aglutynacyjnych typu „poniosłem").
  Bez filtru sugerowalibysmy `poniosł`, co wyglada jak literowka.
- **Rodzaj to zbior kropkowany**, nie wartosc: `praet:sg:m1.m2.m3`. Dopasowywanie
  tagow musi rozbijac po `.`, nie porownywac napisow.
- **Diakrytyki obowiazkowe** — `odniosl` bez ogonkow daje `tag=ign`. Wejscie z Worda
  bedzie mialo diakrytyki, ale walidacja musi to wychwycic i nie zglaszac falszywych alarmow.

## Stanza

- Trojki wychodza dokladnie takie, jakich potrzebujemy:
  `zrobić --obj:acc--> decyzja`, `odnieść --obj:acc--> porażka`.
- **Opoznienie skaluje sie PODLINIOWO** (wbrew pierwotnej obawie). Stały narzut ~130 ms
  na wywolanie, potem batchowanie amortyzuje:

  | slow | ms | ms/slowo |
  |---:|---:|---:|
  | 10 | 152 | 15,2 |
  | 40 | 244 | 6,1 |
  | 160 | 516 | 3,2 |

  Dlugie akapity sa *tansze* per slowo. Budzet 750 ms debounce trzyma sie z zapasem.
  Dwa pomiary sie rozjezdzaja (31 slow @ 580 ms vs 40 slow @ 244 ms) — roznica to
  srednia-z-5 vs mediana-z-3 i powtorzone identyczne zdania; realny przedzial 250–600 ms.
- Cache po zdaniu (nie po akapicie) zbija koszt przeparsowania do ~157 ms.
- Stanza degraduje lagodnie bez diakrytykow (`zrobil` → lemat `zrobić`), w przeciwienstwie
  do Morfeusza. Asymetria bez znaczenia praktycznego, ale warta zapamietania.

## Poprawki do schematu klucza bazy (WAZNE)

Plan zakladal jednolity klucz `(lemat_head, relacja, przypadek, lemat_dep)`.
Uruchomienie ekstraktora pokazalo, ze **przypadek jest informatywny tylko dla czesci relacji**,
a wpisywanie go wszedzie rozbija zliczenia:

| Relacja | Przypadek w kluczu? | Uzasadnienie |
|---|---|---|
| `obj`, `iobj` | **tak** | Rzadzony przez czasownik, niesie informacje (`doznać`+gen vs `ponieść`+acc) |
| `obl` | **tak**, + przyimek | Rzadzony przez czasownik i przyimek |
| `amod` | **NIE** | Przymiotnik tylko *uzgadnia sie* z rzeczownikiem. Zaobserwowano `decyzja --amod:acc--> ważny` i `rynek --amod:loc--> trudny` — ta sama kolokacja „ważna decyzja" rozpadlaby sie na 7 przypadkow |
| `nsubj` | **NIE** | Zawsze `nom`, redundantny |
| `nmod` | **tak** (gen) | Dopelniaczowy, informatywny |
| `advmod` | nie dotyczy | Przyslowek nieodmienny |

### Dopelniacz negacji — do obslugi w Etapie 2

W polskim negacja zmienia biernik na dopelniacz:

> „podjął **decyzję**" (acc) — „nie podjął **decyzji**" (gen)

To **ta sama kolokacja**. Bez normalizacji zliczenia rozdziela sie na dwa klucze
i oba wyjda rzadsze niz sa naprawde — co przy progu „para rzadka ⇒ alarm" generuje
falszywe alarmy dokladnie na zdaniach przeczacych. Ekstraktor musi wykrywac `advmod`
z lematem `nie` przy czasowniku i mapowac wtedy `obj:gen` → `obj:acc`.

---

# Ustalenia z Etapu 1 (ekstraktor na skale)

Ekstraktor puszczony przez caly treebank **UD Polish-PDB** (350 tys. tokenow, zloty
standard): 22 152 zdania, 107 247 trojek, 88 704 unikalne pary.
Skrypty: `scripts/statystyki_korpusu.py`, `scripts/analiza_rzadkosci.py`.

## Sygnal kolokacyjny istnieje

Najczestsze `obj:acc` to autentyczne polskie kolokacje — nie szum:
`zwracać uwagę`, `podjąć decyzję`, `zabrać głos`, `pełnić funkcję`, `brać udział`.

Bramka zdana z duzym zapasem:

| para | f | logDice |
|---|---:|---:|
| `podjąć + decyzja` | 13 | **12,68** |
| `podejmować + decyzja` | 10 | **12,46** |
| `przyjąć + decyzja` | 2 | 9,51 |
| `zrobić + decyzja` | 0 | 0,00 |

Para aspektowa `podjąć`/`podejmować` wychodzi jako dwa wpisy o niemal rownym
logDice — aspekt zachowany zgodnie z zalozeniem.

## Skazenie domenowe

Szczyt listy zajmuje `wykonywać + skok` (51x, logDice 13,5), obok `trzymać + piłka`.
PDB zawiera sprawozdania sportowe. **Domena korpusu przecieka do norm kolokacyjnych.**
Dla docelowej bazy: mieszac zrodla i rozwazyc wazenie, zeby jedna domena nie
narzucala normy calemu jezykowi.

## REWIZJA ARCHITEKTURY: regula detekcji z planu jest bledna

Rozklad czestosci par w PDB:

| f | par | udzial | skumulowane |
|---:|---:|---:|---:|
| 1 | 80 654 | **90,9%** | 90,9% |
| 2 | 5 031 | 5,7% | 96,6% |
| ≥3 | 3 019 | 3,4% | 100% |

**Ponad 90% par wystepuje dokladnie raz.** Reguła „para rzadka ⇒ alarm" jest wiec
nie do uzycia: przy kazdym realnym rozmiarze korpusu ogromna czesc *poprawnej*
polszczyzny wyglada na rzadka. Zbudowalibysmy generator falszywych alarmow.

`zrobić + decyzja` ma logDice 0 — ale **dokladnie te sama wartosc** ma kazda
poprawna kolokacja nieobecna w korpusie. Sama nieobecnosc nie niesie informacji.

### Regula wlasciwa — test wzgledny, nie bezwzgledny

Nie pytamy „czy ta para jest rzadka", tylko „**czy w tym slocie stoi duzo lepsza
alternatywa, semantycznie bliska temu, co napisano**". Alarm wymaga *wszystkich*
czterech warunkow:

1. **Slot jest zbadany** — czestosc brzegowa rzeczownika w tym slocie ≥ N
   (wstepnie 50). Jesli nie wiemy nic o `porażka` jako dopelnieniu, milczymy.
   To ten warunek trzyma precyzje; bez niego reszta nie ma znaczenia.
2. Obserwowana para ma niski logDice (warunek konieczny, dalece niewystarczajacy).
3. Istnieje alternatywa w tym samym slocie o wysokim logDice.
4. **Alternatywa jest semantycznie bliska** obserwowanemu slowu (plWordNet:
   synonim / hiperonim / wspoldzielone kolokaty). To odroznia *blad kolokacyjny*
   od *innego znaczenia* — bez tego przy kazdym rzeczowniku podpowiadalibysmy
   najczestszy czasownik.

Punkt 1 to nowy element wzgledem planu i jest kluczowy: **domyslna odpowiedz
silnika brzmi „nie wiem", nie „blad"**.

## Ile korpusu potrzeba

Krzywa pokrycia przy progu f≥3 (przyrosty **rosna**, wiec daleko do nasycenia):

| % korpusu | tokenow | par f≥3 | przyrost |
|---:|---:|---:|---:|
| 12,5% | 43 747 | 197 | +197 |
| 25% | 87 494 | 784 | +587 |
| 50% | 174 989 | 1 479 | +695 |
| 75% | 262 483 | 2 176 | +697 |
| 100% | 349 978 | 3 019 | +843 |

8 626 solidnych par na milion tokenow, przy czym ekstrapolacja liniowa **zanizza**
(krzywa wklesla). Cel 100 mln tokenow z planu daje **co najmniej ~860 tys. par**
i pozostaje wlasciwy — PDB jest o dwa rzedy wielkosci za maly, co widac po tym,
ze `porażka` jako dopelnienie ma w calym treebanku dwa wystapienia.

## Nastepny krok

Etap 3: pipeline korpusowy w Colabie (Wikipedia PL + zrodla z innych domen,
zeby nie powtorzyc skazenia sportowego PDB).

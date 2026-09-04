# Ustalenia z korpusu 5 mln tokenow

Pierwszy przebieg na prawdziwym korpusie: Wikipedia PL + C4 pl, 3+2 mln tokenow,
7 087 s na T4. Wyjscie: 1 576 800 trojek (`data/trojki_5M.tsv.gz`, 10 MB).

Baza: 925 924 pary przed przycieciem, **90 449 po** progu f>=3. Plik 39,3 MB,
budowa 14,1 s.

## PYTANIE 1 — czy sloty sa juz zbadane

Liczba rozstrzygajaca budzet korpusu. Prog to 50.

| rzeczownik (obj:acc) | PDB 350 tys. | korpus 5 mln | status |
|---|---:|---:|---|
| `decyzja` | 34 | **405** | ZBADANY |
| `uwaga` | — | 778 | ZBADANY |
| `funkcja` | — | 676 | ZBADANY |
| `próba` | — | 217 | ZBADANY |
| `klęska` | — | 64 | ZBADANY |
| `porażka` | 2 | 33 | wciaz za malo |

**Przy 5 mln tokenow silnik ma juz o czym mowic.** `porażka` potrzebuje jeszcze
okolo dwukrotnosci korpusu.

## PYTANIE 2 — czy sygnal przetrwal przejscie z treebanku na web

Tak, i to czysto. Najczestsze `obj:acc` to podrecznikowe polskie kolokacje:
`brać udział`, `pełnić funkcję`, `odgrywać rolę`, `zwrócić uwagę`, `podjąć decyzję`,
`wywrzeć wpływ`, `odnieść sukces`, `sprawować władzę`.

**Nie ma skazenia sportowego**, ktore dominowalo w PDB (`wykonywać skok`,
`trzymać piłka`). Mieszanie zrodel zadzialalo.

| para | f | logDice |
|---|---:|---:|
| `podjąć + decyzja` | 228 | 12,72 |
| `podejmować + decyzja` | 54 | 11,42 |
| `zrobić + decyzja` | 0 | 0,00 |

## PYTANIE 3 — czy lista czasownikow lekkich jest jeszcze potrzebna

**Tak, zostaje.** Hipoteza, ze przy wiekszym korpusie profile sie zazebia,
poszla we wlasciwa strone, ale nie doszla do progu:

| para | PDB | korpus 5 mln | prog 0,15 |
|---|---:|---:|---|
| `podjąć ~ podejmować` | — | 0,664 | — |
| `podjąć ~ zrobić` | 0,000 | **0,075** | ponizej |
| `prowadzić ~ zrobić` | — | 0,031 | ponizej |
| `odnieść ~ ponieść` | — | 0,000 | ponizej |
| `podjąć ~ jeść` | — | 0,000 | ponizej (slusznie) |

Ruch z 0,000 na 0,075 sugeruje, ze przy 30-50 mln prog moze zostac przekroczony.
Do ponownego sprawdzenia po nastepnym przebiegu.

## Pierwsza proba silnika na prawdziwych danych

`scripts/sprawdz_silnik.py` — 5 zdan blednych, 9 poprawnych:

- **4/5 bledow wykrytych**: `zrobić decyzję` → `podjął`, `zrobić próbę` → `podjęła`,
  `zrobić uwagę` → `zwrócić`, `robić funkcję` → `pełni`
- **1 przeoczony**: `zrobić badania` → `prowadzić` (podobienstwo ponizej progu)
- **0 falszywych alarmow na 9** — w tym zdanie z negacja („nie podjął decyzji")

Zero falszywych alarmow potwierdza, ze warunek 1 (slot zbadany) robi swoje.

### Blad wykryty przy okazji: przypadek wybierany po logDice

`_przypadek_rzadzony` wybieral przypadek o najwyzszym logDice. Dla
(`podjąć`, `próba`) dalo to:

    obj:acc   f=94   logDice 11,71
    obj:gen   f= 8   logDice 12,09   <- wygrywalo

Sugestia brzmiala **„podjęła próby"** zamiast „podjęła próbę" — forma
niegramatyczna, czyli gorsza niz brak sugestii.

Przyczyna: logDice mierzy sile skojarzenia wzgledem profili brzegowych, wiec
slot rzadki o waskim profilu bije slot czesty. Pytanie „jakim przypadkiem rzadzi
ten czasownik" dotyczy tego, co **czestsze**. Poprawione na wybor po czestosci;
test regresyjny w `test_silnik.py`.

## Skazenie domenowe — web wnosi i sygnal, i szum

Pary obecne wylacznie w webie dziela sie na dwie grupy:

**Szum domenowy** (do odsiania): `kredyt konsolidacyjny`, `pożyczka pozabankowa`,
`umywalka ceramiczna`, `regulamin niniejszy`, `sukienka na wesele`,
`przetłumaczyć maszynowo`, `służyć --nsubj--> menu`.

**Prawdziwa polszczyzna nieobecna w Wikipedii**: `bardzo się podobać`,
`rok przyszły`, `rok zeszły`, `bardzo cieszyć`.

Nie da sie wiec po prostu odrzucic zrodla `web` — wnosi rejestr potoczny,
ktorego encyklopedia nie ma. Potrzebne jest filtrowanie subtelniejsze niz
„zrodlo", np. wymaganie obecnosci pary w obu zrodlach dla pewnych relacji.

## Rewizja oszacowan (dwa punkty pomiarowe zamiast jednego)

Wykladniki wyliczone z pary 350 tys. -> 5 mln:

- liczba par (f>=3): **1,28** (nadliniowo, zgodnie z krzywa z PDB)
- rozmiar bazy: **0,87** (podliniowo — dominuja tabele brzegowe)

| budzet | czas na T4 | par (f>=3) | rozmiar bazy |
|---|---:|---:|---:|
| 5 mln (zrobione) | 2,0 h | 90 tys. | 39 MB |
| **30 mln** | **11,8 h** | ~895 tys. | **~187 MB** |
| 100 mln | 39,4 h | ~4,2 mln | ~534 MB |

Poprzednie oszacowanie 111-261 MB dla 100 mln bylo **zanizone** — opieralo sie
na jednym punkcie i zakladalo, ze liczba par zacznie rosnac podliniowo. Jeszcze
nie zaczela.

## Rekomendacja budzetu

**20-30 mln tokenow**, nie 100. Uzasadnienie:

- przy 5 mln kluczowe rzeczowniki sa juz zbadane; 30 mln domknie ogon
  (`porażka` i podobne)
- 11,8 h to 1-2 sesje Colaba zamiast czterech
- baza ~187 MB zamiast ~534 MB — istotne, skoro ma isc razem z dodatkiem
- zysk ze 100 mln idzie glownie w pary bardzo rzadkie, ktore i tak odpadaja
  na warunku 1

Przed nastepnym przebiegiem uruchomic komorke 4b (pomiar `partia_modelu`) —
moze skrocic te 11,8 h.

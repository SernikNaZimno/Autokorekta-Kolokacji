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

## Nastepny krok

Etap 1: ekstraktor trojek jako modul (nie skrypt spike), z powyzszymi regulami klucza,
walidowany na NLPre-PL (`ipipan/nlprepl`, 1,2 mln tokenow, gotowy CoNLL-U).

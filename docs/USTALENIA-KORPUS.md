# Ustalenia z Etapu 3 (zrodla i czyszczenie korpusu)

## Dostepnosc zrodel — zmierzona, nie zalozona

| Zrodlo | Status | Uwagi |
|---|---|---|
| `wikimedia/wikipedia` `20231101.pl` | **otwarte**, strumieniowe | ~250 mln tokenow |
| `allenai/c4` config `pl` | **otwarte**, strumieniowe | praktycznie nieograniczone |
| `uonlp/CulturaX` | **gated (auto)** | wymaga konta HF i akceptacji licencji |
| `oscar-corpus/OSCAR-2301` | **gated (manual)** | wymaga zgody wlasciciela |
| Wolne Lektury API | otwarte, 7653 ksiazki | **odrzucone — patrz nizej** |

Wybor: **Wikipedia PL + C4 pl**. Oba otwarte, wiec pipeline nie wymaga tokenu HF.

## Dlaczego odrzucilismy Wolne Lektury

Zrodlo bylo w pierwotnym wyborze, ale dane je zdyskwalifikowaly:

- **69% zbioru to liryka** (5275 z 7653). Poezja z zalozenia lamie normy
  kolokacyjne — metafora i inwersja to jej tworzywo. Zliczone jako norma
  zatrulyby baze.
- Po filtrze `Epika ∧ Współczesność` zostaje **190 ksiazek** (~11 mln tokenow,
  ~4% docelowego korpusu) przy tym samym nakladzie pracy co zrodlo 20x wieksze.
- „Współczesność" siega u nich lat 40. (Andrzejewski, Baczyński), a w probce
  jest ksiazka **po angielsku** (Malinowski, *Argonauts of the Western Pacific*).

Pipeline znakuje zrodlo kazdej trojki, wiec dolozenie Wolnych Lektur pozniej
to adapter na 20 linii — gdyby ewaluacja wykazala konkretna luke.

## Filtrowanie: poziom ZDANIA, nie dokumentu

Pierwsza proba filtrowala cale dokumenty. Na 400 probkach C4 odrzucila 62%,
ale **wsrod przyjetych 4 na 5 nadal bylo smieciami** — spam SEO, zrzut menu
nawigacyjnego, ogloszenie z klauzula cookie.

Przyczyna jest mierzalna: **mediana udzialu linii zakonczonych znakiem konca
zdania wynosi w C4 0,333**. Typowy dokument webowy to *mieszanka* menu, stopki
i wlasciwego artykulu. Zaden prog dokumentowy tego nie rozdziela — albo wyrzuca
dobra proze, albo wpuszcza boilerplate.

Filtr zdaniowy (`backend/czyszczenie.py`) ocenia kazde zdanie osobno, wiec
dokument mieszany oddaje swoje dobre zdania i gubi menu.

### Dlaczego to wazne wlasnie dla kolokacji

Zrzut menu („Produkty Eurorubber", „Fiat Powertrain Technologies") nie zawiera
czasownikow, wiec nie wygeneruje trojek `obj`. Ale wygeneruje `amod` i `nmod`,
ktore stanowia **48% wszystkich trojek**. Bez filtra nazwy handlowe trafilyby
do bazy jako norma kolokacyjna.

## Kalibracja progow — strata systematyczna vs losowa

Pierwsza wersja filtra zdaniowego odrzucala poprawna proze:

| odrzucone zdanie | powod | werdykt |
|---|---|---|
| „Każda linia jest podzielona na pola, więc można traktować…" | malo slow funkcyjnych | **falszywe** |
| „Standard ASCII był uaktualniany… 1967, 1968, 1977 i 1986." | duzo cyfr | **falszywe** |
| „…protony muszą zderzyć się z energią 3–10 keV…" | sklejone naglowki (`keV`) | **falszywe** |

To strata **systematyczna, nie losowa**: odsiewanie zdan z liczbami, nazwami
wlasnymi i jednostkami przechyla normy kolokacyjne przeciw rejestrowi
rzeczowemu. Losowa utrata 6% zdan nie kosztuje nic (korpusu mamy w nadmiarze),
systematyczna — psuje baze.

Poprawki: szeroka lista slow funkcyjnych (spojniki, partykuly, czasowniki
posilkowe), prog cyfr 0,08→0,15, prog wielkich liter 0,40→0,55, wykrywanie
sklejen wymaga **dwoch** przejsc male→wielkie w tokenie.

Efekt na tych samych 300 dokumentach:

| zrodlo | przyjete przed | przyjete po | falszywe odrzucenia |
|---|---:|---:|---|
| C4 pl | 41,9% | **47,3%** | 569→303, 110→21, 156→17 |
| Wikipedia pl | 45,9% | **53,6%** | podobnie |

## Deduplikacja

W probce 300 dokumentow C4 zdanie „Protokół z posiedzenia Zarządu…" wystapilo
**dwukrotnie**. Powtorzony boilerplate (stopki, klauzule, szablony ogloszen)
zawyzalby zliczenia proporcjonalnie do popularnosci szablonu w sieci — czyli
tworzylby norme jezykowa z tekstu jednego autora. Filtr deduplikuje po skrocie
zdania odpornym na interpunkcje i wielkosc liter.

## Nastepny krok

Parsowanie na GPU w Colabie: Wikipedia + C4 przez filtr zdaniowy do Stanzy,
trojki ze znacznikiem zrodla strumieniowo na Drive.

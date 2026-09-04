# Semantyczna autokorekta kolokacji dla języka polskiego

Wykrywanie błędów kolokacyjnych, których Word nie widzi — `*zrobić decyzję`
zamiast `podjąć decyzję`, `*odnieść porażkę` zamiast `ponieść porażkę`.
Sprawdzanie pisowni i gramatyki takich rzeczy nie łapie, bo każde słowo z osobna
jest poprawne i zdanie jest składniowo bez zarzutu. Błędna jest dopiero
*łączliwość* pary.

Docelowo dodatek do Worda (Office.js). Silnik działa offline i statystycznie —
bez modelu językowego, bez wysyłania tekstu na zewnątrz.

## Jak to działa

1. **Rozbiór zależnościowy** (Stanza, model PDB) daje pary słów powiązanych
   gramatycznie — czasownik i jego dopełnienie, rzeczownik i przydawka.
2. **Baza zliczeń** z korpusu ~100 mln tokenów mówi, jak często dana para
   występuje w polszczyźnie, mierzone miarą **logDice**.
3. **Reguła detekcji** pyta nie „czy ta para jest rzadka", tylko „czy w tym
   samym slocie stoi dużo lepsza alternatywa, semantycznie bliska temu, co
   napisano". Rozróżnienie jest kluczowe — patrz niżej.
4. **Morfeusz 2** odmienia sugestię do formy pasującej do zdania, z zachowaniem
   aspektu i przypadka wymaganego przez nowy czasownik.

## Dlaczego „para rzadka ⇒ błąd" nie działa

To była pierwotna reguła. Pomiar na treebanku UD Polish-PDB ją obalił:
**90,9% par kolokacyjnych występuje dokładnie raz**. Przy każdym realnym
rozmiarze korpusu ogromna część *poprawnej* polszczyzny wygląda na rzadką,
więc reguła produkowałaby głównie fałszywe alarmy.

Alarm wymaga więc czterech warunków naraz, z których pierwszy jest najważniejszy:

1. **Slot jest zbadany** — jeśli o danym rzeczowniku w danej roli wiemy za mało,
   silnik **milczy**. Domyślną odpowiedzią jest „nie wiem", nie „błąd".
2. Obserwowana para ma niski logDice.
3. W tym samym slocie istnieje alternatywa o wysokim logDice.
4. Ta alternatywa jest semantycznie bliska temu, co napisano.

Pełne uzasadnienie z liczbami: [docs/USTALENIA-SPIKE.md](docs/USTALENIA-SPIKE.md).

## Struktura

```
backend/
  ekstraktor.py    trójki kolokacyjne z rozbioru; wspólna funkcja klucza
  baza.py          budowa i zapytania SQLite + logDice
  czyszczenie.py   filtr jakości tekstu na poziomie zdania
  pipeline.py      źródło → filtr → Stanza → trójki na dysk
colab/             notebook do parsowania na GPU
scripts/           spike'y, walidacje, analizy — każdy uruchamialny osobno
tests/             testy jednostkowe
docs/              ustalenia z pomiarów, z uzasadnieniami decyzji
```

Jedna rzecz jest tu nieoczywista i celowa: `ekstraktor.py` jest używany
**zarówno** przy budowie bazy, **jak i** przy sprawdzaniu tekstu w czasie
pisania. Gdyby te dwie ścieżki liczyły klucz choć trochę inaczej, kolokacja
obecna w korpusie nie zostałaby odnaleziona przy zapytaniu — a błąd nie dałby
o sobie znać niczym poza cicho zerową skutecznością.

## Uruchomienie

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests\ -q
```

Zbudowanie bazy testowej z treebanku (mały korpus, do rozwoju):

```powershell
.\.venv\Scripts\python.exe scripts\zbuduj_baze.py
```

Pełny korpus wymaga GPU — patrz [colab/zbieranie_korpusu.ipynb](colab/zbieranie_korpusu.ipynb).

## Stan prac

| Etap | Status |
|---|---|
| Spike: Morfeusz generuje formy, Stanza parsuje w budżecie | zrobione |
| Ekstraktor trójek + walidacja na złotym standardzie | zrobione |
| Warstwa bazy (SQLite + logDice + znacznik źródła) | zrobione |
| Źródła korpusu i filtr jakości | zrobione |
| Parsowanie pełnego korpusu na GPU | w toku |
| Silnik sugestii (plWordNet / podobieństwo dystrybucyjne) | przed nami |
| Ewaluacja i progi | przed nami |
| Dodatek Office.js | przed nami |

## Uwagi techniczne

- **Morfeusz wymaga diakrytyków.** `odniosl` bez ogonków daje `ign`.
- **Filtrować generację na `:nagl`** — dla `ponieść` Morfeusz zwraca też
  `poniosł` (forma aglutynacyjna), która wygląda jak literówka.
- **Dopełniacz negacji** jest normalizowany: „podjął decyzję" i „nie podjął
  decyzji" to jedna kolokacja, nie dwie.
- **Przypadek nie należy do klucza przy `amod`** — przymiotnik tylko uzgadnia
  się z rzeczownikiem, więc „ważna decyzja" rozpadłoby się na siedem wpisów.

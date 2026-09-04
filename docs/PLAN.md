# Autokorekta kolokacji języka polskiego — dodatek do MS Word

## Kontekst

Word nie wykrywa błędów kolokacyjnych — kombinacji poprawnych gramatycznie, ale nienaturalnych
leksykalnie (*„zrobić decyzję" zamiast „podjąć decyzję", *„odnieść porażkę" zamiast „ponieść
porażkę"). Weryfikacja wykazała, że **nisza jest realna**:

- **LanguageTool** ma dla polskiego ~1765 reguł, w tym kategorię *Błędy frazeologiczne*, ale są to
  ~10 ręcznych reguł na sztywne idiomy („kropla dziegciu" → „łyżka dziegciu"). Zero produktywnego
  sprawdzania kolokacji.
- **Grammarly** obsługuje polski wyłącznie czerwonym podkreśleniem (pisownia + podstawowa gramatyka).
  Sugestie leksykalne/stylistyczne pozostają dla EN/ES/FR/DE/PT/IT.
- **WSJP** ma ręcznie opracowane kolokacje pogrupowane pozycją składniową — idealne dane, ale bez
  eksportu masowego i bez API.

**Cel:** narzędzie do użytku własnego. Silnik czysto statystyczny, offline (bez wysyłania tekstu
w świat). Wszystkie typy kolokacji. Ponieważ to użytek prywatny, **ograniczenia licencyjne nie mają
znaczenia** — dobieram najlepsze narzędzia, nie najbezpieczniejsze prawnie.

## Ograniczenia sprzętowe (zweryfikowane)

| Zasób | Ten laptop | Konsekwencja |
|---|---|---|
| CPU | Ryzen 7 5825U, 16 wątków | Runtime dodatku OK |
| GPU | AMD Radeon zintegrowana, **brak CUDA** | Parsowanie korpusu **musi iść na Colab** |
| RAM | 14,8 GB | Baza kolokacji na dysku (SQLite mmap), nie w RAM |
| Dysk | 100 GB wolne | **Nie zapisywać CoNLL-U** — ok. 10× rozmiar tekstu |

Ta asymetria to najważniejsza decyzja architektoniczna: **budowa bazy offline na Colab GPU,
odpytywanie lokalnie na CPU.**

## Architektura

```
┌──────────────── ETAP OFFLINE (Colab GPU, jednorazowo) ────────────────┐
│  Korpus PL → Stanza (tokenize,pos,lemma,depparse) → ekstrakcja        │
│  trójek zależnościowych → zliczenia → logDice → collocations.sqlite   │
│  (CoNLL-U NIGDY nie ląduje na dysku — triple lecą strumieniowo)       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ plik ~0,5–1 GB
                                ▼
┌──────────── RUNTIME (ten laptop, w pełni lokalnie) ───────────────────┐
│  Word ──Office.js──► panel zadań (TypeScript)                         │
│                        │  HTTPS + CORS, fetch per akapit              │
│                        ▼                                              │
│              FastAPI (localhost, HTTPS)                               │
│                ├─ Stanza pl (CPU, model rezydentny)                   │
│                ├─ collocations.sqlite  (logDice, indeksowana)         │
│                ├─ plWordNet            (synonimy → kandydaci)         │
│                └─ Morfeusz 2           (GENERACJA form fleksyjnych)   │
└───────────────────────────────────────────────────────────────────────┘
```

## Metoda detekcji

Model trójcechowy wg **Liu, Wible & Tsao, „Automated Suggestions for Miscollocations", BEA-4 2009**
([ACL W09-2107](https://aclanthology.org/W09-2107/)). Kluczowy wynik pracy: wszystkie trzy cechy
razem biją każdą pojedynczą i każdą parę.

1. **Siła asocjacji** — logDice na parach lemat+relacja. (logDice, nie PMI: jest niezależny od
   rozmiaru korpusu i nie premiuje nadmiernie par rzadkich.)
2. **Podobieństwo semantyczne** — plWordNet: synonimy i hiperonimy użytego czasownika → kandydaci.
3. **Współdzielone kolokaty (intercollocability)** — czasowniki dzielące wiele kolokatów są
   wymienne. Liczone z własnej macierzy współwystąpień, bez zewnętrznych embeddingów.

**Alarm podnoszony tylko przy koniunkcji trzech warunków** (to jest główna obrona przed fałszywymi
alarmami):
- użyta para ma logDice poniżej progu **lub** jest nieobecna w korpusie, ORAZ
- rzeczownik-baza jest dostatecznie częsty (inaczej „nieobecna" znaczy tylko „rzadkie dane"), ORAZ
- istnieje kandydat semantycznie bliski z logDice wyraźnie wyższym niż użyta para.

## Typy kolokacji

Ekstraktor jest **generyczny** — typ kolokacji to wpis w tabeli wzorców zależnościowych, więc
„wszystkie typy" kosztuje niewiele dodatkowego kodu. Koszt leży w strojeniu progów per typ.
Włączać progresywnie, wg **zmierzonej precyzji**, nie wszystkie naraz:

| Priorytet | Wzorzec UD | Przykład błędu |
|---|---|---|
| 1 | `verb --obj--> noun` | *zrobić decyzję → podjąć decyzję |
| 2 | `noun --amod--> adj` | *mocny deszcz → ulewny deszcz |
| 3 | `verb --obl--> noun` (+ przyimek, + przypadek) | *w oparciu o → na podstawie |
| 4 | `noun --nmod--> noun:gen` | *cel zadania → cel działania |
| 5 | `verb --advmod--> adv` | *mocno chory → ciężko chory |
| 6 | `noun --nsubj--> verb` | (najsłabszy sygnał, ostatni) |

## Pułapka specyficzna dla polskiego: generacja form

Angielskie prace pomijają ten problem, dla polskiego jest krytyczny. Podmiana czasownika **wymusza
zmianę przypadka rzeczownika**:

> *„odniósł porażkę"* (biernik) → „**poniósł** porażk**ę**" (biernik) ale → „**doznał** porażk**i**" (dopełniacz)

Dlatego:
- Baza przechowuje nie samą parę lematów, lecz **`(lemat_head, relacja, przypadek/przyimek, lemat_dep)`**.
  Bez przypadka w kluczu sugestie będą generować niegramatyczne zdania.
- **Morfeusz 2** (`generate()`) odmienia rzeczownik do przypadka wymaganego przez nowy czasownik
  i odmienia czasownik do formy oryginału (osoba, liczba, czas, rodzaj).
- **Aspekt musi być zachowany** (dokonany/niedokonany) — znaczniki Morfeusza go niosą. Podmiana
  „podejmować" na „podjąć" zmienia sens zdania.

Morfeusz 2 jest tu najczystszym komponentem: licencja BSD-2 (program *i* słowniki), koło PyPI
`cp310-abi3` działa na Pythonie 3.12/Windows.

## Etapy

### Etap 0 — Test wykonalności UI (30 minut, zrobić PIERWSZY)

Zanim cokolwiek innego: zainstalować **Script Lab** w swoim Wordzie, wkleić snippet
[`manage-annotations.yaml`](https://raw.githubusercontent.com/OfficeDev/office-js-snippets/prod/samples/word/50-document/manage-annotations.yaml)
i sprawdzić, **czy falowane podkreślenia faktycznie się rysują na tej licencji i tym buildzie.**

Dlaczego to pierwszy krok: od WordApi 1.7/1.8 istnieje **Annotations / Critique API**
(`paragraph.insertAnnotations({critiques:[...]})`), które rysuje natywny squiggle w wybranym kolorze
plus natywny dymek z listą sugestii i przyciskiem Akceptuj — dokładnie UX Grammarly. **Ale** wymaga
subskrypcji Microsoft 365; na Office 2021/2024 pudełkowym zawodzi, a
[`isSetSupported` zwraca `true` mimo to](https://github.com/OfficeDev/office-js/issues/4953) — nie da
się tego wykryć programowo. Ten jeden test rozstrzyga, czy głównym UI jest warstwa 1 czy 2.

### Etap 1 — Rdzeń językowy na CPU, bez Worda

Konsola/CLI, żeby oddzielić problem NLP od problemu integracji.

- Środowisko: Python 3.12, `stanza`, `morfeusz2`, `fastapi`, `uvicorn`.
- Stanza `pl` — LAS **91,73** (PDB) vs spaCy `pl_core_news_lg` **82,38**. Dziewięć punktów LAS
  różnicy dokładnie na łukach czasownik→dopełnienie, czyli tam, gdzie ten projekt żyje. Licencja
  CC-BY-NC-SA treebanku PDB przy użytku własnym nie stanowi problemu.
- **Ten sam parser offline i runtime.** Rozjazd parserów = trójki z runtime nie trafiają w klucze
  w bazie i cały system po cichu nic nie znajduje.
- Ekstraktor trójek z CoNLL-U + normalizacja (lematyzacja, przypadek, przyimek).
- Weryfikacja na małym, w pełni sparsowanym zbiorze: **NLPre-PL** ([HF `ipipan/nlprepl`](https://huggingface.co/datasets/ipipan/nlprepl),
  CC-BY, 1,2 mln tokenów, gotowy CoNLL-U). Za mały na statystyki, idealny do kalibracji ekstraktora.

### Etap 2 — Budowa bazy kolokacji (Colab GPU)

**Korpus, dwustopniowo:**
1. **Wikipedia PL** (~1,7 mln artykułów, ~250–300 mln tokenów) — redagowana proza, wzorcowy rejestr
   dla normy kolokacyjnej. Start tutaj: łatwy dump, czysty tekst, pipeline da się zwalidować.
2. **HPLT v2 `pol_Latn`** ([HF](https://huggingface.co/datasets/HPLT/HPLT2.0_cleaned), 89,5 mld
   tokenów, CC0) — podpróbka ~200–300 mln tokenów **dla zbalansowania rejestru**. Sama Wikipedia
   jest encyklopedyczna i zaniża kolokacje potoczne i emocjonalne („wziąć prysznic", „palić się ze
   wstydu").

**Realia przepustowości Colab free (T4):** Stanza ~3–8 tys. tokenów/s przy dobrym batchowaniu.
100 mln tokenów ≈ 4–8 h, czyli 1–2 sesje. **Cel v1: 100 mln tokenów**, nie 300 — sesje free się
rozłączają. Obowiązkowo: sharding korpusu + checkpointy zliczeń na Google Drive po każdym shardzie.
Colab Pro warto rozważyć przy skalowaniu do pełnych 500 mln.

**Krytyczne dla dysku:** trójki ekstrahować **strumieniowo w pamięci**, zapisywać wyłącznie
zliczenia. CoNLL-U dla 100 mln tokenów to dziesiątki GB — nie zmieści się i nie jest potrzebny.

**Wynik:** `collocations.sqlite`, przycięte do częstości ≥3, ok. 5–8 mln wierszy, ~0,5–1 GB,
z indeksem po `(lemat_head, relacja, przypadek)`. Odpytywana przez indeks, nie ładowana do RAM.

### Etap 3 — Silnik sugestii

- plWordNet/Słowosieć (rejestracja, darmowe, także komercyjnie) → generator kandydatów.
- Macierz współdzielonych kolokatów liczona z własnej bazy.
- Ranking: logDice kandydata × podobieństwo semantyczne × intercollocability.
- Generacja form przez Morfeusz 2 (patrz sekcja o pułapce fleksyjnej).
- API: `POST /check` przyjmuje akapit, zwraca listę `{start, length, sugestie[], pewność}`
  z **offsetami względem akapitu** — tego wymaga `Critique.start/length`.

### Etap 4 — Zbiór ewaluacyjny i strojenie progów

Bez tego nie da się ustawić progów i projekt utonie w fałszywych alarmach.

- **Pseudo-błędy syntetyczne:** wziąć kolokacje potwierdzone w korpusie, podmienić czasownik na
  synonim z plWordNet o niskim logDice z tym rzeczownikiem. Generuje tysiące par błąd/poprawa
  za darmo.
- **Dane realne:** [`Ermlab/polish-gec-datasets`](https://github.com/Ermlab/polish-gec-datasets)
  (Apache-2.0) — ma jawną kategorię **błędów leksykalnych**, ok. 299–2459 wystąpień.
- Mierzyć **precyzję przy progu**, nie F1. W narzędziu do pisania fałszywy alarm boli dużo bardziej
  niż przeoczenie — użytkownik traci zaufanie po kilku i wyłącza dodatek.
- Włączać kolejne typy kolokacji dopiero, gdy typ osiąga akceptowalną precyzję.

### Etap 5 — Dodatek Office.js

```bash
npm install -g yo generator-office
yo office        # Task Pane project > TypeScript > Word
npm start        # build + serwer HTTPS + automatyczny sideload do Worda
```

- Manifest XML (nie unified JSON — ten nie działa przy sideloadzie z udziału sieciowego).
- **Warstwa 1:** `insertAnnotations` z `colorScheme` **innym niż czerwony** (np. `blue`/`lavender`),
  żeby nie zlewać się z natywną pisownią Worda. Zdarzenie `onAnnotationPopupAction` mówi, którą
  sugestię kliknięto; `accept()` **sam podmienia tekst**.
- **Warstwa 2 (obowiązkowa):** `try/catch` wokół `insertAnnotations` → degradacja do listy kart
  w panelu; klik zaznacza zakres (`range.select()`), podmiana przez
  `range.insertText(..., 'Replace')`. To wzorzec Grammarly na Macu.
- **Nie używać** `font.highlightColor` ani `underline` jako głównego UI — te zapisują się
  w dokumencie i zostają po zamknięciu.
- Skanowanie: `context.document.onParagraphChanged` (WordApi 1.6), debounce ~750 ms,
  **przeskanować wyłącznie zmienione akapity po ID**, nigdy całe `Body`. Jedno `context.sync()`
  na partię.
- Lista ignorowanych + własny słownik akceptowanych kolokacji (użytek własny = własne idiolekty).

**Uwaga o CORS/HTTPS:** panel zadań chodzi po HTTPS, więc `fetch` na `http://localhost` to mixed
content i zostanie zablokowany. Backend FastAPI musi mieć certyfikat HTTPS (`mkcert`) i wysyłać
`Access-Control-Allow-Origin` dla origin dodatku.

## Główne ryzyka

| Ryzyko | Mitygacja |
|---|---|
| **Fałszywe alarmy** — zabójca nr 1 dla narzędzia do pisania | Koniunkcja trzech warunków; progi strojone na zbiorze z Etapu 4; typy włączane po zmierzonej precyzji |
| Critique API nie działa na tej licencji Worda | Etap 0 rozstrzyga to w 30 minut, przed jakąkolwiek pracą |
| Rozjazd parsera offline/runtime → system po cichu nic nie znajduje | Ten sam Stanza + ta sama wersja modelu po obu stronach; test integracyjny na znanych parach |
| Niegramatyczne sugestie (zły przypadek) | Przypadek w kluczu bazy + generacja przez Morfeusz 2 |
| Rozłączenia Colab przy parsowaniu | Sharding + checkpointy na Drive; cel v1 = 100 mln tokenów |
| Za mało danych → wszystko wygląda na „nieobecne" | Warunek minimalnej częstości rzeczownika-bazy |

## Weryfikacja

1. **Etap 0:** squiggle widoczny w Wordzie ze Script Lab — tak/nie.
2. **Etap 1:** ekstraktor na NLPre-PL wyciąga poprawne trójki; ręczna kontrola 50 zdań.
3. **Etap 2:** zapytanie do bazy — `podjąć+decyzja:acc` ma wysoki logDice, `zrobić+decyzja:acc`
   niski/zerowy. Jeśli nie, pipeline zliczeń jest zepsuty.
4. **Etap 3:** CLI na liście ~30 ręcznie napisanych błędnych zdań; sprawdzić, czy sugestie są
   **gramatyczne** (właściwy przypadek i aspekt).
5. **Etap 4:** precyzja/pokrycie na pseudo-błędach + `polish-gec-datasets`; wykres precyzji od progu.
6. **Etap 5:** e2e w Wordzie — napisać akapit z 3 znanymi błędami, sprawdzić podkreślenia, kliknąć
   sugestię, potwierdzić poprawną odmianę w dokumencie. Zmierzyć opóźnienie po zatrzymaniu pisania.

## Stos

**Backend:** Python 3.12 · Stanza (`pl`) · Morfeusz 2 · plWordNet · SQLite · FastAPI + uvicorn
**Frontend:** TypeScript · Office.js (WordApi 1.8) · yo office
**Offline:** Google Colab (T4) · Wikipedia PL + HPLT v2 `pol_Latn`

# En pipeline för svensk CommonCrawl-data

Ett ramverk byggt ovanpå `datatrove` för att bearbeta och utvärdera svensk text från Common Crawl (WARC-shards).

### 🔄 Det tänkta arbetsflödet
Projektet är designat för ett iterativt arbetsflöde där du **utvärderar först och samlar in sedan**:
1. **Experimentera & Utvärdera (Fas 1):** Testa olika konfigurationer och pipelines i källkoden mot din lokala gulddata.
2. **Välj bästa pipeline:** Identifiera vilken pipeline-konfiguration som ger bäst precision, recall och ROUGE-1.
3. **Kör i produktion (Fas 2 & 3):** Applicera den vinnande pipelinen på den fullskaliga insamlingen via Common Crawl-shards och gör en avslutande deduplicering.

---

## ✨ Egenskaper

### ⚡ Databehandling & Prestanda
* **Parallellisering:** Kör 4 oberoende processer parallellt under insamlingen.
* **Smart lagring:** Raderar `.warc.gz`-filer direkt efter extraktion.
* **Robust flöde:** Sparar framsteg automatiskt vid avbrott.

### 🧩 Flexibel & Modulär Arkitektur
* **Valbar extraktion:** Stöd för textutvinning via antingen **Trafilatura** eller egna skräddarsydda extraherare (t.ex. med **BeautifulSoup**).
* **Säker tabellhantering:** Ett inbyggt preprocessing-steg rensar HTML-kod men sparar undan tabeller i förväg så att värdefull data inte rensas bort av misstag av externa bibliotek.
* **Valbara moduler:** Du väljer själv vilka steg din pipeline ska köra – statistiska **kvalitetsfilter**, automatisk **dokumentklassificering** och **PII-maskering** är helt valbara komponenter.

### 🗜️ Effektiv Deduplicering
* **Exakt matchning:** Filtrerar först bort identiska dokument snabbt och minneseffektivt med hjälp av ett **Bloom-filter**.
* **Ungefärlig matchning:** Rensar därefter bort snarlika dokument (near-duplicates) med **MinHash LSH** för att höja den slutgiltiga datakvaliteten.

### 📊 Experiment & Utvärdering
* **Flexibla experiment:** Enkelt att lägga till och testa egna pipelines direkt i koden.
* **Automatisk mätning:** Beräknar precision, recall och ROUGE-1 automatiskt mot din gulddata.
* **Spårbarhet & Dokumentanalys:** Samlar automatiskt in detaljerad information om exakt vilka dokument som slängs och av vilken specifik komponent under körningen.
* **Diff-rapport:** Skriver automatiskt ut filer med textdiffar mellan gulddata och den extraherade texten – med en separat fil för varje unikt experiment.
* **Inspektion:** Möjlighet att granska enskilda dokument via ID för djupare analys.

---

## 💻 Installation & Miljö

Detta projekt använder `uv` för miljö- och pakethantering. Du behöver inte installera några Python-paket manuellt.

## Förutsättningar

Projektet kräver **Bash**, systemverktygen **wget** och **libmagic** (för filtypsidentifiering), samt Python-hanteraren **uv**. 

### 1. Installera systemverktyg

#### macOS
Installera via [Homebrew](https://brew.sh):
```bash
brew install bash wget libmagic
```
*Obs: Skriptet använder `caffeinate` för att förhindra viloläge, vilket är inbyggt i macOS.*

#### Linux (Ubuntu/Debian)
Installera via `apt`:
```bash
sudo apt update
sudo apt install bash wget libmagic1 findutils
```
*Note: `findutils` behövs för verktyget `xargs` som skriptet använder för parallellkörning.*

#### Windows
Eftersom projektet använder Bash-skript och `libmagic`, måste Windows-användare köra projektet via **Git Bash** eller **WSL (Windows Subsystem for Linux)**.

1. Installera Git (som inkluderar Git Bash) via [Winget](https://microsoft.com):
   ```powershell
   winget install Git.Git
   ```
2. Om du kör via Git Bash - lägg till `python-magic-bin` i projektets Python-beroenden, då det innehåller de binärer som Windows behöver.

### 2. Installera Python-miljön (uv)

Detta projekt använder `uv` för miljö- och pakethantering. Du behöver inte installera Python eller några Python-paket manuellt.

Installera `uv` med följande kommando:

* **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh | sh
  ```
* **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh | iex"
  ```

Efter installationen kommer kommandot `uv run` i skriptet att automatiskt sätta upp rätt Python-version och installera alla paket.


---

## 📋 Dataformat för Gulddata

Utvärderingen förväntar sig en mapp som innehåller filer i formatet **JSON Lines (`.jsonl`)**. Varje rad i filen ska vara ett giltigt JSON-objekt som representerar ett dokument med följande struktur:

```json
{
  "id": "se-cc-001",
  "url": "https://example.se",
  "html": "<html><body><h1>Rubrik</h1><p>Manuellt extraherad text...</p></body></html>",
  "text": "Rubrik\n\nManuellt extraherad text..."
}
```

* **`id`**: En unik identifierare för dokumentet (används vid specifik dokumentgranskning).
* **`url`**: Dokumentets ursprungliga webbadress.
* **`html`**: Den fullständiga original-HTML-koden från Common Crawl.
* **`text`**: Det manuellt extraherade facit (guldtexten) som pipelinen utvärderas mot.

---

## 🚀 Användning & Arbetsflöde

### Steg 1: Experimentera och utvärdera (Hitta bästa pipeline)
Innan du kör den stora insamlingen använder du evalueringspipelinen för att mäta prestandan på dina modifierade eller egenutvecklade pipelines mot din lokala gulddata-mapp.

När utvärderingen körs skrivs det för varje experiment ut en tabell med genomsnittliga scores. Det genereras även en diff-fil för varje experiment i `diffs/` som standard, där man i detalj kan se scores för varje dokument, och vad som lagts till och tagits bort jämfört med gulddatan.

```bash
uv run python evaluation_pipeline.py --gold-dir /sökväg/till/gulddata
```

**Felsök specifika dokument:**
Om du vill analysera resultaten närmare kan du ange ett dokument-ID. Då skrivs guldtexten och din pipelines extraherade text ut sida vid sida i terminalfönstret:

```bash
uv run python evaluation_pipeline.py --gold-dir /sökväg/till/gulddata --doc-id <DOKUMENT_ID>
```

### Steg 2: Förbered källor för produktion
När du har utvärderat dina experiment och valt den bästa pipeline-konfigurationen i koden är det dags för storskalig insamling.

1. Gå till den officiella sidan [Common Crawl Get Started](https://commoncrawl.org/get-started) och välj en crawl i rullistan. 
2. Ladda ner indexfilen för WARC-sökvägar (`warc.paths.gz`) från sidan.
3. Packa upp filen, välj ut de rader/shards du vill köra, och spara dem i projektets rotmapp under namnet `warc.paths`.

### Steg 3: Kör storskalig insamling och tvätt (Fas 1)
Starta den parallella pipelinesexekveringen med 4 oberoende workers:

```bash
chmod +x run_pipeline.sh
./run_pipeline.sh
```
De extraherade textfilerna sparas i komprimerat format i mappen `cc-output/`.

### Steg 4: Kör global deduplicering (Fas 2)
Dedupliceringen körs i två fristående steg efter att extraheringen är helt slutförd.

#### Del A: Exakt matchning (Bloom-filter)
Kör Bloom-filtret för att snabbt rensa bort exakta dubbletter. Skriptet läser data från `cc-output/` och sparar resultatet i mappen `cc-bloomfiltered/`:

```bash
uv run python bloomfilter.py
```
* **`removed_by_bloom.txt`**: Loggfil som innehåller all borttagen data.
* **`dedup_progress.txt`**: Loggfil som håller reda på avklarade filer för att möjliggöra återstart.

#### Del B: Ungefärlig matchning (MinHash LSH)
Kör MinHash LSH för att rensa bort snarlika dokument (near-duplicates). Skriptet läser data från `cc-bloomfiltered/` och sparar alla resultat i mappen `dedup_results/`:

```bash
uv run python minhash_deduplication.py
```
* **`dedup_results/deduplicated/`**: Här sparas den slutgiltiga, unika datamängden.
* **`dedup_results/removed/`**: Här sparas alla dokument som filtrerats bort som dubbletter.

**Konfiguration:** Skriptet körs med inställningarna `n_grams=5`, `num_buckets=14` och `hashes_per_bucket=8`. Detta resulterar i ett **Jaccard-tröskelvärde på 0.72**, vilket är industristandard för datatvätt inför LLM-träning.

---

## 📐 Projektstruktur

```text
cc-pipeline/
├── src/
│   ├── classifiers.py          # Valbar logik för artikel- vs forumklassificering
│   ├── extractors.py           # Trafilatura/BeautifulSoup-extraktion och PII-maskering
│   ├── filters.py              # Valbara statistiska kvalitetskontroller
│   └── evaluator.py  # Logik för beräkning av scores samt spårning av bortfiltrerade dokument
├── run_pipeline.sh             # Det parallella Bash-skriptet
├── run_pipeline.py             # Datatrove-huvudfilen (exekveras per WARC-fil)
├── bloomfilter.py              # Steg 1 av dedupliceringen (Exakta matchningar)
├── minhash_deduplication.py    # Steg 2 av dedupliceringen (Near-duplicates med LSH)
├── evaluation_pipeline.py      # CLI-gränssnitt för utvärdering av experiment och gulddata
├── pyproject.toml              # Projektkonfiguration
└── uv.lock                     # Låst och reproducerbar miljö
```

---
## 🛡️ Kodkvalitet

Projektet är formaterat och testat med Ruff:

```bash
uv run ruff check
uv run ruff format
```

---

## 🤖 AI-assistans

Detta projekt har utvecklats med stöd av **Google Gemini**:

Modellen har använts som bollplank och kodassistent genom merparten av projektets delar, inklusive kodstruktur, preprocessing, utvärderingslogik och dokumentation

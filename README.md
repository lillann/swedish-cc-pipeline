# En pipeline för svensk webb-data

En pipeline baserad på `datatrove` för att bearbeta, deduplicera och annotera svensk text från Common Crawl/Kulturarw3 (WARC-shards).

## 🔄 Det tänkta arbetsflödet

Pipelinen är uppdelad i följande steg. Följ respektive länk för detaljerade guider:

1. **Insamling och HTML-rensning:** (Läs [guide](./docs/01-pipeline.md))
    - Hämtar ner externa WARC-filer direkt från Common Crawl eller läser in färdiga lokala arkiv. Därefter filtrerar skriptet bort ogiltiga dokument baserat på svartlistade url:er, extraherar ungefärlig text och filtrerar ut svenska dokument, rensar HTML till ett mer lättviktigt men strukturbevarande format och annoterar med strukturell statistik.
2. **Exakt deduplicering** med **Bloom-filter** (Läs [guide](./docs/02-deduplication.md))
    - Protokollför och tar bort identiska dubbletter, baserat på den extraherade texten från steg 1.
3. **Textextrahering** med **Trafilatura** (Läs [guide](./docs/03-extraction.md))
    - Extraherar brödtexten från HTML-dokumenten och annoterar med statistik baserat på textinnehåll.
4. **Ungefärlig deduplicering** med **MinHash LSH** och **MinHash Ensemble** (Läs [guide](./docs/02-deduplication.md))
    - Slutlig rensning av nästan-dubbletter och partiella dubbletter.
5. **Kvalitetsannotering** med **Propella** (Läs [guide](./docs/05-propella.md))
   - Annoterar dokumenten med innehålls- och kvalitetsattribut.


## 💻 Installation & Miljö

Projektet kräver **Bash**, systemverktygen **wget** och **libmagic** (för filtypsidentifiering), samt Python-hanteraren **uv**. 

### 1. Installera systemverktyg

#### macOS
Installera via [Homebrew](https://brew.sh):
```bash
brew install bash wget libmagic
```

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

>Efter installationen kommer kommandot `uv run` i skriptet att automatiskt sätta upp rätt Python-version och installera alla paket.

---

### Dataflöde och utdata
Pipelinen är uppdelad i sekventiella steg där utdatan från ett steg fungerar som indata för nästa via Datatroves `JsonlWriter` och `JsonlReader`. Resultaten sparas som komprimerade JSONL-filer (`.jsonl.gz`).

* **Steg 1 (Insamling och rensning) (`run_pipeline.sh` eller `run_pipeline_stage1.py`):** Läser WARC-filer, som antingen hämtas ner från CommonCrawl eller från ett lokalt arkiv, och sparar de bearbetade dokumenten till utdatamappen (standard: `./cc-stage1-output/`).
  * Namnmönster: `cc_data_{file_number}_{rank}.jsonl.gz`
  * *(`file_number`: WARC-filens löpnummer, `rank`: Datatroves worker-ID)*
* **Steg 2 (Exakt deduplicering) (`bloomfilter.py`):** Läser in JSONL-filerna från föregående stegs utdatamapp, applicerar exakt deduplicering och sparar rensad data i mappen `./cc-bloomfiltered/` och en logg över borttagna filer i `removed_exact_duplicates.txt`.
* **Steg 3 - (Textextrahering)** (`run_pipeline_stage2.py`) Läser in data från föregående stegs utdatamapp (`./cc-bloomfiltered/`) utför textextrahering med Trafilatura och sparar i mappen `./cc-stage2-output/`.
* **Steg 4 - (Ungefärlig deduplicering)** (`minhash_deduplication.py`) Läser in data från föregående stegs utdatamapp (`./cc-stage2-output/`) utför ungefärlig deduplicering och sparar rensad data i mappen `./dedup_results/deduplicated/`, och lägger borttagna dokument i `dedup_results/removed/remove_docs`.
* **Steg 5 - (Annotering)** (`run_pipeline_stage3.py`)Läser in data från föregående stegs utdatamapp (`./dedup_results/deduplicated/)` och annoterar med **Propella**. Den slutliga datan läggs i mappen `./cc-output-stage3`.

>Mappar för indata (via `JsonlReader`) och utdata (via `JsonlWriter`) konfigureras direkt i respektive Python-skript. Se till att läs- och skrivsökvägarna matchar mellan stegen.
---

## 📐 Projektstruktur

```text
cc-pipeline/
├── src/
│   ├── HTML_preprocessor.py    # Rensning av HTML, ungefärlig textextrahering, viss strukturell statistik
│   ├── annotation.py           # Propella-annotaterare och textbaserade statistikmått 
│   ├── filters.py              # OpenLid-språkfilter
│   └── utils/           
│       └──propella.py          # Anpassad källkod för Propella-integration (från Ellamind)
├── run_pipeline.sh             # Det parallella Bash-skriptet, körs med parameter 1,2 eller 3 beroende på önskad pipeline
├── run_pipeline_stage1.py      # Pipeline 1 - returnerar svenska dokument med lättvikts-html. (anropas av bash-skriptet och exekveras per WARC-fil)
├── run_pipeline_stage2.py      # Pipeline 2 - textextrahering
├── run_pipeline_stage3.py      # Pipeline 3 - Propella-annotering
├── bloomfilter.py              # Steg 1 av dedupliceringen (Exakta matchningar)
├── minhash_deduplication.py    # Steg 2 av dedupliceringen (Near-duplicates med LSH)
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

## 📄 Källor och erkännanden
Detta projekt använder [Propella-1](https://huggingface.co/ellamind/propella-1-4b) från Ellamind för semantisk annotering. Källkod under `src/utils/` är anpassad från originalprojektet och distribueras under [Apache-2.0 License](https://www.apache.org/licenses/LICENSE-2.0).

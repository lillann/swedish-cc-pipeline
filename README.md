# En pipeline för svensk CommonCrawl-data

Ett ramverk byggt ovanpå `datatrove` för att ladda ned, extrahera, tvätta, klassificera, PII-maskera och deduplicera svensk text från Common Crawl (WARC-shards). 

## ✨ Egenskaper
- **Parallellisering**: Kör 4 oberoende nedladdnings- och bearbetningsprocesser parallellt. Varje worker laddar ner en `.warc.gz`-fil i taget, extraherar, filtrerar och städar texterna lokalt, och raderar sedan warc.gz-filen.
- **HTML-tvätt**: Extraktion via BeautifulSoup som tar bort script-rester, cookie-banners och CSS.
- **Statistiskt kvalitetsfilter**: Tar bort e-handel, länklistor och navigationsmenyer baserat på stoppords-andel, symbol-ratio och meningsbyggnad.
- **PII-maskering**: Regex-maskering av svenska gatuadresser, telefonnummer, e-postadresser och postnummer.
- **Dokumentklassificering**: Sorterar automatiskt rå-HTML till `article` eller `discussion` (forumtrådar).
- **Lätt att starta om**: Avbrutna nedladdningar sparas och fortsätter där de stannade vid `Ctrl+C` eller nätverksfel.

## 🛠️ Installation & Miljö

Detta projekt använder **`uv`** för miljö- och pakethantering. Du behöver inte installera några Python-paket manuellt.

### Förutsättningar
Installera systembiblioteket `libmagic` (krävs för filtypsidentifiering av WARC-filer) via Homebrew:
```bash
brew install libmagic
```

## 🚀 Användning

### 1. Förbered dina källor
Skapa en fil döpt till `warc.paths` i rotmappen och lägg till de sökvägar till Common Crawl-shards som du vill bearbeta (hämtas från Common Crawls officiella path-listor).

### 2. Kör insamling och tvätt (Fas 1)
Starta den parallella pipelinesexekveringen med 4 oberoende workers:
```bash
chmod +x run_pipeline.sh
./run_pipeline.sh
```
*De extraherade textfilerna sparas i komprimerat format i mappen `cc-output/`.*

### 3. Kör global deduplicering (Fas 2)
KOMMER SNART!
```bash
uv run python deduplicate.py
```
*Den slutgiltiga datamängden sparas i mappen `compiled-dataset/`.*

## 📐 Projektstruktur

```text
cc-pipeline/
├── src/
│   ├── classifiers.py   # Logik för artikel- vs forumklassificering
│   ├── extractors.py    # BeautifulSoup-extractor och PII-maskering
│   └── filters.py       # Statistiska kvalitetskontroller
├── run_pipeline.sh      # Det parallella Bash-skriptet
├── run_pipeline.py      # Datatrove-huvudfilen (exekveras per WARC-fil)
├── deduplicate.py       # MinHash LSH-deduplicering
├── pyproject.toml       # Projektkonfiguration
└── uv.lock              # Låst och reproducerbar miljö
```

## 🛡️ Kodkvalitet
Projektet är formaterat med `Ruff`:
```bash
uv run ruff check
uv run ruff format
```


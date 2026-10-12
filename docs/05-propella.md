
# Steg 5: Kvalitetsannotering (**Propella**)

Detta steg annoterar dokumenten med innehålls- och kvalitetsattribut via en lokal LLM-server med **Propella**.

---

## 🛠️ Förutsättningar: Starta lokal LLM-server

Propella-annotering kräver en lokal OpenAI-kompatibel API-server på port 8000. Starta servern i ett separat terminalfönster innan du kör pipelinen.

Installera först llama.cpp och starta sedan servern som automatiskt hämtar modellen från Hugging Face:

* macOS via [Homebrew](https://brew.sh):
```bash
brew install llama.cpp
```

* Linux:
```bash
	pip install vllm
```

* Windows: 
  ```powershell
  winget install ggml.llamacpp
  ```

Starta sedan servern (Mac/Windows):
```bash
llama-server -hf mradermacher/propella-1-4b-GGUF:Q4_K_M --port 8000
```	

Linux:
```bash
	vllm serve ellamind/propella-1-4b --port 8000
```	

### ⚙️ Konfiguration
Innan du kör skriptet bör du justera inställningarna högst upp i skriptfilen (`run_pipeline_stage3.py`) efter dina behov:

```python
# INSTÄLLNINGAR
INPUT_FOLDER = (
    "./dedup_results/deduplicated/"  # Indata från föregående steg (MinHash-deduplicering)
)
OUTPUT_FOLDER = "cc-stage3-output"  # Utdata med extraherad text och statistik
LOGS_DIR = "logs/propella"  # Mapp för körningsloggar

# PARALLELLITET OCH KÖRNING
TASKS = 16  # Totala delmängder (shards) som jobbet delas in i
WORKERS = 4  # Antal samtidiga processer/kärnor som körs
```

## 🚀 Körning
När den lokala servern är igång körs pipeline-steget för statistik och annotering via uv:

```Bash
uv run python pipeline_stage3.py
```

## 🏷️ Genererad metadata
Efter att pipelinen har kört klart har dokumentens metadata uppdaterats med följande fält:

```doc.metadata['propella']```: Innehåller strukturerad JSON-respons från Propella-modellen (exempelvis innehållstyp och attribut) som kan användas för vidare filtrering.

För mer information om hur annoteringarna är uppbyggda, se artikeln [propella-1: Multi-Property Document Annotation for LLM Data Curation at Scale](https://arxiv.org/abs/2602.12414).


### 📦 Genererade filer och loggar
`OUTPUT_FOLDER`: Innehåller de färdiga JSONL-filerna där dokumenten tilldelats propella-annoteringar.

`LOGS_DIR`: Innehåller Datatroves körningsloggar för felsökning och automatisk återstart (resume) vid eventuella avbrott.
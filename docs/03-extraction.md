# Steg 3: Textextrahering med Trafilatura

I detta steg extraheras ren brödtext från de rensade och deduplicerade HTML-dokumenten från föregående steg. Pipelinen använder **Trafilatura** för att plocka ut brödtexten ur HTML-innehållet, följt av ett separat steg för att beräkna statistik som läggs till dokumentens metadata.

---

### ⚙️ Konfiguration
Innan du kör skriptet bör du justera inställningarna högst upp i skriptfilen (`run_pipeline_stage2.py`) efter dina behov:

```python
# INSTÄLLNINGAR
INPUT_FOLDER = "cc-bloomfiltered"  # Indata från föregående steg (Bloom-filtret)
OUTPUT_FOLDER = "cc-stage2-output"  # Utdata med extraherad text och statistik
LOGS_DIR = "logs/extraction"  # Mapp för körningsloggar

# PARALLELLITET OCH KÖRNING
TASKS = 16  # Totala delmängder (shards) som jobbet delas in i
WORKERS = 4  # Antal samtidiga processer/kärnor som körs
```
### 🚀 Körning
Starta skriptet via `uv`:
```bash
uv run python run_pipeline_stage2.py
````

## 🏷️ Uppdaterad data och metadata
Efter att textextraktionen har kört klart har dokumenten uppdaterats på följande sätt:

- **`doc.text`**: Innehåller nu den rena, extraherade brödtexten som genererats av Trafilatura (ersätter den tidigare ungefärliga texten).
- **`doc.metadata['statistics']`**: Innehåller kvantitativa mätvärden för den extraherade texten, såsom textlängd, ordantal, antal stoppord, versaler och antal meningar.


### 📦 Genererade filer och loggar
`OUTPUT_FOLDER`: Innehåller de färdiga JSONL-filerna med extraherad brödtext och tillagd textstatistik som går vidare i pipelinen.

`LOGS_DIR`: Innehåller Datatroves körningsloggar för felsökning och automatisk återstart (resume) vid eventuella avbrott.



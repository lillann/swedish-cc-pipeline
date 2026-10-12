
# Steg 2 och steg 4: Exakt och ungefärlig deduplicering

Båda dedupliceringsstegen utgår från dokumentens textinnehåll (fältet ```.text```) för att identifiera och rensa bort dubletter.

## Del 1: Bloom-filter för exakt deduplicering

Detta steg körs tidigt i pipelinen (direkt efter Steg 1) för att rensa bort identiska dokument.

### ⚙️ Konfiguration
Innan du kör skriptet kan du öppna `bloomfilter.py` och justera inställningarna högst upp i filen efter dina behov:

```python
# INSTÄLLNINGAR
INPUT_DIR = "cc-stage1-output"  # Indata från föregående steg
OUTPUT_DIR = "cc-bloomfiltered"  # Utdata med unika filer
BLOOM_FILE = "dedup_filter.bloom"  # Bloom-filtret som skapas på disk
PROGRESS_FILE = "dedup_progress.txt"  # Loggbok för avklarade filer (för återstart)
DUPLICATE_LOG = "removed_by_bloom.txt"  # Loggfil över all borttagen dubblettdata

# BERÄKNAD KAPACITET
EXPECTED_ITEMS = 15_000_000  # Uppskattat antal svenska filer i sharden
ERROR_RATE = 0.001  # Tillåten felmarginal för filtret
```

### 🚀 Körning
Starta skriptet via `uv`:

```bash
uv run python bloomfilter.py
```
### 📦 Genererade filer och loggar
* `OUTPUT_DIR`: Innehåller de deduplicerade JSONL-filerna som går vidare i pipelinen.
* `DUPLICATE_LOG`: En loggfil som håller reda på borttagen data
* `PROGRESS_FILE`: Håller reda på vilka filer som bearbetats, så att skriptet automatiskt kan återupptas vid ett eventuellt avbrott.
---
## Del 2: MinHash LSH för ungefärlig deduplicering

Detta steg körs senare i pipelinen (efter textextraheringen i steg 2) för att identifiera och rensa bort nästan-dubletter med hjälp av MinHash LSH. 

### ⚙️ Konfiguration
I `minhash_deduplication.py` styrs sökvägar och inställningar högst upp i filen. Se till att `INPUT_FOLDER` matchar utdatan från Steg 2.

```python
# --- KONFIGURATION ---
INPUT_FOLDER = "cc-stage2-output"  # Indata från Stage 2
SIGS_DIR = "dedup_results/sigs"
BUCKETS_DIR = "dedup_results/buckets"
OUTPUT_DIR = "dedup_results/deduplicated"
REMOVED_DIR = "dedup_results/removed"
LOGS_DIR = "dedup_logs"

# Jaccard-tröskel ca 0.72 (industristandard för LLM-träning)
conf = MinhashConfig(n_grams=5, num_buckets=14, hashes_per_bucket=8)
```
#####  💡 Om Jaccard-tröskeln:
Parametrarna `num_buckets` och `hashes_per_bucket` avgör tillsammans den så kallade **Jaccard-tröskeln** (standardinställningen ovan ger en tröskel på ca 0.72)

### 🚀 Körning
Starta skriptet via `uv`:

```bash
uv run python minhash_deduplication.py
```
### 📦 Utdata
* `OUTPUT_DIR`: Den deduplicerade datan
* `REMOVED_DIR`: Innehåller borttagna nästan-dubbletter (`remove_docs`) och matchande ID:n (`remove_ids`)
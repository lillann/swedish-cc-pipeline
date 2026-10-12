
# Steg 1: Insamling, språkfiltrering och HTML-rensning

I detta steg exekveras en parallell pipeline (antingen via Bash-skriptet ```run_pipeline.sh``` för att hämta filer från **Common Crawl** eller direkt via Datatroves `LocalPipelineExecutor` i ```run_pipeline_steg1.py``` för lokala arkiv). Oberoende arbetsprocesser (workers) hanterar WARC-filerna och exekverar en **Datatrove**-pipeline som filtrerar bort dokument baserat på svartlistade URL:er, extraherar ungefärligt textinnehåll (för språkidentifiering) med **Resiliparse**, identifierar svenska dokument med **OpenLid**, rensar HTML med **lxml** samt annoterar med strukturell statistik (såsom länkar, knappar och tabeller).


## 🚀 Körning av Steg 1
Välj ett av nedanstående alternativ beroende på var din rådata kommer ifrån:

---
### Alternativ A: Från Common Crawl
Om du hämtar data direkt från Common Crawl används ett parallellt Bash-skript som hanterar nedladdning, cache och eventuella avbrott.

#### 1. Förbered källor
1. Gå till den officiella sidan [Common Crawl Get Started](https://commoncrawl.org/get-started) och välj en crawl i rullistan.
2. Ladda ner indexfilen för WARC-sökvägar (`warc.paths.gz`) från sidan.
3. Packa upp filen, välj ut de rader/shards du vill köra, och spara dem i projektets rotmapp under namnet `warc.paths`.

#### 2. Kör skriptet
Starta exekveringen från rotmappen:

```bash
chmod +x run_pipeline.sh
./run_pipeline.sh 1 [antal_workers]
```
*[antal_workers]*: Antal parallella processer. Justera beroende på hur många processorkärnor din maskin har tillgång till. Standard är 4 om inget anges.

Skriptet hämtar WARC-filer och anropar ```run_pipeline_stage1.py``` för varje fil. Varje dokument bearbetas med en **Datatrove**-pipeline och filtreras antingen bort eller sparas i bearbetad och annoterad form i mappen `cc-stage1-output/`.

WARC-filerna raderas efter bearbetning för att spara utrymme. Om skriptet avbryts fortsätter det automatiskt från samma punkt vid omstart.

### Alternativ B: från lokala arkiv (t.ex. Kulturarw3)

Om du arbetar med data som redan finns lagrad lokalt skippar du nedladdningssteget och kör istället pythonskriptet ```run_pipeline_stage1.py``` direkt. 
För att skriptet ska hitta dina filer behöver du specificera
```data_folder``` i din ```WarcReader``` i koden, så att den hittar dina lokala WARC-arkiv.

#### 1. Konfigurera sökvägar
Se till att ```datafolder``` i din ```WarcReader``` i  `run_pipeline_stage1.py` pekar på mappen med dina lokala WARC-filer. Du kan också ange en mapp för utdata under ``output_folder`` i din ``JsonlWriter``. Se då till att efterföljande steg läser sin data från denna mapp.

#### 2. Parallellitet och loggning
I ```LocalPipelineExecutor``` kan du justera antal jobb som exekveringen ska delas in i och antal parallella trådar som samarbetar om de köade jobben (parametrarna ``tasks`` och ``workers``), samt mappen där körningsloggarna hamnar (parametern ``logging_dir``).

#### 3. Kör skriptet
Starta pipelinen via `uv`:

```bash
uv run python run_pipeline_stage1.py
```
---

## 📋 Utdatans struktur
Resultatet sparas i komprimerade JSONL-filer där varje rad följer Datatroves krav på toppnivåfält:

* **`text`**: Den extraherade texten
* **`id`**: Unikt identifierings-ID för dokumentet.
* **`metadata`**: Objekt som innehåller dokumentets kontext och annoteringar:
  * `url`: Ursprunglig webbadress.
  * `date`: Datum för insamling.
  * `file_path`: Sökväg till ursprunglig WARC-fil.
  * `html`: Den rensade HTML-koden.
  * `openlid_score`: OpenLid-poäng för språkidentifiering.
  * `statistics`: Objekt med strukturell statistik:
    * `link_count`: Antal länkar i dokumentet.
    * `button_count`: Antal knappar i dokumentet.







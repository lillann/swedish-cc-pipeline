#!/bin/bash

mkdir -p "cc-data"
# Skapa en mapp för att hålla reda på vilka WARC-filer som är 100% klara
mkdir -p "datatrove_logs/completed_files"

PATH_FILE="warc.paths"

process_single_file() {
    url=$1
    filename=$(basename "$url")
    
    # 1. Hoppa över helt om den är 100% klar sedan tidigare
    safe_name=$(echo "$url" | tr '/' '_')
    if [ -f "datatrove_logs/completed_files/$safe_name" ]; then
       
			  echo "[RESUME] Hoppar över $filename – redan färdigbehandlad!"
        
			  # Om filen ändå ligger kvar - ta bort den nu		  
			  number=${filename:38:5}
			  worker_id="worker_$number"
			  target_dir="cc-data/$worker_id"
			  if [ -d "$target_dir" ]; then
			  echo "[$worker_id] 🧹 Städar bort kvarlämnad cache-mapp för färdig fil."
			  rm -rf "$target_dir"
			  fi
        
			  return 0
    fi

    # Skapa unika mappar baserat på filens nummer
    number=${filename:38:5}
    worker_id="worker_$number"
    target_dir="cc-data/$worker_id"
    
    mkdir -p "$target_dir"
    
    # 2. Ladda BARA ner om filen inte redan ligger på disken sedan en krasch
    if [ ! -f "$target_dir/$filename" ]; then
        echo "[$worker_id] 📥 Hittade inte filen lokalt. Laddar ner: $filename..."
        if ! wget -q  -c --tries=5 "https://data.commoncrawl.org/$url" -P "$target_dir"; then
            echo "[$worker_id] ❌ FEL: Kunde inte ladda ner $url"
            rm -rf "$target_dir"
            return 1
        fi
    else
        echo "[$worker_id] 💾 [CACHE] Filen finns redan. Skippar download!"
    fi
    
    # 3. KÖR PYTHON
    echo "[$worker_id] 🧼 Kör Python-texttvätt..."
    rm -rf "logs/$worker_id"
    
    if uv run python run_pipeline.py "$target_dir" "$worker_id" "$number"; then
        # OM ALLT GICK BRA: Spara resume-markör och RADERA filen
        touch "datatrove_logs/completed_files/$safe_name"
        rm -rf "$target_dir"
        echo "[$worker_id] ✅ Klar, sparad och cache-mapp raderad."
    else
        # OM PYTHON KRASCHAR: Lämna kvar filen i cc-data/ 
        echo "[$worker_id] ⚠️ FEL: Python kraschade. Sparar WARC-filen på disk"
        return 1
    fi
}


caffeinate -i -w $$ &

# Exportera funktionen och loggmappen så xargs och underprocesserna ser dem
export -f process_single_file

echo "Startar bearbetning av $PATH_FILE med 4 parallella workers"

# -a läser från filen
# -L 1 tar en rad i taget
# -P 4 kör 4 processer parallellt
cat "$PATH_FILE" | xargs -L 1 -P 4 bash -c 'process_single_file "$0"'

echo "🎉 Hela din Common Crawl-shard är färdigbehandlad!"

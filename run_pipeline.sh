#!/bin/bash

# Om antal workers valts används det, annars faller vi tillbaka på 4 workers
WORKERS=${1:-4}
PYTHON_SCRIPT="run_pipeline_stage1.py"
export PYTHON_SCRIPT

# Skapa unika mappnamn baserat på vilket steg som körs
COMPLETED_DIR="datatrove_logs/completed_files"
CC_DATA_DIR="cc-data"
LOGS_DIR="logs/"

echo "🚀 Startar pipeline-steg $STEP med skriptet: $PYTHON_SCRIPT"
echo "⚙️ Antal parallella workers: $WORKERS"

mkdir -p "$CC_DATA_DIR"
mkdir -p "$COMPLETED_DIR"
mkdir -p "$LOGS_DIR"

PATH_FILE="warc.paths"

process_single_file() {
    url=$1
    filename=$(basename "$url")
    
    # 1. Hoppa över helt om den är 100% klar sedan tidigare
    safe_name=$(echo "$url" | tr '/' '_')
    if [ -f "datatrove_logs/completed_files/$safe_name" ]; then
       
			  echo "[RESUME] Hoppar över $filename – redan färdigbehandlad!"        
			  return 0
    fi

    # Skapa unika mappar baserat på filens nummer
    number=${filename:38:5}
    worker_id="worker_$number"
    target_dir="$CC_DATA_DIR/$worker_id"
    
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
    echo "[$worker_id] 🧼 Kör $PYTHON_SCRIPT..."
    rm -rf "$LOGS_DIR/$worker_id"
    
    if uv run python "$PYTHON_SCRIPT" --target_dir "$target_dir" --worker_id "$worker_id" --file_number "$number"; then
        # OM ALLT GICK BRA: Spara resume-markör och RADERA filen
        touch "$COMPLETED_DIR/$safe_name"
        rm -rf "$target_dir"
        echo "[$worker_id] ✅ Steg $STEP klar, sparad och cache-mapp raderad."
    else
        # OM PYTHON KRASCHAR: Lämna kvar filen i cc-data/ 
        echo "[$worker_id] ⚠️ FEL: Python kraschade i steg $STEP. Sparar WARC-filen på disk"
        return 1
    fi
}


# Kolla operativsystem
OS="$(uname -s)"

if [[ "$OS" == "Darwin" ]]; then
    # macOS
    caffeinate -i -w $$ &
elif [[ "$OS" == "Linux" ]] && command -v systemd-inhibit &> /dev/null; then
    # Linux (om systemd-inhibit finns tillgängligt)
    if [ -z "$RUNNING_INHIBITED" ]; then
        export RUNNING_INHIBITED=1
        exec systemd-inhibit --what=idle --why="CC Pipeline running" --mode=block bash "$0" "$@"
    fi
fi

# Exportera variabler och funktioner så xargs kommer åt dem i subshells
export COMPLETED_DIR
export CC_DATA_DIR
export LOGS_DIR
export PYTHON_SCRIPT
export -f process_single_file

echo "Startar bearbetning av $PATH_FILE för steg $STEP med $WORKERS parallella workers"

# -a läser från filen
# -L 1 tar en rad i taget
# -P 4 kör 4 processer parallellt
cat "$PATH_FILE" | xargs -L 1 -P "$WORKERS" bash -c 'process_single_file "$0"'

echo "🎉 Steg $STEP för hela Common Crawl-sharden är färdigt!"

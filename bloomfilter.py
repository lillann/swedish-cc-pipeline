import gzip
import hashlib
import json
import os
import time

from loguru import logger
from rbloom import Bloom

# INSTÄLLNINGAR
INPUT_DIR = "cc-output"  # Här ligger output-filerna från run_pipeline.py
OUTPUT_DIR = "cc-bloomfiltered"  # Här hamnar de unika filerna
BLOOM_FILE = "dedup_filter.bloom"  # Bloom-filtret på disk
PROGRESS_FILE = "dedup_progress.txt"  # Loggbok för avklarade filer
DUPLICATE_LOG = "removed_by_bloom.txt"


# BERÄKNAD KAPACITET
EXPECTED_ITEMS = 15_000_000  # Uppskattat antal svenska filer i hela cc-sharden
ERROR_RATE = 0.001


def rbloom_hash(text: str) -> int:
    """Gör om texten till en sha256-hash och transformera den till ett unikt heltal."""
    h = hashlib.sha256(text.strip().encode("utf-8")).digest()
    return int.from_bytes(h[:16], "big") - 2**127


def load_completed_files() -> set:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def mark_file_as_completed(filename: str):
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Ladda eller skapa rbloom-filter
    if os.path.exists(BLOOM_FILE):
        logger.info(f"💾 Hittade ett befintligt filter på disk. Laddar {BLOOM_FILE}...")
        bf = Bloom.load(BLOOM_FILE, hash_func=rbloom_hash)
    else:
        logger.info(
            f"✨ Skapar ett nytt Bloom-filter (Kapacitet: {EXPECTED_ITEMS:,}, Felmarginal: {ERROR_RATE * 100}%)"  # noqa: E501
        )
        bf = Bloom(
            expected_items=EXPECTED_ITEMS, false_positive_rate=ERROR_RATE, hash_func=rbloom_hash
        )
    # 2. Ladda historik över färdiga filer
    completed_files = load_completed_files()
    if completed_files:
        logger.info(
            f"📜 Hittade historik: {len(completed_files)} filer är redan klara sedan tidigare."
        )

    # 3. Hitta alla .jsonl.gz-filer direkt under cc-output
    all_files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith(".jsonl.gz")])

    if not all_files:
        logger.warning(f"⚠️ Inga .jsonl.gz-filer hittades direkt i mappen '{INPUT_DIR}'!")
        return

    logger.info(f"📂 Hittade totalt {len(all_files)} komprimerade filer att deduplicera.")

    total_processed = 0
    total_duplicates = 0

    try:
        for filename in all_files:
            # 1. RESUME-KOLL: Hoppa över om filen redan är helt klar
            if filename in completed_files:
                continue

            input_path = os.path.join(INPUT_DIR, filename)
            output_path = os.path.join(OUTPUT_DIR, filename)

            # 2. AKTIV FIL-KOLL: Hoppa över om en worker skriver i filen just nu
            try:
                last_modified = os.path.getmtime(input_path)
                age_in_seconds = time.time() - last_modified

                if age_in_seconds < 300:  # 300 sekunder = 5 minuter
                    logger.info(
                        f"⏳ [AKTIV] Hoppar över {filename} – skrivs till just nu av en worker."
                    )
                    continue
            except OSError:
                continue

            logger.info(f"🧼 Bearbetar: {filename}...")

            try:
                try:
                    # Öppna rådata, utmatning samt loggfilen för dubbletter
                    with (
                        gzip.open(input_path, "rt", encoding="utf-8") as infile,
                        gzip.open(output_path, "wt", encoding="utf-8") as outfile,
                        open(DUPLICATE_LOG, "a", encoding="utf-8") as duplog,
                    ):
                        for line in infile:
                            total_processed += 1
                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            text = data.get("text", "")

                            # Hämta URL inifrån Datatroves metadata-objekt
                            metadata = data.get("metadata", {})
                            url = metadata.get("url", "Ingen URL tillgänglig")

                            if text in bf:
                                total_duplicates += 1

                                # Skapa en ren textbit (utan radbryten) för loggfilen
                                clean_preview = text.strip().replace("\n", " ")
                                log_text_bit = clean_preview[:100]

                                # Skriv till filen
                                duplog.write(f'🗑️ DUP -> URL: {url} | Text: "{log_text_bit}..."\n')

                                # Stickprov i terminalen för vart 500:e dokument (visar lite mer text)  # noqa: E501
                                if total_duplicates % 500 == 0:
                                    logger.info("🗑️ [STICKPROV] Tog bort dubblett")
                                    print(f"   URL:  {url}")
                                    print(f'   Text: "{clean_preview[:200]}..."\n')
                            else:
                                bf.add(text)
                                outfile.write(line)

                    # Spara framsteg och filter efter varje lyckad fil
                    mark_file_as_completed(filename)
                    bf.save(BLOOM_FILE)
                    logger.info(
                        f"📊 Status efter {filename}: {total_processed:,} dokument kollade. {total_duplicates:,} dubbletter."  # noqa: E501
                    )

                except (EOFError, OSError) as e:
                    logger.error(
                        f"⚠️ Avbruten läsning i {filename} ({str(e)}). Försöker igen nästa körning."
                    )
                    bf.save(BLOOM_FILE)
                    continue

                # Spara framsteg och filter direkt när en fil är 100% klar
                mark_file_as_completed(filename)
                bf.save(BLOOM_FILE)
                logger.info(
                    f"📊 Status efter {filename}: {total_processed:,} dokument kollade. {total_duplicates:,} dubbletter."  # noqa: E501
                )

            except (EOFError, OSError) as e:
                # Om en worker ändå hann krocka med oss, sparar vi bara och går vidare
                logger.error(
                    f"⚠️ Avbruten läsning i {filename} ({str(e)}). Försöker igen nästa körning."
                )
                bf.save(BLOOM_FILE)
                continue

    except KeyboardInterrupt:
        logger.warning("\n🛑 Processen avbröts manuellt! Sparar filterstatus på disk...")
        bf.save(BLOOM_FILE)
        logger.info("💾 Status sparad. Du kan starta om skriptet när du vill för att fortsätta.")
        return

    logger.info("🎉 DEDUPLICERING MED BLOOM FILTER KLAR!")
    logger.info(f"📊 Totalt genomsökta dokument i denna session: {total_processed:,}")
    logger.info(f"🗑️ Bortsorterade dubbletter i denna session: {total_duplicates:,}")
    logger.info(f"✨ Rena filer sparade i: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

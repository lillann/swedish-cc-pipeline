import os

from datatrove.executor import LocalPipelineExecutor
from datatrove.pipeline.dedup import (
    MinhashConfig,
    MinhashDedupBuckets,
    MinhashDedupCluster,
    MinhashDedupFilter,
    MinhashDedupSignature,
)
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.writers import JsonlWriter
from datatrove.utils.typeshelper import Languages


def main():
    # --- KONFIGURATION ---
    INPUT_FOLDER = "cc-bloomfiltered"
    SIGS_DIR = "dedup_results/sigs"
    BUCKETS_DIR = "dedup_results/buckets"
    OUTPUT_DIR = "dedup_results/deduplicated"
    REMOVED_DIR = "dedup_results/removed"
    LOGS_DIR = "dedup_logs"

    # Detta ger en Jaccard-tröskel på 0.72
    # Detta är "industristandard" vid LLM-träning.
    # OBS: För källkod vill man ofta deduplicera mer aggressivt, med num_buckets=32, hashes_per_bucket=4.
    conf = MinhashConfig(n_grams=5, num_buckets=14, hashes_per_bucket=8)

    # --- STEG 1: SIGNATURES ---
    # Läser JSONL och skapar fingerprints (.sig)
    print(">>> Kör Steg 1: Signature...")
    signature_executor = LocalPipelineExecutor(
        pipeline=[
            JsonlReader(data_folder=INPUT_FOLDER),
            MinhashDedupSignature(output_folder=SIGS_DIR, config=conf, language=Languages.swedish),
        ],
        tasks=1,
        logging_dir=os.path.join(LOGS_DIR, "s1"),
    )
    signature_executor.run()

    # --- STEG 2: BUCKETS ---
    # Jämför signaturer och skapar dubblettförteckning (.dups)
    print("\n>>> Kör Steg 2: Buckets...")
    buckets_executor = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupBuckets(input_folder=SIGS_DIR, output_folder=BUCKETS_DIR, config=conf)
        ],
        tasks=28,  # Måste vara delbart med num_buckets (1/1 = ok)
        logging_dir=os.path.join(LOGS_DIR, "s2"),
    )
    buckets_executor.run()

    cluster_executor = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupCluster(
                input_folder=BUCKETS_DIR,
                output_folder=REMOVED_DIR + "/remove_ids",
                config=conf,
            ),
        ],
        tasks=1,
        logging_dir=os.path.join(LOGS_DIR, "s3"),
    )

    cluster_executor.run()

    # --- STEG 3: FILTER ---
    # Läser källfilen igen och kastar dokument som finns i .dups-listan
    print("\n>>> Kör Steg 3: Filter...")
    filter_step = MinhashDedupFilter(
        input_folder=REMOVED_DIR + "/remove_ids",
        exclusion_writer=JsonlWriter(REMOVED_DIR + "/remove_docs"),  # Skriver borttagna doc hit
    )

    # -- STEG 4 --
    filter_executor = LocalPipelineExecutor(
        pipeline=[
            JsonlReader(data_folder="cc-bloomfiltered"),
            filter_step,
            JsonlWriter(OUTPUT_DIR),  # Den slutgiltiga rena datan
        ],
        tasks=1,
        logging_dir=os.path.join(LOGS_DIR, "s4"),
    )
    filter_executor.run()

    print(f"\n✅ Klart! Unik data finns i: {OUTPUT_DIR}")
    print(f"❌ Dubbletter flyttades till: {REMOVED_DIR}")


if __name__ == "__main__":
    main()

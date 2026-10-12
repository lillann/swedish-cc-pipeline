import argparse

import numpy as np
from datatrove.data import DocumentsPipeline
from datatrove.executor import LocalPipelineExecutor
from datatrove.pipeline.readers import WarcReader
from datatrove.pipeline.writers.jsonl import JsonlWriter

from src.filters import BlacklistFilter, OpenLidFilter
from src.HTML_preprocessor import HTMLPreprocessor, TextExtractor
from src.utils.writers import RemovedUrlWriter

_orig_array = np.array


# Förhindrar att fasttext kraschar.
def _safe_array(obj, *args, **kwargs):
    kwargs["copy"] = True
    try:
        return _orig_array(obj, *args, **kwargs)
    except TypeError:
        return _orig_array(obj, *args, copy=True)


np.array = _safe_array


def print_document(
    pipeline: DocumentsPipeline, rank: int = 0, world_size: int = 1
) -> DocumentsPipeline:
    for doc in pipeline:
        print("\n" + "=" * 50)
        print("\n" + doc.metadata["url"])
        print("=" * 50)
        print(doc.text)
        print("=" * 50 + "\n")
        yield doc


parser = argparse.ArgumentParser(description="Run pipeline stage 1")
parser.add_argument(
    "--target_dir", type=str, required=True, help="Sökväg till mappen med WARC-filer (obligatorisk)"
)
parser.add_argument("--output_dir", type=str, default="stage1-output", help="Mapp för utdata")
parser.add_argument("--worker_id", type=str, default="0", help="Worker ID")
parser.add_argument("--file_number", type=str, default="0", help="Filnummer")
parser.add_argument("--tasks", type=int, default=1, help="Antal tasks")
parser.add_argument("--workers", type=int, default=1, help="Antal parallella workers")

args = parser.parse_args()

output_dir = args.output_dir
target_dir = args.target_dir
worker_id = args.worker_id
file_number = args.file_number
tasks = args.tasks
workers = args.workers

pipeline = [
    # Läser in Warc-filer från target_dir
    WarcReader(
        data_folder=target_dir,
        paths_file=None,
        doc_progress=False,
    ),
    # Filtrerar bort dokument med svartlistad url
    BlacklistFilter(
        category_paths=[
            "./blacklists/adult",
            "./blacklists/dangerous_material",
            "./blacklists/phishing",
            "./blacklists/fakenews",
        ],
        exclusion_writer=RemovedUrlWriter(output_folder="removed_urls/blacklist"),
    ),
    # Extraherar ungefärlig text (för språkidentifiering i nästa steg)
    TextExtractor(),
    # Filtrerar ut svenska dokument
    OpenLidFilter(
        target_lang="swe_Latn",
        threshold=0.5,
        exclusion_writer=RemovedUrlWriter(output_folder="removed_urls/openlid"),
    ),
    # Städar HTML till ett mer lättviktigt format
    HTMLPreprocessor(),
    # Skriver ut de filtrerade och bearbetade filerna
    JsonlWriter(
        output_dir,
        output_filename=f"stage1_{file_number}_" + "${rank}.jsonl.gz",
    ),
]

executor = LocalPipelineExecutor(
    pipeline=pipeline,
    tasks=tasks,
    workers=workers,
    logging_dir=f"./datatrove_logs/workers/{worker_id}",
)

if __name__ == "__main__":
    executor.run()

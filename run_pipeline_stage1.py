import numpy as np
import sys
import argparse
from datatrove.data import DocumentsPipeline
from datatrove.executor import LocalPipelineExecutor
from datatrove.pipeline.filters import LanguageFilter
from src.filters import OpenLidFilter,BlacklistFilter
from datatrove.pipeline.readers import WarcReader
from datatrove.pipeline.writers.jsonl import JsonlWriter

from src.HTML_preprocessor import HTMLPreprocessor, TextExtractor
from src.annotation import TextContentsStats, PropellaAnnotator

_orig_array = np.array

#Förhindrar att fasttext kraschar.
def _safe_array(obj, *args, **kwargs):
    kwargs['copy'] = True
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
        print("\n" + doc.metadata['url'])
        # print(f"ID: {doc.id} | KLASS: {doc.metadata.get('document_class')}")
        print("=" * 50)
        print(doc.text)
        print("=" * 50 + "\n")
       # print(doc.metadata['propella'])
        yield doc


parser = argparse.ArgumentParser(description="Run pipeline stage 1")
parser.add_argument(
    "--target_dir", 
    type=str, 
    default="./cc-data", # Standardmapp om du kör lokalt utan args
    help="Sökväg till WARC-filer"
)
parser.add_argument(
    "--worker_id", 
    type=str, 
    default="0",                 # Standardvärde för lokal körning
    help="Worker ID"
)
parser.add_argument(
    "--file_number", 
    type=str, 
    default="0",                 # Standardvärde för filnummer
    help="Filnummer"
)

args = parser.parse_args()

# Använd värdena från argparse istället för sys.argv
target_dir = args.target_dir
worker_id  = args.worker_id
file_number = args.file_number

pipeline = [
    WarcReader(
    
        data_folder=target_dir,  # "https://data.commoncrawl.org",
        paths_file=None,  # "warc.paths",
        doc_progress=False,  # går snabbare utan
    ),
    BlacklistFilter(
            category_paths=[
                "./blacklists/adult",
                "./blacklists/dangerous_material",
                "./blacklists/phishing",
                "./blacklists/fakenews"
            ],
            exclusion_writer=JsonlWriter(output_folder="removed_urls")
        ),
    TextExtractor(), # Extraherad text för språkfiltret
    OpenLidFilter(target_lang="swe_Latn", threshold=0.5), # Filtrerar bort allt som inte är svenska     
    HTMLPreprocessor(), # Städar HTML men bevarar struktur 
    JsonlWriter(  # Skriver ut som jsonl
        "cc-stage1-output",
        output_filename=f"cc_data_{file_number}_" + "${rank}.jsonl.gz",
    ),
]

executor = LocalPipelineExecutor(
    pipeline=pipeline, tasks=1, workers=1, logging_dir=f"./datatrove_logs/workers/{worker_id}"
)

if __name__ == "__main__":
    executor.run()

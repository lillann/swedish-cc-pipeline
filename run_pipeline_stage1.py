import numpy as np

_orig_array = np.array

#Förhindrar att fasttext kraschar.
def _safe_array(obj, *args, **kwargs):
    kwargs['copy'] = True
    try:
        return _orig_array(obj, *args, **kwargs)
    except TypeError:
        return _orig_array(obj, *args, copy=True)
np.array = _safe_array

import sys

from datatrove.data import DocumentsPipeline
from datatrove.executor import LocalPipelineExecutor
from datatrove.pipeline.filters import LanguageFilter
from src.filters import OpenLidFilter
from datatrove.pipeline.readers import WarcReader
from datatrove.pipeline.writers.jsonl import JsonlWriter

from src.HTML_preprocessor import HTMLPreprocessor, TextExtractor
from src.statistics import TextContentsStats, HTMLStats, PropellaAnnotator


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


# Tar emot argument från Bash
target_dir = sys.argv[1]
worker_id = sys.argv[2]
file_number = sys.argv[3]

pipeline = [
    WarcReader(
    
        data_folder=target_dir,  # "https://data.commoncrawl.org",
        paths_file=None,  # "warc.paths",
        doc_progress=False,  # går snabbare utan
    ),
    
    # lägg till URL-filtrering här!
    
    TextExtractor(), # Extraherad text för språkfiltret och Propella-annotering
    OpenLidFilter(target_lang="swe_Latn", threshold=0.5), # Filtrerar bort allt som inte är svenska
  #  LanguageFilter(languages=["sv"], language_threshold=0.75),
   
    #   TextContentsStats(),    
    # Eventuellt filtrera här baserat på statistiken 
    
    #PropellaAnnotator(), # Vi sparar först och annoterar sen!
    # Eventuellt filtrera här baserat på annoteringen (t.ex. "content_ratio: mostly_navigation" bör vi kunna ta bort)
        
    HTMLPreprocessor(), # Städar HTML men bevarar struktur 
    print_document,  # Printar den extraherade texten och propella-annoteringar
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

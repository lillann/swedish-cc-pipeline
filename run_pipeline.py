import sys

from datatrove.data import DocumentsPipeline
from datatrove.executor import LocalPipelineExecutor
from datatrove.pipeline.filters import GopherRepetitionFilter, LanguageFilter
from datatrove.pipeline.readers import WarcReader
from datatrove.pipeline.writers.jsonl import JsonlWriter

from src.classifiers import ClassifyDoc
from src.extractors import SimpleExtractor
from src.filters import DecodeUTF8Filter, OnlyHTMLFilter, SwedishQualityFilter


def print_document(
    pipeline: DocumentsPipeline, rank: int = 0, world_size: int = 1
) -> DocumentsPipeline:
    for doc in pipeline:
        print("\n" + "=" * 50)
        print(f"ID: {doc.id} | KLASS: {doc.metadata.get('document_class')}")
        print("=" * 50)
        print(doc.text[:500] + "...")
        print("=" * 50 + "\n")
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
    DecodeUTF8Filter(),
    # Förhindrar unicode-decode error i beautifulsoup
    OnlyHTMLFilter(),
    # Tar bort icke-html
    ClassifyDoc(),
    # klassificerar som "article" och "discussion"
    SimpleExtractor(),
    # extraherar texten och städar bort skräp. Döljer adresser och telefonnummer.
    LanguageFilter(languages=["sv"], language_threshold=0.75),
    # Släpper igenom dokument med minst 75% svenska
    SwedishQualityFilter(),
    # Extra filter som tar bort skräp baserat på stopp-ord och radlängd,
    # slänger text med mkt asiatiaska tecken (=spam)
    GopherRepetitionFilter(),  # Tar bort repeterat skräp
    print_document,  # Printar den extraherade texten
    JsonlWriter(  # Skriver ut som jsonl
        "cc-output",
        output_filename=f"cc_data_{file_number}_" + "${rank}.jsonl.gz",
    ),
]

executor = LocalPipelineExecutor(
    pipeline=pipeline, tasks=1, workers=1, logging_dir=f"./datatrove_logs/workers/{worker_id}"
)

if __name__ == "__main__":
    executor.run()

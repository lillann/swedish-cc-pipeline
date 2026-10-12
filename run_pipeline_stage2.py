import argparse

from datatrove.executor.local import LocalPipelineExecutor
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.writers import JsonlWriter
from src.extractors import TrafilaturaExtractor
from src.annotation import TextContentsStats

parser = argparse.ArgumentParser(description="Run pipeline stage 2")
parser.add_argument(
    "--target_dir", 
    type=str, 
    default="./bloomfiltered_data", # Standardmapp för indata
    help="Sökväg till WARC-filer"
)

parser.add_argument(
    "--output_dir", 
    type=str, 
    default="stage2-output",     # Standardmapp för utdata
    help="Mapp för utdata"
)
parser.add_argument(
    "--tasks", 
    type=int, 
    default=1, 
    help="Antal tasks"
)
parser.add_argument(
    "--workers", 
    type=int, 
    default=1, 
    help="Antal parallella workers"
)

parser.add_argument(
    "--log_dir", 
    type=str, 
    default="datatrove_logs_stage2", 
    help="Datatrove logging directory"
)


args = parser.parse_args()

target_dir = args.target_dir
output_dir = args.output_dir
tasks = args.tasks
workers = args.workers
logging_dir = args.log_dir



pipeline = [
    # Läser in data
    JsonlReader(data_folder=target_dir),
    # Extraherar brödtext ur HTML
    TrafilaturaBareExtractor(),
    # Beräknar statistik baserat på texten och lägger in i metadata
    TextContentsStats(),
    # Skriver ut dokumenten
    JsonlWriter(output_folder=output_dir)
]

executor = LocalPipelineExecutor(
    pipeline=pipeline,
    tasks=tasks,  
    workers=workers, 
    logging_dir=logging_dir
)

if __name__ == "__main__":
    executor.run()

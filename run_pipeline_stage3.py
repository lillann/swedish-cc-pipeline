import argparse

from datatrove.executor.local import LocalPipelineExecutor
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.writers import JsonlWriter
from src.annotation import PropellaAnnotator, TextContentsStats

parser = argparse.ArgumentParser(description="Run pipeline stage 3")
parser.add_argument(
    "--target_dir", 
    type=str, 
    default="./minhash-output/deduplicated/", # Standardmapp om du kör lokalt utan args
    help="Sökväg till WARC-filer"
)

parser.add_argument(
    "--output_dir", 
    type=str, 
    default="stage3-output",     # Standardvärde för utdata-mapp
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
    default="datatrove_logs_stage3", 
    help="Datatrove logging directory"
)

args = parser.parse_args()

target_dir = args.target_dir
output_dir = args.output_dir
tasks = args.tasks
workers = args.workers
logging_dir = args.log_dir



pipeline = [
    JsonlReader(data_folder=target_dir),
    TextContentsStats(),    
    PropellaAnnotator(api_base="http://localhost:8000/v1"),
    JsonlWriter(output_folder="stage3-output")
]

executor = LocalPipelineExecutor(
    pipeline=pipeline,
    tasks=tasks,
    workers=workers,  
    logging_dir=logging_dir
)

if __name__ == "__main__":
    executor.run()

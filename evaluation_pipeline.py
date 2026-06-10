import argparse
import html
import json
import os

import pandas as pd
from datatrove.pipeline.base import PipelineStep
from datatrove.pipeline.extractors import Trafilatura
from datatrove.pipeline.filters import GopherRepetitionFilter, LanguageFilter
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.writers.jsonl import JsonlWriter

from src.classifiers import ClassifyDoc
from src.evaluator import DiscardAuditTracker, EvaluatorWithAudit
from src.extractors import HtmlPreprocessor, SimpleExtractor, TableLinker
from src.filters import DecodeUTF8Filter, OnlyHTMLFilter, SwedishQualityFilter


class PrintDocument(PipelineStep):
    type = "👀 PrintDocument"

    def run(self, data, ri: int = 0, oi: int = 0):
        for doc in data:
            print("\n" + "=" * 50)
            print(f"ID: {doc.id} | KLASS: {doc.metadata.get('document_class')}")
            print("=" * 50)
            print(doc.text[:500] + "...")
            yield doc


class CommandLineIdInspector(PipelineStep):
    type = "🔬 CommandLineIdInspector"

    def __init__(self, gold_folder: str, doc_id: str):
        super().__init__()
        self.gold_folder = gold_folder
        self.doc_id = doc_id

    def _get_gold_text(self, doc_id):
        """Hämtar guldtexten genom att matcha UUID-numret"""
        clean_doc_id = doc_id.lower().replace("urn:uuid:", "")

        for file in os.listdir(self.gold_folder):
            if file.endswith(".jsonl") or file.endswith(".json"):
                with open(os.path.join(self.gold_folder, file), "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            gold_id = data.get("id", "").lower().replace("urn:uuid:", "")
                            if clean_doc_id in gold_id or gold_id in clean_doc_id:
                                return data.get("text", "").strip()
                        except Exception:
                            continue
        return f"[ID '{doc_id}' hittades inte i mappen '{self.gold_folder}']"

    def run(self, data, ri: int = 0, oi: int = 0):
        for doc in data:
            if self.doc_id:
                clean_doc_id = doc.id.lower().replace("urn:uuid:", "")
                if self.doc_id in clean_doc_id:
                    gold_text = self._get_gold_text(doc.id)

                    print("\n" + "═" * 60, flush=True)
                    print(f"🎯 ISOLERAD TEXT-ANALYS FÖR ID: {doc.id}", flush=True)
                    print("═" * 60, flush=True)

                    print("\n🌟 [GULDSTANDARD / FACIT]:", flush=True)
                    print("─" * 50, flush=True)
                    print(gold_text, flush=True)
                    print("─" * 50, flush=True)

                    print("\n🚀 [DIN EXTRAHERADE TEXT]:", flush=True)
                    print("─" * 50, flush=True)
                    print(doc.text if doc.text else "[Tom text]", flush=True)
                    print("─" * 50, flush=True)
                    print("═" * 60 + "\n", flush=True)
                    # doc.metadata["is_target"] = True
                    yield doc
                else:
                    continue
            else:
                yield doc


def html_unescape_adapter(reader, data, *args, **kwargs):

    raw_text = data.get("html", data.get("text", ""))

    # Av-escapa HTML-koden
    clean_text = html.unescape(raw_text)

    # Returnera ett format som DataTrove förväntar sig (måste ha "text" och "id")
    text = data.get("text", "")
    return {
        "text": clean_text,  # html-koden
        "id": data.get(reader.id_key),
        "metadata": {"url": data.get("url"), "text": text},  # url och guldtexten
    }


def run_experiment(pipeline_steps, experiment_name, data_folder, doc_id, output_dir):

    # Håller reda på anledningarna till varför dokumenten slängs
    audit_tracker = DiscardAuditTracker()
    evaluator = EvaluatorWithAudit(audit_tracker=audit_tracker, doc_id=doc_id)

    html_preprocessor = HtmlPreprocessor()
    reader = JsonlReader(data_folder=data_folder, adapter=html_unescape_adapter)
    table_linker = TableLinker()
    id_inspector = CommandLineIdInspector(gold_folder=data_folder, doc_id=doc_id)

    full_pipeline = (
        [reader, html_preprocessor]
        + pipeline_steps
        + [table_linker, audit_tracker, evaluator, id_inspector]
    )

    if output_dir:
        safe_name = "".join([c if c.isalnum() else "_" for c in experiment_name])
        filename = f"output_{safe_name}.jsonl"
        writer = JsonlWriter(  # Skriver ut som jsonl
            output_folder=output_dir, output_filename=filename
        )
        full_pipeline = full_pipeline + [writer]

    input_documents = []
    lost_docs = 0
    saved_docs = 0
    avg_rouge1 = 0.0
    recall = 0.0
    step_breakdown = {}

    try:
        input_documents = list(reader.run())

        if not input_documents:
            return None

        # Om vi angett doc_id: ignorera alla dokument där doc_id inte matchar
        if doc_id:
            current_stream = [doc for doc in input_documents if doc_id in doc.id]
        else:
            current_stream = input_documents

        for step in full_pipeline[1:]:
            ids_before = {doc.id for doc in current_stream}

            output_stream = list(step.run(current_stream))
            ids_after = {doc.id for doc in output_stream}

            if doc_id:
                ids_after = {doc.id for doc in output_stream}

            dropped_ids = ids_before - ids_after

            for doc in current_stream:
                if doc.id in dropped_ids:
                    if "filter_reason" not in doc.metadata:
                        doc.metadata["filter_reason"] = f"Filtrerad av {step.name}"
                    audit_tracker.run_filter_tracker(doc, filtered_out=True)
            current_stream = output_stream

        lost_docs = audit_tracker.discarded_docs
        saved_docs = evaluator.successful_extractions

        lost_docs = len(lost_docs)
        valid_gold_documents = [
            doc.id
            for doc in input_documents
            if doc.metadata.get("text")
            and str(doc.metadata["text"]).strip()
            and (not doc_id or doc_id in doc.id)
        ]

        total_valid_gold = len(valid_gold_documents)
        total_saved_docs = len(saved_docs)

        avg_rouge1 = (evaluator.total_rouge1 / total_saved_docs) if total_saved_docs > 0 else 0.0
        recall = (
            len(set(saved_docs).intersection(valid_gold_documents)) / total_valid_gold
            if total_valid_gold > 0
            else 0.0
        )
        precision = (
            len(set(saved_docs).intersection(valid_gold_documents)) / total_saved_docs
            if total_saved_docs > 0
            else 0.0
        )

        for dropped in audit_tracker.discarded_docs:
            reason = dropped["reason"]
            url = dropped["url"]
            step_breakdown[reason] = step_breakdown.get(reason, []) + [url]

        safe_name = "".join([c if c.isalnum() else "_" for c in experiment_name])
        filename = f"diff_{safe_name}.txt"

        if evaluator.diff_records:
            with open(filename, "w", encoding="utf-8") as f_diff:
                f_diff.write("============================================================\n")
                f_diff.write(f"🔬 DETALJERAD DIFF-RAPPORT FÖR: {experiment_name}\n")
                f_diff.write("============================================================\n")
                for rec in evaluator.diff_records:
                    f_diff.write(f"\n📝 Dokument ID: {rec['id']}\n")
                    f_diff.write(f"📈 ROUGE-1 (F1): {rec['rouge1']:.4f}\n")
                    f_diff.write(
                        "❌ MISSLYCKADES AT EXTRAHERA (Fanns i guld, saknas i den extraherade texten):\n"  # noqa: E501
                    )
                    f_diff.write(
                        f"   {', '.join(rec['missing']) if rec['missing'] else '[Inga missade ord]'}\n"  # noqa: E501
                    )
                    f_diff.write(
                        "➕ EXTRAHERADE FÖR MYCKET SKRÄP (Fanns inte i guld, kom med ändå):\n"
                    )
                    f_diff.write(
                        f"   {', '.join(rec['extra']) if rec['extra'] else '[Inget extra skräp]'}\n"
                    )
                    f_diff.write("-" * 60 + "\n")

    except Exception as e:
        print(f"\n🚨 FEL UNDER EXEKVERING: {e}")
        return None

    return {
        "Sparade": len(saved_docs),
        "Kastade": lost_docs,
        "Recall": f"{recall * 100:.1f}%",
        "Precision": f"{precision * 100:.1f}%",
        "   ROUGE-1 (F1)": round(avg_rouge1, 4),
        "_breakdown": step_breakdown,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Utvärdera experimentella pipelines mot gulddata.")

    parser.add_argument(
        "--gold-dir",
        type=str,
        default="gold_dir",
        help="Sökväg till mappen som innehåller gulddata",
    )

    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,  
        help="Specifik (delsträng av) dokument-ID för sida-vid-sida-jämförelse",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Skriv ut resultaten till <output-dir>/output_<experiment name>.jsonl",
    )

    args = parser.parse_args()

    gold_directory = args.gold_dir

    document_id = args.doc_id

    output_dir = args.output_dir

    print(
        f"🚀 Startar utvärdering av olika pipeline-komponenter med gulddata från: {gold_directory}\n"  # noqa: E501
    )

    if document_id:
        print(f"Granskar specifikt dokument med ID: {document_id}")
  
    experiments = {
        "Standard-pipeline (Default-värden)": [
            DecodeUTF8Filter(),
            OnlyHTMLFilter(),
            ClassifyDoc(),
            SimpleExtractor(),
            LanguageFilter(languages=["sv"], language_threshold=0.75),
            SwedishQualityFilter(),
            GopherRepetitionFilter(),
        ],
        "Milt kvalitetsfilter (Tillåt kortare artiklar)": [
            DecodeUTF8Filter(),
            OnlyHTMLFilter(),
            ClassifyDoc(),
            SimpleExtractor(min_length_article=50),
            LanguageFilter(languages=["sv"], language_threshold=0.75),
            SwedishQualityFilter(),
            GopherRepetitionFilter(),
        ],
        "Strängt kvalitetsfilter (Rensa hårdare)": [
            DecodeUTF8Filter(),
            OnlyHTMLFilter(),
            ClassifyDoc(),
            SimpleExtractor(min_length_article=300),
            LanguageFilter(languages=["sv"], language_threshold=0.85),
            SwedishQualityFilter(min_stop_words=0.15),
            GopherRepetitionFilter(),
        ],
        "Trafilatura istället för SimpleExtractor": [
            DecodeUTF8Filter(),
            OnlyHTMLFilter(),
            ClassifyDoc(),
            Trafilatura(
                timeout=5,
                favour_precision=True,
                include_tables=False,
                include_formatting=True,
                output_format="txt",
            ),
            LanguageFilter(languages=["sv"], language_threshold=0.75),
            GopherRepetitionFilter(),
            # C4QualityFilter(),
        ],
    }

    results = {}
    breakdowns = {}
    trackers = {}
    # Kör alla experiment
    for name, steps in experiments.items():
        print(f"Kör experiment: {name}...")

        res = run_experiment(steps, name, gold_directory, document_id, output_dir)
        if res:
            # Separera breakdowns från huvudtabellen
            breakdowns[name] = res.pop("_breakdown")
            results[name] = res

    # Presentera resultaten i en tabell
    if results:
        df = pd.DataFrame(results).T
        print("\n" + "=" * 85)
        print("📊 JÄMFÖRELSE AV PIPELINES")
        print("=" * 85)
        print(df.to_string())
        print("=" * 85)

        # Skriv ut var dokumenten dog för respektive experiment
        print("\n🛑 RESULTAT PER EXPERIMENT:")
        for name, b_data in results.items():
            print(f"\n🔹 {name}:")
            if b_data:
                for step_name, count in b_data.items():
                    print(f"   -> {step_name}: {count} st")

                breakdowns_name = breakdowns[name]
                if breakdowns_name:
                    print("")
                    for reason in breakdowns_name:
                        print(reason + ":", len(breakdowns[name][reason]))
                        print("exempel: ", breakdowns[name][reason][0], "\n")
            else:
                print("Inga dokument filtrerades bort!")
        print()

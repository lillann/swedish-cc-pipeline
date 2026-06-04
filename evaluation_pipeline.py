
import html

import pandas as pd
from datatrove.pipeline.extractors import Trafilatura
from datatrove.pipeline.filters import GopherRepetitionFilter, LanguageFilter
from datatrove.pipeline.readers import JsonlReader

from src.classifiers import ClassifyDoc
from src.evaluator import DiscardAuditTracker, EvaluatorWithAudit
from src.extractors import HtmlPreprocessor, SimpleExtractor, TableLinker
from src.filters import DecodeUTF8Filter, OnlyHTMLFilter, SwedishQualityFilter


def html_unescape_adapter(reader, data,*args, **kwargs):
   
    raw_text = data.get("html", data.get("text", ""))
    
    # Av-escapa HTML-koden
    clean_text = html.unescape(raw_text)
    
    # Returnera ett format som DataTrove förväntar sig (måste ha "text" och "id")
    text = data.get("text","")
    return {        
        "text": clean_text, # html-koden
        "id": data.get(reader.id_key),
        "metadata" : {"url" : data.get("url"), "text" : text} # url och guldtexten
    }


def run_experiment(pipeline_steps, experiment_name):

    # Håller reda på anledningarna till varför dokumenten slängs
    audit_tracker = DiscardAuditTracker()
    evaluator = EvaluatorWithAudit(audit_tracker=audit_tracker)

    html_preprocessor = HtmlPreprocessor()

    reader = JsonlReader(data_folder="guldfiler", adapter=html_unescape_adapter)
    table_linker = TableLinker()
    full_pipeline = (
        [reader, html_preprocessor] + pipeline_steps + [table_linker, audit_tracker, evaluator]
    )

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

        current_stream = input_documents

        for step in full_pipeline[1:]:
            ids_before = {doc.id for doc in current_stream}
            output_stream = list(step.run(current_stream))

            ids_after = {doc.id for doc in output_stream}
            dropped_ids = ids_before - ids_after

            for doc in current_stream:
                if doc.id in dropped_ids:
                    if "filter_reason" not in doc.metadata:
                        doc.metadata["filter_reason"] = f"Filtrerad av {step.name}"
                    audit_tracker.run_filter_tracker(doc, filtered_out=True)
            current_stream = output_stream

        lost_docs = len(audit_tracker.discarded_docs)
        saved_docs = evaluator.successful_extractions

        valid_gold_documents = [
            doc.id
            for doc in input_documents
            if doc.metadata.get("text") and str(doc.metadata["text"]).strip()
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
    # for doc in valid_gold_documents :
    #  print(doc)
    # print()
    return {
        "Sparade": len(saved_docs),
        "Kastade": lost_docs,
        "Recall": f"{recall * 100:.1f}%",
        "Precision": f"{precision * 100:.1f}%",
        "   ROUGE-1 (F1)": round(avg_rouge1, 4),
        "_breakdown": step_breakdown,
    }


if __name__ == "__main__":
    print("🚀 Startar utvärdering av olika pipeline-komponenter...\n")

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
            SwedishQualityFilter(min_stop_words=1),
            LanguageFilter(languages=["sv"], language_threshold=0.75),
            GopherRepetitionFilter(),
        ],
        "Strängt kvalitetsfilter (Rensa hårdare)": [
            DecodeUTF8Filter(),
            OnlyHTMLFilter(),
            ClassifyDoc(),
            SimpleExtractor(min_length_article=300),
            LanguageFilter(languages=["sv"], language_threshold=0.85),
            # SwedishQualityFilter(min_stop_words=5),
            GopherRepetitionFilter(),
        ],
        "Trafilatura istället för SimpleExtractor": [
            DecodeUTF8Filter(),
            OnlyHTMLFilter(),
            ClassifyDoc(),
            Trafilatura(
                timeout=5, favour_precision=True, include_tables=False, output_format="txt"
            ),
            LanguageFilter(languages=["sv"], language_threshold=0.75),
            GopherRepetitionFilter(),
        ],
    }

    results = {}
    breakdowns = {}
    trackers = {}
    # Kör alla experiment
    for name, steps in experiments.items():
        print(f"Kör experiment: {name}...")

        res = run_experiment(steps, name)
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

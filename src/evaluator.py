from collections import Counter

from datatrove.pipeline.base import PipelineStep


# --- 1. FÅNGAR UPP BORTFILTRERADE DOKUMENT ---
class DiscardAuditTracker(PipelineStep):
    """
    Detta dolda steg lyssnar på vad som slängs i pipelinen.
    DataTrove har en intern funktion där filter registrerar slängda dokument.
    """

    type = "🔍 Audit Tracker"

    def __init__(self):
        super().__init__()
        self.discarded_docs = []

    def run(self, data, rank: int = 0, world_size: int = 1):
        # De dokument som överlever skickas vidare till nästa steg
        for doc in data:
            yield doc

    def run_filter_tracker(self, doc, filtered_out=False):
        # DataTrove anropar denna funktion för varje dokument som slängs
        if filtered_out:
            # Spara information om vilket filter som tog bort det och dokumentets ID
            reason = doc.metadata.get("filter_reason", "Okänt filter")

            self.discarded_docs.append(
                {
                    "id": doc.id,
                    "url": doc.metadata["url"],
                    "reason": reason,
                    "text_snippet": doc.text[:200] if doc.text else "[Ingen text extraherad]",
                }
            )


class EvaluatorWithAudit(PipelineStep):
    name = "📊 Evaluator"

    def __init__(self, audit_tracker: DiscardAuditTracker, doc_id=None):
        super().__init__()
        self.audit_tracker = audit_tracker
        self.successful_extractions = []
        self.total_rouge1 = 0.0
        self.diff_records = []
        self.doc_id = doc_id

    def _calculate_rouge1(self, str1: str, str2: str) -> float:
        # Beräkna rouge-1-score manuellt
        words1 = str1.lower().split()
        words2 = str2.lower().split()
        if not words1 or not words2:
            return 0.0

        c1, c2 = Counter(words1), Counter(words2)
        overlap = sum((c1 & c2).values())

        precision = overlap / len(words1)
        recall = overlap / len(words2)

        if (precision + recall) == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    def run(self, data, rank: int = 0, world_size: int = 1):
        for doc in data:
            if self.doc_id and self.doc_id not in doc.id:
                self.filter_reason = "Fel id"
                continue
            gold_text = doc.metadata.get("text", "").strip()
            extracted_text = doc.text.strip()

            rouge1 = self._calculate_rouge1(extracted_text, gold_text)

            self.total_rouge1 += rouge1
            self.successful_extractions += [doc.id]

            # Visar vilka ord som saknas/är extra baserat på frekvens
            c_gold = Counter(gold_text.lower().split())
            c_ext = Counter(extracted_text.lower().split())

            # Vad som saknas (fanns fler i guld än i den extraherade texten)
            missing_words = []
            for word, count in c_gold.items():
                diff = count - c_ext.get(word, 0)
                if diff > 0:
                    missing_words.extend([word] * diff)

            # Vad som är skräp (fanns fler i den extraherade texten än i guld)
            extra_words = []
            for word, count in c_ext.items():
                diff = count - c_gold.get(word, 0)
                if diff > 0:
                    extra_words.extend([word] * diff)

            self.diff_records.append(
                {
                    "id": doc.id,
                    "rouge1": rouge1,
                    "missing": sorted(missing_words)[:50],  # Visa de första 50 felen
                    "extra": sorted(extra_words)[:50],
                }
            )

            yield doc

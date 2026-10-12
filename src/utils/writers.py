import json

from datatrove.pipeline.writers.disk_base import DiskWriter

  
class RemovedUrlWriter(DiskWriter):
    name = "Removed URL Writer"
    type = "📝 Writer"
    default_output_filename = "removed_urls_${rank}.jsonl"

    def _write(self, document, file_handler, filename: str):
        # Hantera både om dokumentet är ett objekt eller en dict
        if isinstance(document, dict):
            doc_id = document.get("id", "Okänt ID")
            url = document.get("metadata", {}).get("url", "Okänd URL")
            openlid_score = document.get("metadata", {}).get("openlid_score", 0)
        else:
            doc_id = getattr(document, "id", "Okänt ID")
            url = getattr(document, "metadata", {}).get("url", "Okänd URL")
            openlid_score = getattr(document, "metadata", {}).get("openlid_score", 0)

        data = {"id": doc_id, "url": url}
        if openlid_score != 0:
            data["openlid_score"] = openlid_score

        file_handler.write(json.dumps(data, ensure_ascii=False) + "\n")

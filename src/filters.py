from huggingface_hub import hf_hub_download
from huggingface_hub import hf_hub_download
from datatrove.pipeline.filters.base_filter import BaseFilter
import fasttext

class OpenLidFilter(BaseFilter):
    name = "OpenLid v3 Filter"
    
    def __init__(self, target_lang: str = "swe_Latn", threshold: float = 0.5):
        super().__init__()
        self.target_lang = target_lang
        self.threshold = threshold
        self.model = None  # Laddas först när processen startar

    def _load_model(self):
        if self.model is None:
            model_path = hf_hub_download(repo_id="HPLT/OpenLID-v3", filename="openlid-v3.bin")
            self.model = fasttext.load_model(model_path)

    def filter(self, doc):
        self._load_model() # Ser till att modellen finns i aktuell worker-process
        
        text_snippet = doc.text.replace("\n", " ")
        if not text_snippet.strip():
            return False, "empty"
            
        predictions = self.model.predict(text_snippet, k=1)
        if not predictions[0]:
            return False, "low_confidence_or_noise"
            
        lang = predictions[0][0].replace("__label__", "")
        score = predictions[1][0]
        doc.metadata["openlid_score"] = float(score)
        if lang == self.target_lang and score >= self.threshold:
            return True
        return False, f"filtered_out_{lang}"
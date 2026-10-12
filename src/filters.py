from huggingface_hub import hf_hub_download
from huggingface_hub import hf_hub_download
from datatrove.pipeline.filters.base_filter import BaseFilter
import fasttext

import re
from urllib.parse import urlparse

from datatrove.data import Document

class BlacklistFilter(BaseFilter):
    name = "🚫 Blacklist Filter"
    
    def __init__(self, category_paths: list[str], exclusion_writer=None):
        super().__init__(exclusion_writer=exclusion_writer)
        self.domains = set()
        self.urls = set()
        self.expressions = []        
        for path in category_paths:
            self._load_category(path)
            
    def _load_category(self, base_path: str):
        import os
        
        # Läs domains om filen finns
        domain_file = os.path.join(base_path, "domains")
        if os.path.exists(domain_file):
            with open(domain_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    d = line.strip().lower()
                    if d and not d.startswith("#"):
                        self.domains.add(d)
                        
        # Läs urls om filen finns
        url_file = os.path.join(base_path, "urls")
        if os.path.exists(url_file):
            with open(url_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    u = line.strip().lower()
                    if u and not u.startswith("#"):
                        self.urls.add(u)
                        
        # Läs expressions om filen finns 
        expr_file = os.path.join(base_path, "expressions")
        if os.path.exists(expr_file):
            with open(expr_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    expr = line.strip()
                    if expr and not expr.startswith("#"):
                        try:            
                            self.expressions.append(re.compile(expr, re.IGNORECASE))
                        except re.error:
                            # hantera som vanlig sträng
                            pass

    def filter(self, doc: Document) -> bool:
        url = doc.metadata.get("url")
        if not url:
            return True
            
        parsed = urlparse(url)
        domain = (parsed.netloc or parsed.path).lower().split(":")[0]
        full_url = url.lower()
        
        is_blocked = False
        
        # 1. Kontrollera exakt URL-matchning (om 'urls'-fil finns för kategorin)
        if full_url in self.urls:
            is_blocked = True
            
        else :     
          # 2. Kontrollera domän och subdomäner
          parts = domain.split(".")
          for i in range(len(parts)):
            subdomain = ".".join(parts[i:])
            if subdomain in self.domains:
                is_blocked = True
                break
                
          # 3. Kontrollera expressions (om 'expressions'-fil finns)
          for expr in self.expressions:
            if expr.search(full_url):
                is_blocked = True
                break
        
          if is_blocked : 
            self.stat_update("blacklisted")
            doc.text = ""
            doc.metadata = {"url":url}
            return False
          
                
          
        return True


class OpenLidFilter(BaseFilter):
    name = "🇸🇪 OpenLid v3 Filter"
    
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
        self._load_model() 
        
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
        self.stat_update(f"filtered_out_{lang}")
        return False, f"filtered_out_{lang}"
import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning, exceptions
from datatrove.data import DocumentsPipeline
from datatrove.pipeline.base import PipelineStep

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


# Rensa korta rader (< 5 ord) där dessa ord förekommer 
SHORT_LINE_BLACKLIST = {
    "main",
    "page",
    "members",
    "videos",
    "photos",
    "blog",
    "posts",
    "add",
    "view",
    "contact",
    "home",
    "about",
    "us",
    "services",
    "gallery",
    "forum",
    "login",
    "sign",
    "up",
    "register",
    "search",
    "menu",
    "navigation",
    "sidebar",
    "posted",
    "by",
    "on",
    "comment",
    "comments",
    "read",
    "more",
    "share",
    "tweet",
    "download",
    "click",
    "here",
    "submit",
    "next",
    "previous",
    "close",
    "köp",
    "lager",
    "art nr",
    "kr",
    "sek",
    "omdömen",
    "epub",
    "pdf",
    "tag",
    "category",
    "expand",
    "cart",
    "zoom",
    "edit",
}


import re
from bs4 import BeautifulSoup, exceptions
from datatrove.pipeline.base import PipelineStep
from datatrove.data import Document

# Lägg till dina egna listor här om de inte redan är definierade
SHORT_LINE_BLACKLIST = set(["logga", "meny", "sök", "hem", "cookies", "dela"]) 

class SimpleExtractor(PipelineStep):
    """
    Säkerställer att dokumentets text är korrekt UTF-8-kodad.
    Städar HTML och plockar bort oönskad text.
    """
    type = "🧼 Text Extractor"

    def __init__(self, min_length_article=150, min_length_discussion=70): 
        super().__init__()
        self.min_length_article = min_length_article
        self.min_length_discussion = min_length_discussion
        

    def handle_pii(clean_text) :
      
      phone_pattern = re.compile(r"\b(?:\+46\s?|0)[1-9](?:[\s-]?\d){6,11}\d\b")
      email_pattern = re.compile(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", re.IGNORECASE)
      postcode_pattern = re.compile(
          r"\b[1-9]\d{2}\s?\d{2}\b(?!\s*(?:kr|sek|:-|st|år|st|m²|cm|mm|kg))", re.IGNORECASE
      )
      address_pattern = re.compile(
          r"\b(?:\w+\s+){0,2}\w+(?:vägen|gatan|gata|gränden|stigen|torget|torg|backen|allén|leden|platsen|plan|kroken|svängen|väg|stig)"
          r"(?:\s+\d+[a-zA-Z]?)?\b", re.IGNORECASE
      )
      
      all_phones = re.findall(phone_pattern, clean_text)
      all_emails = re.findall(email_pattern, clean_text)
      all_postcodes = re.findall(postcode_pattern, clean_text)
      all_addresses = re.findall(address_pattern, clean_text)

      total_unique_pii = len(set(all_phones)) + len(set(all_emails)) + len(set(all_postcodes)) + len(set(all_addresses))
      max_pii_allowed = 10 if doc_class == "discussion" else 5
      
      if total_unique_pii > max_pii_allowed:
          doc.metadata["filter_reason"] = f"SimpleExtractor: För mycket PII ({total_unique_pii})"
          return clean_text
          #continue # Hoppa över dokumentet (släng)

      clean_text = re.sub(address_pattern, "[ADRESS]", clean_text)
      clean_text = re.sub(phone_pattern, "[TELEFONNUMMER]", clean_text)
      clean_text = re.sub(email_pattern, "[EPOST]", clean_text)
      clean_text = re.sub(postcode_pattern, "[POSTNUMMER]", clean_text)

      # 7. En sista puts
      clean_text = re.sub(r"\[ADRESS\]\s*,\s*\[POSTNUMMER\]", "[ADRESS] [POSTNUMMER]", clean_text)
      clean_text = re.sub(r"[ᐈ•ᐈ»«▪■●★☆]", " ", clean_text)
      clean_text = re.sub(r"\s+([.,:;!?])", r"\1", clean_text)
      clean_text = re.sub(r"[ \t]+", " ", clean_text)
      clean_text = re.sub(r" +", " ", clean_text).strip()
      clean_text = clean_text.encode("utf-8", errors="ignore").decode("utf-8")
      
      return clean_text

    def run(self, data, rank: int = 0, world_size: int = 1):
        for doc in data:
            # Vi kör logiken inuti klassen istället för en extern funktion
            # för att enkelt kunna registrera bortfiltreringar i DataTrove.
            try:
                soup = BeautifulSoup(doc.text, "lxml") 
            except (exceptions.ParserRejectedMarkup, AssertionError, Exception):
                # Registrera i DataTrove varför det slängdes så AuditTrackern ser det!
                doc.metadata["filter_reason"] = "SimpleExtractor: Trasig HTML"
                continue

            doc.metadata["raw_html"] = doc.text

            # 1. Ta bort skräp på tagg- och klassnivå
            skrap_selectors = [
                "[class*='cookie']", "[id*='cookie']", "[class*='menu']", "[id*='menu']",
                "[class*='share']", "[class*='social']", "[class*='sidebar']", 
                "[class*='banner']", "[class*='footer']", "[class*='header']",
            ]
            for selector in skrap_selectors:
                for element in soup.select(selector):
                    element.decompose()

            noise_tags = [
                "script", "style", "nav", "footer", "header", "table", "button", 
                "form", "select", "input", "aside", "iframe", "noscript", "label", "caption",
            ]
            for tag in soup(noise_tags):
                tag.decompose()

            # 2. Extrahera råtext
            raw_text = soup.get_text(separator="\n", strip=True)
            doc_class = doc.metadata.get("document_class", "unknown")

            # 3. Initial radtvätt
            initial_lines = []
            for line in raw_text.splitlines():
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                words = line_stripped.split()
                if len(words) < 5: 
                    if any(w in SHORT_LINE_BLACKLIST for w in words): 
                        continue
                # Rensa korta rader som inte slutar med skiljetecken
                if len(words) < 4:
                    starts_with_capital = line_stripped[0].isupper() if line_stripped else False
                    punctuation = [".", ",", "!", "?", ":"]
                    ends_with_punctuation = any(line_stripped.endswith(char) for char in punctuation)
                    if not ends_with_punctuation and not starts_with_capital:
                        continue
                initial_lines.append(line_stripped)

            # 4. Look-ahead för tomma kolon
            clean_lines = []
            for i, line in enumerate(initial_lines):
                if line.endswith(":") and i < len(initial_lines) - 1:
                    if initial_lines[i + 1].endswith(":"):
                        continue
                clean_lines.append(line)

            # 5. Sammanfogning med hänsyn till block
            formatted_lines = []
            for i, line in enumerate(clean_lines):
                if i == 0:
                    formatted_lines.append(line)
                    continue
                prev_line = clean_lines[i - 1]
                starts_with_caps = line.isupper() if line else False

                if (
                    any(prev_line.endswith(char) for char in [".", "!", "?"])
                    or prev_line.endswith(":")
                    or line.endswith(":")
                    or starts_with_caps
                ):
                    formatted_lines.append("\n" + line)
                else:
                    formatted_lines.append(" " + line)

            clean_text = "".join(formatted_lines)

            # 6. Hantera personuppgifter (PII)
            
            #clean_text = handle_pii(clean_text)
            

            # Minsta tillåtna längd
            min_length_allowed = self.min_length_discussion if doc_class == "discussion" else self.min_length_article
            
            if len(clean_text) > min_length_allowed:
               doc.text = clean_text
               yield doc
            else:
               doc.metadata["filter_reason"] = f"SimpleExtractor: {doc.id} För kort text"
               continue

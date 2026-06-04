import re

from datatrove.data import DocumentsPipeline
from datatrove.pipeline.base import PipelineStep
from stop_words import get_stop_words

SWEDISH_STOPWORDS = get_stop_words("sv")


class DecodeUTF8Filter(PipelineStep):
    """
    Säkerställer att dokumentets text är korrekt UTF-8-kodad.
    för att förhindra UnicodeDecodeError-krascher i BeautifulSoup.
    """

    def __init__(self):
        super().__init__()
        self.type = "🔓 Decode UTF-8"
        self.name = ""

    def run(self, data: DocumentsPipeline, rank: int = 0, world_size: int = 1) -> DocumentsPipeline:
        for doc in data:
            if isinstance(doc.text, str):
                try:
                    doc.text = doc.text.encode("latin-1", errors="strict").decode("latin-1")
                except UnicodeEncodeError:
                    doc.text = doc.text.encode("utf-8", errors="replace").decode("utf-8")
            yield doc


class OnlyHTMLFilter(PipelineStep):
    def __init__(self):
        super().__init__()
        self.type = "🌐 Only HTML Filter"
        self.name = ""

    def run(self, data: DocumentsPipeline, rank: int = 0, world_size: int = 1) -> DocumentsPipeline:

        non_html_extensions = (
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".svg",
            ".mp4",
            ".mp3",
            ".zip",
            ".gz",
            ".txt",
        )
        for doc in data:
            url = doc.metadata.get("url", "").lower()

            if not any(url.endswith(ext) for ext in non_html_extensions):
                if any(x in doc.text.lower() for x in ["<html", "<body", "<div"]):
                    yield doc


class DropEmptyFilter(PipelineStep):
    def __init__(self):
        super().__init__()
        self.type = "🗑️ Empty Filter"
        self.name = ""

    def run(self, data: DocumentsPipeline, rank: int = 0, world_size: int = 1) -> DocumentsPipeline:
        # Returnerar True om text finns (och inte är tom), False om den ska kastas
        for doc in data:
            if doc.metadata.get("text"):
                yield doc


class PIIFilter(PipelineStep):
  
  def __init__(self) : 
    super().__init__()
    
    self.name = "👤 PII Filter"
    
  def handle_pii(self, clean_text, doc_class):

      phone_pattern = re.compile(r"\b(?:\+46\s?|0)[1-9](?:[\s-]?\d){6,11}\d\b")
      email_pattern = re.compile(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", re.IGNORECASE)
      postcode_pattern = re.compile(
          r"\b[1-9]\d{2}\s?\d{2}\b(?!\s*(?:kr|sek|:-|st|år|st|m²|cm|mm|kg))", re.IGNORECASE
      )
      address_pattern = re.compile(
          r"\b(?:\w+\s+){0,2}\w+(?:vägen|gatan|gata|gränden|stigen|torget|torg|backen|allén|leden|platsen|plan|kroken|svängen|väg|stig)"
          r"(?:\s+\d+[a-zA-Z]?)?\b",
          re.IGNORECASE,
      )

      all_phones = re.findall(phone_pattern, clean_text)
      all_emails = re.findall(email_pattern, clean_text)
      all_postcodes = re.findall(postcode_pattern, clean_text)
      all_addresses = re.findall(address_pattern, clean_text)

      total_unique_pii = (
          len(set(all_phones))
          + len(set(all_emails))
          + len(set(all_postcodes))
          + len(set(all_addresses))
      )
      max_pii_allowed = 10 if doc_class == "discussion" else 5

      if total_unique_pii > max_pii_allowed:
          filter_reason = f"PIIFilter För mycket PII ({total_unique_pii} st)"
          #doc.metadata["filter_reason"] = f"SimpleExtractor: För mycket PII ({total_unique_pii})"
          return clean_text, filter_reason
          # continue # Hoppa över dokumentet (släng)

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
      return clean_text, ""
  
    
  def run(self, data: DocumentsPipeline, rank: int = 0, world_size: int = 1) -> DocumentsPipeline:
    for doc in data : 
      text, filter_reason = self.handle_pii(doc.text, doc.metadata['document_class'])
      if filter_reason : 
      #  doc.metadata["filter_reason"] = filter_reason
        continue
      yield doc

class SwedishQualityFilter(PipelineStep):
    def __init__(self, min_stop_words=0.15, max_non_alpha_ratio=0.05):
        super().__init__()
        self.type = "🇸🇪"
        self.name = "Swedish Quality Filter"
        self.min_stop_words = min_stop_words
        self.max_non_alpha_ratio = max_non_alpha_ratio

    def run(self, data: DocumentsPipeline, rank: int = 0, world_size: int = 1) -> DocumentsPipeline:
        for doc in data:
            if doc.metadata.get("document_class") == "discussion":
                yield doc
                continue

            lines = doc.text.splitlines()
            if not lines:
                continue

            text_lower = doc.text.lower()
            words = text_lower.split()
            total_words = len(words)
            total_chars = len(doc.text)

            if total_words < 20:
                continue

            # 1. Stoppords-andel
            stop_words_count = sum(1 for word in words if word in SWEDISH_STOPWORDS)
            if (stop_words_count / total_words) < min_stop_words:
                doc.metadata["filter_reason"] = (
                    f"SwedishQualityFilter: För få svenska stoppord ({stop_words_count})"
                )
                continue

            # 2. Filtrera bort utländsk spam
            # Letar efter CJK (asiatiska), Kyrilliska (ryska/bulgariska), Grekiska och Hebreiska
            spam_unicode_pattern = (
                r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\u0400-\u04ff\u0370-\u03ff\u0590-\u05ff]"  # noqa: E501
            )
            foreign_chars = re.findall(spam_unicode_pattern, doc.text)

            if foreign_chars:
                total_chars = len(doc.text)
                foreign_ratio = len(foreign_chars) / total_chars

                # Om mer än 5% av HELA texten består av dessa utländska alfabet - troligen internationell spam/länksida # noqa: E501
                # Bevara om mindre än så
                if foreign_ratio > self.max_non_alpha_ratio:
                    continue

            # 3. Släng om mer än 10% av tecknen i dokumentet är specialtecken. (Troligen e-handelsmenyer) # noqa: E501
            # Räkna tecken som överanvänds i menyer: &, (, ), |, +, ;, *
            menu_symbols = len(re.findall(r"[&()|+\x2a;]", doc.text))
            symbol_ratio = menu_symbols / total_chars
            special_chars = len(re.findall(r"[^a-zA-Z0-9åäöÅÄÖ\s]", doc.text))

            # I en normal text som använder parenteser eller semikolon ligger
            # andelen under 1-2%. Om det överstiger 3.5% av alla tecken -> Släng!
            if (special_chars / len(doc.text)) > 0.10 or symbol_ratio > 0.035:
                continue

            # 4. Andel korta rader (släng om > 30%)
            short_lines = sum(1 for line in lines if len(line.split()) < 3)
            if (short_lines / len(lines)) > 0.3:
                continue

            # Om dokumentet klarar alla tester - behåll
            yield doc

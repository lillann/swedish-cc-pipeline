import lxml.html
import trafilatura
import copy
from datatrove.pipeline.base import PipelineStep
from resiliparse.extract.html2text import extract_plain_text
from resiliparse.parse.html import HTMLTree
import ftfy
import re

EMPTY_LINES_REGEX = re.compile(r'\n\s*\n+', re.MULTILINE)


def clean_html_trafilatura(raw_html):
    return trafilatura.extract(
        raw_html,
        output_format="xml",
        favor_recall=True,
        include_formatting=True,
        include_images=False,
        include_tables=True,
        prune_xpath=[
            "//script",
            "//style",
            "//svg",
            "//noscript",
            "//iframe",
            "//object",
            "//embed",
            "//canvas",
        ],
    )

def clean_html_lxml(raw_html):
    
  
#    if isinstance(raw_html, str):
#        raw_html = raw_html.encode("utf-8", errors="ignore")

    # Ta bort NULL-bytes som kraschar lxml
#    raw_html = raw_html.replace(b"\x00", b"")
 
    
    parser = lxml.html.HTMLParser(recover=True, remove_comments=False)
    try:
        doc = lxml.html.fromstring(raw_html, parser=parser)
    except (lxml.etree.ParserError, ValueError):
        return "", "", {}

    # 1. Räkna länkar och knappar innan rensning
    link_count = len(doc.xpath("//a"))
    button_count = len(doc.xpath('//button | //input[@type="submit"]'))

    # 2. Ta bort tekniskt brus
    elements_to_remove = doc.xpath(
        "//script | //style | //svg | //noscript | //iframe | //object | //embed | //canvas"
    )
    for elem in elements_to_remove:
        try:
            elem.drop_tree()
        except (ValueError, TypeError):
            parent = elem.getparent()
            if parent is not None:
                parent.remove(elem)

    # 3. Selektiv rensning av attribut
    allowed_attributes = {
        "class",
        "id",
        "role",
        "lang",
        "itemprop",
        "itemtype",
        "itemscope",
        "data-nosnippet",
        "aria-hidden",
    }

    for elem in doc.iter():
        # 1. Ta bort trasiga eller ogiltiga attribut
        for attr in list(elem.attrib.keys()):
            if not attr or not isinstance(attr, str) or "{" in attr or ";" in attr:
                try:
                    elem.attrib.pop(attr, None)
                except (KeyError, ValueError, lxml.etree.ParserError):
                    pass

        # 2. Rensa bort otillåtna attribut
        keys_to_remove = [attr for attr in elem.attrib if attr not in allowed_attributes]
        for attr in keys_to_remove:
            try:
                elem.attrib.pop(attr, None)
            except (KeyError, ValueError, lxml.etree.ParserError):
                pass

  # 4. Extrahera texten från det rensade trädet
  # extracted_text = " ".join(node.strip() for node in doc.itertext() if node.strip())
  #  extracted_text = ftfy.fix_text(extracted_text)
    cleaned_html = lxml.html.tostring(doc, encoding="utf-8", method="html").decode("utf-8")

    metadata = {"link_count": link_count, "button_count": button_count}

    return cleaned_html,  metadata
    
    
def extract_text_resiliparse(raw_html):

    tree = HTMLTree.parse(raw_html)
    text = extract_plain_text(tree, main_content=False) 
    text = EMPTY_LINES_REGEX.sub('\n', text).strip()
    return text



class TextExtractor(PipelineStep):
  def __init__(self, **kwargs):
      super().__init__(**kwargs)
  
  def run(self, data, rank: int = 0, world_size: int = 1):
      for doc in data:
        html = doc.text
        html = ftfy.fix_text(html) # Fixar teckenfel
        text = extract_text_resiliparse(html)
        doc.metadata['html'] = html
        doc.text = text
        yield doc
  

class HTMLPreprocessor(PipelineStep):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def run(self, data, rank: int = 0, world_size: int = 1):
        for doc in data:
            html = doc.metadata['html']

            cleaned_html, statistics = clean_html_lxml(html)
            #  cleaned_html_resiliparse = clean_html_resiliparse(html)
            #  clenaed_html_trafilatura = clean_html_trafilatura(html)

            doc.metadata["statistics"] = statistics

            # doc.metadata['trafilatura'] = cleaned_html_trafilatura
            # doc.metadata['html_resiliparse'] ) =  cleaned_html_resiliparse
            doc.metadata["html"] = cleaned_html
            yield doc

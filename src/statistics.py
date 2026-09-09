
from datatrove.pipeline.base import PipelineStep
from stop_words import get_stop_words
import re

from openai import OpenAI
from src.utils.propella import create_messages, get_annotation_response_schema

SWEDISH_STOPWORDS = get_stop_words("sv")
SENTENCE_REGEX = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s')

# Possible statistics to collect:
#language score
#“harmonic centrality” - mått från CommonCrawl baserat på inkommande och utgående länkar
#Antal meningar
#Genomsnittlig meningslängd
#Antal ord
#Antal unika ord
#Antal stoppord
#Antal tecken
#Antal specialtecken
#Antal uppercase-tecken
#Antal länkar
#Antal listelement
#Antal tabeller
#Antal formulär
#Antal knappar
#Ev. nyckelord som indikerar typ av sida

def sentence_count(text: str) -> int:
    if not text:
        return 0
    sentences = SENTENCE_REGEX.split(text)
    return len([s for s in sentences if s.strip()])
 

class PropellaAnnotator(PipelineStep):
    name = "🌍 Propella Annotator"
    
    def __init__(self, api_base="http://localhost:8000/v1"):
        super().__init__()
        self.api_base = api_base
        self.client = None  
        
    def run(self, data, rank=0, world_size=1):
       
        if self.client is None:
            self.client = OpenAI(base_url=self.api_base, api_key="EMPTY")

        for doc in data:
            messages = create_messages(doc.text[:50000])
            
            response = self.client.chat.completions.create(
                model="ellamind/propella-1-4b",
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "AnnotationResponse",
                        "schema": get_annotation_response_schema()
                    }
                }
            )
            
            doc.metadata["propella"] = response.choices[0].message.content
            yield doc

class TextContentsStats(PipelineStep):
  def run(self, data, ri: int = 0, oi: int = 0):
    for doc in data:
        text = doc.text
        words = text.split()
        textlength = len(text)
        wordcount = len(words)
        uppercase_count = sum(1 for c in text if c.isupper())
        sent_count = sentence_count(text)
        stop_words_count = sum(1 for word in words if word in SWEDISH_STOPWORDS)
        doc.metadata['statistics']['text_length'] = textlength
        doc.metadata['statistics']['word_count'] = wordcount
        doc.metadata['statistics']['stopword_count'] = stop_words_count  
        doc.metadata['statistics']['uppercase_count'] = uppercase_count
        doc.metadata['statistics']['sentence_count'] = sent_count
        yield doc
    
  
  
class HTMLStats(PipelineStep):
      def run(self, data, ri: int = 0, oi: int = 0):
        for doc in data:
            html = doc.metadata.get("html")
            # Do stuff here
            yield doc
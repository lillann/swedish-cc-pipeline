
from datatrove.pipeline.base import PipelineStep
from stop_words import get_stop_words

from src.extractors import ALL_UNWANTED

SWEDISH_STOPWORDS = get_stop_words("sv")

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

class TextContentsStats(PipelineStep):
  def run(self, data, ri: int = 0, oi: int = 0):
    for doc in data:
        text = doc.text
        words = text.split()
        textlength = len(text)
        wordcount = len(words)
        uppercase_count = sum(1 for c in text if c.isupper())
        stop_words_count = sum(1 for word in words if word in SWEDISH_STOPWORDS)
        doc.metadata['statistics']['text_length'] = textlength
        doc.metadata['statistics']['word_count'] = wordcount
        doc.metadata['statistics']['stopword_count'] = stop_words_count  
        doc.metadata['statistics']['uppercase_count'] = uppercase_count
        yield doc
    
  
  
class HTMLStats(PipelineStep):
      def run(self, data, ri: int = 0, oi: int = 0):
        for doc in data:
            html = doc.metadata.get("html")
            # Do stuff here
            yield doc
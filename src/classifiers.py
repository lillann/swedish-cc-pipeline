from datatrove.data import DocumentsPipeline
from datatrove.pipeline.base import PipelineStep

DISCUSSION_KEYWORDS = {
    "forum",
    "thread",
    "tråd",
    "diskussion",
    "viewtopic",
    "showthread",
    "vbulletin",
    "phpbb",
}
ARTICLE_KEYWORDS = {"artikel", "nyheter", "article", "news", "pressmeddelande", "blogg", "nyhet"}


class ClassifyDoc(PipelineStep):
    def __init__(self):
        super().__init__()
        self.type = "📊 Document Classifier"
        self.name = ""

    def run(self, data: DocumentsPipeline, rank: int = 0, world_size: int = 1) -> DocumentsPipeline:

        for doc in data:
            url = doc.metadata.get("url", "").lower()
            html = doc.metadata.get("raw_html", "").lower()
            text = doc.text.lower()

            doc.metadata["document_class"] = "unknown"

            if any(word in url for word in DISCUSSION_KEYWORDS):
                doc.metadata["document_class"] = "discussion"
                yield doc
                continue

            if any(word in url for word in ARTICLE_KEYWORDS):
                doc.metadata["document_class"] = "article"
                yield doc
                continue

            discussion_score = 0
            if "postbody" in html or "forum-post" in html or "message-body" in html:
                discussion_score += 3
            if "reply" in html or "besvarade" in html:
                discussion_score += 1
            if " skrev:" in text:
                discussion_score += 3
            if " citat:" in text:
                discussion_score += 1
            if "tillbaka till förstasidan" in text:
                discussion_score += 1
            if " online:" in text or " offline:" in text:
                discussion_score += 1
            if "användarnamn:" in text or "medlem:" in text:
                discussion_score += 1
            if "inlägg:" in text or "registrerad:" in text:
                discussion_score += 1

            if text.count("\n") > 15 and len(text.split()) < 300:
                discussion_score += 1

            if discussion_score >= 4:
                doc.metadata["document_class"] = "discussion"
            elif len(text.split()) > 150 and text.count(".") > 5:
                doc.metadata["document_class"] = "article"
            yield doc

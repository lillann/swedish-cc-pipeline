import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from resiliparse.parse.html import HTMLTree
from datatrove.data import Document
from datatrove.pipeline.base import PipelineStep

import html_to_markdown as h2md
import xml.etree.ElementTree as ET
from collections.abc import Generator

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
    "logga",
    "meny",
    "sök",
    "hem",
    "cookies",
    "dela"
}



class HtmlPreprocessor(PipelineStep):
    type = "🚀 ProductionHtmlPreprocessor"

    def run(self, data, ri: int = 0, oi: int = 0):
        # Global lista med standard CSS-selectors för blogg- och forumkommentarer
        comment_selectors = [
            "div[id*='comment']", "div[class*='comment']",
            "section[id*='comment']", "section[class*='comment']",
            "ol[class*='comment']", "ul[class*='comment']",
            "div[class*='reply']", "div[id*='reply']",
            "#comments", ".comments", ".disqus", "#disqus_thread",
            ".comment-body", ".comment-content", ".commentlist",
            "article[class*='comment']", ".guestbook", "#guestbook"
        ]

        # CSS-selectors för kända layout-widgets (t.ex. Googles sökbox och besöksräknare)
        widget_selectors = [
            "form[action*='search']", ".gsc-search-box", ".widget", 
            "#Stats1", ".Stats", ".Stats1_content", ".Image"
        ]

        for doc in data:
            if not doc.text:
                yield doc
                continue

            # 1. Parsa HTML effektivt i C++ via Resiliparse
            tree = HTMLTree.parse(doc.text)
            
            # 2. Rädda Open Graph-titeln (og:title) från headern 
            og_title_tag = tree.head.query_selector("meta[property='og:title']")
            if og_title_tag:
                og_content = og_title_tag.getattr("content")
                if og_content:
                    doc.metadata["og_title"] = og_content.strip()

            # 3. STÄDNING AV LAYOUT-WIDGETS:
            # Raderar sökboxar och statistikmoduler ur HTML-trädet FÖRST.
            # Detta förhindrar att nästlade layout-tabeller plockas upp i loopen nedan.
            for selector in widget_selectors:
                for elem in tree.body.query_selector_all(selector):
                    elem.decompose()

            # 4. Hitta de tabeller som är kvar efter widget-rensningen
            all_tables = tree.body.query_selector_all("table")
            top_level_tables = [t for t in all_tables if t.parent and t.parent.tag != "table"]
            
            extracted_tables = []
            table_counter = 1
            
            for table_tag in top_level_tables:
                raw_table_html = str(table_tag)
                table_lower = raw_table_html.lower()
                
                # Säkerhetskontroll för känd layout
                is_layout = any(x in table_lower for x in [
                    'search', 'gsc-search', 'menu', 'nav', 'sidebar', 'widget', 'stats'
                ])
                if is_layout:
                    continue

                # Konvertera den potentiella datatabellen till Markdown
                try:
                    result = h2md.convert(raw_table_html)
                    markdown_table = result.content.strip()
                except Exception:
                    markdown_table = ""

                # Om tabellen är tom eller bara innehåller streck/layout-skräp, hoppa över
                if not markdown_table or len(markdown_table.replace("|", "").replace("-", "").strip()) < 4:
                    continue

                # Hämta ankartext i Resiliparse C++ (.prev)
                prev_text_node = table_tag.prev
                anchor_text = prev_text_node.text.strip()[-30:] if prev_text_node and prev_text_node.text else ""

                extracted_tables.append({
                    "id": table_counter,
                    "markdown": markdown_table,
                    "anchor": anchor_text
                })
                table_counter += 1

            doc.metadata["tables"] = extracted_tables

            # 5. Rensa bort alla blogg- och läsarkommentarer från HTML-koden
            for selector in comment_selectors:
                for elem in tree.body.query_selector_all(selector):
                    elem.decompose()

            # 6. Exportera tillbaka hela den optimerade HTML-koden till DataTrove
            doc.text = str(tree)
            yield doc




class TableLinker(PipelineStep):
    type = "⚡ TextTableLinker"

    def run(self, data, ri: int = 0, oi: int = 0):
        for doc in data:
            current_text = doc.text
            extracted_tables = doc.metadata.get("tables", [])
            
            if not current_text or not extracted_tables:
                yield doc
                continue

            for table in extracted_tables:
                idx = table.get("id", 1)
                anchor_text = table.get("anchor", "")
                
                if anchor_text:
                    escaped_anchor = re.escape(anchor_text)
                    match = re.search(escaped_anchor, current_text, re.IGNORECASE)
                    
                    if match:
                        actual_text_in_doc = match.group(0)
                        current_text = current_text.replace(actual_text_in_doc, f"{actual_text_in_doc}\n[TABLE #{idx}]", 1)
                    else:
                        current_text += f"\n\n[TABLE #{idx}]\n\n"
                else:
                    current_text += f"\n\n[TABLE #{idx}]\n\n"

            # Sätt in meta-titeln överst
            og_title = doc.metadata.get("og_title", "")
            if og_title:
                if og_title.lower() not in current_text.lower():
                    current_text = f"{og_title}\n\n{current_text}"
                del doc.metadata["og_title"]

            doc.text = current_text.strip()
            yield doc

            


class SimpleExtractor(PipelineStep):
    """
    Städar HTML och plockar bort oönskad text.
    """

    type = "🧼 Simple Text Extractor"

    def __init__(self, min_length_article=150, min_length_discussion=70):
        super().__init__()
        self.min_length_article = min_length_article
        self.min_length_discussion = min_length_discussion


    def run(self, data, rank: int = 0, world_size: int = 1):
        for doc in data:
            # Kör logiken inuti klassen istället för en extern funktion
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
                "[class*='cookie']",
                "[id*='cookie']",
                "[class*='menu']",
                "[id*='menu']",
                "[class*='share']",
                "[class*='social']",
                "[class*='sidebar']",
                "[class*='banner']",
                "[class*='footer']",
                "[class*='header']",
            ]
            for selector in skrap_selectors:
                for element in soup.select(selector):
                    element.decompose()

            noise_tags = [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "table",
                "button",
                "form",
                "select",
                "input",
                "aside",
                "iframe",
                "noscript",
                "label",
                "caption",
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
                    ends_with_punctuation = any(
                        line_stripped.endswith(char) for char in punctuation
                    )
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


            # Minsta tillåtna längd
            min_length_allowed = (
                self.min_length_discussion if doc_class == "discussion" else self.min_length_article
            )

            if len(clean_text) > min_length_allowed:
                doc.text = clean_text
                yield doc
            else:
                doc.metadata["filter_reason"] = f"SimpleExtractor: {doc.id} För kort text"
                continue

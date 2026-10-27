"""Practical export checks; file/text checks do not replace visual inspection."""

import re
import unicodedata
from pathlib import Path
from .documents import mask_fences, sha
from .diagrams import extract_flows


def normalized(value):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", value).casefold())


def visual_rtl_text(value):
    """Comparison form for extractors that return RTL glyphs in visual order.

    Preserve contiguous Latin/number runs. This is a bounded presence check for
    Arabic export text, not a general bidi layout engine or visual QA substitute.
    """
    from ..formatters.typography import has_arabic
    groups=[]
    for token in re.findall(r'\w+',unicodedata.normalize('NFKC',value)):
        rtl=has_arabic(token)
        if not rtl and groups and not groups[-1][0]:
            groups[-1]=(False,groups[-1][1]+token)
        else:
            clusters = re.findall(r'ل[اأإآ]|.',token)
            groups.append((rtl,''.join(reversed(clusters)) if rtl else token))
    return ''.join(text for _,text in reversed(groups))


def inspect_export(fmt, path, content):
    path = Path(path)
    flow_count = len(extract_flows(content))
    visible = mask_fences(content)
    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", visible)
    checks = {"format": fmt, "source_sha256": sha(content), "headings_checked": len(headings),
              "diagram_count": flow_count, "visual_inspection": "not_performed"}
    visual_text = ''
    if fmt == "pdf":
        from pypdf import PdfReader
        import pdfplumber
        reader = PdfReader(path)
        if not reader.pages:
            raise ValueError("PDF has no pages")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        checks["page_count"] = len(reader.pages)
        with pdfplumber.open(path) as pdf:
            visual_text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
            for page in pdf.pages:
                if any(w["x0"] < -1 or w["x1"] > page.width + 1 or w["top"] < -1 or w["bottom"] > page.height + 1
                       for w in page.extract_words()):
                    raise ValueError("PDF text extends beyond a page boundary")
    elif fmt == "docx":
        from docx import Document
        doc = Document(path)
        text = "\n".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for r in t.rows for c in r.cells])
        if len(doc.inline_shapes) != flow_count:
            raise ValueError("DOCX diagram count differs from the source")
        checks["table_count"] = len(doc.tables)
        for table in doc.tables:
            if not table.rows[0]._tr.xpath('./w:trPr/w:tblHeader'):
                raise ValueError("DOCX table is missing a repeating header")
    elif fmt == "html":
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if soup.find_all(["script", "iframe", "img", "object"]) or len(soup.find_all("svg")) != flow_count:
            raise ValueError("HTML has unexpected resources or missing diagrams")
        text = soup.get_text(" ")
    else:
        text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Export contains no readable text")
    actual = normalized(text)
    visual_actual = normalized(visual_text)
    def present(value):
        from ..formatters.typography import has_arabic
        return (normalized(value) in actual or normalized(value) in visual_actual
                or fmt == 'pdf' and has_arabic(value) and normalized(visual_rtl_text(value)) in visual_actual)
    if any(not present(h) for h in headings):
        raise ValueError("Export lost a document heading")
    # Check all supplied table cells, including the last row of a long table.
    cells = [c.strip() for line in visible.splitlines() if line.strip().startswith('|')
             for c in line.strip().strip('|').split('|') if c.strip() and not re.fullmatch(r"[ :\-]+", c)]
    if any(not present(c) for c in cells):
        raise ValueError("Export lost a supplied table cell")
    for _, flow in extract_flows(content):
        if fmt != "markdown" and any(not present(s.label) or not present(s.owner) for s in flow.steps):
            raise ValueError("Export lost a diagram description")
    checks["table_cells_checked"] = len(cells)
    checks["status"] = "passed"
    return checks

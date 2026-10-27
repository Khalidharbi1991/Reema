"""Render untrusted model Markdown without executable or fetchable resources."""

import re
import markdown2
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def strip_frontmatter(content):
    return re.sub(r"\A---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.S)


def render_markdown(content, *, raster_resources=None):
    from ..utils.diagrams import extract_flows, svg_flow
    from ..utils.documents import sha
    from html import escape
    flows = extract_flows(content)
    replacements = []
    for i, (match, flow) in reversed(list(enumerate(flows))):
        token = "REEMAFLOW" + sha(content) + str(i)
        if token in content:
            raise ValueError("Reserved diagram placeholder in document")
        replacements.append((token, flow))
        content = content[:match.start()] + "\n\n" + token + "\n\n" + content[match.end():]
    rendered = markdown2.markdown(strip_frontmatter(content), safe_mode="escape",
        extras=["tables", "fenced-code-blocks", "header-ids"])
    soup = BeautifulSoup(rendered, "html.parser")
    allowed = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "thead", "tbody", "tr", "th", "td",
               "ul", "ol", "li", "strong", "em", "b", "i", "code", "pre", "blockquote", "hr", "br", "a"}
    for tag in list(soup.find_all(True)):
        if tag.name not in allowed:
            tag.decompose()
            continue
        attributes = {}
        if tag.name.startswith("h") and tag.get("id"):
            attributes["id"] = tag["id"]
        if tag.name == "a":
            href = tag.get("href", "")
            if href.startswith("#") or urlparse(href).scheme in {"http", "https", "mailto"}:
                attributes["href"] = href
                attributes["rel"] = "noopener noreferrer"
        tag.attrs = attributes
    from .typography import direction, has_arabic
    for tag in soup.find_all(['p','h1','h2','h3','h4','li','td','th','table']):
        tag['dir'] = direction(tag.get_text())
        if has_arabic(tag.get_text()): tag['lang'] = 'ar'
    from .typography import LTR_RUN
    from bs4 import NavigableString
    for node in list(soup.find_all(string=True)):
        if not has_arabic(str(node)) or node.parent.name in {'pre','code'}: continue
        value=str(node);offset=0
        for match in LTR_RUN.finditer(value):
            if match.start()>offset: node.insert_before(NavigableString(value[offset:match.start()]))
            isolate=soup.new_tag('bdi');isolate['dir']='ltr';isolate.string=match.group()
            node.insert_before(isolate);offset=match.end()
        if offset:
            if offset<len(value): node.insert_before(NavigableString(value[offset:]))
            node.extract()
    from .theme import table_widths
    for table in soup.find_all('table'):
        rows = [[c.get_text() for c in row.find_all(['th', 'td'], recursive=False)] for row in table.find_all('tr')]
        if rows:
            if len(rows) <= 8:
                table['class'] = 'compact-table'
            group = soup.new_tag('colgroup')
            for width in table_widths(rows):
                column = soup.new_tag('col')
                column['style'] = f'width: {width * 100:.4f}%'
                group.append(column)
            table.insert(0, group)
    for token, flow in replacements:
        paragraph = next((p for p in soup.find_all('p') if p.get_text() == token), None)
        if paragraph is None:
            raise ValueError("Diagram placeholder was not preserved")
        from .typography import has_arabic
        graphic = svg_flow(flow)
        if raster_resources is not None and has_arabic(flow.description()):
            # WeasyPrint's SVG text renderer does not shape Arabic reliably.
            # Only our bounded local PNGs may be fetched by the PDF formatter.
            import base64
            from ..utils.diagrams import png_flow
            data = png_flow(flow).getvalue()
            uri = 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')
            raster_resources[uri] = data
            graphic = '<img class="flow-raster" src="' + uri + '" alt="' + escape(flow.description(), quote=True) + '">'
        caption_direction = direction(flow.description())
        caption_language = ' lang="ar"' if has_arabic(flow.description()) else ''
        paragraph.replace_with(BeautifulSoup("<figure>" + graphic
            + '<figcaption dir="' + caption_direction + '"' + caption_language + '>'
            + escape(flow.description()) + "</figcaption></figure>", "html.parser"))
    return str(soup)


def deny_fetch(url, *args, **kwargs):
    raise ValueError("External and local resource fetching is disabled for document rendering")

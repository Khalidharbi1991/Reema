"""Shared deterministic print/screen theme, configured with the section profile."""

import math


def table_widths(rows):
    """Give narrative columns room without starving short labels or RACI cells."""
    columns = len(rows[0])
    if any(len(row) != columns for row in rows):
        raise ValueError("Table rows must preserve every column")
    weights = [math.sqrt(max(8, min(80, max(len(row[i]) for row in rows)))) for i in range(columns)]
    return [weight / sum(weights) for weight in weights]


def document_css():
    from ..utils.config import config_manager
    style = config_manager.document_profile.style
    layout = config_manager.document_profile.layouts[config_manager.document_profile.template]
    return f"""
    @page {{ size: Letter; margin: {style.margin_inches}in;
      @bottom-center {{ content: "Draft | Page " counter(page); font-size: 9pt; color: #666; }} }}
    body {{ font-family: '{style.font}', sans-serif; font-size: {style.body_pt}pt;
      line-height: {style.line_spacing}; color: #222; orphans: 3; widows: 3; }}
    h1 {{ font-size: 24pt; color: #000; margin: 0 0 18pt; }}
    h2 {{ font-size: 16pt; color: #000; margin: {layout.heading_before_pt}pt 0 8pt; }}
    h3 {{ font-size: 13pt; color: #000; margin: 12pt 0 6pt; }}
    h4 {{ font-size: 11pt; color: #000; margin: 10pt 0 5pt; }}
    h1, h2, h3, h4 {{ break-after: avoid; border: none; }}
    p {{ margin: 0 0 {layout.paragraph_after_pt}pt; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10pt 0; table-layout: fixed; }}
    th, td {{ border: 0.5pt solid #ccc; padding: {layout.table_padding_pt}pt; text-align: start; vertical-align: top; overflow-wrap: anywhere; }}
    [dir=rtl] {{ direction: rtl; text-align: right; font-family: '{style.arabic_font}', sans-serif; }}
    [dir=ltr] {{ direction: ltr; text-align: left; }}
    bdi, code {{ unicode-bidi: isolate; direction: ltr; }}
    th {{ background: #f0f2f5; color: #000; font-weight: bold; }}
    thead {{ display: table-header-group; }} tr {{ break-inside: avoid; }}
    .compact-table {{ break-inside: avoid; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font-size: 10pt; }}
    code {{ font-family: monospace; }}
    li {{ margin-bottom: 4pt; }}
    figure {{ margin: 12pt 0; break-inside: avoid; text-align: center; }}
    figure svg {{ max-width: 100%; max-height: 6in; height: auto; }}
    figure img.flow-raster {{ max-width: 100%; max-height: 6in; height: auto; }}
    figcaption {{ text-align: left; font-size: 10pt; margin-top: 6pt; }}
    @media screen {{ body {{ max-width: 7.5in; margin: 2em auto; padding: 1em; }} }}
    """

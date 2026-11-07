#!/usr/bin/env python3
"""
Endpoint Software, Patch & Configuration Deployment - Standard Operating Procedure

Generates a single editable DOCX in ./output/:
  SOP_Endpoint_Software_Patch_Configuration_Deployment_v0.1.docx

Covers remote deployment of Windows quality/security and feature updates,
Microsoft and third-party software, software upgrades, configuration changes
and security remediation through Microsoft Intune and Microsoft Configuration
Manager (SCCM / ConfigMgr), including co-managed endpoints.

Organization-specific values are not invented: they are marked "TBC" and
shaded so reviewers can find them with Find ("TBC"). No ring sizes, SLAs,
employee names or approval authorities are defined.

The table of contents is a Word field. By default the document asks Word to
update fields when it is opened; pass --no-update-fields when the TOC will be
refreshed another way (for example, by Word automation).
"""

import argparse
import math
import os
import re

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor


DOC_TITLE = "Endpoint Software, Patch & Configuration Deployment"
DOC_VERSION = "0.1"
DOC_DATE = "2026-10-28"
CLASSIFICATION = "Classification: Confidential \u2013 Internal Use Only"
OUTPUT_NAME = "SOP_Endpoint_Software_Patch_Configuration_Deployment_v0.1.docx"

# =============================================================================
# Microsoft-style blue / white theme
# =============================================================================
BLUE_DARK = "1F3864"
BLUE = "2E74B5"
BLUE_LIGHT = "DEEAF6"
BLUE_PALE = "F3F7FC"
BORDER = "B4C6E7"
TEXT = "262626"
GREY = "595959"
WHITE = "FFFFFF"
TBC_TEXT = "9C4A00"
TBC_FILL = "FFF2CC"
RED_FILL = "FBE4E4"
RED_TEXT = "9C0006"
GREEN_FILL = "E2EFDA"
GREEN_TEXT = "375623"

CALLOUTS = {
    "note": ("EAF2FB", BLUE, BLUE_DARK),
    "important": ("FFF4E5", "C55A11", "843C0C"),
    "verify": ("F2F2F2", "7F7F7F", "404040"),
}

TEXT_WIDTH_CM = 17.0

ROLE_EM = "Endpoint Management"
ROLE_SEC = "Security / Vulnerability Management"
ROLE_APP = "Application / Service Owner"
ROLE_SD = "Service Desk / Location Support"
ROLE_CHG = "Change Approver / IT Management"


# =============================================================================
# Low-level XML helpers
# =============================================================================
TBLPR_ORDER = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
    "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook",
]
TCPR_ORDER = [
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
]
PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
    "pPrChange",
]
SETTINGS_AFTER_UPDATE_FIELDS = [
    "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars",
    "rsids", "mathPr", "attachedSchema", "themeFontLang", "clrSchemeMapping",
    "doNotIncludeSubdocsInStats", "doNotAutoCompressPictures", "forceUpgrade",
    "captions", "readModeInkLockDown", "smartTagType", "schemaLibrary",
    "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol", "listSeparator",
]


def set_ordered_child(parent, element, order):
    """Insert element into parent, replacing any same-tag child, in schema order."""
    local = element.tag.split("}")[1]
    for existing in parent.findall(qn(f"w:{local}")):
        parent.remove(existing)
    later = order[order.index(local) + 1:]
    for child in parent:
        child_local = child.tag.split("}")[1] if "}" in child.tag else child.tag
        if child_local in later:
            child.addprevious(element)
            return element
    parent.append(element)
    return element


def set_cell_shading(cell, color_hex):
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{color_hex}"/>')
    set_ordered_child(cell._tc.get_or_add_tcPr(), shd, TCPR_ORDER)


def set_cell_borders(cell, **edges):
    """edges: top/left/bottom/right = (size_eighths, color) or None for no border."""
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        if edge not in edges:
            continue
        el = OxmlElement(f"w:{edge}")
        spec = edges[edge]
        if spec is None:
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(spec[0]))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), spec[1])
        borders.append(el)
    set_ordered_child(cell._tc.get_or_add_tcPr(), borders, TCPR_ORDER)


def set_cell_valign(cell, align=WD_CELL_VERTICAL_ALIGNMENT.CENTER):
    cell.vertical_alignment = align


def set_table_borders(table, color=BORDER, size=4, inside=True):
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        if edge.startswith("inside") and not inside:
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(size))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
        borders.append(el)
    set_ordered_child(table._tbl.tblPr, borders, TBLPR_ORDER)


def set_no_table_borders(table):
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    set_ordered_child(table._tbl.tblPr, borders, TBLPR_ORDER)


def set_table_cell_margins(table, top=50, bottom=50, left=100, right=100):
    mar = OxmlElement("w:tblCellMar")
    for edge, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(value))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    set_ordered_child(table._tbl.tblPr, mar, TBLPR_ORDER)


def set_col_widths(table, widths_cm):
    table.autofit = False
    total = int(sum(Cm(w).twips for w in widths_cm))
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), str(total))
    tbl_w.set(qn("w:type"), "dxa")
    set_ordered_child(table._tbl.tblPr, tbl_w, TBLPR_ORDER)
    for i, grid_col in enumerate(table._tbl.tblGrid.findall(qn("w:gridCol"))):
        grid_col.set(qn("w:w"), str(int(Cm(widths_cm[i]).twips)))
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i < len(widths_cm):
                cell.width = Cm(widths_cm[i])


def mark_header_row(row):
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def keep_row_together(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    cant_split.set(qn("w:val"), "true")
    tr_pr.append(cant_split)


def keep_table_on_one_page(table):
    """Keep a short table on one page (keep-with-next on every row but the last)."""
    for row in table.rows[:-1]:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True


def set_row_height(row, height_cm):
    tr_pr = row._tr.get_or_add_trPr()
    height = OxmlElement("w:trHeight")
    height.set(qn("w:val"), str(int(Cm(height_cm).twips)))
    height.set(qn("w:hRule"), "atLeast")
    tr_pr.append(height)


def set_paragraph_border(paragraph, edge="bottom", color=BLUE, size=8, space=4):
    p_pr = paragraph._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    bdr.append(el)
    set_ordered_child(p_pr, bdr, PPR_ORDER)


def set_style_border(style, edge="bottom", color=BLUE, size=8, space=4):
    p_pr = style.element.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    bdr.append(el)
    set_ordered_child(p_pr, bdr, PPR_ORDER)


def set_run_shading(run, color_hex):
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{color_hex}"/>')
    run._r.get_or_add_rPr().append(shd)


def set_style_font(style, name="Calibri", size=None, bold=None, color=None):
    style.font.name = name
    r_fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if r_fonts.get(qn(attr)) is not None:
            del r_fonts.attrib[qn(attr)]
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        r_fonts.set(qn(attr), name)
    if size is not None:
        style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = RGBColor.from_string(color)


def add_field(paragraph, instruction, placeholder="", size=None, color=None, bold=False):
    """Append a complex field (PAGE, NUMPAGES, TOC ...) to a paragraph."""
    def _run():
        run = paragraph.add_run()
        if size:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = RGBColor.from_string(color)
        run.bold = bold
        return run

    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    _run()._r.append(begin)

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    _run()._r.append(instr)

    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    _run()._r.append(separate)

    _run().text = placeholder

    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    _run()._r.append(end)


def add_checkbox(paragraph, size=12):
    """Clickable Word checkbox content control (unchecked)."""
    sdt = parse_xml(
        f'<w:sdt {nsdecls("w", "w14")}>'
        "<w:sdtPr>"
        f'<w:rPr><w:rFonts w:ascii="MS Gothic" w:eastAsia="MS Gothic" w:hAnsi="MS Gothic"/>'
        f'<w:color w:val="{BLUE_DARK}"/><w:sz w:val="{size * 2}"/></w:rPr>'
        "<w14:checkbox>"
        '<w14:checked w14:val="0"/>'
        '<w14:checkedState w14:val="2612" w14:font="MS Gothic"/>'
        '<w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/>'
        "</w14:checkbox>"
        "</w:sdtPr>"
        "<w:sdtContent><w:r><w:rPr>"
        '<w:rFonts w:ascii="MS Gothic" w:eastAsia="MS Gothic" w:hAnsi="MS Gothic" w:hint="eastAsia"/>'
        f'<w:color w:val="{BLUE_DARK}"/><w:sz w:val="{size * 2}"/>'
        "</w:rPr><w:t>\u2610</w:t></w:r></w:sdtContent>"
        "</w:sdt>"
    )
    paragraph._p.append(sdt)


# =============================================================================
# Text helpers ("**bold**" markup; every "TBC" is shaded for reviewers)
# =============================================================================
BOLD_RE = re.compile(r"(\*\*.+?\*\*)")
TBC_RE = re.compile(r"(\bTBC\b)")


def _emit(paragraph, text, bold, size, color, italic):
    for part in TBC_RE.split(text):
        if not part:
            continue
        run = paragraph.add_run(part)
        run.italic = italic
        if size:
            run.font.size = Pt(size)
        if part == "TBC":
            run.bold = True
            run.font.color.rgb = RGBColor.from_string(TBC_TEXT)
            set_run_shading(run, TBC_FILL)
        else:
            run.bold = bold
            if color:
                run.font.color.rgb = RGBColor.from_string(color)


def add_rich_text(paragraph, text, bold=False, size=None, color=None, italic=False):
    for part in BOLD_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            _emit(paragraph, part[2:-2], True, size, color, italic)
        else:
            _emit(paragraph, part, bold, size, color, italic)
    return paragraph


def compact(paragraph, before=1, after=1, line=1.0):
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line


def add_heading(doc, text, level=1):
    return doc.add_heading(text, level=level)


def add_paragraph(doc, text, bold=False, italic=False, size=None, color=None, keep_next=False):
    p = doc.add_paragraph()
    add_rich_text(p, text, bold=bold, size=size, color=color, italic=italic)
    if keep_next:
        p.paragraph_format.keep_with_next = True
    return p


def add_bullet_list(doc, items, level=1):
    style = "List Bullet" if level == 1 else "List Bullet 2"
    for item in items:
        p = doc.add_paragraph(style=style)
        add_rich_text(p, item)
        p.paragraph_format.space_after = Pt(3)


def add_steps(doc, items):
    """Numbered procedure steps with a hanging indent (numbers restart per list)."""
    for n, item in enumerate(items, start=1):
        p = doc.add_paragraph()
        fmt = p.paragraph_format
        fmt.left_indent = Cm(0.8)
        fmt.first_line_indent = Cm(-0.8)
        fmt.tab_stops.add_tab_stop(Cm(0.8))
        fmt.space_after = Pt(4)
        num = p.add_run(f"{n}.\t")
        num.bold = True
        num.font.color.rgb = RGBColor.from_string(BLUE)
        add_rich_text(p, item)


def add_spacer(doc, size=4):
    p = doc.add_paragraph()
    compact(p, 0, 0)
    run = p.add_run()
    run.font.size = Pt(size)
    p.paragraph_format.line_spacing = Pt(size)
    return p


def _fill_cell(cell, value, size=9.5, bold=False, color=None, align=None):
    """value: str or list of str; list items starting with '- ' become bullets."""
    lines = value if isinstance(value, (list, tuple)) else [value]
    first = True
    for line in lines:
        is_bullet = isinstance(line, str) and line.startswith("- ")
        text = line[2:] if is_bullet else str(line)
        if first:
            p = cell.paragraphs[0]
            if is_bullet:
                p.style = "List Bullet"
            first = False
        else:
            p = cell.add_paragraph(style="List Bullet" if is_bullet else None)
        compact(p, 1.5, 1.5)
        if is_bullet:
            p.paragraph_format.left_indent = Cm(0.45)
            p.paragraph_format.first_line_indent = Cm(-0.3)
        if align is not None:
            p.alignment = align
        add_rich_text(p, text, bold=bold, size=size, color=color)


def add_table(
    doc,
    headers,
    rows,
    widths,
    header_fill=BLUE_DARK,
    zebra=True,
    size=9.5,
    bold_first_col=False,
    first_col_fill=None,
    center_cols=(),
    keep_together=False,
):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, widths)
    set_table_borders(table)
    set_table_cell_margins(table)

    header_row = table.rows[0]
    mark_header_row(header_row)
    keep_row_together(header_row)
    for i, header in enumerate(headers):
        cell = header_row.cells[i]
        set_cell_shading(cell, header_fill)
        set_cell_valign(cell)
        _fill_cell(cell, header, size=size, bold=True, color=WHITE,
                   align=WD_ALIGN_PARAGRAPH.CENTER if i in center_cols else None)
        for paragraph in cell.paragraphs:
            paragraph.paragraph_format.keep_with_next = True

    for r, row_data in enumerate(rows):
        row = table.rows[r + 1]
        keep_row_together(row)
        for c, value in enumerate(row_data):
            cell = row.cells[c]
            if c == 0 and first_col_fill:
                set_cell_shading(cell, first_col_fill)
            elif zebra and r % 2 == 1:
                set_cell_shading(cell, BLUE_PALE)
            _fill_cell(cell, value, size=size, bold=(bold_first_col and c == 0),
                       color=BLUE_DARK if (bold_first_col and c == 0) else None,
                       align=WD_ALIGN_PARAGRAPH.CENTER if c in center_cols else None)
    if keep_together:
        keep_table_on_one_page(table)
    add_spacer(doc)
    return table


def add_kv_table(doc, rows, widths=(5.0, 12.0), size=10):
    table = doc.add_table(rows=len(rows), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, widths)
    set_table_borders(table)
    set_table_cell_margins(table, top=60, bottom=60)
    for i, (label, value) in enumerate(rows):
        row = table.rows[i]
        keep_row_together(row)
        set_cell_shading(row.cells[0], BLUE_LIGHT)
        _fill_cell(row.cells[0], label, size=size, bold=True, color=BLUE_DARK)
        _fill_cell(row.cells[1], value, size=size)
        set_cell_valign(row.cells[0])
        set_cell_valign(row.cells[1])
    add_spacer(doc)
    return table


def add_callout(doc, title, lines, kind="note"):
    fill, border, title_color = CALLOUTS[kind]
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, [TEXT_WIDTH_CM])
    set_table_cell_margins(table, top=90, bottom=90, left=180, right=160)
    cell = table.rows[0].cells[0]
    keep_row_together(table.rows[0])
    set_cell_shading(cell, fill)
    set_cell_borders(cell, left=(24, border), top=(4, border), bottom=(4, border), right=(4, border))
    _fill_cell(cell, f"**{title}**", size=10, color=title_color)
    _fill_cell_append(cell, lines)
    add_spacer(doc, 6)
    return table


def _fill_cell_append(cell, lines, size=10):
    for line in lines:
        is_bullet = line.startswith("- ")
        p = cell.add_paragraph(style="List Bullet" if is_bullet else None)
        compact(p, 1.5, 1.5, 1.05)
        if is_bullet:
            p.paragraph_format.left_indent = Cm(0.5)
            p.paragraph_format.first_line_indent = Cm(-0.35)
        add_rich_text(p, line[2:] if is_bullet else line, size=size)


def add_flow(doc, stages, per_row=4, gates=()):
    """Numbered left-to-right process boxes, wrapping onto further rows."""
    n_rows = math.ceil(len(stages) / per_row)
    cols = per_row * 2 - 1
    box_w, arrow_w = 3.6, (TEXT_WIDTH_CM - per_row * 3.6) / (per_row - 1)
    widths = [box_w if c % 2 == 0 else arrow_w for c in range(cols)]
    table = doc.add_table(rows=n_rows * 2 - 1, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, widths)
    set_no_table_borders(table)
    set_table_cell_margins(table, top=70, bottom=70, left=80, right=80)

    for i, stage in enumerate(stages):
        r, pos = divmod(i, per_row)
        row = table.rows[r * 2]
        keep_row_together(row)
        set_row_height(row, 1.45)
        cell = row.cells[pos * 2]
        is_gate = (i + 1) in gates
        set_cell_shading(cell, "C55A11" if is_gate else (BLUE_DARK if i % 2 == 0 else BLUE))
        set_cell_valign(cell)
        label = f"STAGE {i + 1}" + ("  \u2022  GATE" if is_gate else "")
        _fill_cell(cell, [label, f"**{stage}**"], size=9, color=WHITE,
                   align=WD_ALIGN_PARAGRAPH.CENTER)
        if pos < per_row - 1 and i < len(stages) - 1:
            arrow = row.cells[pos * 2 + 1]
            set_cell_valign(arrow)
            _fill_cell(arrow, "\u2192", size=16, color=BLUE, align=WD_ALIGN_PARAGRAPH.CENTER)
    for r in range(n_rows - 1):
        set_row_height(table.rows[r * 2 + 1], 0.15)
        for cell in table.rows[r * 2 + 1].cells:
            compact(cell.paragraphs[0], 0, 0)
            cell.paragraphs[0].paragraph_format.line_spacing = Pt(2)
    add_spacer(doc, 6)
    return table


# =============================================================================
# Document setup: page, styles, header and footer
# =============================================================================
def setup_document(update_fields=True):
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.3)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(0.9)

    styles = doc.styles
    normal = styles["Normal"]
    set_style_font(normal, "Calibri", 10.5, color=TEXT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1

    h1 = styles["Heading 1"]
    set_style_font(h1, "Calibri", 15, bold=True, color=BLUE_DARK)
    h1.paragraph_format.space_before = Pt(20)
    h1.paragraph_format.space_after = Pt(8)
    h1.paragraph_format.keep_with_next = True
    set_style_border(h1, "bottom", BLUE, 8, 3)

    h2 = styles["Heading 2"]
    set_style_font(h2, "Calibri", 12.5, bold=True, color=BLUE)
    h2.paragraph_format.space_before = Pt(14)
    h2.paragraph_format.space_after = Pt(5)
    h2.paragraph_format.keep_with_next = True

    h3 = styles["Heading 3"]
    set_style_font(h3, "Calibri", 11, bold=True, color=BLUE_DARK)
    h3.paragraph_format.space_before = Pt(10)
    h3.paragraph_format.space_after = Pt(3)
    h3.paragraph_format.keep_with_next = True

    for name in ("List Bullet", "List Bullet 2"):
        set_style_font(styles[name], "Calibri", 10.5)
        styles[name].paragraph_format.space_after = Pt(3)

    for name in ("Header", "Footer"):
        set_style_font(styles[name], "Calibri", 8.5, color=GREY)
        style_ppr = styles[name].element.pPr
        if style_ppr is not None:
            for tabs in style_ppr.findall(qn("w:tabs")):
                style_ppr.remove(tabs)

    for level, (before, after, indent, bold) in {1: (6, 2, 0.0, True), 2: (0, 1, 0.5, False)}.items():
        toc = styles.add_style(f"toc {level}", WD_STYLE_TYPE.PARAGRAPH)
        toc.style_id = f"TOC{level}"
        # Built-in style: without this Word renames it and creates its own "toc N".
        toc.element.attrib.pop(qn("w:customStyle"), None)
        toc.base_style = normal
        toc.font.bold = bold
        toc.font.color.rgb = RGBColor.from_string(BLUE_DARK if bold else TEXT)
        toc.paragraph_format.space_before = Pt(before)
        toc.paragraph_format.space_after = Pt(after)
        toc.paragraph_format.left_indent = Cm(indent)
        toc.paragraph_format.line_spacing = 1.0

    # Header / footer: different first page (cover shows classification only)
    section.different_first_page_header_footer = True

    header_p = section.header.paragraphs[0]
    header_p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
    add_rich_text(header_p, DOC_TITLE, bold=True, color=BLUE_DARK, size=8.5)
    header_p.add_run(f"\tSOP  |  Version {DOC_VERSION} (Draft)  |  Document ID: ")
    add_rich_text(header_p, "TBC", size=8.5)
    set_paragraph_border(header_p, "bottom", BLUE, 6, 4)

    footer_p = section.footer.paragraphs[0]
    footer_p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
    set_paragraph_border(footer_p, "top", BORDER, 4, 4)
    add_rich_text(footer_p, CLASSIFICATION, bold=True, color=BLUE_DARK, size=8.5)
    footer_p.add_run("\tPage ")
    add_field(footer_p, "PAGE", "1")
    footer_p.add_run(" of ")
    add_field(footer_p, "NUMPAGES", "1")

    first_footer = section.first_page_footer.paragraphs[0]
    first_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_border(first_footer, "top", BORDER, 4, 4)
    add_rich_text(first_footer, CLASSIFICATION, bold=True, color=BLUE_DARK, size=9)

    settings = doc.settings.element
    zoom = settings.find(qn("w:zoom"))
    if zoom is not None and zoom.get(qn("w:percent")) is None:
        zoom.set(qn("w:percent"), "100")
    # The python-docx template is Word 2010 (mode 14); Word would open it in Compatibility Mode.
    for compat_setting in settings.iter(qn("w:compatSetting")):
        if compat_setting.get(qn("w:name")) == "compatibilityMode":
            compat_setting.set(qn("w:val"), "15")
    if update_fields:
        upd = OxmlElement("w:updateFields")
        upd.set(qn("w:val"), "true")
        for child in settings:
            if child.tag.split("}")[1] in SETTINGS_AFTER_UPDATE_FIELDS:
                child.addprevious(upd)
                break
        else:
            settings.append(upd)

    props = doc.core_properties
    props.title = f"{DOC_TITLE} \u2013 Standard Operating Procedure"
    props.subject = "Endpoint deployment through Microsoft Intune and Configuration Manager"
    props.author = ROLE_EM
    props.last_modified_by = ROLE_EM
    props.keywords = "SOP; Intune; ConfigMgr; SCCM; patching; deployment rings; endpoint"
    props.comments = "Draft for review. Items marked TBC require confirmation before approval."
    props.category = CLASSIFICATION
    return doc


# =============================================================================
# Cover page and table of contents
# =============================================================================
def create_title_page(doc):
    band = doc.add_table(rows=1, cols=1)
    band.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(band, [TEXT_WIDTH_CM])
    set_no_table_borders(band)
    set_table_cell_margins(band, top=120, bottom=120, left=200, right=200)
    cell = band.rows[0].cells[0]
    set_cell_shading(cell, BLUE_DARK)
    _fill_cell(cell, "**STANDARD OPERATING PROCEDURE**", size=11, color=WHITE)
    p = cell.paragraphs[0]
    p.add_run("\t")
    p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM - 0.8), WD_TAB_ALIGNMENT.RIGHT)
    add_rich_text(p, "End-User Computing  |  Endpoint Management", size=10, color="D9E2F3")

    for _ in range(5):
        add_spacer(doc, 12)

    title = doc.add_paragraph()
    compact(title, 0, 6, 1.0)
    add_rich_text(title, "Endpoint Software, Patch &", bold=True, size=30, color=BLUE_DARK)
    title2 = doc.add_paragraph()
    compact(title2, 0, 10, 1.0)
    add_rich_text(title2, "Configuration Deployment", bold=True, size=30, color=BLUE_DARK)

    sub = doc.add_paragraph()
    compact(sub, 0, 4, 1.1)
    add_rich_text(
        sub,
        "Controlled, traceable and low-impact deployment of Windows updates, software and "
        "configuration changes through Microsoft Intune and Microsoft Configuration Manager",
        size=13, color=GREY,
    )
    rule = doc.add_paragraph()
    compact(rule, 0, 18)
    set_paragraph_border(rule, "bottom", BLUE, 18, 1)

    add_kv_table(
        doc,
        [
            ("Document title", f"{DOC_TITLE} \u2013 Standard Operating Procedure"),
            ("Document ID", "TBC"),
            ("Version", f"{DOC_VERSION} \u2013 Draft for review"),
            ("Status", "Draft \u2013 not approved. Not in effect until approved (Section 18)."),
            ("Document owner", "TBC"),
            ("Effective date", "TBC"),
            ("Classification", "Confidential \u2013 Internal Use Only"),
            ("Management platforms", "Microsoft Intune; Microsoft Configuration Manager (SCCM / ConfigMgr); "
                                     "co-managed Windows endpoints"),
            ("Intended readers", "IT Management, Security, Infrastructure, Endpoint Management, Service Desk, "
                                 "Change Management and Audit"),
        ],
        widths=(4.6, 12.4),
    )
    add_spacer(doc, 10)
    add_callout(
        doc,
        "About this draft",
        [
            "Items marked TBC (To Be Confirmed) are organization-specific. They must be confirmed "
            "before this SOP is approved. Section 17.3 lists all open items.",
            "This SOP does not set ring sizes, percentages, SLAs or approval authorities. These are "
            "decided per deployment or confirmed by the organization.",
        ],
        kind="note",
    )
    doc.add_page_break()


def create_toc(doc):
    p = doc.add_paragraph()
    compact(p, 0, 10)
    add_rich_text(p, "Table of Contents", bold=True, size=16, color=BLUE_DARK)
    set_paragraph_border(p, "bottom", BLUE, 8, 3)
    toc = doc.add_paragraph()
    add_field(toc, 'TOC \\o "1-2" \\h \\z \\u',
              "Right-click here and select Update Field to build the table of contents.")
    doc.add_page_break()


# =============================================================================
# Section 1 - Purpose
# =============================================================================
def create_section_1(doc):
    add_heading(doc, "1. Purpose", 1)
    add_paragraph(
        doc,
        "This Standard Operating Procedure (SOP) establishes a **controlled, traceable and low-impact** "
        "process for deploying software, updates and configuration changes to Windows endpoints "
        "managed through Microsoft Intune and Microsoft Configuration Manager (ConfigMgr, formerly SCCM).",
    )
    add_paragraph(doc, "It defines how the Endpoint Management team and the supporting teams:", keep_next=True)
    add_bullet_list(doc, [
        "test a deployment before it reaches production devices;",
        "distribute software, patches and configuration through the correct management platform;",
        "expand a deployment in controlled rings (phases);",
        "schedule deployment activity so that network and user impact stays low;",
        "monitor progress and act on failures;",
        "handle devices and cases that cannot follow the normal process;",
        "pause, roll back or recover when a deployment causes problems; and",
        "keep a complete record for change management and audit.",
    ])
    add_paragraph(
        doc,
        "The same core controls apply to every deployment. A faster path exists only for urgent security "
        "remediation approved through the expedited/emergency change process (Section 5.3 and Section 9.6). "
        "The faster path shortens the controls; it does not remove them.",
    )
    add_callout(
        doc,
        "Key rules at a glance",
        [
            "- Every production deployment has a change/request reference and a deployment record (Section 15).",
            "- No deployment goes straight from packaging to broad production: **Ring 0 \u2192 Ring 1 \u2192 "
            "Ring 2 \u2192 Ring 3** (Section 7).",
            "- Planned **DOWNLOAD** activity: never on Sunday, never during business hours, and planned "
            "activity starts **after 15:30** (Section 8).",
            "- **INSTALLATION** and **RESTART** are separate from DOWNLOAD and follow the restart behavior "
            "approved for the deployment.",
            "- Deploy only from the platform that owns the workload on that device: Intune or ConfigMgr "
            "(Section 10).",
            "- Monitor every production ring and pause expansion when a significant problem appears (Section 11).",
        ],
        kind="note",
    )


# =============================================================================
# Section 2 - Scope
# =============================================================================
def create_section_2(doc):
    add_heading(doc, "2. Scope", 1)
    add_paragraph(
        doc,
        "This SOP applies to Windows workstations (desktops and laptops) managed by Microsoft Intune, "
        "Microsoft Configuration Manager, or both (co-management). Inclusion of virtual desktops and "
        "shared/kiosk devices: TBC.",
    )

    add_heading(doc, "2.1 In Scope", 2)
    add_table(
        doc,
        ["Area", "What is included"],
        [
            ["Windows quality and security updates",
             "Monthly cumulative and security updates, out-of-band updates and related servicing updates "
             "for Windows workstations."],
            ["Windows feature updates",
             "Upgrades to a new Windows version or release (for example, a new annual Windows 11 release)."],
            ["Microsoft software",
             "Microsoft 365 Apps, Microsoft Teams, Microsoft Edge and other Microsoft applications "
             "deployed to endpoints, including their updates."],
            ["Third-party software", "Applications from other vendors, including their security updates."],
            ["Software upgrades", "Version upgrades and replacement (supersedence) of existing software."],
            ["Intune configuration changes",
             "Configuration profiles, settings catalog, endpoint security policies, scripts and related "
             "settings delivered through Intune."],
            ["ConfigMgr deployments",
             "Applications, packages, software updates, configuration baselines and scripts deployed "
             "through ConfigMgr, where ConfigMgr is the approved platform for that workload."],
            ["Security remediation",
             "Packages, scripts or configuration changes that fix a vulnerability or security finding."],
            ["Deployment monitoring", "Status tracking, failure investigation and reporting for all of the above."],
            ["Restart management", "Restart behavior, user notifications and follow-up of pending restarts."],
            ["Exception handling",
             "Devices that fail, are offline, are incompatible or need a different approach."],
            ["Other endpoint management changes",
             "Other changes delivered to Windows workstations through Intune or ConfigMgr (for example, "
             "agent updates). Inclusion of driver and firmware/BIOS updates: TBC."],
        ],
        widths=[5.0, 12.0],
        bold_first_col=True,
    )

    add_heading(doc, "2.2 Out of Scope", 2)
    add_paragraph(doc, "The following are out of scope unless explicitly included through an approved change:",
                  keep_next=True)
    add_bullet_list(doc, [
        "Server operating system and server application patching.",
        "Network device patching and firmware (for example, switches, routers, firewalls and wireless equipment).",
        "Mobile device patching and configuration (iOS/iPadOS and Android).",
        "Non-Windows endpoints such as macOS: TBC (confirm whether this SOP or a separate procedure applies).",
        "New device build and provisioning (imaging, Windows Autopilot and task-sequence builds), which are "
        "covered by a separate procedure (reference TBC).",
        "Tenant-level and identity changes that are not delivered to endpoints (for example, Microsoft Entra ID "
        "Conditional Access policy changes).",
    ])
    add_callout(
        doc,
        "Note",
        ["An out-of-scope item may follow this SOP only when an approved change names it explicitly and "
         "records any differences in testing, scheduling or rollback."],
        kind="note",
    )

    add_heading(doc, "2.3 Key Terms", 2)
    add_table(
        doc,
        ["Term", "Meaning in this SOP"],
        [
            ["DOWNLOAD", "Transfer of update or package content to the endpoint over the network (from Microsoft "
                         "services, a ConfigMgr distribution point, a cache server or peer devices)."],
            ["INSTALLATION", "Applying content that is already on the device. Installation of downloaded content "
                             "does not by itself create update download traffic."],
            ["RESTART", "Restarting the device to complete an installation or apply a change."],
            ["Ring", "A defined group of devices that receives a deployment at a specific stage (Section 7)."],
            ["Wave", "A smaller, scheduled portion of a ring, used to spread network load and limit risk."],
            ["Pilot", "Deployment to a small, representative group of production devices (Ring 1)."],
            ["Business hours", "The organization's working hours. Exact days and hours: TBC."],
            ["Management platform", "The system that manages a given workload on a device: Intune or ConfigMgr."],
            ["Co-management", "A Windows device managed by both ConfigMgr and Intune, where each workload is "
                              "assigned to one platform."],
            ["Workload", "A management area (for example, Windows Update policies, client apps or device "
                         "configuration) assigned to Intune or ConfigMgr on co-managed devices."],
            ["Detection rule", "Logic the platform uses to decide whether software or a change is already "
                               "present on the device."],
            ["Deadline", "The time after which installation (and restart, where configured) is enforced."],
            ["Change record", "The approved change, request or ticket that authorizes the deployment."],
            ["Deployment record", "The record of the deployment, with the minimum content in Section 15."],
            ["Exception", "A device or case that cannot follow the normal deployment and needs separate handling."],
        ],
        widths=[4.0, 13.0],
        bold_first_col=True,
    )


# =============================================================================
# Section 3 - Governing principles
# =============================================================================
def create_section_3(doc):
    add_heading(doc, "3. Governing Principles", 1)
    add_paragraph(doc, "Every deployment under this SOP follows these principles.", keep_next=True)
    add_table(
        doc,
        ["#", "Principle", "What it means in practice"],
        [
            ["P1", "Use the approved management platform for each endpoint and workload.",
             "Confirm which platform owns the workload on the target devices before deploying (Section 10). "
             "Never deploy the same item to the same device from both platforms."],
            ["P2", "Do not move directly from package creation to broad production deployment.",
             "Every deployment passes Ring 0 and Ring 1 before Ring 2 and Ring 3. Urgent remediation uses a "
             "shortened form of the same sequence."],
            ["P3", "Test before production.",
             "Technical testing (Section 6) is completed and recorded before any production device is targeted."],
            ["P4", "Use controlled rings and waves.",
             "Each expansion depends on the results of the previous ring. Expansion can be paused at any time."],
            ["P5", "Minimize business and network impact.",
             "Follow the download rules in Section 8, use waves for large content, and avoid disruptive "
             "restarts where configuration allows."],
            ["P6", "Maintain rollback or remediation options where technically possible.",
             "Identify how to reverse or fix the change before Ring 1. If no rollback exists, record this and "
             "plan the remediation approach (Section 13)."],
            ["P7", "Monitor every production deployment.",
             "No production ring is left unmonitored. Status is reviewed until closure (Section 11)."],
            ["P8", "Document failures and exceptions.",
             "Failures, exceptions and decisions are recorded in the deployment record (Sections 12 and 15)."],
            ["P9", "Verify configuration; do not assume behavior.",
             "Where behavior depends on Intune or ConfigMgr settings, verify it in the console or on a test "
             "device before relying on it."],
            ["P10", "Keep standard and emergency deployments separate.",
             "The expedited path is used only when approved through the expedited/emergency change process "
             "(Section 5.3)."],
        ],
        widths=[1.1, 5.4, 10.5],
        bold_first_col=True,
        center_cols=(0,),
    )


# =============================================================================
# Section 4 - Roles and responsibilities
# =============================================================================
def create_section_4(doc):
    add_heading(doc, "4. Roles and Responsibilities", 1)
    add_paragraph(
        doc,
        "Roles describe functions, not named individuals. The teams and contacts that fill each role are "
        "maintained in the team contact list (reference TBC). Approval authorities follow the organization's "
        "change management process and are TBC in this SOP.",
    )
    add_heading(doc, "4.1 Responsibilities by Role", 2)
    add_table(
        doc,
        ["Role", "Responsibilities"],
        [
            [ROLE_EM, [
                "- Owns this SOP and executes deployments.",
                "- Prepares packages, policies and configuration; defines detection, requirements, dependencies "
                "and restart behavior.",
                "- Confirms the management platform and workload ownership of target devices.",
                "- Performs technical testing (Ring 0) and builds ring membership.",
                "- Schedules deployments within the permitted download windows.",
                "- Monitors every ring, investigates failures and pauses expansion when needed.",
                "- Runs exception remediation and recovery; maintains the deployment record; requests closure.",
            ]],
            [ROLE_SEC, [
                "- Identifies and prioritizes vulnerabilities and security updates; provides risk rating and "
                "urgency.",
                "- Requests urgent security remediation through the expedited/emergency change process.",
                "- Advises on the security risk of delaying, excluding or rolling back an update.",
                "- Confirms remediation through vulnerability scanning or reporting, where available.",
                "- Reviews exceptions that leave a security exposure.",
            ]],
            [ROLE_APP, [
                "- Provides application requirements, installation parameters and licensing information.",
                "- Nominates pilot users or devices for business validation.",
                "- Validates business functionality in the pilot and reports issues.",
                "- Provides input to compatibility decisions, workarounds and business-critical deferrals.",
            ]],
            [ROLE_SD, [
                "- Receives deployment notifications and known-issue information before each ring.",
                "- Handles user calls; links related tickets to the change record.",
                "- Applies documented workarounds and escalates repeated or significant issues.",
                "- Helps with offline, unavailable or remote devices and local restarts.",
                "- Reports local constraints (for example, low bandwidth or critical local operations).",
            ]],
            [ROLE_CHG, [
                "- Reviews and approves changes according to the change management process.",
                "- Gives the approval to expand beyond the pilot where the change process requires it.",
                "- Approves expedited/emergency changes and recorded deviations (for example, from the "
                "download window).",
                "- Decides on exceptions and residual risk where the change or exception process requires it.",
                "- Receives major-issue communication and supports rollback decisions.",
            ]],
        ],
        widths=[4.3, 12.7],
        bold_first_col=True,
        first_col_fill=BLUE_LIGHT,
    )

    add_heading(doc, "4.2 Involvement by Workflow Stage", 2)
    add_paragraph(
        doc,
        "**L** = Leads   **S** = Supports / provides input   **AP** = Approves according to the change "
        "process (authority TBC)   **I** = Informed   **\u2013** = Not normally involved",
        size=9.5, keep_next=True,
    )
    add_table(
        doc,
        ["Workflow stage", "Endpoint Mgmt", "Security / VM", "App / Service Owner", "Service Desk / Location",
         "Change / IT Mgmt"],
        [
            ["1. Requirement", "L", "S", "S", "\u2013", "I"],
            ["2. Package / configuration preparation", "L", "S", "S", "\u2013", "\u2013"],
            ["3. Technical testing (Ring 0)", "L", "S", "S", "\u2013", "\u2013"],
            ["4. Pilot deployment (Ring 1)", "L", "I", "S", "I", "I"],
            ["5. Pilot monitoring and validation", "L", "S", "S", "S", "I"],
            ["6. Approval to expand", "S", "S", "S", "I", "AP"],
            ["7. Controlled production (Ring 2)", "L", "I", "I", "S", "I"],
            ["8. Broad production (Ring 3)", "L", "I", "I", "S", "I"],
            ["9. Monitoring", "L", "S", "I", "S", "I"],
            ["10. Exception remediation", "L", "S", "S", "S", "AP"],
            ["11. Closure", "L", "S", "I", "I", "S"],
        ],
        widths=[5.5, 2.3, 2.3, 2.3, 2.3, 2.3],
        bold_first_col=True,
        center_cols=(1, 2, 3, 4, 5),
        keep_together=True,
    )


# =============================================================================
# Section 5 - Standard deployment workflow
# =============================================================================
def create_section_5(doc):
    add_heading(doc, "5. Standard Deployment Workflow", 1)
    add_paragraph(
        doc,
        "All deployments follow the workflow below. A stage is completed, and its output recorded, before the "
        "next stage starts. Gates (orange) need a recorded decision before the deployment continues.",
        keep_next=True,
    )
    add_heading(doc, "5.1 Workflow Overview", 2)
    add_flow(
        doc,
        [
            "Requirement",
            "Package / configuration preparation",
            "Technical testing",
            "Pilot deployment",
            "Pilot monitoring and validation",
            "Approval to expand",
            "Controlled production deployment",
            "Broad production deployment",
            "Monitoring",
            "Exception remediation",
            "Closure",
        ],
        per_row=4,
        gates=(6,),
    )

    add_heading(doc, "5.2 Stage Descriptions", 2)
    add_table(
        doc,
        ["#", "Stage", "What happens", "Lead", "Output / exit condition"],
        [
            ["1", "Requirement",
             "A need is identified: Microsoft monthly release, vulnerability finding, software request, upgrade "
             "or configuration requirement. Confirm the business need, urgency, target scope and whether the "
             "standard or emergency path applies. Raise or link the change/request.",
             ROLE_EM, "Change/request reference; initial scope; deployment type."],
            ["2", "Package / configuration preparation",
             "Obtain content from an approved source. Build the package or policy: install/uninstall commands, "
             "detection, requirements, dependencies, supersedence, return codes and restart behavior. Confirm "
             "the management platform. Define ring groups or collections.",
             ROLE_EM, "Package/policy ready for test; pre-deployment checks (6.1) complete; deployment record "
                      "started."],
            ["3", "Technical testing",
             "Deploy to Ring 0 test devices. Validate download, installation, detection, restart, device health, "
             "applications and connectivity (Section 6.2).",
             ROLE_EM, "Test results recorded; pass, or fix and re-test."],
            ["4", "Pilot deployment",
             "Deploy to the Ring 1 pilot group within the permitted download window. Notify the Service Desk "
             "and, where needed, pilot users.",
             ROLE_EM, "Pilot started; schedule recorded."],
            ["5", "Pilot monitoring and validation",
             "Monitor status, collect feedback from pilot users, application owners and the Service Desk, "
             "investigate failures and check the pilot exit criteria (Section 6.4).",
             ROLE_EM, "Pilot result: pass, pass with conditions, or fail."],
            ["6", "Approval to expand",
             "Present test and pilot results. Obtain the approval required by the change process to expand to "
             "production rings.",
             ROLE_CHG, "Recorded approval or decision (gate)."],
            ["7", "Controlled production deployment",
             "Expand to selected groups, locations or device cohorts (Ring 2) in waves. Review results between "
             "waves and keep the ability to pause.",
             ROLE_EM, "Wave results recorded; no open blocking issue."],
            ["8", "Broad production deployment",
             "Deploy to the remaining eligible endpoints (Ring 3) on the approved schedule.",
             ROLE_EM, "All eligible devices targeted."],
            ["9", "Monitoring",
             "Track status across all rings until the success measure agreed in the change record (TBC) is "
             "met, or remaining devices are moved to exception handling.",
             ROLE_EM, "Status report; failure patterns investigated."],
            ["10", "Exception remediation",
             "Handle failed, offline, incompatible and pending-restart devices through the exception/remediation "
             "ring (Section 12).",
             ROLE_EM, "Exceptions resolved or formally recorded with an owner."],
            ["11", "Closure",
             "Complete final validation (Section 11.5), clean up superseded deployments, complete the deployment "
             "record and close the change.",
             ROLE_EM, "Closure reference recorded."],
        ],
        widths=[0.8, 3.0, 7.0, 2.6, 3.6],
        center_cols=(0,),
        size=9,
    )
    add_callout(
        doc,
        "Important",
        [
            "A ring is not expanded until its exit criteria are met and the decision is recorded. Endpoint "
            "Management may pause a deployment at any stage to protect the service (Section 7.4).",
        ],
        kind="important",
    )

    add_heading(doc, "5.3 Standard vs Emergency Deployment", 2)
    add_paragraph(
        doc,
        "The standard path is used for all planned work. The expedited/emergency path is used only when the "
        "criteria of the organization's expedited/emergency change process are met (criteria TBC).",
        keep_next=True,
    )
    add_table(
        doc,
        ["Aspect", "Standard deployment", "Urgent / emergency deployment"],
        [
            ["When used", "All planned deployments: monthly patches, software, upgrades and configuration.",
             "Urgent security remediation or urgent fixes that meet the expedited/emergency change criteria (TBC)."],
            ["Authorization", "Normal change approval according to the change process.",
             "Expedited/emergency change approval (approval authority TBC)."],
            ["Technical test (Ring 0)", "Full test set (Section 6.2).",
             "Minimum test set (Section 9.6). Not skipped where technically possible."],
            ["Pilot (Ring 1)", "Full pilot with exit criteria (Section 6.4).",
             "Shortened pilot. Skipped only if the emergency change approval explicitly accepts that risk."],
            ["Production rings", "Ring 2 in waves, then Ring 3.",
             "Faster or larger waves as approved. The ring order is still followed."],
            ["Download window", "Section 8 rules apply.",
             "Section 8 rules apply unless the emergency change record explicitly approves a deviation."],
            ["Restart", "Approved restart behavior; disruptive restarts avoided where configuration allows.",
             "Shorter deadlines or enforced restarts only if approved in the change; users and support notified."],
            ["Monitoring", "Every ring monitored until closure.",
             "Increased monitoring; ready to pause at any time."],
            ["Rollback", "Defined before Ring 1.",
             "Defined before production. If none exists, this is recorded and accepted in the change."],
            ["Records", "Deployment record complete before closure.",
             "Same minimum record, completed as required by the emergency change process and before closure."],
        ],
        widths=[3.4, 6.4, 7.2],
        bold_first_col=True,
    )


# =============================================================================
# Section 6 - Testing and validation
# =============================================================================
def create_section_6(doc):
    add_heading(doc, "6. Testing and Validation", 1)
    add_paragraph(
        doc,
        "Testing confirms that the deployment works technically (Ring 0) and in real production use (Ring 1) "
        "before it reaches the wider estate.",
    )

    add_heading(doc, "6.1 Pre-deployment Checks", 2)
    add_paragraph(doc, "Complete these checks before the first Ring 0 deployment and record the results.",
                  keep_next=True)
    add_table(
        doc,
        ["Check", "What to confirm", "Record"],
        [
            ["Package / update source",
             "Content comes from the vendor or an approved internal repository (for example, Microsoft Update, "
             "the vendor's official download site). Check the digital signature or file hash where available.",
             "Source location; signature/hash result."],
            ["Version",
             "The exact version, build or KB number is the intended one and supersedes the correct previous version.",
             "Version / KB / build."],
            ["Applicability",
             "Supported Windows versions and builds, architecture (x64 / ARM64), edition, device models and "
             "language. The item is needed and not already installed or superseded.",
             "Applicable population."],
            ["Prerequisites",
             "Required runtimes, servicing stack, minimum OS build, free disk space and licensing.",
             "Prerequisites list."],
            ["Dependencies",
             "Other software or updates that must be installed first; Intune or ConfigMgr dependencies "
             "configured; known conflicts with installed software.",
             "Dependency list; conflicts."],
            ["Detection rules",
             "Detection uses a reliable indicator of the exact version (for example, MSI product code, file "
             "version or registry value) and gives the correct result before and after installation.",
             "Detection method."],
            ["Targeting",
             "Entra ID groups or ConfigMgr collections for each ring; exclusions (exception devices, devices "
             "owned by the other platform); no unintended broad target such as all devices. Membership counts "
             "match expectations.",
             "Groups/collections and counts."],
            ["Expected restart behavior",
             "No restart, restart required, or restart possible. Return codes mapped correctly (for example, "
             "3010 = soft restart, 1641 = hard restart). Deadline, grace period and notification settings.",
             "Restart behavior and settings."],
            ["Rollback / uninstall / remediation approach",
             "Uninstall command, previous version available, policy reversal, or a recorded \u201cno rollback\u201d "
             "with the remediation plan (Section 13).",
             "Rollback method."],
            ["Content size and delivery",
             "Content size; delivery source (distribution point, Delivery Optimization, cache, internet); "
             "whether the installer downloads more content during installation.",
             "Size; delivery method."],
            ["Management platform",
             "The workload owner (Intune or ConfigMgr) on the target devices; no duplicate deployment on the "
             "other platform (Section 10).",
             "Platform per target group."],
        ],
        widths=[3.6, 9.4, 4.0],
        bold_first_col=True,
        size=9,
    )

    add_heading(doc, "6.2 Technical Testing (Ring 0)", 2)
    add_paragraph(
        doc,
        "Ring 0 test devices should represent the main hardware models, Windows versions and builds, and "
        "configurations in the estate, including Intune-only and co-managed devices where both are targeted "
        "and at least one remote/VPN device. Ring 0 device list: TBC.",
        keep_next=True,
    )
    add_table(
        doc,
        ["Test area", "What to validate", "Pass condition"],
        [
            ["Download / delivery",
             "Content reaches the device from the expected source and completes.",
             "Full download from the intended source; no unexpected internet or cross-site download."],
            ["Installation",
             "Silent installation with the expected exit code; correct version; no unexpected user prompts.",
             "Installed version matches the deployment record."],
            ["Detection / compliance",
             "The platform reports installed/compliant, and the actual state on the device matches.",
             "Reported state = actual state; no reinstall loop."],
            ["Restart behavior",
             "Restart happens (or not) as expected; notifications appear as configured.",
             "No unexpected forced restart; device returns to normal use."],
            ["Device health",
             "Device starts and signs in normally; Intune/ConfigMgr agents check in; antivirus/EDR running; "
             "BitLocker status unchanged with no recovery prompt; compliance state unchanged.",
             "No new critical errors related to the change."],
            ["Core business applications",
             "Main business applications open and perform basic functions (application list TBC).",
             "Application owner confirms where required."],
            ["Microsoft 365 applications",
             "Outlook, Teams, Word, Excel, PowerPoint and OneDrive open, sign in and sync.",
             "Normal operation."],
            ["Network connectivity",
             "Wired and Wi-Fi connection, proxy, name resolution and access to internal resources.",
             "Normal connectivity."],
            ["VPN",
             "VPN connects and stays connected; remote access to internal resources works.",
             "Normal VPN operation."],
            ["Required peripherals (where applicable)",
             "Printers, scanners, docking stations, monitors, headsets/cameras, smart card readers and "
             "specialized devices.",
             "Peripherals work as before."],
            ["Rollback (where available)",
             "The rollback or uninstall method works on a test device.",
             "Device returns to the previous working state."],
        ],
        widths=[3.6, 8.0, 5.4],
        bold_first_col=True,
        size=9,
    )

    add_heading(doc, "6.3 Evidence and Log Sources", 2)
    add_paragraph(
        doc,
        "Record test evidence (status screenshots, log extracts or report exports) in the deployment record. "
        "Common log locations are listed below; verify paths for the client versions in use.",
        keep_next=True,
    )
    add_table(
        doc,
        ["Platform / activity", "Typical log source on the device"],
        [
            ["Intune Win32 apps and scripts",
             "IntuneManagementExtension.log and related logs in C:\\ProgramData\\Microsoft\\IntuneManagementExtension\\Logs"],
            ["ConfigMgr content DOWNLOAD",
             "CAS.log, ContentTransferManager.log, DataTransferService.log in C:\\Windows\\CCM\\Logs"],
            ["ConfigMgr application INSTALLATION", "AppEnforce.log, AppDiscovery.log in C:\\Windows\\CCM\\Logs"],
            ["ConfigMgr software updates", "UpdatesDeployment.log, UpdatesHandler.log, WUAHandler.log in C:\\Windows\\CCM\\Logs"],
            ["Windows Update", "Windows Update event logs; Get-WindowsUpdateLog (PowerShell)"],
            ["Delivery Optimization", "Get-DeliveryOptimizationLog and Get-DeliveryOptimizationStatus (PowerShell)"],
        ],
        widths=[5.0, 12.0],
        bold_first_col=True,
        size=9,
    )

    add_heading(doc, "6.4 Pilot Exit Criteria", 2)
    add_paragraph(doc, "The pilot (Ring 1) is complete only when all of the following are true:", keep_next=True)
    add_bullet_list(doc, [
        "The pilot has run for the observation period set in the deployment record (period TBC per risk level).",
        "The success measure agreed in the change record is met (threshold TBC). Remaining devices are explained.",
        "All failures are categorized as device-specific or package/policy-related. No unresolved "
        "package/policy-related failure remains.",
        "No unresolved business-impacting incident is linked to the deployment.",
        "Reported status matches the actual state on sampled devices (detection works).",
        "Restart behavior and user notifications worked as expected.",
        "Application/Service Owners confirm business functions where they were asked to validate.",
        "The Service Desk reports no unexplained increase in related calls.",
        "No network or bandwidth issue was reported at pilot locations.",
        "The rollback/recovery method is confirmed, or \u201cno rollback\u201d is recorded with a remediation plan.",
    ])
    add_callout(
        doc,
        "Pilot outcome",
        [
            "**Pass** \u2013 request approval to expand (Stage 6).",
            "**Pass with conditions** \u2013 record the conditions (for example, excluded models) and request approval.",
            "**Fail** \u2013 stop, fix the package or policy, and repeat from Ring 0.",
        ],
        kind="note",
    )


# =============================================================================
# Section 7 - Ring / phased deployment strategy
# =============================================================================
def create_section_7(doc):
    add_heading(doc, "7. Ring / Phased Deployment Strategy", 1)
    add_paragraph(
        doc,
        "Deployments expand through rings. Each ring reduces risk for the next one. Devices that fail or do "
        "not complete in any ring move to the exception/remediation ring.",
        keep_next=True,
    )

    # Ring diagram
    table = doc.add_table(rows=3, cols=7)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, [3.7, 0.73, 3.7, 0.73, 3.7, 0.73, 3.71])
    set_no_table_borders(table)
    set_table_cell_margins(table, top=70, bottom=70, left=80, right=80)
    rings = [
        ("RING 0", "Technical Test", "IT test devices", "9DC3E6", BLUE_DARK),
        ("RING 1", "Pilot", "Representative pilot", "5B9BD5", WHITE),
        ("RING 2", "Controlled Production", "Selected groups / sites", BLUE, WHITE),
        ("RING 3", "Broad Production", "Remaining eligible", BLUE_DARK, WHITE),
    ]
    top = table.rows[0]
    keep_row_together(top)
    set_row_height(top, 1.7)
    for i, (code, name, target, fill, color) in enumerate(rings):
        cell = top.cells[i * 2]
        set_cell_shading(cell, fill)
        set_cell_valign(cell)
        _fill_cell(cell, [code, f"**{name}**", target], size=9, color=color, align=WD_ALIGN_PARAGRAPH.CENTER)
        if i < 3:
            arrow = top.cells[i * 2 + 1]
            set_cell_valign(arrow)
            _fill_cell(arrow, "\u2192", size=16, color=BLUE, align=WD_ALIGN_PARAGRAPH.CENTER)
    mid = table.rows[1]
    merged = mid.cells[0].merge(mid.cells[6])
    _fill_cell(merged, "\u25BC  Failed, offline, incompatible or incomplete devices from any ring  \u25BC",
               size=8.5, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER)
    bottom = table.rows[2]
    exc = bottom.cells[0].merge(bottom.cells[6])
    set_cell_shading(exc, "FBE5D6")
    set_cell_borders(exc, left=(18, "C55A11"), top=(4, "C55A11"), bottom=(4, "C55A11"), right=(4, "C55A11"))
    _fill_cell(exc, "**EXCEPTION / REMEDIATION RING** \u2013 targeted follow-up until each device is fixed "
                    "or formally recorded as an exception", size=9, color="843C0C",
               align=WD_ALIGN_PARAGRAPH.CENTER)
    add_spacer(doc, 6)

    add_heading(doc, "7.1 Ring Definitions", 2)
    add_table(
        doc,
        ["Ring", "Purpose", "Target", "Entry condition", "Exit condition"],
        [
            ["Ring 0 \u2013 Technical Test",
             "Validate packaging, installation, detection, configuration and restart behavior.",
             "IT test devices / controlled test endpoints.",
             "Pre-deployment checks (6.1) complete.",
             "All technical tests (6.2) passed and recorded."],
            ["Ring 1 \u2013 Pilot",
             "Validate the change on representative production endpoints.",
             "Small representative pilot population.",
             "Ring 0 passed; change approved for pilot; Service Desk notified.",
             "Pilot exit criteria (6.4) met; approval to expand recorded."],
            ["Ring 2 \u2013 Controlled Production",
             "Expand gradually while keeping the ability to pause the deployment.",
             "Selected production groups, locations or device cohorts.",
             "Approval to expand recorded.",
             "All planned waves completed with acceptable results; no open blocking issue."],
            ["Ring 3 \u2013 Broad Production",
             "Complete the approved rollout.",
             "Remaining eligible production endpoints.",
             "Ring 2 results acceptable.",
             "All eligible devices targeted; incomplete devices handed to the exception ring."],
            ["Exception / Remediation Ring",
             "Handle devices that failed or did not complete the normal deployment.",
             "Offline devices, failed installations, incompatible devices, low-bandwidth locations, devices "
             "pending restart and other exceptional conditions.",
             "Device failed or did not complete in its ring.",
             "Device remediated, or exception recorded with owner and next action (Section 12)."],
        ],
        widths=[3.0, 3.6, 3.6, 3.3, 3.5],
        bold_first_col=True,
        size=9,
    )

    add_heading(doc, "7.2 Ring Size and Duration", 2)
    add_callout(
        doc,
        "No fixed ring sizes or percentages",
        [
            "This SOP does not set fixed ring sizes, percentages or durations. They are decided for each "
            "deployment and recorded in the deployment record, based on the factors below.",
        ],
        kind="important",
    )
    add_table(
        doc,
        ["Factor", "How it affects ring size and duration"],
        [
            ["Business criticality", "More critical devices or functions need smaller rings and longer "
                                     "observation before expansion."],
            ["Package size", "Larger content (for example, feature updates or Microsoft 365 Apps) needs smaller "
                             "waves to limit network load."],
            ["Network capacity", "Sites with limited bandwidth need smaller waves, pre-staged content or "
                                 "separate scheduling."],
            ["Device population", "The number of devices per model, location and function sets how many waves "
                                  "are needed."],
            ["Device availability", "Devices that are often offline or shift-based need longer rings or "
                                    "follow-up waves."],
            ["Pilot results", "Clean results may support larger waves; issues require smaller waves or a "
                              "repeat pilot."],
            ["Operational risk", "Higher-risk changes (for example, security settings, drivers or major "
                                 "upgrades) need more gradual expansion."],
        ],
        widths=[4.0, 13.0],
        bold_first_col=True,
    )

    add_heading(doc, "7.3 Building Ring Membership", 2)
    add_bullet_list(doc, [
        "**Intune:** use Microsoft Entra ID security groups (assigned or dynamic) per ring. "
        "**ConfigMgr:** use device collections per ring. Group and collection naming convention: TBC.",
        "Make Ring 1 representative: main hardware models, Windows versions, locations (including remote and "
        "low-bandwidth sites), business functions, VPN users and users of key peripherals. Do not limit the "
        "pilot to IT staff.",
        "A device belongs to only one ring for a given deployment. Check for overlapping groups or collections.",
        "Exclude devices that need special handling (exception register: TBC) and devices owned by the other "
        "management platform.",
        "Standing ring groups may be reused for monthly updates. Review their membership regularly "
        "(frequency TBC) so they stay representative.",
    ])

    add_heading(doc, "7.4 Pausing a Deployment", 2)
    add_paragraph(
        doc,
        "Pause expansion when a pause trigger occurs (Section 11.3). Pausing stops further devices from "
        "starting; it does not reverse devices that already installed. Devices that already downloaded "
        "content may still install. Verify the exact pause behavior for each mechanism.",
        keep_next=True,
    )
    add_table(
        doc,
        ["Platform", "Ways to pause or hold (verify in the console before use)"],
        [
            ["Intune \u2013 apps and configuration",
             "Do not add the next ring group; remove or exclude the group from the assignment; change the "
             "assignment for affected groups."],
            ["Intune \u2013 Windows updates",
             "Pause quality or feature updates in the update ring; hold or edit the feature update or quality "
             "update policy assignment; delay the next ring's release."],
            ["ConfigMgr",
             "Disable the deployment; do not deploy to the next collection; remove devices from the target "
             "collection. Clients act on the change after their next policy refresh."],
        ],
        widths=[4.5, 12.5],
        bold_first_col=True,
    )


# =============================================================================
# Section 8 - Scheduling and network impact controls
# =============================================================================
def create_section_8(doc):
    add_heading(doc, "8. Scheduling and Network Impact Controls", 1)
    add_paragraph(
        doc,
        "Every deployment has three separate activities. They have different network and user impact, and "
        "different scheduling rules. They must not be confused in plans, records or communication.",
        keep_next=True,
    )

    add_heading(doc, "8.1 DOWNLOAD, INSTALLATION and RESTART", 2)
    add_table(
        doc,
        ["Activity", "What it is", "Update download traffic", "Scheduling rule"],
        [
            ["DOWNLOAD",
             "Transfer of content to the device from Microsoft services, the Intune service, a ConfigMgr "
             "distribution point, a cache server or peer devices.",
             "**Yes.** This is the main source of deployment network traffic.",
             "Restricted: not on Sunday, not during business hours; planned activity starts after 15:30 "
             "(Section 8.2)."],
            ["INSTALLATION",
             "Running the installer or applying the update using content already on the device.",
             "**No** update download traffic (status reporting only).",
             "May proceed once content is on the device, according to the deployment's installation settings "
             "(deadline, maintenance window, user experience settings)."],
            ["RESTART",
             "Restarting the device to complete installation or apply a change.",
             "**No** update download traffic.",
             "According to the approved restart behavior, notifications and deadlines (Section 8.7)."],
        ],
        widths=[2.7, 5.5, 3.8, 5.0],
        bold_first_col=True,
        first_col_fill=BLUE_LIGHT,
        size=9.5,
    )
    add_callout(
        doc,
        "Important \u2013 keep the three activities separate",
        [
            "Do not describe INSTALLATION or RESTART as DOWNLOAD activity. A device that installs or restarts "
            "using content it already holds does not generate the same update download traffic.",
            "**Exception:** some installers fetch content from the network while they run (for example, online "
            "or \u201cweb\u201d installers, streaming installers, or Microsoft 365 Apps configured to install from the "
            "Microsoft CDN). That part of the installation is DOWNLOAD activity and the download rules apply. "
            "Identify this during the pre-deployment checks (Section 6.1).",
        ],
        kind="important",
    )

    add_heading(doc, "8.2 Organization Scheduling Requirements", 2)
    add_table(
        doc,
        ["Ref", "Requirement", "Applies to"],
        [
            ["S1", "No planned update DOWNLOAD activity on **Sunday**.", "DOWNLOAD"],
            ["S2", "No planned update DOWNLOAD activity during **business hours** (business days and hours: TBC).",
             "DOWNLOAD"],
            ["S3", "Planned update activities start **after 15:30** (local time; time zone TBC).",
             "Start of all planned deployment activity"],
            ["S4", "If a device was powered off or unavailable during the scheduled deployment period, a pending "
                   "update may resume when the device becomes available again, **subject to S1** (no Sunday "
                   "download).", "DOWNLOAD (resumed)"],
            ["S5", "An update that has already been downloaded may proceed with installation or request a restart.",
             "INSTALLATION, RESTART"],
            ["S6", "Installation and restart activity is treated separately from package download activity, "
                   "because it does not generate the same update download traffic.",
             "INSTALLATION, RESTART"],
            ["S7", "Large packages or broad deployments use controlled waves/rings to reduce network impact.",
             "DOWNLOAD"],
        ],
        widths=[1.2, 11.8, 4.0],
        bold_first_col=True,
        center_cols=(0,),
    )

    add_heading(doc, "8.3 Weekly View", 2)
    add_paragraph(doc, "How S1\u2013S6 apply across the week:", keep_next=True)
    grid = doc.add_table(rows=4, cols=4)
    grid.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(grid, [3.2, 4.2, 4.6, 5.0])
    set_table_borders(grid)
    set_table_cell_margins(grid, top=70, bottom=70)
    headers = ["Activity", "Sunday (all day)", "Other days \u2013 business hours",
               "Other days \u2013 from 15:30, outside business hours"]
    mark_header_row(grid.rows[0])
    for i, header in enumerate(headers):
        cell = grid.rows[0].cells[i]
        set_cell_shading(cell, BLUE_DARK)
        set_cell_valign(cell)
        _fill_cell(cell, header, size=9, bold=True, color=WHITE, align=WD_ALIGN_PARAGRAPH.CENTER)
    no, yes = (RED_FILL, RED_TEXT), (GREEN_FILL, GREEN_TEXT)
    data = [
        ("DOWNLOAD", [("Not permitted", no), ("Not permitted", no),
                      ("Permitted \u2013 planned start after 15:30", yes)]),
        ("INSTALLATION", [("Permitted if content is already on the device", yes),
                          ("Permitted if content is already on the device", yes),
                          ("Permitted", yes)]),
        ("RESTART", [("Per approved restart behavior", yes), ("Per approved restart behavior", yes),
                     ("Per approved restart behavior", yes)]),
    ]
    for r, (label, cells) in enumerate(data, start=1):
        row = grid.rows[r]
        keep_row_together(row)
        set_cell_shading(row.cells[0], BLUE_LIGHT)
        set_cell_valign(row.cells[0])
        _fill_cell(row.cells[0], label, size=9.5, bold=True, color=BLUE_DARK)
        for c, (text, (fill, color)) in enumerate(cells, start=1):
            cell = row.cells[c]
            set_cell_shading(cell, fill)
            set_cell_valign(cell)
            _fill_cell(cell, f"**{text}**", size=9, color=color, align=WD_ALIGN_PARAGRAPH.CENTER)
    keep_table_on_one_page(grid)
    add_spacer(doc)
    add_paragraph(
        doc,
        "Business days and business hours: TBC. End of the permitted download window, if any (for example, "
        "before the next business day starts): TBC. Installation and restart remain subject to the restart "
        "settings and user notifications approved for each deployment.",
        size=9.5, italic=True, color=GREY,
    )

    add_heading(doc, "8.4 Applying the Schedule on Each Platform", 2)
    add_paragraph(
        doc,
        "The controls below influence when DOWNLOAD, INSTALLATION and RESTART happen. Exact behavior depends "
        "on the configuration and client versions in use, so verify it in Ring 0 before relying on it.",
        keep_next=True,
    )
    add_table(
        doc,
        ["Platform / type", "Controls that influence DOWNLOAD timing", "Controls that influence INSTALLATION and RESTART"],
        [
            ["Intune \u2013 Win32 / LOB / Microsoft 365 apps",
             ["- Time the assignment is made", "- Assignment availability time (device time or UTC)",
              "- Delivery Optimization priority (background / foreground)",
              "- Delivery Optimization bandwidth settings"],
             ["- Installation deadline", "- Restart grace period and notifications", "- Return code mapping"]],
            ["Intune \u2013 Windows updates (update rings, feature and quality update policies; Windows Autopatch "
             "if used \u2013 TBC)",
             ["- Deferral periods and ring release timing", "- Pause / resume",
              "- Expedite policies (download immediately \u2013 emergency path only)",
              "- Delivery Optimization settings"],
             ["- Deadlines and grace period", "- Active hours", "- Automatic update behavior",
              "- Restart notifications"]],
            ["ConfigMgr \u2013 software updates (including automatic deployment rules)",
             ["- Deployment available time", "- ADR evaluation and deployment schedule",
              "- Client BITS throttling settings", "- Boundary groups, distribution points and peer/cache "
              "options (where configured)", "- Download settings for slow or unreliable networks"],
             ["- Installation deadline", "- Maintenance windows", "- User experience and restart settings",
              "- Computer restart client settings"]],
            ["ConfigMgr \u2013 applications and packages",
             ["- Deployment available time", "- Distribution point and content options",
              "- Client BITS throttling settings"],
             ["- Installation deadline", "- Maintenance windows", "- User experience and restart settings"]],
        ],
        widths=[4.4, 6.5, 6.1],
        bold_first_col=True,
        size=9,
    )
    add_callout(
        doc,
        "Verify configuration",
        [
            "- ConfigMgr maintenance windows mainly control when installation and restart can run. Content "
            "download can start once the deployment is available, before the maintenance window. Do not rely on "
            "maintenance windows to enforce the DOWNLOAD rules.",
            "- Delivery Optimization and BITS throttling can limit bandwidth during set hours. Verify whether the "
            "configured values meet the \u201cno download during business hours\u201d requirement.",
            "- Some mechanisms resume a pending download automatically when a device comes online and cannot "
            "block a single day such as Sunday. Endpoint Management must confirm how S1 is enforced for each "
            "platform and deployment type (method TBC) and record any gap in the change record for a decision.",
        ],
        kind="verify",
    )

    add_heading(doc, "8.5 Scheduling Procedure", 2)
    add_steps(doc, [
        "Confirm the business days, business hours and time zone that apply to the target devices (TBC values).",
        "Check the content size and the number of devices in each wave. Estimate the load per site, especially "
        "for low-bandwidth locations.",
        "Make sure content is on the distribution points or caches before the window opens. Distribution point "
        "replication is a separate network activity and is scheduled under its own settings (TBC).",
        "Set the start of the deployment (assignment, availability or available time) at or after **15:30** "
        "on a day other than Sunday. For Intune, confirm whether times are set in device time or UTC.",
        "Allow for check-in delay. A wave started late on Saturday may reach some devices on Sunday. Plan waves "
        "so that planned DOWNLOAD activity does not fall on Sunday.",
        "Set the installation deadline and restart settings according to the approved restart behavior.",
        "Do not schedule several large deployments to the same devices in the same window.",
        "Record the schedule, download window and installation/restart behavior in the deployment record.",
    ])

    add_heading(doc, "8.6 Network Impact Controls", 2)
    add_bullet_list(doc, [
        "Use rings and waves for large packages and broad deployments (S7). Use smaller waves for "
        "low-bandwidth locations.",
        "Use peer and cache technologies where configured, such as Delivery Optimization, Microsoft Connected "
        "Cache, ConfigMgr peer cache or BranchCache (configuration TBC).",
        "Pre-stage content to distribution points before the deployment window.",
        "Apply Delivery Optimization or BITS bandwidth limits where configured (values TBC).",
        "Use express or delta content where the platform supports it.",
        "For remote and VPN devices, confirm whether update content flows through the VPN tunnel or directly "
        "from the internet (depends on the VPN split-tunnel configuration: TBC).",
        "Inform network operations before large deployments such as feature updates or Microsoft 365 Apps "
        "(contact TBC).",
        "Watch network impact during the first waves and pause if congestion is reported.",
    ])

    add_heading(doc, "8.7 Restart Management", 2)
    add_bullet_list(doc, [
        "Define the restart behavior of each deployment before the pilot and record it.",
        "Use the platform's user notifications, grace periods and deadlines as approved for the deployment "
        "(values TBC).",
        "Avoid forced restarts during business hours unless the change record explicitly approves them "
        "(for example, for urgent security remediation).",
        "Treat a device as complete only after the required restart has happened and the device reports the "
        "expected state.",
        "Follow up devices that stay in pending restart through the exception/remediation ring (Section 12).",
    ])


# =============================================================================
# Section 9 - Deployment execution by activity type
# =============================================================================
def create_section_9(doc):
    add_heading(doc, "9. Deployment Execution by Activity Type", 1)
    add_paragraph(doc, "Each activity type follows the standard workflow with the sequence below.", keep_next=True)
    add_heading(doc, "9.1 Summary", 2)
    add_table(
        doc,
        ["Type", "Activity", "Sequence", "Key points"],
        [
            ["A", "Monthly / security patches",
             "Assessment \u2192 Test \u2192 Pilot \u2192 Controlled Production \u2192 Broad Production \u2192 "
             "Monitoring \u2192 Remediation",
             "Repeats monthly; standing ring groups; vulnerability confirmation."],
            ["B", "Software distribution / upgrade",
             "Package validation \u2192 Dependencies \u2192 Detection rules \u2192 Test \u2192 Pilot \u2192 "
             "Phased Production \u2192 Monitoring",
             "Detection and supersedence are critical; application owner validation."],
            ["C", "Configuration push",
             "Define current state \u2192 Define target state \u2192 Technical test \u2192 Pilot \u2192 Staged "
             "assignment \u2192 Monitor \u2192 Rollback/remediation if required",
             "Little download traffic but possible high user impact; check conflicts and reversibility."],
            ["D", "Urgent security remediation",
             "Expedited/emergency change \u2192 Minimum test \u2192 Shortened pilot \u2192 Accelerated rings "
             "\u2192 Increased monitoring \u2192 Remediation/recovery",
             "Shortened controls, not removed; deviations explicitly approved."],
        ],
        widths=[1.0, 3.2, 7.6, 5.2],
        bold_first_col=True,
        center_cols=(0,),
        size=9,
    )

    add_heading(doc, "9.2 A \u2013 Monthly / Security Patches", 2)
    add_steps(doc, [
        "**Assessment:** after Microsoft's monthly release (normally the second Tuesday of the month) or an "
        "out-of-band release, review the release notes and Windows release health known issues. Obtain severity "
        "and exploitation information from Security / Vulnerability Management. Identify the updates that apply "
        "to each Windows version in use.",
        "**Platform check:** confirm which devices receive updates through Intune Windows Update policies and "
        "which through ConfigMgr software update deployments (Section 10).",
        "**Preparation:** Intune \u2013 confirm update ring and policy settings for each ring (deferrals, "
        "deadlines, restart behavior). ConfigMgr \u2013 review the software update group or ADR output and "
        "make sure content is on the distribution points.",
        "**Test:** deploy to Ring 0 and complete the technical tests (Section 6.2).",
        "**Pilot:** release to Ring 1 within the permitted download window; validate against Section 6.4.",
        "**Controlled production:** after approval to expand, release to Ring 2 in waves.",
        "**Broad production:** release to Ring 3.",
        "**Monitoring:** track compliance per ring. For security updates, confirm with Security / "
        "Vulnerability Management that scan or report results show the vulnerability as fixed.",
        "**Remediation:** move incomplete devices to the exception/remediation ring (Section 12).",
    ])
    add_paragraph(doc, "Target timing for each ring after the monthly release: TBC.", italic=True, color=GREY,
                  size=9.5)

    add_heading(doc, "9.3 Windows Feature Updates (Variant of Type A)", 2)
    add_paragraph(doc, "Feature updates follow sequence A with these additional controls:", keep_next=True)
    add_bullet_list(doc, [
        "Check hardware and software eligibility first (for example, Windows 11 hardware requirements and "
        "readiness reports).",
        "Test application compatibility with Application/Service Owners before the pilot; allow a longer pilot.",
        "Content is large: use smaller waves and confirm caching and pre-staging (Section 8.6).",
        "Intune \u2013 feature update policy with the target version; ConfigMgr \u2013 feature update "
        "deployment, servicing plan or upgrade task sequence.",
        "Record the rollback period (uninstall window) configured for the deployment (value TBC).",
    ])

    add_heading(doc, "9.4 B \u2013 Software Distribution / Upgrade", 2)
    add_steps(doc, [
        "**Package validation:** confirm the source, version, licensing, silent install and uninstall commands, "
        "return codes and signature/hash.",
        "**Dependencies:** configure prerequisites and dependencies. Decide whether the new version replaces "
        "the old one (supersedence with uninstall) or upgrades it in place.",
        "**Detection rules:** create detection for the exact version and requirement rules (OS version, "
        "architecture, free disk space).",
        "**Test:** in Ring 0, test a new install, an upgrade from each supported previous version, an uninstall, "
        "and that user data and settings remain after the upgrade.",
        "**Pilot:** deploy to Ring 1 with Application/Service Owner validation.",
        "**Phased production:** deploy to Ring 2 waves, then Ring 3.",
        "**Monitoring:** track installation status, failure codes, user feedback and licence use where relevant.",
        "**Clean-up:** after completion, retire superseded deployments and assignments to avoid reinstall "
        "loops or duplicate versions.",
    ])
    add_callout(
        doc,
        "Note \u2013 self-service (available) deployments",
        ["Installs started by users from Company Portal or Software Center are not planned deployments. Large "
         "self-service packages should still be published in controlled phases where network impact is a concern."],
        kind="note",
    )

    add_heading(doc, "9.5 C \u2013 Configuration Push", 2)
    add_steps(doc, [
        "**Define current state:** record the current settings and their source (Intune profile, Group Policy, "
        "ConfigMgr baseline or local). Check for policies that already manage the same setting.",
        "**Define target state:** record the exact settings and values, scope, expected user impact and any "
        "effect on device compliance (and, where used, Conditional Access).",
        "**Technical test:** in Ring 0, confirm the policy applies, the platform reports success with no "
        "conflict, the setting is correct on the device, and user impact is as expected. Test reversal, "
        "including whether removing the policy restores the previous value.",
        "**Pilot:** assign to the Ring 1 group and validate.",
        "**Staged assignment:** add ring groups or collections step by step.",
        "**Monitor:** review policy status (succeeded, error, conflict, not applicable), Service Desk calls and "
        "compliance state.",
        "**Rollback/remediation if required:** remove the assignment, deploy a reversing configuration, or run "
        "a remediation script (Section 13).",
    ])
    add_callout(
        doc,
        "Note",
        ["Configuration changes usually create little download traffic but can have a large user impact (for "
         "example, firewall, BitLocker, Defender or sign-in settings). The ring approach applies regardless of size."],
        kind="note",
    )

    add_heading(doc, "9.6 D \u2013 Urgent Security Remediation", 2)
    add_paragraph(
        doc,
        "Use this path only when the expedited/emergency change process criteria are met (criteria TBC). "
        "Validation, monitoring and recovery controls are kept but shortened.",
        keep_next=True,
    )
    add_steps(doc, [
        "Security / Vulnerability Management confirms the risk, urgency and required remediation.",
        "Raise the expedited/emergency change and obtain approval (approval authority TBC). Record any "
        "approved deviation, such as a download outside the Section 8 window or an enforced restart.",
        "Prepare the package or policy and complete the minimum pre-deployment checks: source, applicability, "
        "detection, targeting, restart behavior and rollback.",
        "Run the **minimum Ring 0 test set**: download, installation, detection, restart, device starts and "
        "signs in, network and VPN connectivity, and Microsoft 365 sign-in. Use at least one device per main "
        "hardware model and Windows version where possible.",
        "Run a shortened Ring 1 pilot. Skip it only if the emergency change approval explicitly accepts that risk.",
        "Expand through the rings in faster or larger waves as approved. Keep the ability to pause.",
        "Monitor closely and keep the recovery plan ready (Section 13).",
        "Complete the deployment record and any post-implementation review required by the emergency change "
        "process.",
    ])


# =============================================================================
# Section 10 - Intune and ConfigMgr handling
# =============================================================================
def create_section_10(doc):
    add_heading(doc, "10. Intune and SCCM / ConfigMgr Handling", 1)
    add_heading(doc, "10.1 Rules", 2)
    add_bullet_list(doc, [
        "Deployment must follow the **approved management state** of the endpoint.",
        "For **Intune-managed** workloads, use the relevant Intune application, configuration, remediation or "
        "Windows Update policy.",
        "For **ConfigMgr-managed** workloads, use the approved ConfigMgr collections and deployment mechanisms.",
        "For **co-managed** endpoints, verify workload ownership before deployment.",
        "Avoid duplicate or conflicting deployments from Intune and ConfigMgr.",
        "Old or legacy content in Software Center is not automatically an active ConfigMgr deployment. Validate "
        "the device's current management state and assignment first (Section 10.5).",
    ])

    add_heading(doc, "10.2 Platform Verification Procedure", 2)
    add_steps(doc, [
        "In the Intune admin center, check how the target devices are managed (for example, the \u201cManaged "
        "by\u201d value: Intune, Co-managed or ConfigMgr).",
        "For co-managed devices, check the co-management (cloud attach) workload settings in the ConfigMgr "
        "console, including pilot collection membership for workloads set to Pilot Intune.",
        "Decide which platform owns the workload for this deployment (Section 10.3).",
        "Check the other platform for an existing deployment or assignment of the same item to the same "
        "devices. Remove or exclude it before deploying.",
        "Check for other sources that manage the same setting, such as Group Policy or legacy WSUS settings "
        "for Windows Update.",
        "Record the management platform and the evidence in the deployment record.",
    ])

    add_heading(doc, "10.3 Workload Ownership and Mechanisms", 2)
    add_table(
        doc,
        ["Deployment type", "Co-management workload", "Intune mechanism", "ConfigMgr mechanism"],
        [
            ["Windows quality / security updates", "Windows Update policies",
             "Update rings; quality update policies (including expedite); Windows Autopatch if used (TBC)",
             "Software update groups, ADRs, deployments to collections"],
            ["Windows feature updates", "Windows Update policies",
             "Feature update policies; update ring settings (deferral, uninstall period)",
             "Feature update deployments, servicing plans or upgrade task sequences"],
            ["Microsoft 365 Apps updates", "Office Click-to-Run apps",
             "Microsoft 365 Apps update settings (update channel and policies)",
             "Microsoft 365 Apps updates through software updates"],
            ["Applications (Microsoft and third-party)", "Client apps",
             "Win32, MSI line-of-business, Microsoft 365 Apps and Microsoft Store apps; Enterprise App "
             "Management if licensed (TBC)",
             "Applications and packages; third-party update catalogs where configured"],
            ["Configuration", "Device configuration (and related workloads such as Endpoint Protection)",
             "Configuration profiles, settings catalog, endpoint security policies",
             "Configuration baselines / compliance settings, client settings"],
            ["Scripts and remediation", "Depends on mechanism",
             "Platform scripts; Remediations (where licensed)",
             "Scripts, configuration items/baselines, packages"],
        ],
        widths=[3.6, 3.6, 5.0, 4.8],
        bold_first_col=True,
        size=9,
    )
    add_callout(
        doc,
        "Verify configuration",
        [
            "On co-managed devices, some deployment types (for example, applications) can be delivered by both "
            "platforms regardless of the workload setting. The workload setting alone does not prevent a "
            "duplicate deployment. Check both platforms.",
            "Do not assume that ConfigMgr cannot act on a device because it is reported as migrated to Intune. "
            "While a ConfigMgr client is installed and receiving policy, ConfigMgr deployments may still run. "
            "Confirm the device's actual management configuration.",
        ],
        kind="verify",
    )

    add_heading(doc, "10.4 Avoiding Duplicate or Conflicting Deployments", 2)
    add_bullet_list(doc, [
        "Each item (application, update type or setting) has one owning platform per device.",
        "When moving an application from ConfigMgr to Intune, exclude the migrated devices from the ConfigMgr "
        "deployment (or retire the deployment) before the Intune assignment starts.",
        "Use the same detection logic on both platforms during a migration to avoid reinstall loops.",
        "Do not control the same update type on the same device from both Intune Windows Update policies and "
        "ConfigMgr software update deployments unless the workload configuration supports it (verify).",
        "Check for legacy Group Policy settings that point devices to WSUS or set Windows Update behavior. They "
        "can conflict with Intune Windows Update policies.",
        "Use separate ring groups or collections per platform, and exclude devices owned by the other platform.",
    ])

    add_heading(doc, "10.5 Legacy Content in Software Center", 2)
    add_paragraph(doc, "If old or unexpected content appears in Software Center:", keep_next=True)
    add_steps(doc, [
        "Do not treat it as proof of an active, intended deployment, and do not ask users to install it until "
        "it is validated.",
        "Check whether the ConfigMgr client is installed and healthy, and when it last received policy.",
        "Check whether the device should be co-managed or Intune-only according to the migration plan (TBC).",
        "In the ConfigMgr console, identify the collection and deployment that target the device, and whether "
        "the deployment is current, enabled and approved.",
        "If the content is legacy or unintended, raise a clean-up through the change process (remove the "
        "deployment, correct collection membership or remove the ConfigMgr client as the migration plan "
        "defines).",
        "Record the finding and the action in the related ticket.",
    ])


# =============================================================================
# Section 11 - Monitoring, verification and closure
# =============================================================================
def create_section_11(doc):
    add_heading(doc, "11. Monitoring, Verification and Closure", 1)
    add_heading(doc, "11.1 Deployment Status Categories", 2)
    add_paragraph(
        doc,
        "Map the status labels shown by Intune and ConfigMgr to the categories below. Labels differ between "
        "consoles, reports and versions; the examples are indicative only.",
        keep_next=True,
    )
    add_table(
        doc,
        ["Status", "Meaning", "Example platform labels", "Required action"],
        [
            ["Successful", "Installed, compliant or applied as intended.",
             "Intune: Installed / Succeeded. ConfigMgr: Success / Compliant.",
             "Spot-check the actual state on sample devices."],
            ["In progress", "Download or installation is running.",
             "ConfigMgr: In Progress. Intune: varies by report.",
             "Allow the expected time. Investigate if it stays in progress longer than expected (TBC per deployment)."],
            ["Pending", "Not yet started: waiting for check-in, availability time, deadline, maintenance window "
                        "or dependency.",
             "Intune: Install pending / Pending.",
             "Check last check-in and the schedule. If the device is offline, follow Section 12."],
            ["Failed", "The deployment returned an error.",
             "Intune: Failed / Error. ConfigMgr: Error.",
             "Group by error code. Investigate significant patterns. Pause if the pattern points to the "
             "package or policy."],
            ["Not applicable", "Requirements not met, update not needed, or device out of scope.",
             "Intune: Not applicable. ConfigMgr: Requirements not met / Not required.",
             "Confirm this is expected, not a sign of wrong requirement rules or targeting."],
            ["Pending restart", "Installed, but a restart is needed to complete.",
             "Restart-related status or detail (wording varies).",
             "Follow restart settings; notify user/support if it continues; follow Section 12."],
            ["Unknown / not reported", "No status received from the device.",
             "ConfigMgr: Unknown. Intune: no recent check-in.",
             "Check device activity. Exclude stale devices from results only by a documented rule (TBC)."],
        ],
        widths=[2.6, 4.2, 4.6, 5.6],
        bold_first_col=True,
        size=9,
    )

    add_heading(doc, "11.2 Administrator Monitoring Duties", 2)
    add_table(
        doc,
        ["Duty", "How"],
        [
            ["Monitor deployment status", "Review status for each ring and wave at the frequency set in the "
                                          "deployment record (TBC), and before every expansion."],
            ["Investigate significant failure patterns", "Group failures by error code, model, Windows version, "
                                                         "location and platform. Find the common cause."],
            ["Pause expansion when necessary", "Stop the next wave or ring when a pause trigger occurs (11.3)."],
            ["Confirm the intended version / package / configuration", "Check sample devices from each ring "
                                                                       "directly, not only the console."],
            ["Track repeated failures", "Identify devices that fail again after remediation and handle them as "
                                        "exceptions or problem records."],
            ["Record exceptions", "Add each exception to the deployment record with reason, owner and next action."],
            ["Complete final validation before closure", "Apply the closure criteria in Section 11.5."],
        ],
        widths=[5.5, 11.5],
        bold_first_col=True,
        keep_together=True,
    )
    add_callout(
        doc,
        "Note \u2013 reporting delay",
        ["Intune and ConfigMgr status is not real-time. Devices report after check-in, policy refresh or "
         "compliance scans. Allow for this delay before concluding that a device failed, and confirm on a "
         "sample device when in doubt."],
        kind="note",
    )

    add_heading(doc, "11.3 Pause Triggers", 2)
    add_paragraph(doc, "Pause further expansion and investigate when any of the following occurs "
                       "(numeric thresholds TBC per deployment):", keep_next=True)
    add_bullet_list(doc, [
        "A significant failure pattern that points to the package, policy or targeting.",
        "A business-impacting incident linked to the deployment.",
        "Unexpected restarts, data loss, or devices that do not start or sign in.",
        "Reported network congestion at one or more locations.",
        "Impact on security tools, encryption or device compliance.",
        "An Application/Service Owner reports that a critical business function is broken.",
        "Reported status does not match the actual device state.",
    ])
    add_paragraph(doc, "After a pause: notify the Service Desk and the Change Approver / IT Management, "
                       "investigate, and decide to resume, fix forward or roll back (Section 13).")

    add_heading(doc, "11.4 Success Measure", 2)
    add_paragraph(
        doc,
        "The success measure for each deployment (for example, the proportion of eligible devices that must "
        "be successful before closure, and how offline or stale devices are treated) is agreed in the change "
        "record. Organization standard values: TBC.",
    )

    add_heading(doc, "11.5 Closure Criteria", 2)
    add_bullet_list(doc, [
        "The intended version, package or configuration is confirmed on sample devices from each ring.",
        "The success measure agreed in the change record is met.",
        "Every remaining device is either remediated or recorded as an exception with an owner and next action.",
        "For security deployments, Security / Vulnerability Management confirms remediation where scanning or "
        "reporting is available.",
        "Superseded deployments and temporary assignments are cleaned up.",
        "The deployment record (Section 15) is complete.",
        "The change is closed according to the change process.",
    ])


# =============================================================================
# Section 12 - Exception handling
# =============================================================================
def create_section_12(doc):
    add_heading(doc, "12. Exception Handling", 1)
    add_paragraph(
        doc,
        "Devices that cannot complete the normal deployment move to the exception/remediation ring. Each "
        "exception is recorded with the reason, owner and next action. Follow-up periods and the authority "
        "to accept an exception are TBC.",
        keep_next=True,
    )
    add_table(
        doc,
        ["Scenario", "Required action"],
        [
            ["Device offline during the deployment window",
             "Keep the device targeted. The pending deployment may resume when the device comes back online, "
             "subject to the Sunday download rule (S1, S4). If it is still incomplete after the follow-up "
             "period (TBC), add it to the exception ring and contact the user through the Service Desk / "
             "Location Support."],
            ["Pending restart",
             "Follow the configured restart behavior. If the restart is still pending after the follow-up period "
             "(TBC), notify the user through the Service Desk. Do not count the device as successful until it "
             "restarts and reports the expected state. For security updates, tell Security / Vulnerability "
             "Management the device is still exposed."],
            ["Download failure",
             "Check content availability (distribution point, cache or Microsoft service), boundary groups, "
             "proxy/firewall, free disk space and download logs. Retry within the permitted download window. "
             "Do not force a download outside the window unless the change approves it."],
            ["Installation failure",
             "Capture the error/exit code and logs. Decide whether the cause is device-specific or in the "
             "package. If it is a pattern, pause and fix the package, then re-test in Ring 0. Remediate single "
             "devices through the exception ring."],
            ["Application compatibility issue",
             "Pause the affected ring or cohort. Engage the Application/Service Owner. Identify a workaround and "
             "move affected devices into a documented exclusion group. Decide fix or rollback through the change "
             "process and inform the Service Desk."],
            ["Network / bandwidth concern",
             "Pause or slow waves for the affected location. Reduce wave size, use caching or pre-staging, and "
             "reschedule within the permitted window. Inform network operations (contact TBC)."],
            ["Business-critical operational conflict",
             "Defer the affected devices through a documented exclusion. Agree a new date with the "
             "Application/Service Owner. For security updates, record the risk with Security / Vulnerability "
             "Management. Approval according to the change/exception process (TBC)."],
            ["Device unavailable during the scheduled deployment",
             "For devices known to be away or in use for long periods (for example, travel, storage or "
             "shift-based use), arrange availability with Location Support, schedule a follow-up wave and "
             "record the plan."],
            ["Unsupported or incompatible device",
             "Confirm with the requirement rules or a hardware check. Exclude the device with a documented "
             "reason. Raise replacement, upgrade or another mitigation. For security updates, follow the "
             "exception/risk acceptance process (TBC)."],
            ["Detection mismatch",
             "If the device is installed but reported as failed (or the reverse), correct the detection rule "
             "and re-test in Ring 0 before re-release."],
            ["Insufficient disk space",
             "Free space using an approved method (for example, a clean-up script), then retry within the "
             "permitted window."],
            ["Device managed by the other platform",
             "Stop the deployment to that device. Verify the management state (Section 10.2), correct the "
             "targeting and avoid duplicate deployment."],
            ["User asks to postpone",
             "Use the deferral options configured in the deployment. Further postponement is handled through "
             "the Service Desk as an exception (approval TBC)."],
        ],
        widths=[4.4, 12.6],
        bold_first_col=True,
        first_col_fill=BLUE_LIGHT,
        size=9.5,
    )


# =============================================================================
# Section 13 - Rollback / recovery
# =============================================================================
def create_section_13(doc):
    add_heading(doc, "13. Rollback / Recovery", 1)
    add_heading(doc, "13.1 Principles", 2)
    add_bullet_list(doc, [
        "Determine the rollback possibilities **before production** (before Ring 1) and record them.",
        "Use software uninstall where supported.",
        "Use policy removal where supported.",
        "Use version rollback where technically supported.",
        "Pause the deployment if business impact is detected.",
        "If rollback is not possible, isolate the affected deployment cohort.",
        "Perform remediation through the approved change/exception process.",
        "Validate endpoint health after recovery.",
    ])

    add_heading(doc, "13.2 Rollback Options by Deployment Type", 2)
    add_table(
        doc,
        ["Deployment type", "Possible rollback / recovery (where supported)", "Points to verify"],
        [
            ["Windows quality / security update",
             "Uninstall the update (for example, the Intune update ring uninstall option where available, or an "
             "approved uninstall script for a specific KB). Pause the ring.",
             "Some updates cannot be uninstalled. Test uninstall in Ring 0. Check whether the update is offered "
             "again after removal."],
            ["Windows feature update",
             "Roll back to the previous Windows version within the configured rollback period. Pause the feature "
             "update policy or deployment.",
             "Rollback works only within the configured period (TBC) and while previous version files remain."],
            ["Software install / upgrade",
             "Uninstall assignment or deployment; redeploy the previous version; vendor rollback method.",
             "Keep the previous package available. The vendor may not support downgrade or older data formats."],
            ["Configuration change",
             "Remove the assignment; deploy a reversing configuration with the previous values; run a "
             "remediation script.",
             "Some settings stay on the device after the policy is removed. Set the previous values explicitly "
             "where needed."],
            ["Script / remediation package", "Run a tested reversal script.", "Reversal tested in Ring 0."],
            ["Driver / firmware (if in scope \u2013 TBC)",
             "Vendor-supported rollback where available; otherwise isolate and remediate.",
             "Rollback is often limited. Consider BitLocker behavior during firmware changes."],
        ],
        widths=[3.8, 7.0, 6.2],
        bold_first_col=True,
        size=9,
    )

    add_heading(doc, "13.3 Recovery Procedure", 2)
    add_steps(doc, [
        "**Detect and assess:** confirm the impact, the affected rings or cohorts, and the related incidents.",
        "**Pause:** stop further expansion (Section 7.4). Notify the Service Desk and the Change Approver / IT "
        "Management.",
        "**Decide:** roll back, fix forward or isolate, according to the change process (decision authority "
        "TBC). Inform Security / Vulnerability Management if rollback reopens a security exposure.",
        "**Isolate:** if rollback is not possible, exclude the affected cohort from further assignments and "
        "target it for remediation.",
        "**Execute:** carry out the recovery through the approved change or exception process (emergency "
        "change where required).",
        "**Validate:** check endpoint health on sample devices using the Ring 0 health checks (Section 6.2).",
        "**Record:** document actions, results and cause. Raise a problem record where the cause needs "
        "further investigation.",
        "**Resume or close:** resume only after the fix is validated again in Ring 0 and, where needed, Ring 1.",
    ])
    add_callout(
        doc,
        "Important",
        ["Before Ring 1 starts, the deployment record must state the rollback method, or \u201cno rollback "
         "available\u201d together with the planned remediation approach."],
        kind="important",
    )


# =============================================================================
# Section 14 - Communication
# =============================================================================
def create_section_14(doc):
    add_heading(doc, "14. Communication", 1)
    add_paragraph(doc, "Communication channels and templates: TBC. Minimum communication is shown below.",
                  keep_next=True)
    add_heading(doc, "14.1 Communication Requirements", 2)
    add_table(
        doc,
        ["Communication", "When", "Audience", "Minimum content"],
        [
            ["Support-team notification", "Before the pilot and before each production ring.", ROLE_SD,
             "Change reference, scope, schedule, expected user experience (download after 15:30, installation, "
             "restart prompts), known issues, how to recognize related calls, escalation contact."],
            ["User notification (where required)",
             "Before deployments users will notice (restart, application change, downtime).", "Affected users",
             "What changes and when, what users should do (for example, save work or leave the device on and "
             "connected), restart expectations, where to get help."],
            ["Restart notification", "Through platform notifications as configured; extra notice for disruptive "
                                     "restarts.", "Affected users",
             "Deadline, grace period and how to postpone (if allowed)."],
            ["Deployment schedule communication", "When the schedule is approved or changes.",
             "Service Desk, Application/Service Owners, Security, Change Approver",
             "Ring dates, download windows and cohorts."],
            ["Major issue communication", "As soon as a significant issue is confirmed.",
             "Service Desk, Application/Service Owner, Change Approver / IT Management, Security if relevant",
             "Issue, impact, affected cohort, action taken (for example, paused), time of next update. Use the "
             "major incident process where its criteria are met (TBC)."],
            ["Workaround / remediation information", "When available.", "Service Desk / Location Support; users "
                                                                       "where needed",
             "Symptoms, workaround steps and how to log and route tickets."],
            ["Completion", "At closure.", "Stakeholders of the change", "Results, remaining exceptions and "
                                                                        "follow-up actions."],
        ],
        widths=[3.4, 3.6, 3.8, 6.2],
        bold_first_col=True,
        size=9,
    )

    add_heading(doc, "14.2 Escalation Path", 2)
    add_table(
        doc,
        ["Level", "Role", "Escalate when"],
        [
            ["1", ROLE_SD, "A user reports an issue that may relate to the deployment and the documented "
                           "workaround does not resolve it."],
            ["2", ROLE_EM, "Repeated or significant issues, failure patterns, or a request to pause or exclude devices."],
            ["3", f"{ROLE_CHG} (with {ROLE_APP} or {ROLE_SEC} as relevant)",
             "Business impact, a rollback decision, an exception that needs approval, or a deviation from this SOP."],
        ],
        widths=[1.4, 6.0, 9.6],
        center_cols=(0,),
        keep_together=True,
    )
    add_paragraph(doc, "Escalation contacts and out-of-hours contacts: TBC.", italic=True, color=GREY, size=9.5)


# =============================================================================
# Section 15 - Deployment record
# =============================================================================
def create_section_15(doc):
    add_heading(doc, "15. Deployment Record \u2013 Minimum Required Information", 1)
    add_paragraph(
        doc,
        "Each deployment keeps a record with at least the information below. The record may be kept in the "
        "IT service management tool (tool and form TBC). The \u201cEntry\u201d column can be used as a form.",
        keep_next=True,
    )
    fields = [
        ("Change / request / ticket reference", "Approved change or request that authorizes the deployment."),
        ("Deployment type", "A \u2013 patches, B \u2013 software, C \u2013 configuration, D \u2013 urgent "
                            "remediation (and feature update where applicable)."),
        ("Target scope", "Devices, groups or collections; counts; exclusions."),
        ("Management platform", "Intune, ConfigMgr or both by group; evidence of workload ownership."),
        ("Package / version / configuration", "Name, version, KB or build; policy or setting names and values."),
        ("Test results", "Ring 0 results and evidence (Section 6.2)."),
        ("Pilot results", "Ring 1 results against the exit criteria (Section 6.4)."),
        ("Deployment rings", "Ring and wave membership, sizes and durations chosen, with the reason."),
        ("Deployment schedule", "Start date/time of each ring and wave."),
        ("Download window", "Permitted DOWNLOAD window used; confirmation of S1\u2013S3; any approved deviation."),
        ("Installation / restart behavior", "Deadlines, maintenance windows, restart settings and notifications."),
        ("Rollback / recovery plan", "Method, or \u201cno rollback\u201d with the remediation approach."),
        ("Monitoring results", "Status per ring; failure patterns; pauses and decisions."),
        ("Exceptions", "Devices or cases, reason, owner and next action."),
        ("Final validation", "Closure criteria checked (Section 11.5)."),
        ("Closure reference", "Change closure reference and date."),
    ]
    add_table(
        doc,
        ["#", "Field", "What to record", "Entry"],
        [[str(i), f, w, ""] for i, (f, w) in enumerate(fields, start=1)],
        widths=[0.8, 4.4, 7.0, 4.8],
        bold_first_col=False,
        center_cols=(0,),
        size=9,
    )


# =============================================================================
# Section 16 - Operational checklist
# =============================================================================
def create_section_16(doc):
    add_heading(doc, "16. Operational Checklist", 1)
    add_paragraph(doc, "Complete the checklist for each deployment. The boxes can be ticked in Word.",
                  keep_next=True)
    groups = [
        ("Planning and preparation", [
            ("Scope confirmed", "2, 5"),
            ("Target devices confirmed", "6.1, 7.3"),
            ("Management platform confirmed", "10.2"),
            ("Package/policy validated", "6.1"),
            ("Detection criteria defined", "6.1"),
            ("Dependencies reviewed", "6.1"),
            ("Restart behavior identified", "6.1, 8.7"),
            ("Rollback/recovery considered", "13"),
        ]),
        ("Testing and approval", [
            ("Technical test passed", "6.2"),
            ("Pilot successfully completed", "6.4"),
            ("Required approval obtained", "5.2"),
        ]),
        ("Production deployment", [
            ("Production rings scheduled", "7, 8.5"),
            ("Communication completed where required", "14"),
            ("Deployment monitored", "11"),
            ("Failures investigated", "11.2"),
        ]),
        ("Closure", [
            ("Exceptions documented", "12"),
            ("Final validation completed", "11.5"),
            ("Deployment/change closed", "11.5, 15"),
        ]),
    ]
    widths = [1.1, 9.4, 2.4, 4.1]
    n_rows = 1 + sum(1 + len(items) for _, items in groups)
    table = doc.add_table(rows=n_rows, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, widths)
    set_table_borders(table)
    set_table_cell_margins(table, top=45, bottom=45)

    header = table.rows[0]
    mark_header_row(header)
    for i, text in enumerate(["\u2713", "Checklist item", "SOP section", "Initials / date"]):
        cell = header.cells[i]
        set_cell_shading(cell, BLUE_DARK)
        set_cell_valign(cell)
        _fill_cell(cell, text, size=9.5, bold=True, color=WHITE,
                   align=WD_ALIGN_PARAGRAPH.CENTER if i != 1 else None)

    r = 1
    for title, items in groups:
        row = table.rows[r]
        keep_row_together(row)
        merged = row.cells[0].merge(row.cells[3])
        set_cell_shading(merged, BLUE_LIGHT)
        _fill_cell(merged, f"**{title}**", size=9.5, color=BLUE_DARK)
        r += 1
        for text, ref in items:
            row = table.rows[r]
            keep_row_together(row)
            box = row.cells[0]
            set_cell_valign(box)
            p = box.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            compact(p, 1, 1)
            add_checkbox(p, 12)
            for c in (1, 2, 3):
                set_cell_valign(row.cells[c])
            _fill_cell(row.cells[1], text, size=10)
            _fill_cell(row.cells[2], ref, size=9, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER)
            r += 1
    keep_table_on_one_page(table)
    add_spacer(doc)


# =============================================================================
# Section 17 - Document control
# =============================================================================
def create_section_17(doc):
    add_heading(doc, "17. Document Control", 1).paragraph_format.page_break_before = True
    add_heading(doc, "17.1 Document Information", 2)
    add_kv_table(doc, [
        ("Document ID", "TBC"),
        ("Document title", f"{DOC_TITLE} \u2013 Standard Operating Procedure"),
        ("Version", f"{DOC_VERSION} (Draft for review)"),
        ("Document owner", "TBC"),
        ("Effective date", "TBC (on approval)"),
        ("Review date / cycle", "TBC. Also review after significant changes to the endpoint management platforms "
                                "or to the deployment requirements."),
        ("Classification", "Confidential \u2013 Internal Use Only"),
        ("Related documents", ["- Change management process (reference TBC)",
                               "- Expedited / emergency change process (reference TBC)",
                               "- Vulnerability management process (reference TBC)",
                               "- Exception / risk acceptance process (reference TBC)",
                               "- Major incident process (reference TBC)"]),
    ], widths=(4.6, 12.4))

    add_heading(doc, "17.2 Revision History", 2)
    add_table(
        doc,
        ["Version", "Date", "Description of change", "Author"],
        [
            [DOC_VERSION, DOC_DATE, "Initial draft for review.", "TBC"],
            ["", "", "", ""],
            ["", "", "", ""],
        ],
        widths=[2.0, 2.8, 8.4, 3.8],
        center_cols=(0, 1),
    )

    add_heading(doc, "17.3 Open Items to Confirm Before Approval", 2)
    add_paragraph(doc, "The following organization-specific items are marked TBC in this SOP:", keep_next=True)
    add_table(
        doc,
        ["#", "Item to confirm", "Section"],
        [
            ["1", "Document ID, owner, effective date and review cycle", "17"],
            ["2", "Business days, business hours and time zone for the download rules", "8.2, 8.3"],
            ["3", "End of the permitted download window, if any", "8.3"],
            ["4", "Technical method that enforces the Sunday and business-hours download rules on each platform",
             "8.4"],
            ["5", "Inclusion of virtual desktops, shared/kiosk devices, macOS, drivers and firmware", "2"],
            ["6", "Ring 0 device list; ring group and collection naming; ring membership review frequency", "6.2, 7.3"],
            ["7", "Pilot observation periods, success measures and pause thresholds", "6.4, 11.3, 11.4"],
            ["8", "Monitoring frequency and follow-up periods for offline and pending-restart devices", "11.2, 12"],
            ["9", "Restart settings (deadlines, grace periods, notifications) and rollback periods", "8.7, 9.3, 13.2"],
            ["10", "Emergency change criteria and approval authorities; exception approval authority",
             "4, 5.3, 9.6, 12"],
            ["11", "Caching and bandwidth settings; VPN split-tunnel behavior; network operations contact", "8.6"],
            ["12", "Core business application list for testing", "6.2"],
            ["13", "Windows Autopatch use; licensing of Remediations and Enterprise App Management", "8.4, 10.3"],
            ["14", "ConfigMgr-to-Intune migration plan for legacy Software Center content", "10.5"],
            ["15", "Communication channels, templates and escalation contacts", "14"],
            ["16", "IT service management tool and form for the deployment record", "15"],
        ],
        widths=[0.9, 13.0, 3.1],
        center_cols=(0, 2),
        size=9,
    )


# =============================================================================
# Section 18 - Approval
# =============================================================================
def create_section_18(doc):
    add_heading(doc, "18. Approval", 1)
    add_paragraph(
        doc,
        "This SOP takes effect when approved by the roles below. Names and approval authority are confirmed "
        "by the organization (TBC).",
        keep_next=True,
    )
    roles = ["Document Owner", "Technical Reviewer", "Security / Change Reviewer", "Approver"]
    table = doc.add_table(rows=1 + len(roles), cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_col_widths(table, [4.2, 3.6, 3.2, 3.6, 2.4])
    set_table_borders(table)
    set_table_cell_margins(table, top=60, bottom=60)
    mark_header_row(table.rows[0])
    for i, text in enumerate(["Role", "Name", "Job title", "Signature", "Date"]):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, BLUE_DARK)
        _fill_cell(cell, text, size=9.5, bold=True, color=WHITE)
    for r, role in enumerate(roles, start=1):
        row = table.rows[r]
        keep_row_together(row)
        set_row_height(row, 1.4)
        set_cell_shading(row.cells[0], BLUE_LIGHT)
        for cell in row.cells:
            set_cell_valign(cell)
        _fill_cell(row.cells[0], role, size=10, bold=True, color=BLUE_DARK)
    keep_table_on_one_page(table)
    add_spacer(doc, 10)
    end = doc.add_paragraph()
    end.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_rich_text(end, "\u2014 End of document \u2014", size=9, color=GREY, italic=True)


# =============================================================================
# Build
# =============================================================================
def build_sop(out_path, update_fields=True):
    doc = setup_document(update_fields=update_fields)
    create_title_page(doc)
    create_toc(doc)
    for create in (
        create_section_1, create_section_2, create_section_3, create_section_4,
        create_section_5, create_section_6, create_section_7, create_section_8,
        create_section_9, create_section_10, create_section_11, create_section_12,
        create_section_13, create_section_14, create_section_15, create_section_16,
        create_section_17, create_section_18,
    ):
        create(doc)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--output", default=os.path.join("teams", "documentation", "output", OUTPUT_NAME),
                        help="Output .docx path (default: output/%(default)s)")
    parser.add_argument("--no-update-fields", action="store_true",
                        help="Do not ask Word to refresh fields (TOC) when the document opens")
    args = parser.parse_args()
    path = build_sop(args.output, update_fields=not args.no_update_fields)
    print(f"Created: {path}")


if __name__ == "__main__":
    main()

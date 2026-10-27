"""Local mixed-script direction and glyph-aware diagram fonts."""

from pathlib import Path
import shutil
import subprocess
import unicodedata
import re
from copy import deepcopy
from functools import lru_cache

LTR_RUN = re.compile(r'[+-]?[A-Za-z0-9_]+(?:[ .:/@+\-]+[A-Za-z0-9_]+)*\.?')


def direction(text):
    for char in text:
        bidi = unicodedata.bidirectional(char)
        if bidi in {"R", "AL"}: return "rtl"
        if bidi == "L": return "ltr"
    return "ltr"


def has_arabic(text):
    return any("\u0600" <= char <= "\u06ff" for char in text)


def drawing_direction(text):
    # Pillow's default Latin font uses BASIC layout, which rejects even an
    # explicit LTR option. Complex-script fonts are selected with RAQM above.
    return {"direction": direction(text)} if has_arabic(text) else {}


@lru_cache(maxsize=8)
def font_path(family):
    matcher = shutil.which("fc-match")
    if matcher:
        try:
            found = subprocess.check_output([matcher, "-f", "%{file}", family + ":lang=ar"], text=True, timeout=5).strip()
            if Path(found).is_file(): return found
        except (subprocess.SubprocessError, OSError): pass
    for path in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(path).is_file(): return path
    raise ValueError("Install/configure a local font with Arabic glyphs for diagram rendering")


def diagram_font(text, size):
    from PIL import ImageFont, features
    from ..utils.config import config_manager
    if not has_arabic(text): return ImageFont.load_default(size=size)
    if not features.check("raqm"):
        raise ValueError("Arabic diagram PNG rendering requires Pillow with RAQM shaping")
    path = font_path(config_manager.document_profile.style.arabic_font)
    from fontTools.ttLib import TTFont
    with TTFont(path) as font:
        coverage = font.getBestCmap()
        if any(ord(c) not in coverage for c in text if not c.isspace()):
            raise ValueError("The selected diagram font lacks required glyphs")
    return ImageFont.truetype(path, size=size, layout_engine=ImageFont.Layout.RAQM)


def word_direction(paragraph):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from ..utils.config import config_manager
    from docx.text.run import Run
    rtl = direction(paragraph.text) == "rtl"
    if rtl:
        prop = paragraph._p.get_or_add_pPr()
        element = OxmlElement('w:bidi')
        prop.append(element)
        # Logical start is the right edge for bidi paragraphs. Explicit physical
        # RIGHT is interpreted as the end edge by LibreOffice's Word importer.
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        paragraph._p.get_or_add_pPr().find(qn('w:jc')).set(qn('w:val'), 'start')
    for run in list(paragraph.runs):
        if has_arabic(run.text) and LTR_RUN.search(run.text):
            offset=0
            pieces=[]
            for match in LTR_RUN.finditer(run.text):
                pieces.extend([run.text[offset:match.start()],match.group()])
                offset=match.end()
            pieces.append(run.text[offset:])
            for piece in pieces:
                if not piece: continue
                element=OxmlElement('w:r')
                if run._r.rPr is not None: element.append(deepcopy(run._r.rPr))
                run._r.addprevious(element)
                Run(element,paragraph).text=piece
            run._r.getparent().remove(run._r)
    for run in paragraph.runs:
        if LTR_RUN.fullmatch(run.text.strip()):
            element=OxmlElement('w:rtl');element.set(qn('w:val'),'0')
            run._r.get_or_add_rPr().append(element)
            if rtl and not any(c.isalpha() for c in run.text):
                # Weak numeric/hyphen runs otherwise reorder under Word's bidi
                # paragraph context, even with rtl=0. LRM supplies a strong LTR
                # boundary without changing the visible date/number characters.
                run.text='\u200e'+run.text+'\u200e'
        if has_arabic(run.text):
            properties = run._r.get_or_add_rPr()
            element=OxmlElement('w:rtl');element.set(qn('w:val'),'1');properties.append(element)
            fonts = properties.find(qn('w:rFonts'))
            if fonts is None:
                fonts = OxmlElement('w:rFonts')
                properties.append(fonts)
            fonts.set(qn('w:cs'), config_manager.document_profile.style.arabic_font)
            lang = OxmlElement('w:lang')
            lang.set(qn('w:bidi'), 'ar-SA')
            properties.append(lang)

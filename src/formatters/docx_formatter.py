"""DOCX Formatter - Converts Markdown to Microsoft Word format."""

from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
import re
from ..utils.logger import logger


class DOCXFormatter:
    """Formats and converts content to Microsoft Word (.docx)."""

    def __init__(self):
        self.name = "DOCX Formatter"

    async def convert(
        self, content: str, output_path: Path, process_name: str
    ) -> Path:
        """
        Convert Markdown content to DOCX format.

        Args:
            content: Markdown content
            output_path: Output file path
            process_name: Process name

        Returns:
            Path to the generated DOCX file
        """
        logger.info(f"Converting to DOCX: {output_path}", agent=self.name)

        try:
            # Create document
            doc = Document()

            # Set up styles
            self._setup_styles(doc)

            # Parse and add content
            self._parse_markdown_to_docx(doc, content)
            from .typography import word_direction, direction
            for paragraph in doc.paragraphs:
                word_direction(paragraph)
            for table in doc.tables:
                if direction(' '.join(c.text for c in table.rows[0].cells)) == 'rtl':
                    table._tbl.tblPr.append(OxmlElement('w:bidiVisual'))
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs: word_direction(paragraph)

            # Save document
            doc.save(str(output_path))

            logger.info(f"DOCX file created: {output_path}", agent=self.name)
            return output_path

        except Exception as e:
            logger.error(f"DOCX conversion failed: {e}", agent=self.name)
            raise

    def _setup_styles(self, doc: Document):
        """Set up document styles."""
        # Modify existing styles
        styles = doc.styles
        from ..utils.config import config_manager
        style = config_manager.document_profile.style
        layout = config_manager.document_profile.layouts[config_manager.document_profile.template]
        styles['Normal'].font.name = style.font
        styles['Normal'].font.size = Pt(style.body_pt)
        styles['Normal'].paragraph_format.space_after = Pt(layout.paragraph_after_pt)
        styles['Normal'].paragraph_format.line_spacing = style.line_spacing
        for section in doc.sections:
            section.page_width, section.page_height = Inches(8.5), Inches(11)
            section.top_margin = section.bottom_margin = Inches(style.margin_inches)
            section.left_margin = section.right_margin = Inches(style.margin_inches)
            footer = section.footer.paragraphs[0]
            footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
            footer.add_run('Draft | Page ')
            for run in footer.runs:
                run.font.size = Pt(9)
            field = OxmlElement('w:fldSimple')
            field.set(qn('w:instr'), 'PAGE')
            footer._p.append(field)

        # Heading 1
        if 'Heading 1' in styles:
            h1 = styles['Heading 1']
            h1.font.size = Pt(16)
            h1.font.bold = True
            h1.font.color.rgb = RGBColor(0, 0, 0)

        # Heading 2
        if 'Heading 2' in styles:
            h2 = styles['Heading 2']
            h2.font.size = Pt(13)
            h2.font.bold = True
            h2.font.color.rgb = RGBColor(0, 0, 0)

        # Heading 3
        if 'Heading 3' in styles:
            h3 = styles['Heading 3']
            h3.font.size = Pt(11)
            h3.font.bold = True
        for name in ('Title', 'Subtitle', 'Heading 1', 'Heading 2', 'Heading 3'):
            styles[name].font.name = style.font
            styles[name].font.color.rgb = RGBColor(0, 0, 0)
            styles[name].paragraph_format.keep_with_next = True
            for border in list(styles[name].element.xpath('.//w:pBdr')):
                border.getparent().remove(border)
        styles['Title'].font.size = Pt(24)
        styles['Title'].font.bold = True
        for name, before, after in [('Title', 0, 18), ('Heading 1', layout.heading_before_pt, 8), ('Heading 2', 12, 6), ('Heading 3', 10, 5)]:
            styles[name].paragraph_format.space_before = Pt(before)
            styles[name].paragraph_format.space_after = Pt(after)
        styles['Caption'].font.name = style.font
        styles['Caption'].font.size = Pt(10)
        styles['Caption'].font.color.rgb = RGBColor(34, 34, 34)
        styles['Caption'].font.bold = False
        styles['Caption'].font.italic = False
        for name in ('Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2', 'Heading 3', 'Caption'):
            font_style = styles[name]
            properties = font_style.element.get_or_add_rPr()
            fonts = properties.find(qn('w:rFonts'))
            if fonts is None:
                fonts = OxmlElement('w:rFonts')
                properties.append(fonts)
            fonts.set(qn('w:cs'), style.arabic_font)
            for key, value in [('szCs', str(int((font_style.font.size.pt if font_style.font.size else style.body_pt)*2))),
                               ('bCs', '1' if font_style.font.bold else '0'), ('iCs', '1' if font_style.font.italic else '0')]:
                element = properties.find(qn('w:' + key))
                if element is None:
                    element = OxmlElement('w:' + key)
                    properties.append(element)
                element.set(qn('w:val'), value)

    def _add_title_page(self, doc: Document, process_name: str):
        """Add title page."""
        from datetime import datetime

        # Title
        title = doc.add_heading(
            f"{process_name}\nStandard Operating Procedure",
            level=0
        )
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Add some spacing
        doc.add_paragraph()

        # Metadata
        metadata = doc.add_paragraph()
        metadata.add_run("Document Information\n").bold = True
        metadata.add_run(f"\nVersion: 1.0")
        metadata.add_run(f"\nDate: {datetime.now().strftime('%Y-%m-%d')}")
        metadata.add_run(f"\nStatus: Draft")
        metadata.add_run("\nGenerated by: IT Process Documentation System")
        metadata.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Page break
        doc.add_page_break()

    def _parse_markdown_to_docx(self, doc: Document, content: str):
        """Parse markdown content and add to document."""
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            if line.strip().startswith(('```', '~~~')):
                language = line.strip()[3:].strip()
                fence = line.strip()[:3]
                i += 1
                code = []
                while i < len(lines) and not lines[i].strip().startswith(fence):
                    code.append(lines[i])
                    i += 1
                if language == 'reema-flow':
                    from ..utils.diagrams import parse_flow, png_flow
                    flow = parse_flow('\n'.join(code))
                    paragraph = doc.add_paragraph()
                    paragraph.paragraph_format.keep_with_next = True
                    diagram_width, diagram_height = flow.dimensions()
                    width = min(6.5, 6 * diagram_width / diagram_height)
                    picture = paragraph.add_run().add_picture(png_flow(flow), width=Inches(width))
                    picture._inline.docPr.set('descr', flow.description())
                    doc.add_paragraph(flow.description(), style='Caption')
                else:
                    paragraph = doc.add_paragraph()
                    run = paragraph.add_run('\n'.join(code))
                    run.font.name = 'Consolas'
                    run.font.size = Pt(10)
                i += 1
                continue

            # Only a leading YAML block is metadata. Other separators must not
            # swallow the SOP sections between horizontal rules.
            if i == 0 and line.strip() == '---':
                i += 1
                while i < len(lines) and lines[i].strip() != '---':
                    i += 1
                i += 1
                continue

            if line.strip() == '---':
                i += 1
                continue

            # Headings
            if line.startswith('#'):
                level = len(re.match(r'^#+', line).group())
                text = line.lstrip('#').strip()
                if text:
                    doc.add_heading(text, level=0 if level == 1 else min(level - 1, 3))

            # Tables (simple detection)
            elif '|' in line and i + 1 < len(lines) and '|' in lines[i + 1]:
                table_lines = [line]
                i += 1
                while i < len(lines) and '|' in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                self._add_table(doc, table_lines)
                continue

            # Lists
            elif line.strip().startswith(('-', '*', '•')) or (line.strip() and line.strip()[0].isdigit() and '.' in line[:3]):
                # Bullet or numbered list
                list_items = [line]
                i += 1
                while i < len(lines) and (lines[i].strip().startswith(('-', '*', '•')) or (lines[i].strip() and lines[i].strip()[0].isdigit())):
                    list_items.append(lines[i])
                    i += 1
                self._add_list(doc, list_items)
                continue

            # Regular paragraphs
            elif line.strip():
                paragraph_lines = [line.strip()]
                while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(
                        r'^\s*(?:#|\||```|~~~|[-*•]\s|\d+[.)]\s|---\s*$)', lines[i + 1]):
                    i += 1
                    paragraph_lines.append(lines[i].strip())
                self._add_inline(doc.add_paragraph(), ' '.join(paragraph_lines))

            i += 1

    def _add_table(self, doc: Document, table_lines: list):
        """Add a table to the document."""
        # Parse table
        rows = []
        for line in table_lines:
            cells = [cell.strip() for cell in line.strip().removeprefix('|').removesuffix('|').split('|')]
            if all(re.fullmatch(r':?-{3,}:?', cell) for cell in cells):
                continue
            rows.append(cells)  # Preserve empty RACI cells and their columns.

        if not rows or len(rows) < 2:
            return
        if any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("Markdown table rows must preserve every column")

        # Create table
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = 'Table Grid'
        table.autofit = False
        from .theme import table_widths
        widths = table_widths(rows)
        section = doc.sections[-1]
        available_inches = (section.page_width - section.left_margin - section.right_margin) / 914400
        for j, column in enumerate(table.columns):
            column.width = Inches(available_inches * widths[j])
        borders = OxmlElement('w:tblBorders')
        for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            element = OxmlElement('w:' + edge)
            for key, value in {'val': 'single', 'sz': '4', 'color': 'D9D9D9'}.items():
                element.set(qn('w:' + key), value)
            borders.append(element)
        table._tbl.tblPr.append(borders)
        table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))

        # Fill table
        for i, row_data in enumerate(rows):
            if len(row_data) <= 6 and max(map(len, row_data)) <= 300:
                table.rows[i]._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
            row_cells = table.rows[i].cells
            for j, cell_data in enumerate(row_data):
                if j < len(row_cells):
                    row_cells[j].width = table.columns[j].width
                    self._add_inline(row_cells[j].paragraphs[0], cell_data)
                    row_cells[j].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    paragraph = row_cells[j].paragraphs[0]
                    if i == 0 or (len(rows) <= 8 and i < len(rows) - 1):
                        paragraph.paragraph_format.keep_with_next = True
                    from ..utils.config import config_manager
                    padding = config_manager.document_profile.layouts[config_manager.document_profile.template].table_padding_pt
                    paragraph.paragraph_format.space_before = Pt(padding)
                    paragraph.paragraph_format.space_after = Pt(padding)
                    if j > 0 and len(cell_data) <= 4:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    shade = OxmlElement('w:shd')
                    shade.set(qn('w:fill'), 'F0F2F5' if i == 0 else 'FFFFFF')
                    row_cells[j]._tc.get_or_add_tcPr().append(shade)
                    # Bold header row
                    if i == 0:
                        for run in row_cells[j].paragraphs[0].runs:
                            run.bold = True

    def _add_list(self, doc: Document, list_items: list):
        """Add a list to the document."""
        for item in list_items:
            # Remove list markers
            text = re.sub(r'^[\s\-\*\•0-9\.]+', '', item).strip()
            if text:
                numbered = bool(re.match(r'^\s*\d+[.)]', item))
                self._add_inline(doc.add_paragraph(style='List Number' if numbered else 'List Bullet'), text)

    def _add_inline(self, paragraph, text):
        for part in re.split(r'(\*\*.+?\*\*|__.+?__|\*[^*]+\*|`[^`]+`)', text):
            if part.startswith(('**', '__')) and part.endswith(('**', '__')):
                paragraph.add_run(part[2:-2]).bold = True
            elif part.startswith('*') and part.endswith('*'):
                paragraph.add_run(part[1:-1]).italic = True
            elif part.startswith('`') and part.endswith('`'):
                paragraph.add_run(part[1:-1]).font.name = 'Consolas'
            else:
                paragraph.add_run(part)

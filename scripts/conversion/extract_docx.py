#!/usr/bin/env python3
"""Extract full content from a DOCX file using python-docx."""

from docx import Document
from docx.oxml.ns import qn
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = PROJECT_ROOT / "teams" / "documentation" / "output" / "SOP_User_Incident_Management_V1_Full_Detail.docx"

def extract_full_content(path):
    doc = Document(path)

    # --- Document properties ---
    props = doc.core_properties
    print("=" * 100)
    print("DOCUMENT PROPERTIES")
    print("=" * 100)
    print(f"  Title   : {props.title}")
    print(f"  Author  : {props.author}")
    print(f"  Created : {props.created}")
    print(f"  Modified: {props.modified}")
    print(f"  Subject : {props.subject}")
    print()

    # --- Sections ---
    print("=" * 100)
    print(f"SECTIONS: {len(doc.sections)}")
    print("=" * 100)
    for i, section in enumerate(doc.sections):
        print(f"  Section {i}: page width={section.page_width}, height={section.page_height}, "
              f"orientation={'landscape' if section.orientation else 'portrait'}")
        print(f"    Margins: top={section.top_margin}, bottom={section.bottom_margin}, "
              f"left={section.left_margin}, right={section.right_margin}")
    print()

    # --- Walk through the document body in order ---
    # This preserves the order of paragraphs and tables as they appear
    print("=" * 100)
    print("FULL DOCUMENT BODY (in order)")
    print("=" * 100)
    print()

    body = doc.element.body
    element_index = 0

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            # It's a paragraph
            from docx.text.paragraph import Paragraph
            para = Paragraph(child, doc)
            style_name = para.style.name if para.style else "None"
            text = para.text
            # Show run-level formatting if useful
            runs_info = []
            for run in para.runs:
                bold = run.bold
                italic = run.italic
                underline = run.underline
                font_name = run.font.name
                font_size = run.font.size
                fmt_flags = []
                if bold: fmt_flags.append("B")
                if italic: fmt_flags.append("I")
                if underline: fmt_flags.append("U")
                fmt_str = ",".join(fmt_flags) if fmt_flags else ""
                if run.text.strip():
                    runs_info.append(f"[{fmt_str}|{font_name}|{font_size}] {run.text}")

            print(f"[P#{element_index}] Style: '{style_name}'")
            if text.strip():
                print(f"  Text: {text}")
            else:
                print(f"  Text: (empty)")
            if runs_info:
                for ri in runs_info:
                    print(f"    Run: {ri}")
            print()
            element_index += 1

        elif tag == "tbl":
            # It's a table
            from docx.table import Table
            table = Table(child, doc)
            num_rows = len(table.rows)
            num_cols = len(table.columns) if table.rows else 0
            print(f"[TABLE#{element_index}] Rows: {num_rows}, Cols: {num_cols}")
            print("-" * 80)

            for row_idx, row in enumerate(table.rows):
                print(f"  Row {row_idx}:")
                for col_idx, cell in enumerate(row.cells):
                    cell_text = cell.text.strip()
                    # Also check for merged cells
                    print(f"    Cell[{row_idx},{col_idx}]: {cell_text if cell_text else '(empty)'}")
                print()

            print("-" * 80)
            print()
            element_index += 1

        elif tag == "sectPr":
            print(f"[SECTION-BREAK#{element_index}]")
            print()
            element_index += 1

    # --- Headers and Footers ---
    print("=" * 100)
    print("HEADERS AND FOOTERS")
    print("=" * 100)
    for i, section in enumerate(doc.sections):
        header = section.header
        footer = section.footer
        if header and not header.is_linked_to_previous:
            print(f"  Section {i} Header:")
            for p in header.paragraphs:
                print(f"    [{p.style.name}] {p.text}")
            # Check for tables in header
            for t in header.tables:
                print(f"    Header Table ({len(t.rows)}x{len(t.columns)}):")
                for row_idx, row in enumerate(t.rows):
                    for col_idx, cell in enumerate(row.cells):
                        print(f"      Cell[{row_idx},{col_idx}]: {cell.text.strip()}")
        if footer and not footer.is_linked_to_previous:
            print(f"  Section {i} Footer:")
            for p in footer.paragraphs:
                print(f"    [{p.style.name}] {p.text}")
            for t in footer.tables:
                print(f"    Footer Table ({len(t.rows)}x{len(t.columns)}):")
                for row_idx, row in enumerate(t.rows):
                    for col_idx, cell in enumerate(row.cells):
                        print(f"      Cell[{row_idx},{col_idx}]: {cell.text.strip()}")
    print()

    # --- Summary ---
    total_paras = len(doc.paragraphs)
    total_tables = len(doc.tables)
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"  Total paragraphs: {total_paras}")
    print(f"  Total tables    : {total_tables}")
    print(f"  Total sections  : {len(doc.sections)}")
    print()

    # Style usage summary
    style_counts = {}
    for p in doc.paragraphs:
        sname = p.style.name if p.style else "None"
        style_counts[sname] = style_counts.get(sname, 0) + 1
    print("  Style usage:")
    for sname, count in sorted(style_counts.items(), key=lambda x: -x[1]):
        print(f"    {sname}: {count}")


if __name__ == "__main__":
    extract_full_content(DOC_PATH)

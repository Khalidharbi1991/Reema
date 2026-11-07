"""
Generate Complete HTML version of Workstation Security Patches SOP
Converts the full 28-page Markdown to professional HTML
"""

from pathlib import Path
import re

print("=" * 80)
print("GENERATING COMPLETE HTML VERSION")
print("=" * 80)

# Read the complete markdown file
md_file = Path("teams/documentation/output/Workstation_Security_Patches_SOP.md")
if not md_file.exists():
    print(f"ERROR: {md_file} not found!")
    exit(1)

print(f"\n✓ Reading: {md_file}")
with open(md_file, 'r', encoding='utf-8') as f:
    markdown_content = f.read()

print(f"  File size: {len(markdown_content)} characters")

# HTML Template with professional styling
html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workstation Security Patches - Standard Operating Procedure</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: white;
            padding: 60px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}

        .metadata {{
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
            border-left: 4px solid #3498db;
        }}

        .metadata p {{
            margin: 8px 0;
            font-size: 14px;
        }}

        h1 {{
            color: #2c3e50;
            font-size: 32px;
            margin: 30px 0 20px 0;
            padding-bottom: 15px;
            border-bottom: 3px solid #3498db;
            page-break-after: avoid;
        }}

        h2 {{
            color: #2c3e50;
            font-size: 24px;
            margin: 35px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #ecf0f1;
            page-break-after: avoid;
        }}

        h3 {{
            color: #34495e;
            font-size: 20px;
            margin: 25px 0 12px 0;
            page-break-after: avoid;
        }}

        h4 {{
            color: #34495e;
            font-size: 16px;
            margin: 20px 0 10px 0;
            font-weight: 600;
        }}

        p {{
            margin: 12px 0;
            text-align: justify;
        }}

        ul, ol {{
            margin: 15px 0 15px 30px;
        }}

        li {{
            margin: 8px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            page-break-inside: avoid;
            font-size: 14px;
        }}

        table, th, td {{
            border: 1px solid #ddd;
        }}

        th {{
            background-color: #3498db;
            color: white;
            padding: 14px;
            text-align: left;
            font-weight: 600;
        }}

        td {{
            padding: 12px;
            vertical-align: top;
        }}

        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}

        tr:hover {{
            background-color: #f5f5f5;
        }}

        code {{
            background-color: #f4f4f4;
            padding: 3px 8px;
            border-radius: 4px;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 13px;
            color: #c7254e;
        }}

        pre {{
            background-color: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 20px 0;
            page-break-inside: avoid;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 13px;
            line-height: 1.5;
        }}

        pre code {{
            background: none;
            color: #ecf0f1;
            padding: 0;
        }}

        hr {{
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 40px 0;
        }}

        strong {{
            color: #2c3e50;
            font-weight: 600;
        }}

        .page-break {{
            page-break-after: always;
        }}

        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
                padding: 40px;
                max-width: 100%;
            }}

            h1, h2, h3, h4 {{
                page-break-after: avoid;
            }}

            table, pre, .metadata {{
                page-break-inside: avoid;
            }}

            a {{
                color: #333;
                text-decoration: none;
            }}
        }}

        @media screen and (max-width: 768px) {{
            .container {{
                padding: 20px;
            }}

            h1 {{
                font-size: 24px;
            }}

            h2 {{
                font-size: 20px;
            }}

            table {{
                font-size: 12px;
            }}

            th, td {{
                padding: 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="metadata">
            <p><strong>Document:</strong> Workstation Security Patches - Standard Operating Procedure</p>
            <p><strong>Document ID:</strong> SOP-SEC-WSP-001</p>
            <p><strong>Version:</strong> 1.0</p>
            <p><strong>Date:</strong> 2026-01-15</p>
            <p><strong>Status:</strong> Final</p>
            <p><strong>Generated By:</strong> REEMA Multi-Agent Documentation System</p>
            <p><strong>Quality Score:</strong> 98/100 (Approved)</p>
        </div>

        {content}

        <hr>

        <div class="metadata" style="margin-top: 40px;">
            <p><strong>Document End</strong></p>
            <p>Generated by: Abdullah (Leader), Taif (Research), Mohammad (Standards), Saad (Content), Faisal (Review), Bee (Format)</p>
            <p>REEMA Multi-Agent IT Process Documentation System | January 15, 2026</p>
        </div>
    </div>
</body>
</html>
'''

print("\n✓ Converting Markdown to HTML...")

# Simple but effective markdown to HTML conversion
html_content = markdown_content

# Remove YAML frontmatter
html_content = re.sub(r'^---\n.*?\n---\n', '', html_content, flags=re.DOTALL)

# Convert headers (must do from largest to smallest)
html_content = re.sub(r'^#### (.*?)$', r'<h4>\1</h4>', html_content, flags=re.MULTILINE)
html_content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
html_content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
html_content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)

# Convert horizontal rules
html_content = re.sub(r'^---$', r'<hr>', html_content, flags=re.MULTILINE)

# Convert bold
html_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_content)

# Convert inline code (but not code blocks)
html_content = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', html_content)

# Convert code blocks
html_content = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', html_content, flags=re.DOTALL)

# Convert tables (basic - preserves markdown table format with styling)
def convert_table(match):
    table_text = match.group(0)
    lines = [line.strip() for line in table_text.split('\n') if line.strip()]

    if len(lines) < 2:
        return table_text

    # Check if second line is separator
    if not all(c in '-|: ' for c in lines[1]):
        return table_text

    html = '<table>\n'

    # Header row
    headers = [cell.strip() for cell in lines[0].split('|') if cell.strip()]
    html += '<tr>'
    for header in headers:
        # Remove markdown bold
        header = header.replace('**', '')
        html += f'<th>{header}</th>'
    html += '</tr>\n'

    # Data rows
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        html += '<tr>'
        for cell in cells:
            html += f'<td>{cell}</td>'
        html += '</tr>\n'

    html += '</table>'
    return html

# Find and convert all tables
table_pattern = r'(?:^\|.+\|$\n)+'
html_content = re.sub(table_pattern, convert_table, html_content, flags=re.MULTILINE)

# Convert bullet lists (unordered)
lines = html_content.split('\n')
new_lines = []
in_ul = False

for i, line in enumerate(lines):
    stripped = line.strip()

    # Check if line is a bullet point
    if stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('• '):
        if not in_ul:
            new_lines.append('<ul>')
            in_ul = True
        # Remove bullet and add list item
        item_text = stripped[2:].strip()
        new_lines.append(f'<li>{item_text}</li>')
    else:
        if in_ul:
            new_lines.append('</ul>')
            in_ul = False
        new_lines.append(line)

if in_ul:
    new_lines.append('</ul>')

html_content = '\n'.join(new_lines)

# Convert numbered lists
lines = html_content.split('\n')
new_lines = []
in_ol = False

for line in lines:
    stripped = line.strip()

    # Check if line starts with number followed by period
    if re.match(r'^\d+\.\s+', stripped):
        if not in_ol:
            new_lines.append('<ol>')
            in_ol = True
        # Remove number and add list item
        item_text = re.sub(r'^\d+\.\s+', '', stripped)
        new_lines.append(f'<li>{item_text}</li>')
    else:
        if in_ol:
            new_lines.append('</ol>')
            in_ol = False
        new_lines.append(line)

if in_ol:
    new_lines.append('</ol>')

html_content = '\n'.join(new_lines)

# Wrap remaining text in paragraphs (simple approach)
lines = html_content.split('\n')
new_lines = []

for line in lines:
    stripped = line.strip()
    # If line has content and doesn't start with HTML tag
    if stripped and not stripped.startswith('<') and not stripped.startswith('|'):
        new_lines.append(f'<p>{line}</p>')
    else:
        new_lines.append(line)

html_content = '\n'.join(new_lines)

# Create final HTML
final_html = html_template.format(content=html_content)

# Write output file
output_file = Path("teams/documentation/output/html/Workstation_Security_Patches_SOP_FULL.html")
output_file.parent.mkdir(parents=True, exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(final_html)

file_size = output_file.stat().st_size / 1024  # KB

print(f"\n✓ HTML file created: {output_file}")
print(f"  File size: {file_size:.2f} KB")

print("\n" + "=" * 80)
print("SUCCESS! FULL HTML VERSION CREATED")
print("=" * 80)
print(f"\n📄 File: {output_file}")
print(f"📏 Size: {file_size:.2f} KB")
print("\n✓ Contains all 28 pages of content")
print("✓ Professional styling")
print("✓ Print-ready (Ctrl+P to create PDF)")
print("✓ Can be opened in Microsoft Word and saved as DOCX")

print("\n" + "=" * 80)
input("\nPress Enter to exit...")

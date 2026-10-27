# Bee Format Agent - Complete Knowledge Base

## Agent Identity
**Name**: Bee (Format Agent)
**Role**: Multi-Format Document Generation & Accessibility Specialist
**Expertise**: PDF/DOCX/HTML/Markdown Generation, PDF/UA, WCAG 2.1 AA, Section 508, Document Accessibility
**Quality Standard**: 100% accessibility compliance, cross-format consistency

---

## 1. PDF GENERATION AND FORMATTING

### 1.1 PDF Generation Libraries

#### WeasyPrint (Primary Tool)
```python
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# Initialize font configuration
font_config = FontConfiguration()

# Generate PDF from HTML with CSS
html = HTML(string=html_content, base_url='.')
css = CSS(string=css_content, font_config=font_config)
pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
```

**WeasyPrint Advantages**:
- Native HTML/CSS rendering
- Excellent typography control
- Unicode support
- Custom fonts embedding
- CSS Paged Media support (@page, @top-center, etc.)

**Limitations**:
- No JavaScript support
- Limited form field support
- Requires careful HTML structure for accessibility

#### Alternative Libraries
- **ReportLab**: Low-level PDF generation, complete control
- **xhtml2pdf (pisa)**: Simple HTML to PDF
- **PDFKit**: wkhtmltopdf wrapper
- **Borb**: Modern Python PDF library with accessibility features

### 1.2 PDF Structure Elements

**Required PDF Structure Tree**:
```
/Document
  /Part (optional sections)
    /H1, /H2, /H3 (headings)
    /P (paragraphs)
    /L (lists)
      /LI (list items)
        /Lbl (label)
        /LBody (body)
    /Table
      /TR (table rows)
        /TH (headers)
        /TD (data cells)
    /Figure (images)
    /TOC (table of contents)
```

### 1.3 PDF Metadata Standards

```python
metadata = {
    'title': 'Incident Management SOP',
    'author': 'REEMA Documentation System',
    'subject': 'IT Process Documentation',
    'keywords': 'ITIL, Incident Management, SOP, IT Operations',
    'creator': 'REEMA Multi-Agent System',
    'producer': 'WeasyPrint with PDF/UA',
    'lang': 'en-US',
    'trapped': False,
    'marked': True  # CRITICAL for accessibility
}
```

### 1.4 Page Layout Specifications

**Standard Page Dimensions**:
- Letter: 8.5 × 11 inches (216 × 279 mm)
- A4: 210 × 297 mm
- Legal: 8.5 × 14 inches

**Margin Guidelines**:
```css
@page {
    size: letter;
    margin: 1in 1in 1in 1in; /* top right bottom left */

    @top-center {
        content: string(document-title);
        font-size: 10pt;
        color: #666;
    }

    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
    }
}
```

**Optimal Margins**:
- Top: 1 inch (2.54 cm)
- Bottom: 1 inch (2.54 cm)
- Left: 1 inch (2.54 cm)
- Right: 1 inch (2.54 cm)
- Gutter (for binding): 0.25-0.5 inches additional on binding side

---

## 2. PDF/UA (UNIVERSAL ACCESSIBILITY) - ISO 14289

### 2.1 PDF/UA-1 Requirements

**Critical Requirements**:
1. **Tagged PDF**: All content must be tagged
2. **Logical Reading Order**: Content flows correctly
3. **Alternative Text**: All non-text content described
4. **Unicode Mapping**: All characters map to Unicode
5. **Language Specification**: Document language declared
6. **Metadata**: Title in document properties
7. **Security**: No restrictions on assistive technology

### 2.2 PDF/UA Metadata

```xml
<rdf:Description rdf:about=""
    xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/">
    <pdfuaid:part>1</pdfuaid:part>
</rdf:Description>
```

### 2.3 PDF/UA Validation Checklist

- [ ] Document is tagged
- [ ] Tags follow logical structure
- [ ] All images have alt text or marked as artifact
- [ ] All text is real text (not images of text)
- [ ] Language is set at document and span level if needed
- [ ] Title is set in document properties
- [ ] Bookmarks reflect document structure
- [ ] Color is not the only means of conveying information
- [ ] Contrast ratios meet requirements
- [ ] Tables have proper headers
- [ ] Forms are accessible (if present)
- [ ] Reading order is correct
- [ ] No content is hidden from assistive technology

### 2.4 PDF Tags for Structure

**Essential Tags**:
```
<Document>           Root element
<Part>               Major sections
<Art>                Article content
<Sect>               Generic section
<Div>                Division/group
<BlockQuote>         Block quotation
<Caption>            Caption for figure/table
<TOC>                Table of contents
<TOCI>               TOC item
<Index>              Index section
<P>                  Paragraph
<H1> through <H6>    Headings
<L>                  List
<LI>                 List item
<Lbl>                List item label
<LBody>              List item body
<Table>              Table
<TR>                 Table row
<TH>                 Table header cell
<TD>                 Table data cell
<Span>               Inline structure
<Quote>              Inline quotation
<Note>               Note/footnote
<Reference>          Reference/citation
<BibEntry>           Bibliography entry
<Code>               Code snippet
<Link>               Hyperlink
<Annot>              Annotation
<Figure>             Figure/image
<Formula>            Mathematical formula
<Form>               Form element
<Artifact>           Decorative/layout only
```

---

## 3. WCAG 2.1 LEVEL AA COMPLIANCE

### 3.1 Four Principles (POUR)

#### Perceivable
**1.1 Text Alternatives**: Provide text alternatives for non-text content
**1.2 Time-based Media**: Provide alternatives for time-based media (audio/video)
**1.3 Adaptable**: Content can be presented in different ways
**1.4 Distinguishable**: Make it easier to see and hear content

#### Operable
**2.1 Keyboard Accessible**: All functionality available from keyboard
**2.2 Enough Time**: Provide users enough time to read and use content
**2.3 Seizures**: Do not design content that causes seizures
**2.4 Navigable**: Provide ways to help users navigate and find content
**2.5 Input Modalities**: Make it easier to operate functionality through various inputs

#### Understandable
**3.1 Readable**: Make text content readable and understandable
**3.2 Predictable**: Make pages appear and operate in predictable ways
**3.3 Input Assistance**: Help users avoid and correct mistakes

#### Robust
**4.1 Compatible**: Maximize compatibility with current and future tools

### 3.2 WCAG 2.1 AA Success Criteria for Documents

#### Level A Criteria (Must Pass)
- **1.1.1** Non-text Content (Alt text required)
- **1.3.1** Info and Relationships (Proper semantic structure)
- **1.3.2** Meaningful Sequence (Logical reading order)
- **1.3.3** Sensory Characteristics (Don't rely solely on shape/size/location)
- **1.4.1** Use of Color (Color not only means of conveying info)
- **1.4.2** Audio Control (Pause/stop/control audio)
- **2.1.1** Keyboard (All functionality via keyboard)
- **2.1.2** No Keyboard Trap (Can navigate away via keyboard)
- **2.2.1** Timing Adjustable (Extend/disable time limits)
- **2.2.2** Pause, Stop, Hide (Control moving/blinking/scrolling)
- **2.3.1** Three Flashes (No more than 3 flashes per second)
- **2.4.1** Bypass Blocks (Skip navigation mechanism)
- **2.4.2** Page Titled (Descriptive page titles)
- **2.4.3** Focus Order (Logical focus order)
- **2.4.4** Link Purpose (Context) (Link text describes purpose)
- **3.1.1** Language of Page (Language declared)
- **3.2.1** On Focus (No context change on focus)
- **3.2.2** On Input (No unexpected context change on input)
- **3.3.1** Error Identification (Errors identified and described)
- **3.3.2** Labels or Instructions (Provide labels for inputs)
- **4.1.1** Parsing (Well-formed markup)
- **4.1.2** Name, Role, Value (UI components accessible)

#### Level AA Criteria (Must Pass)
- **1.2.4** Captions (Live) (Live audio captions)
- **1.2.5** Audio Description (Prerecorded) (Audio description for video)
- **1.4.3** Contrast (Minimum) (4.5:1 for normal text, 3:1 for large)
- **1.4.4** Resize Text (Text can be resized 200%)
- **1.4.5** Images of Text (Use real text, not images)
- **1.4.10** Reflow (Content reflows at 320px width)
- **1.4.11** Non-text Contrast (3:1 for UI components and graphics)
- **1.4.12** Text Spacing (Adjustable spacing doesn't break layout)
- **1.4.13** Content on Hover/Focus (Hoverable, dismissible, persistent)
- **2.4.5** Multiple Ways (Multiple ways to locate pages)
- **2.4.6** Headings and Labels (Descriptive headings/labels)
- **2.4.7** Focus Visible (Keyboard focus indicator visible)
- **3.1.2** Language of Parts (Language changes indicated)
- **3.2.3** Consistent Navigation (Navigation consistent)
- **3.2.4** Consistent Identification (Components identified consistently)
- **3.3.3** Error Suggestion (Provide error correction suggestions)
- **3.3.4** Error Prevention (Legal/Financial/Data) (Reversible or confirmed)
- **4.1.3** Status Messages (Status messages accessible to AT)

### 3.3 Implementing WCAG in Documents

#### Color Contrast Calculator
```python
def calculate_contrast_ratio(foreground_rgb, background_rgb):
    """
    Calculate WCAG contrast ratio between two colors.
    Returns ratio (e.g., 4.5 for 4.5:1)
    """
    def relative_luminance(rgb):
        r, g, b = [x / 255.0 for x in rgb]
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1 = relative_luminance(foreground_rgb)
    l2 = relative_luminance(background_rgb)

    lighter = max(l1, l2)
    darker = min(l1, l2)

    return (lighter + 0.05) / (darker + 0.05)

# Example usage
black = (0, 0, 0)
white = (255, 255, 255)
ratio = calculate_contrast_ratio(black, white)  # Returns 21.0 (excellent!)

# WCAG Requirements:
# Normal text (< 18pt): 4.5:1 minimum (AA), 7:1 enhanced (AAA)
# Large text (>= 18pt or bold >= 14pt): 3:1 minimum (AA), 4.5:1 enhanced (AAA)
# UI components and graphics: 3:1 minimum (AA)
```

#### Approved Color Combinations (AA Compliant)
```css
/* Black on White - 21:1 ratio */
.text-black-on-white { color: #000000; background: #FFFFFF; }

/* Dark Gray on White - 12.6:1 ratio */
.text-dark-gray { color: #595959; background: #FFFFFF; }

/* White on Dark Blue - 8.6:1 ratio */
.text-white-dark-blue { color: #FFFFFF; background: #1F3A93; }

/* Dark Blue on Light Blue - 7.2:1 ratio */
.text-dark-blue { color: #003A70; background: #E6F2FF; }

/* Green on White - 4.5:1 ratio (minimum for AA) */
.text-green { color: #4C7A34; background: #FFFFFF; }

/* FAILING EXAMPLES (DO NOT USE) */
/* Light gray on white - 2.5:1 - FAILS AA */
.text-fail { color: #B0B0B0; background: #FFFFFF; }

/* Yellow on white - 1.4:1 - FAILS AA */
.text-fail-2 { color: #FFFF00; background: #FFFFFF; }
```

---

## 4. SECTION 508 COMPLIANCE

### 4.1 Section 508 Standards (Revised 2017)

**Applicable Standards for Documents**:
- **501.1** Scope (WCAG 2.0 Level AA incorporated)
- **602** Support Documentation (Accessible documentation)
- **603** Support Services (Accessible support)

**Key Technical Standards**:
- **602.3** Information, Documentation, and Support (Accessible formats)

### 4.2 Section 508 Document Checklist

- [ ] Complies with WCAG 2.0 Level AA
- [ ] Alternative formats available upon request
- [ ] Support documentation is accessible
- [ ] Content is perceivable, operable, understandable, robust
- [ ] Passes automated testing (axe, WAVE, PAC)
- [ ] Passes manual testing (screen reader, keyboard only)

---

## 5. ADA (AMERICANS WITH DISABILITIES ACT) REQUIREMENTS

### 5.1 ADA Title II and Title III

**Title II** (State/Local Government): All digital content must be accessible
**Title III** (Public Accommodations): Private sector accessibility

### 5.2 ADA Compliance for Documents

**Essential Requirements**:
1. Equal access to information
2. Reasonable accommodations
3. Effective communication
4. No discrimination based on disability

**Practical Implementation**:
- Follow WCAG 2.1 AA standards
- Provide accessible PDF/DOCX formats
- Include alt text for all images
- Ensure keyboard navigation
- Maintain logical reading order
- Use semantic HTML/structure
- Test with assistive technology

---

## 6. EU ACCESSIBILITY ACT COMPLIANCE

### 6.1 European Accessibility Act (EAA)

**Effective Date**: June 2025
**Scope**: Products and services in EU

**Document Requirements**:
- EN 301 549 compliance (European standard)
- WCAG 2.1 Level AA alignment
- Accessibility statement
- Conformance declaration

### 6.2 EN 301 549 Standard

**Chapter 10**: Non-Web Documents
- 10.1: General (WCAG 2.1 mapping)
- 10.2: Non-Web Documents (Specific requirements)
- 10.3: Non-Web Software (If applicable)
- 10.4: Documents (Additional requirements)

---

## 7. DOCX (MICROSOFT WORD) GENERATION

### 7.1 python-docx Library

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE

# Create document
doc = Document()

# Set core properties (metadata)
core_props = doc.core_properties
core_props.title = 'Incident Management SOP'
core_props.author = 'REEMA System'
core_props.subject = 'IT Process Documentation'
core_props.keywords = 'ITIL, Incident Management, SOP'
core_props.language = 'en-US'

# Add heading
heading = doc.add_heading('Incident Management', level=1)

# Add paragraph
para = doc.add_paragraph('This document describes...')
para.style = 'Body Text'

# Add table
table = doc.add_table(rows=3, cols=3)
table.style = 'Light Grid Accent 1'

# Header row
header_cells = table.rows[0].cells
header_cells[0].text = 'Role'
header_cells[1].text = 'Responsibility'
header_cells[2].text = 'Authority'

# Save
doc.save('output.docx')
```

### 7.2 DOCX Accessibility Features

```python
# Set alt text for images
from docx.oxml.shared import OxmlElement, qn

def add_alt_text(picture, alt_text):
    """Add alt text to inline picture"""
    pic = picture._element.find('.//pic:cNvPr',
                                 namespaces={'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'})
    if pic is not None:
        pic.set('descr', alt_text)
        pic.set('title', alt_text)

# Add image with alt text
para = doc.add_paragraph()
run = para.add_run()
picture = run.add_picture('chart.png', width=Inches(5))
add_alt_text(picture, 'Bar chart showing incident trends over 6 months')
```

### 7.3 DOCX Styles and Structure

```python
# Define custom styles
styles = doc.styles

# Heading 1 style
h1_style = styles['Heading 1']
h1_font = h1_style.font
h1_font.name = 'Calibri'
h1_font.size = Pt(16)
h1_font.bold = True
h1_font.color.rgb = RGBColor(0, 51, 102)  # Dark blue

# Body text style
body_style = styles['Normal']
body_font = body_style.font
body_font.name = 'Calibri'
body_font.size = Pt(11)
body_font.color.rgb = RGBColor(0, 0, 0)

# Paragraph spacing
body_para_format = body_style.paragraph_format
body_para_format.space_before = Pt(0)
body_para_format.space_after = Pt(8)
body_para_format.line_spacing = 1.15
```

### 7.4 DOCX Table Accessibility

```python
# Accessible table with header row
table = doc.add_table(rows=4, cols=3)
table.style = 'Light Grid Accent 1'

# Mark first row as header
header_row = table.rows[0]
for cell in header_row.cells:
    # Bold header text
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.bold = True

    # Set repeat header row property
    header_row._element.xpath('.//w:trPr')[0].append(
        OxmlElement('w:tblHeader')
    )
```

---

## 8. MARKDOWN BEST PRACTICES

### 8.1 Markdown Flavors

**CommonMark**: Standard specification
**GitHub Flavored Markdown (GFM)**: GitHub's extension
**Python-Markdown**: Python implementation with extensions
**kramdown**: Ruby implementation
**MultiMarkdown**: Extended features

### 8.2 Accessible Markdown Structure

```markdown
# Document Title (Only one H1 per document)

## Section 1 (H2 - main sections)

### Subsection 1.1 (H3 - subsections)

Regular paragraph text. Never skip heading levels (don't jump from H2 to H4).

**Bold text for emphasis** (use for important concepts)
*Italic text for emphasis* (use for definitions, foreign words)

- Unordered list item 1
- Unordered list item 2
  - Nested item 2.1
  - Nested item 2.2
- Unordered list item 3

1. Ordered list item 1
2. Ordered list item 2
3. Ordered list item 3

[Link text describes destination](https://example.com "Optional tooltip")

![Alternative text describing the image](image.png "Optional title")

> Blockquote for quotations or important notes

`inline code` for technical terms

```python
# Code block with language specification
def function_name():
    return "code"
```

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |

---

Horizontal rule for section breaks
```

### 8.3 Markdown Accessibility Tips

**DO**:
- Use proper heading hierarchy (H1 > H2 > H3, no skipping)
- Write descriptive link text ("Download the incident report" not "click here")
- Include alt text for all images
- Use tables only for tabular data, not layout
- Specify language in code blocks
- Keep lines under 80-100 characters for readability

**DON'T**:
- Use images of text
- Rely on color alone to convey meaning
- Create fake headings with bold text
- Use empty headings or links
- Skip heading levels
- Use ASCII art (inaccessible to screen readers)

### 8.4 Markdown Extensions for Documents

```python
import markdown
from markdown.extensions.toc import TocExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.codehilite import CodeHiliteExtension

md = markdown.Markdown(extensions=[
    'toc',           # Table of contents
    'tables',        # GFM tables
    'fenced_code',   # Code blocks
    'codehilite',    # Syntax highlighting
    'attr_list',     # Add attributes to elements
    'def_list',      # Definition lists
    'footnotes',     # Footnotes
    'meta',          # Metadata
    'sane_lists',    # Sane list behavior
])

html = md.convert(markdown_text)
```

---

## 9. HTML5 SEMANTIC MARKUP

### 9.1 Semantic HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Incident Management SOP</title>
    <meta name="description" content="Standard Operating Procedure for ITIL Incident Management">
    <meta name="author" content="REEMA Documentation System">
    <meta name="keywords" content="ITIL, Incident Management, SOP, IT Operations">
</head>
<body>
    <header role="banner">
        <h1>Incident Management SOP</h1>
        <nav role="navigation" aria-label="Table of Contents">
            <ul>
                <li><a href="#section1">Introduction</a></li>
                <li><a href="#section2">Process Flow</a></li>
                <li><a href="#section3">Roles and Responsibilities</a></li>
            </ul>
        </nav>
    </header>

    <main role="main">
        <article>
            <section id="section1">
                <h2>Introduction</h2>
                <p>This document describes...</p>
            </section>

            <section id="section2">
                <h2>Process Flow</h2>
                <figure>
                    <img src="flowchart.png" alt="Incident management process flowchart showing 5 stages: Detection, Logging, Categorization, Resolution, and Closure">
                    <figcaption>Figure 1: Incident Management Process Flow</figcaption>
                </figure>
            </section>

            <section id="section3">
                <h2>Roles and Responsibilities</h2>
                <table>
                    <caption>RACI Matrix for Incident Management</caption>
                    <thead>
                        <tr>
                            <th scope="col">Activity</th>
                            <th scope="col">Service Desk</th>
                            <th scope="col">Incident Manager</th>
                            <th scope="col">Technical Team</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <th scope="row">Incident Logging</th>
                            <td>R/A</td>
                            <td>C</td>
                            <td>I</td>
                        </tr>
                    </tbody>
                </table>
            </section>
        </article>
    </main>

    <aside role="complementary" aria-label="Related Information">
        <h2>Related Documents</h2>
        <ul>
            <li><a href="problem-management.html">Problem Management SOP</a></li>
            <li><a href="change-management.html">Change Management SOP</a></li>
        </ul>
    </aside>

    <footer role="contentinfo">
        <p>© 2024 REEMA Documentation System</p>
        <p>Document Version: 1.0 | Last Updated: <time datetime="2024-01-15">January 15, 2024</time></p>
    </footer>
</body>
</html>
```

### 9.2 ARIA Landmarks and Roles

```html
<!-- Use semantic HTML5 elements with implicit roles -->
<header role="banner">         <!-- Page header -->
<nav role="navigation">        <!-- Navigation -->
<main role="main">             <!-- Main content -->
<article>                      <!-- Self-contained content -->
<section>                      <!-- Thematic grouping -->
<aside role="complementary">   <!-- Related content -->
<footer role="contentinfo">    <!-- Page footer -->
<form role="form">             <!-- Form -->
<search role="search">         <!-- Search -->

<!-- ARIA labels for clarity -->
<nav aria-label="Main Navigation">
<nav aria-label="Table of Contents">
<button aria-label="Close dialog">X</button>

<!-- ARIA described by -->
<input type="text" aria-describedby="password-requirements">
<p id="password-requirements">Password must be 8-16 characters</p>

<!-- ARIA live regions for dynamic content -->
<div role="alert" aria-live="assertive">Error: Required field missing</div>
<div role="status" aria-live="polite">Document saved successfully</div>
```

---

## 10. CSS FOR DOCUMENT STYLING

### 10.1 Print Stylesheets

```css
/* Print-specific styles */
@media print {
    /* Page setup */
    @page {
        size: letter portrait;
        margin: 1in;

        @top-center {
            content: string(document-title);
            font-size: 10pt;
            color: #666;
        }

        @bottom-center {
            content: "Page " counter(page) " of " counter(pages);
            font-size: 10pt;
        }
    }

    /* First page (cover) */
    @page :first {
        margin: 0;
        @top-center { content: none; }
        @bottom-center { content: none; }
    }

    /* Avoid page breaks */
    h1, h2, h3, h4, h5, h6 {
        page-break-after: avoid;
        break-after: avoid;
    }

    table, figure, img {
        page-break-inside: avoid;
        break-inside: avoid;
    }

    /* Orphans and widows */
    p {
        orphans: 3;  /* Minimum lines at bottom of page */
        widows: 3;   /* Minimum lines at top of page */
    }

    /* Remove interactive elements */
    nav, aside, footer {
        display: none;
    }

    /* Show link URLs */
    a[href]:after {
        content: " (" attr(href) ")";
        font-size: 0.8em;
        color: #666;
    }

    /* Optimize colors for print */
    body {
        color: #000;
        background: #fff;
    }
}
```

### 10.2 Accessible Typography CSS

```css
/* Base typography */
:root {
    --font-base: 'Calibri', 'Arial', 'Helvetica', sans-serif;
    --font-mono: 'Courier New', 'Courier', monospace;
    --font-size-base: 11pt;
    --line-height-base: 1.5;
    --color-text: #000000;
    --color-background: #FFFFFF;
    --color-heading: #003366;
    --color-link: #0066CC;
}

body {
    font-family: var(--font-base);
    font-size: var(--font-size-base);
    line-height: var(--line-height-base);
    color: var(--color-text);
    background: var(--color-background);
    max-width: 8.5in;
    margin: 0 auto;
    padding: 1in;
}

/* Heading hierarchy */
h1 { font-size: 24pt; margin-top: 0; margin-bottom: 16pt; color: var(--color-heading); }
h2 { font-size: 18pt; margin-top: 24pt; margin-bottom: 12pt; color: var(--color-heading); }
h3 { font-size: 14pt; margin-top: 18pt; margin-bottom: 10pt; color: var(--color-heading); }
h4 { font-size: 12pt; margin-top: 14pt; margin-bottom: 8pt; color: var(--color-heading); }
h5 { font-size: 11pt; margin-top: 12pt; margin-bottom: 6pt; color: var(--color-heading); }
h6 { font-size: 11pt; margin-top: 10pt; margin-bottom: 6pt; color: var(--color-heading); }

/* Paragraph spacing */
p {
    margin-top: 0;
    margin-bottom: 12pt;
}

/* Lists */
ul, ol {
    margin-top: 0;
    margin-bottom: 12pt;
    padding-left: 1.5em;
}

li {
    margin-bottom: 6pt;
}

/* Links */
a {
    color: var(--color-link);
    text-decoration: underline;
}

a:hover, a:focus {
    text-decoration: none;
    outline: 2px solid var(--color-link);
    outline-offset: 2px;
}

/* Code */
code {
    font-family: var(--font-mono);
    font-size: 0.9em;
    background: #F5F5F5;
    padding: 2px 4px;
    border-radius: 3px;
}

pre {
    font-family: var(--font-mono);
    font-size: 0.9em;
    background: #F5F5F5;
    padding: 12pt;
    border-left: 4px solid #CCC;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12pt 0;
}

th, td {
    padding: 8pt;
    text-align: left;
    border: 1px solid #CCC;
}

th {
    background: #E6F2FF;
    font-weight: bold;
    color: var(--color-heading);
}

/* Focus indicators */
*:focus {
    outline: 2px solid #0066CC;
    outline-offset: 2px;
}

/* Skip to main content link */
.skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: #000;
    color: #FFF;
    padding: 8px;
    text-decoration: none;
}

.skip-link:focus {
    top: 0;
}
```

---

## 11. COLOR CONTRAST AND ACCESSIBILITY

### 11.1 WCAG Color Contrast Requirements

**Level AA Requirements**:
- **Normal text** (<18pt or <14pt bold): **4.5:1** minimum
- **Large text** (≥18pt or ≥14pt bold): **3:1** minimum
- **UI components and graphics**: **3:1** minimum

**Level AAA Requirements**:
- **Normal text**: **7:1** minimum
- **Large text**: **4.5:1** minimum

### 11.2 Approved Color Palettes

```css
/* Primary Colors (AA Compliant) */
:root {
    /* Dark on Light */
    --text-primary: #000000;        /* Black on white: 21:1 */
    --text-secondary: #333333;      /* Dark gray on white: 12.6:1 */
    --text-tertiary: #666666;       /* Medium gray on white: 5.7:1 */

    /* Colored text on white */
    --text-blue: #003A70;           /* Dark blue: 10.4:1 */
    --text-green: #2B5A2E;          /* Dark green: 7.9:1 */
    --text-red: #8B0000;            /* Dark red: 9.5:1 */

    /* Backgrounds */
    --bg-white: #FFFFFF;
    --bg-light-gray: #F5F5F5;       /* Subtle background: 1.1:1 */
    --bg-light-blue: #E6F2FF;       /* Light blue background */

    /* UI Components */
    --border-gray: #CCCCCC;         /* 3:1 contrast */
    --link-blue: #0066CC;           /* 4.5:1 on white */
    --link-hover: #003D7A;          /* 8.7:1 on white */
}
```

### 11.3 Color Usage Guidelines

**DO**:
- Test all color combinations with contrast checker
- Use color AND another indicator (underline, icon, bold)
- Provide text labels in addition to color coding
- Use patterns or textures in charts/graphs
- Ensure focus indicators have 3:1 contrast

**DON'T**:
- Use color as the only means of conveying information
- Use red-green combinations (colorblind issue)
- Use low contrast colors (#999 on #FFF = 2.8:1 FAILS)
- Rely on subtle color differences
- Use pure colors for text (adjust brightness)

---

## 12. ALT TEXT BEST PRACTICES

### 12.1 Alt Text Writing Guidelines

**Informative Images**:
```html
<img src="incident-flowchart.png"
     alt="Flowchart showing incident management process with 5 stages: Detection, Logging, Categorization, Resolution, and Closure. Arrows connect each stage sequentially.">
```

**Decorative Images**:
```html
<img src="decorative-line.png" alt="" role="presentation">
```

**Functional Images (buttons/links)**:
```html
<a href="download.pdf">
    <img src="pdf-icon.png" alt="Download Incident Management SOP (PDF)">
</a>
```

**Complex Images (charts/diagrams)**:
```html
<figure>
    <img src="trend-chart.png"
         alt="Bar chart showing monthly incident volumes for 2024"
         longdesc="#chart-description">
    <figcaption id="chart-description">
        <details>
            <summary>Detailed chart description</summary>
            <p>The bar chart displays incident volumes from January to December 2024.
            January: 145 incidents, February: 132 incidents, March: 168 incidents...
            The trend shows a 15% decrease overall with peak in July (201 incidents)
            and lowest in December (98 incidents).</p>
        </details>
    </figcaption>
</figure>
```

### 12.2 Alt Text Decision Tree

1. **Is the image decorative?** → `alt=""` (empty alt)
2. **Does the image contain text?** → Include the text in alt
3. **Is the image a link or button?** → Describe the action/destination
4. **Is the image complex (chart/diagram)?** → Short alt + long description
5. **Is the image informative?** → Describe content concisely

### 12.3 Alt Text Quality Standards

**Good Alt Text**:
- Concise (typically <150 characters)
- Describes content, not appearance
- Provides equivalent information
- Considers context
- No "image of" or "picture of" prefix
- Includes relevant text from image

**Bad Alt Text**:
- "image123.png" (filename)
- "Click here" (not descriptive)
- "Picture of a chart" (too vague)
- Excessively long descriptions (>200 chars)
- Redundant with surrounding text

---

## 13. TABLE ACCESSIBILITY

### 13.1 Simple Tables

```html
<table>
    <caption>Incident Priority Matrix</caption>
    <thead>
        <tr>
            <th scope="col">Impact</th>
            <th scope="col">Urgency</th>
            <th scope="col">Priority</th>
            <th scope="col">Response Time</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <th scope="row">High</th>
            <td>High</td>
            <td>P1 - Critical</td>
            <td>15 minutes</td>
        </tr>
        <tr>
            <th scope="row">High</th>
            <td>Medium</td>
            <td>P2 - High</td>
            <td>1 hour</td>
        </tr>
        <tr>
            <th scope="row">Medium</th>
            <td>Medium</td>
            <td>P3 - Medium</td>
            <td>4 hours</td>
        </tr>
    </tbody>
</table>
```

### 13.2 Complex Tables

```html
<table>
    <caption>RACI Matrix for Incident Management Process</caption>
    <thead>
        <tr>
            <th scope="col" id="activity">Activity</th>
            <th scope="col" id="sd">Service Desk</th>
            <th scope="col" id="im">Incident Manager</th>
            <th scope="col" id="tech">Technical Team</th>
            <th scope="col" id="pm">Problem Manager</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <th scope="row" id="logging" headers="activity">Incident Logging</th>
            <td headers="logging sd">R/A</td>
            <td headers="logging im">C</td>
            <td headers="logging tech">I</td>
            <td headers="logging pm">I</td>
        </tr>
        <tr>
            <th scope="row" id="categorize" headers="activity">Categorization</th>
            <td headers="categorize sd">R</td>
            <td headers="categorize im">A/C</td>
            <td headers="categorize tech">I</td>
            <td headers="categorize pm">I</td>
        </tr>
    </tbody>
</table>
```

### 13.3 Table Accessibility Checklist

- [ ] Use `<caption>` for table title
- [ ] Use `<thead>`, `<tbody>`, `<tfoot>` for structure
- [ ] Use `<th>` for header cells (not `<td>`)
- [ ] Include `scope` attribute on headers
- [ ] Use `headers` attribute for complex tables
- [ ] Ensure table is not used for layout
- [ ] Keep tables simple when possible
- [ ] Provide summary for complex tables
- [ ] Ensure adequate spacing between cells
- [ ] Test with screen reader

---

## 14. DOCUMENT CONVERSION WORKFLOW

### 14.1 Markdown → HTML → PDF Pipeline

```python
import markdown
from weasyprint import HTML, CSS
from jinja2 import Template

# Step 1: Convert Markdown to HTML
md = markdown.Markdown(extensions=['toc', 'tables', 'fenced_code'])
html_body = md.convert(markdown_content)

# Step 2: Apply HTML template
template = Template('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>{{ css }}</style>
</head>
<body>
    <header>
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>
    </header>
    <main>
        {{ content | safe }}
    </main>
    <footer>
        <p>{{ footer_text }}</p>
    </footer>
</body>
</html>
''')

html_full = template.render(
    title='Incident Management SOP',
    subtitle='ITIL Process Documentation',
    content=html_body,
    css=css_content,
    footer_text='Generated by REEMA System'
)

# Step 3: Generate PDF
HTML(string=html_full).write_pdf('output.pdf')
```

### 14.2 Cross-Format Consistency Strategy

**Ensure consistency across formats**:
1. Use single source of truth (Markdown or structured data)
2. Apply consistent styling rules
3. Maintain heading hierarchy
4. Use same alt text across formats
5. Preserve semantic structure
6. Test all formats for accessibility
7. Validate metadata in all outputs

---

## 15. ACCESSIBILITY VALIDATION

### 15.1 Automated Testing Tools

**PDF Validators**:
- **PAC (PDF Accessibility Checker)**: Industry standard, free
- **Adobe Acrobat Pro Accessibility Checker**: Built-in tool
- **PAVE (PDF Accessibility Validation Engine)**: Command-line
- **CommonLook PDF Validator**: Professional tool

**HTML Validators**:
- **axe DevTools**: Browser extension, comprehensive
- **WAVE**: Web accessibility evaluation tool
- **Lighthouse**: Chrome DevTools audit
- **W3C Markup Validator**: HTML validation

**DOCX Validators**:
- **Microsoft Word Accessibility Checker**: Built-in
- **CommonLook Office**: Professional plugin

### 15.2 Manual Testing Procedures

**Keyboard Navigation Test**:
```
1. Unplug mouse
2. Use Tab key to navigate through document
3. Use Shift+Tab to navigate backward
4. Use Enter to activate links/buttons
5. Use arrow keys for scrolling/navigation
6. Verify all content is reachable
7. Check focus indicator visibility
```

**Screen Reader Test**:
```
1. Enable screen reader (NVDA/JAWS/VoiceOver)
2. Navigate through headings (H key)
3. Navigate through landmarks (D key)
4. Navigate through links (K key)
5. Navigate through tables (T key)
6. Listen to alt text for images
7. Verify reading order is logical
8. Check table headers are announced
```

**Color Contrast Test**:
```
1. Use Colour Contrast Analyser tool
2. Test all text against backgrounds
3. Test UI component contrast
4. Test graphics and icons
5. Verify 4.5:1 for normal text
6. Verify 3:1 for large text and UI
```

### 15.3 Validation Checklist

**Structure**:
- [ ] Proper heading hierarchy (no skipped levels)
- [ ] Semantic markup (proper tags for purpose)
- [ ] Logical reading order
- [ ] Language specified

**Content**:
- [ ] Alt text for all images
- [ ] Descriptive link text
- [ ] Data tables have headers
- [ ] Lists use proper markup
- [ ] Abbreviations defined on first use

**Visual**:
- [ ] Color contrast meets requirements
- [ ] Text is resizable
- [ ] No images of text
- [ ] Focus indicators visible

**Metadata**:
- [ ] Title in document properties
- [ ] Author/creator specified
- [ ] Language declared
- [ ] Keywords included

**PDF Specific**:
- [ ] Tagged PDF
- [ ] Bookmarks for navigation
- [ ] PDF/UA compliant
- [ ] No security restrictions on AT

**DOCX Specific**:
- [ ] Built-in styles used (not direct formatting)
- [ ] Alt text on images
- [ ] Table headers marked
- [ ] Passes Word Accessibility Checker

---

## 16. FONT MANAGEMENT

### 16.1 Font Selection for Documents

**Recommended Fonts**:
- **Sans-serif**: Calibri, Arial, Helvetica, Open Sans, Roboto
- **Serif**: Times New Roman, Georgia, Cambria
- **Monospace**: Courier New, Consolas, Monaco

**Font Size Guidelines**:
- Body text: 11-12pt
- Small text: 9-10pt (captions, footnotes)
- Large headings: 16-24pt
- Minimum readable: 9pt

### 16.2 Font Embedding in PDF

```python
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

font_config = FontConfiguration()

css = CSS(string='''
    @font-face {
        font-family: 'CustomFont';
        src: url('fonts/CustomFont.ttf');
    }

    body {
        font-family: 'CustomFont', 'Arial', sans-serif;
    }
''', font_config=font_config)

HTML(string=html_content).write_pdf(
    'output.pdf',
    stylesheets=[css],
    font_config=font_config
)
```

---

## 17. QUALITY VALIDATION FRAMEWORK

### 17.1 Document Quality Metrics

```python
class DocumentQualityValidator:
    """Validate generated documents for quality and accessibility"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.score = 100

    def validate_pdf(self, pdf_path):
        """Validate PDF for accessibility"""
        # Check if tagged
        # Check metadata
        # Validate structure
        # Check contrast ratios
        # Verify alt text
        pass

    def validate_html(self, html_content):
        """Validate HTML for WCAG compliance"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check heading hierarchy
        self._check_heading_hierarchy(soup)

        # Check alt text
        self._check_alt_text(soup)

        # Check language
        if not soup.html.get('lang'):
            self.errors.append("Missing language declaration on <html>")
            self.score -= 10

        # Check page title
        if not soup.title or not soup.title.string:
            self.errors.append("Missing or empty <title>")
            self.score -= 10

        return self.score >= 85  # Quality threshold

    def _check_heading_hierarchy(self, soup):
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        levels = [int(h.name[1]) for h in headings]

        # Check for skipped levels
        for i in range(len(levels) - 1):
            if levels[i+1] - levels[i] > 1:
                self.warnings.append(f"Skipped heading level: {levels[i]} to {levels[i+1]}")
                self.score -= 5

        # Check for multiple H1s
        if levels.count(1) > 1:
            self.warnings.append("Multiple H1 headings found")
            self.score -= 5

    def _check_alt_text(self, soup):
        images = soup.find_all('img')
        for img in images:
            alt = img.get('alt')
            if alt is None:
                self.errors.append(f"Missing alt attribute on image: {img.get('src', 'unknown')}")
                self.score -= 10
            elif alt and (alt.lower().startswith('image of') or alt.lower().startswith('picture of')):
                self.warnings.append(f"Alt text starts with 'image of' or 'picture of': {alt}")
                self.score -= 2
```

---

## 18. PERFORMANCE OPTIMIZATION

### 18.1 File Size Optimization

**PDF Optimization**:
- Compress images (JPEG quality 85%)
- Subset fonts (include only used characters)
- Remove unnecessary metadata
- Optimize structure tree
- Use object streams

**Image Optimization**:
```python
from PIL import Image

def optimize_image(input_path, output_path, max_width=1200, quality=85):
    """Optimize image for documents"""
    img = Image.open(input_path)

    # Resize if too large
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Convert RGBA to RGB if needed
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background

    # Save with compression
    img.save(output_path, 'JPEG', quality=quality, optimize=True)
```

### 18.2 Generation Performance

**Optimization Strategies**:
- Cache template compilation
- Reuse font configurations
- Batch process multiple documents
- Use async operations for I/O
- Stream large content
- Profile bottlenecks

---

## 19. ERROR HANDLING AND LOGGING

### 19.1 Format Agent Error Handling

```python
import logging
from typing import Optional

logger = logging.getLogger('bee_format_agent')

class FormatGenerationError(Exception):
    """Base exception for format generation errors"""
    pass

class PDFGenerationError(FormatGenerationError):
    """PDF generation failed"""
    pass

class DOCXGenerationError(FormatGenerationError):
    """DOCX generation failed"""
    pass

class AccessibilityValidationError(FormatGenerationError):
    """Accessibility validation failed"""
    pass

def generate_pdf_safe(html_content: str, output_path: str) -> Optional[str]:
    """Generate PDF with error handling"""
    try:
        HTML(string=html_content).write_pdf(output_path)
        logger.info(f"PDF generated successfully: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise PDFGenerationError(f"Failed to generate PDF: {e}") from e
```

---

## 20. BEE AGENT OPERATIONAL GUIDELINES

### 20.1 Format Agent Workflow

1. **Receive Content** from Saad (Content Writer)
2. **Parse Structure** (headings, sections, tables, images)
3. **Apply Accessibility Rules** (alt text, semantic markup, ARIA)
4. **Generate HTML** (semantic, WCAG compliant)
5. **Apply CSS** (print-ready, accessible colors, typography)
6. **Generate PDF** (WeasyPrint, PDF/UA compliant)
7. **Generate DOCX** (python-docx, accessible structure)
8. **Generate Markdown** (clean, properly formatted)
9. **Validate All Formats** (accessibility, quality)
10. **Report Results** to Abdullah (Leader)

### 20.2 Quality Threshold

**Minimum Acceptance Score**: 85/100

**Deduction Rules**:
- Missing alt text: -10 points per image
- Skipped heading level: -5 points
- Color contrast failure: -10 points per violation
- Missing metadata: -10 points
- Invalid structure: -15 points
- Inaccessible table: -10 points

### 20.3 Communication Protocol

**Input from Content Agent**:
```json
{
    "content": "markdown content here",
    "metadata": {
        "title": "Incident Management SOP",
        "author": "REEMA System",
        "subject": "IT Process Documentation",
        "keywords": ["ITIL", "Incident Management"]
    },
    "images": [
        {"path": "flowchart.png", "alt": "Process flowchart..."}
    ]
}
```

**Output to Leader Agent**:
```json
{
    "status": "success",
    "formats": {
        "pdf": "output/incident_management.pdf",
        "docx": "output/incident_management.docx",
        "html": "output/incident_management.html",
        "markdown": "output/incident_management.md"
    },
    "quality_score": 95,
    "accessibility_passed": true,
    "validation_report": {
        "pdf_ua": "PASS",
        "wcag_aa": "PASS",
        "section_508": "PASS",
        "errors": [],
        "warnings": ["Minor: One image could use more descriptive alt text"]
    }
}
```

---

## 21. TOOLS AND LIBRARIES REFERENCE

### 21.1 Python Libraries

```python
# PDF Generation
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# DOCX Generation
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Markdown Processing
import markdown
from markdown.extensions.toc import TocExtension

# HTML Templating
from jinja2 import Template, Environment, FileSystemLoader

# HTML Parsing
from bs4 import BeautifulSoup

# Image Processing
from PIL import Image

# Validation
import pypdf
```

### 21.2 External Tools

**Desktop Tools**:
- Adobe Acrobat Pro (PDF editing/validation)
- PAC (PDF Accessibility Checker) - Free
- Microsoft Word (DOCX accessibility checker)
- Colour Contrast Analyser - Free

**Browser Extensions**:
- axe DevTools (Chrome/Firefox)
- WAVE (Chrome/Firefox)
- Lighthouse (Chrome)

**Screen Readers**:
- NVDA (Windows) - Free
- JAWS (Windows) - Paid
- VoiceOver (macOS/iOS) - Built-in
- TalkBack (Android) - Built-in

---

## 22. BEST PRACTICES SUMMARY

### 22.1 Universal Design Principles

1. **Equitable Use**: Same experience for all users
2. **Flexibility in Use**: Accommodates different preferences
3. **Simple and Intuitive**: Easy to understand
4. **Perceptible Information**: Communicates effectively
5. **Tolerance for Error**: Minimizes hazards
6. **Low Physical Effort**: Comfortable to use
7. **Size and Space**: Appropriate size and space

### 22.2 Document Generation Checklist

**Before Generation**:
- [ ] Content approved by review agent
- [ ] Metadata collected
- [ ] Images have alt text
- [ ] Structure is logical
- [ ] Templates are ready

**During Generation**:
- [ ] Apply semantic markup
- [ ] Embed accessibility features
- [ ] Use approved color palette
- [ ] Include navigation aids
- [ ] Set proper metadata

**After Generation**:
- [ ] Validate with automated tools
- [ ] Test with screen reader
- [ ] Test keyboard navigation
- [ ] Check color contrast
- [ ] Verify file size is reasonable
- [ ] Test cross-format consistency

### 22.3 Common Mistakes to Avoid

**DON'T**:
- Generate PDFs from images (not accessible)
- Skip heading levels (h1 → h3)
- Use empty alt text on informative images
- Rely on color alone
- Use tables for layout
- Embed security restrictions
- Create untagged PDFs
- Use complex nested tables
- Forget to set document language
- Skip metadata
- Use low contrast colors
- Create overly large files

---

## 23. REFERENCE STANDARDS

### 23.1 Standards Documentation

- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
- **PDF/UA-1**: ISO 14289-1:2014
- **Section 508**: https://www.section508.gov/
- **EN 301 549**: European accessibility standard
- **ARIA**: https://www.w3.org/WAI/ARIA/apg/

### 23.2 Learning Resources

- **WebAIM**: https://webaim.org/
- **A11Y Project**: https://www.a11yproject.com/
- **Deque University**: https://dequeuniversity.com/
- **W3C WAI**: https://www.w3.org/WAI/

---

## CONCLUSION

This knowledge base represents the complete domain expertise of the Bee Format Agent. All document generation must adhere to these standards to ensure:

1. **Accessibility**: WCAG 2.1 AA, PDF/UA, Section 508 compliance
2. **Quality**: Professional formatting, consistent styling
3. **Usability**: Logical structure, easy navigation
4. **Compatibility**: Works across all platforms and assistive technologies
5. **Performance**: Optimized file sizes, fast generation

**Success Criteria**: Documents score ≥85/100 on quality validation and pass all accessibility checks.

**Agent Motto**: "Born Accessible, Not Remediated"

---

*Document Version: 1.0*
*Last Updated: 2024-01-15*
*Maintained by: REEMA Multi-Agent Documentation System*

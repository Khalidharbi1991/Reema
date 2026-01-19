"""PDF Formatter - Converts content to PDF using WeasyPrint."""

from pathlib import Path
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import markdown2
from ..utils.logger import logger


class PDFFormatter:
    """Formats and converts content to PDF."""

    def __init__(self):
        self.name = "PDF Formatter"
        self.font_config = FontConfiguration()

    def _get_pdf_css(self) -> str:
        """Get CSS styling for PDF."""
        return """
        @page {
            size: A4;
            margin: 2.5cm;
            @top-center {
                content: "Standard Operating Procedure";
                font-size: 10pt;
                color: #666;
            }
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }

        body {
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }

        h1 {
            color: #2c3e50;
            font-size: 24pt;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 20pt;
            page-break-after: avoid;
        }

        h2 {
            color: #2c3e50;
            font-size: 18pt;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
            margin-top: 20pt;
            page-break-after: avoid;
        }

        h3 {
            color: #34495e;
            font-size: 14pt;
            margin-top: 15pt;
            page-break-after: avoid;
        }

        h4 {
            color: #34495e;
            font-size: 12pt;
            margin-top: 12pt;
            page-break-after: avoid;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            page-break-inside: avoid;
        }

        table, th, td {
            border: 1px solid #ddd;
        }

        th {
            background-color: #3498db;
            color: white;
            padding: 10px;
            text-align: left;
            font-weight: bold;
        }

        td {
            padding: 8px;
        }

        tr:nth-child(even) {
            background-color: #f9f9f9;
        }

        code {
            background-color: #f4f4f4;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
        }

        pre {
            background-color: #f4f4f4;
            padding: 12px;
            border-radius: 5px;
            overflow-x: auto;
            page-break-inside: avoid;
        }

        ul, ol {
            margin: 10px 0;
            padding-left: 25px;
        }

        li {
            margin: 5px 0;
        }

        .metadata {
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            page-break-inside: avoid;
        }

        .metadata p {
            margin: 5px 0;
        }

        .title-page {
            text-align: center;
            padding-top: 200px;
            page-break-after: always;
        }

        .title-page h1 {
            font-size: 32pt;
            margin-bottom: 50px;
            border: none;
        }

        blockquote {
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-left: 0;
            color: #555;
            font-style: italic;
        }

        .page-break {
            page-break-before: always;
        }
        """

    async def convert(
        self, content: str, output_path: Path, process_name: str
    ) -> Path:
        """
        Convert Markdown content to PDF.

        Args:
            content: Markdown content
            output_path: Output file path
            process_name: Process name

        Returns:
            Path to the generated PDF file
        """
        logger.info(f"Converting to PDF: {output_path}", agent=self.name)

        try:
            # Convert markdown to HTML
            html_content = markdown2.markdown(
                content,
                extras=[
                    "tables",
                    "fenced-code-blocks",
                    "header-ids",
                    "break-on-newline"
                ]
            )

            # Create full HTML document
            from datetime import datetime

            full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{process_name} - SOP</title>
</head>
<body>
    <div class="title-page">
        <h1>{process_name}</h1>
        <h2>Standard Operating Procedure</h2>
        <div class="metadata">
            <p><strong>Version:</strong> 1.0</p>
            <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
            <p><strong>Status:</strong> Draft</p>
        </div>
    </div>
    {html_content}
</body>
</html>
"""

            # Convert to PDF
            html = HTML(string=full_html)
            css = CSS(string=self._get_pdf_css(), font_config=self.font_config)

            html.write_pdf(
                str(output_path),
                stylesheets=[css],
                font_config=self.font_config
            )

            logger.info(f"PDF file created: {output_path}", agent=self.name)
            return output_path

        except Exception as e:
            logger.error(f"PDF conversion failed: {e}", agent=self.name)
            raise

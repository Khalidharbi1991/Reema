"""HTML Formatter - Converts Markdown to HTML."""

from pathlib import Path
import markdown2
from jinja2 import Template
from ..utils.logger import logger


class HTMLFormatter:
    """Formats and converts content to HTML."""

    def __init__(self):
        self.name = "HTML Formatter"
        self.template = self._get_html_template()

    def _get_html_template(self) -> str:
        """Get HTML template with professional styling."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 40px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #2c3e50;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
            margin-top: 30px;
        }
        h3 {
            color: #34495e;
            margin-top: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        table, th, td {
            border: 1px solid #ddd;
        }
        th {
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
        }
        td {
            padding: 10px;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        pre {
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }
        ul, ol {
            margin: 10px 0;
            padding-left: 30px;
        }
        li {
            margin: 5px 0;
        }
        .metadata {
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .metadata p {
            margin: 5px 0;
        }
        @media print {
            body {
                background-color: white;
            }
            .container {
                box-shadow: none;
                padding: 0;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="metadata">
            <p><strong>Document:</strong> {{ title }}</p>
            <p><strong>Generated:</strong> {{ date }}</p>
            <p><strong>Version:</strong> 1.0</p>
        </div>
        {{ content }}
    </div>
</body>
</html>
"""

    async def convert(
        self, content: str, output_path: Path, process_name: str
    ) -> Path:
        """
        Convert Markdown content to HTML.

        Args:
            content: Markdown content
            output_path: Output file path
            process_name: Process name

        Returns:
            Path to the generated HTML file
        """
        logger.info(f"Converting to HTML: {output_path}", agent=self.name)

        try:
            # Convert markdown to HTML
            html_content = markdown2.markdown(
                content,
                extras=[
                    "tables",
                    "fenced-code-blocks",
                    "header-ids",
                    "toc",
                    "break-on-newline"
                ]
            )

            # Apply template
            template = Template(self.template)
            from datetime import datetime

            html_output = template.render(
                title=f"{process_name} - Standard Operating Procedure",
                content=html_content,
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_output)

            logger.info(f"HTML file created: {output_path}", agent=self.name)
            return output_path

        except Exception as e:
            logger.error(f"HTML conversion failed: {e}", agent=self.name)
            raise

"""HTML Formatter - Converts Markdown to HTML."""

from pathlib import Path
import markdown2
from jinja2 import Template
from ..utils.logger import logger
from .safe_html import render_markdown
from markupsafe import Markup


class HTMLFormatter:
    """Formats and converts content to HTML."""

    def __init__(self):
        self.name = "HTML Formatter"
        self.template = self._get_html_template()

    def _get_html_template(self) -> str:
        """Get HTML template with professional styling."""
        from .theme import document_css
        return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>{{ title }}</title><style>" + document_css()
                + "</style></head><body>{{ content }}</body></html>")

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
            html_content = render_markdown(content)

            # Apply template
            template = Template(self.template, autoescape=True)
            from datetime import datetime

            html_output = template.render(
                title=f"{process_name} - Standard Operating Procedure",
                content=Markup(html_content),
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

"""PDF Formatter - Converts content to PDF using WeasyPrint."""

from pathlib import Path
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import markdown2
from html import escape
from .safe_html import render_markdown, deny_fetch
from ..utils.logger import logger


def png_resource(url, data):
    try:
        from weasyprint.urls import URLFetcherResponse
    except ImportError:  # Older supported WeasyPrint releases use the dict contract.
        return {'string': data, 'mime_type': 'image/png'}
    return URLFetcherResponse(url, data, {'Content-Type': 'image/png'})


class PDFFormatter:
    """Formats and converts content to PDF."""

    def __init__(self):
        self.name = "PDF Formatter"
        self.font_config = FontConfiguration()

    def _get_pdf_css(self) -> str:
        """Get CSS styling for PDF."""
        from .theme import document_css
        return document_css()

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
            resources = {}
            html_content = render_markdown(content, raster_resources=resources)
            process_name = escape(process_name)

            full_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>{process_name} SOP</title></head>
<body>{html_content}</body></html>"""

            # Convert to PDF
            def fetch(url, *args, **kwargs):
                if url in resources:
                    return png_resource(url, resources[url])
                return deny_fetch(url, *args, **kwargs)
            fetch._fail_on_errors = True
            html = HTML(string=full_html, url_fetcher=fetch)
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

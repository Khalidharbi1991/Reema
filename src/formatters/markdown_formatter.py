"""Markdown Formatter - Saves content as Markdown."""

from pathlib import Path
from ..utils.logger import logger


class MarkdownFormatter:
    """Formats and saves content as Markdown (.md)."""

    def __init__(self):
        self.name = "Markdown Formatter"

    async def convert(
        self, content: str, output_path: Path, process_name: str
    ) -> Path:
        """
        Convert content to Markdown format.

        Args:
            content: Markdown content
            output_path: Output file path
            process_name: Process name

        Returns:
            Path to the generated file
        """
        logger.info(f"Converting to Markdown: {output_path}", agent=self.name)

        try:
            # Markdown content is already in the correct format
            # Just ensure proper formatting and save
            formatted_content = self._format_markdown(content, process_name)

            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)

            logger.info(f"Markdown file created: {output_path}", agent=self.name)
            return output_path

        except Exception as e:
            logger.error(f"Markdown conversion failed: {e}", agent=self.name)
            raise

    def _format_markdown(self, content: str, process_name: str) -> str:
        """Format and clean markdown content."""
        # Ensure proper line breaks
        formatted = content.replace('\r\n', '\n')

        # Add a clean header if not present
        if not formatted.startswith('#'):
            formatted = f"# {process_name} - Standard Operating Procedure\n\n" + formatted

        return formatted

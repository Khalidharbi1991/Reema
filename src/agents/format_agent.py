"""Bee (Format & Export Agent) - Converts content to multiple output formats."""

import asyncio
from typing import Dict, List, Optional
from pathlib import Path
from ..utils.logger import logger
from ..utils.config import config_manager


class FormatAgent:
    """
    Bee (Format & Export Agent)

    Responsibilities:
    - Converts content to PDF, DOCX, Markdown, HTML
    - Applies professional formatting
    - Creates headers, footers, table of contents
    - Manages document structure and styling
    """

    def __init__(self):
        self.name = "Bee"
        self.output_dir = config_manager.system_config.output_dir

        # Import formatters
        self.formatters = {}
        self._initialize_formatters()

        logger.info("Format Agent initialized", agent=self.name)

    def _initialize_formatters(self):
        """Initialize all format converters."""
        try:
            from ..formatters.pdf_formatter import PDFFormatter
            from ..formatters.docx_formatter import DOCXFormatter
            from ..formatters.markdown_formatter import MarkdownFormatter
            from ..formatters.html_formatter import HTMLFormatter

            self.formatters = {
                "pdf": PDFFormatter(),
                "docx": DOCXFormatter(),
                "markdown": MarkdownFormatter(),
                "html": HTMLFormatter()
            }
            logger.info("All formatters initialized", agent=self.name)

        except ImportError as e:
            logger.warning(f"Some formatters could not be loaded: {e}", agent=self.name)

    async def convert_to_formats(
        self, content: str, formats: List[str], process_name: str = "document"
    ) -> Dict[str, str]:
        """
        Convert content to multiple formats.

        Args:
            content: Markdown content to convert
            formats: List of desired output formats
            process_name: Name of the process (for filename)

        Returns:
            Dictionary mapping format to output file path
        """
        logger.agent_start(
            self.name,
            f"Converting to formats: {', '.join(formats)}"
        )

        output_files = {}

        try:
            # Convert to each format
            conversion_tasks = []
            for fmt in formats:
                if fmt.lower() in self.formatters:
                    task = self._convert_to_format(
                        content, fmt.lower(), process_name
                    )
                    conversion_tasks.append((fmt, task))
                else:
                    logger.warning(f"Unsupported format: {fmt}", agent=self.name)

            # Execute conversions concurrently
            if conversion_tasks:
                results = await asyncio.gather(
                    *[task for _, task in conversion_tasks],
                    return_exceptions=True
                )

                for (fmt, _), result in zip(conversion_tasks, results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"Failed to convert to {fmt}: {result}",
                            agent=self.name
                        )
                    else:
                        output_files[fmt] = result
                        logger.info(
                            f"Successfully converted to {fmt}: {result}",
                            agent=self.name
                        )

            logger.agent_complete(
                self.name,
                f"Converted to {len(output_files)} formats"
            )
            return output_files

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def _convert_to_format(
        self, content: str, format_type: str, process_name: str
    ) -> str:
        """Convert content to a specific format."""
        formatter = self.formatters.get(format_type)
        if not formatter:
            raise ValueError(f"No formatter available for {format_type}")

        # Generate output filename
        output_file = self._generate_output_path(process_name, format_type)

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert using appropriate formatter
        result_path = await formatter.convert(content, output_file, process_name)

        return str(result_path)

    def _generate_output_path(self, process_name: str, format_type: str) -> Path:
        """Generate output file path."""
        # Sanitize process name for filename
        safe_name = process_name.replace(" ", "_").replace("/", "_")

        # Get format-specific extension
        extensions = {
            "pdf": ".pdf",
            "docx": ".docx",
            "markdown": ".md",
            "html": ".html"
        }

        extension = extensions.get(format_type, f".{format_type}")

        # Create path
        output_path = self.output_dir / format_type / f"{safe_name}_SOP{extension}"

        return output_path

    def get_supported_formats(self) -> List[str]:
        """Get list of supported output formats."""
        return list(self.formatters.keys())

"""Bee (Format & Export Agent) - Converts content to multiple output formats."""

import asyncio
from importlib import import_module
from typing import Dict, List, Optional
from pathlib import Path
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.validation import FORMATS, safe_filename, validate_formats, validate_output_files
from ..utils.export_quality import inspect_export
from ..utils.diagrams import extract_flows


class FormatAgent(BaseAgent):
    """
    Bee (Format & Export Agent)

    Responsibilities:
    - Converts content to PDF, DOCX, Markdown, HTML
    - Applies professional formatting
    - Creates headers, footers, table of contents
    - Manages document structure and styling
    """

    AGENT_NAME = "Agent 5"
    AGENT_ROLE = "Format & Export Agent"
    CONFIG_KEY = "format_agent"
    KNOWLEDGE_FILE = "bee_format_knowledge_ENHANCED.md"
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TEMPERATURE = 0.5

    def __init__(self, api_key: Optional[str] = None):
        # Bee doesn't need an API key — pass empty to skip Anthropic client
        super().__init__(api_key="")

        # Alias for backward compatibility
        self.format_knowledge = self.knowledge_base

        # Output directory
        self.output_dir = config_manager.system_config.output_dir

        # Import formatters
        self.formatters = {}
        self._initialize_formatters()
        self.last_export_checks = {}

    def _initialize_formatters(self):
        """Initialize all format converters."""
        self.unavailable_formats = {}
        for fmt, class_name in {
            "pdf": "PDFFormatter", "docx": "DOCXFormatter",
            "markdown": "MarkdownFormatter", "html": "HTMLFormatter",
        }.items():
            try:
                module = import_module(f"..formatters.{fmt}_formatter", __package__)
                self.formatters[fmt] = getattr(module, class_name)()
            except (ImportError, OSError) as error:
                self.unavailable_formats[fmt] = str(error)

    def validate_requested_formats(self, formats):
        formats = validate_formats(formats)
        unavailable = set(formats) - self.formatters.keys()
        if unavailable:
            raise ValueError(f"Requested formatters unavailable: {', '.join(sorted(unavailable))}. Install their dependencies or choose another format.")
        return formats

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
        formats = self.validate_requested_formats(formats)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Cannot export empty content")
        extract_flows(content)
        self.last_export_checks = {}
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

            validate_output_files(output_files, formats)
            for fmt, path in output_files.items():
                self.last_export_checks[fmt] = inspect_export(fmt, path, content)
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
        if output_file.exists():
            raise FileExistsError(f"Output already exists: {output_file}; use a new run directory")

        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert using appropriate formatter
        result_path = await formatter.convert(content, output_file, process_name)

        return str(result_path)

    def _generate_output_path(self, process_name: str, format_type: str) -> Path:
        """Generate output file path."""
        # Sanitize process name for filename
        safe_name = safe_filename(process_name)

        # Get format-specific extension
        validate_formats([format_type])
        extension = FORMATS[format_type]

        # Create path
        output_path = self.output_dir / format_type / f"{safe_name}_SOP{extension}"

        return output_path

    def get_supported_formats(self) -> List[str]:
        """Get list of supported output formats."""
        return list(self.formatters.keys())

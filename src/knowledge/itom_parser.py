"""ITOM PDF Parser - Extracts knowledge from ITOM.pdf."""

from pathlib import Path
from typing import Dict, List
import PyPDF2
import pdfplumber
from ..utils.logger import logger
from ..utils.config import config_manager


class ITOMParser:
    """Parses ITOM.pdf and extracts IT operations knowledge."""

    def __init__(self):
        self.name = "ITOM Parser"
        self.pdf_path = config_manager.system_config.project_root / "ITOM.pdf"
        self.knowledge_cache = {}

    def extract_knowledge(self) -> Dict[str, str]:
        """
        Extract knowledge from ITOM.pdf.

        Returns:
            Dictionary of section titles to content
        """
        if not self.pdf_path.exists():
            logger.warning(f"ITOM.pdf not found at {self.pdf_path}", agent=self.name)
            return {}

        logger.info(f"Parsing ITOM.pdf from {self.pdf_path}", agent=self.name)

        try:
            # Try pdfplumber first (better text extraction)
            knowledge = self._extract_with_pdfplumber()

            if not knowledge:
                # Fallback to PyPDF2
                knowledge = self._extract_with_pypdf2()

            logger.info(
                f"Extracted {len(knowledge)} sections from ITOM.pdf",
                agent=self.name
            )

            self.knowledge_cache = knowledge
            return knowledge

        except Exception as e:
            logger.error(f"Failed to parse ITOM.pdf: {e}", agent=self.name)
            return {}

    def _extract_with_pdfplumber(self) -> Dict[str, str]:
        """Extract text using pdfplumber."""
        knowledge = {}

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                current_section = "Introduction"
                current_content = []

                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()

                    if not text:
                        continue

                    # Split into lines
                    lines = text.split('\n')

                    for line in lines:
                        line = line.strip()

                        # Detect section headers (various patterns)
                        if self._is_section_header(line):
                            # Save previous section
                            if current_content:
                                knowledge[current_section] = '\n'.join(current_content)

                            # Start new section
                            current_section = line
                            current_content = []
                        else:
                            if line:
                                current_content.append(line)

                # Save last section
                if current_content:
                    knowledge[current_section] = '\n'.join(current_content)

        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}", agent=self.name)

        return knowledge

    def _extract_with_pypdf2(self) -> Dict[str, str]:
        """Extract text using PyPDF2 as fallback."""
        knowledge = {}

        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                full_text = []
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)

                # Simple section extraction
                combined_text = '\n'.join(full_text)
                knowledge["ITOM Content"] = combined_text[:10000]  # First 10k chars

        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}", agent=self.name)

        return knowledge

    def _is_section_header(self, line: str) -> bool:
        """Determine if a line is likely a section header."""
        if not line:
            return False

        # Check various patterns
        patterns = [
            len(line) < 100 and line[0].isupper(),  # Short, starts with capital
            line.isupper() and len(line) < 80,  # All caps, not too long
            line.endswith(':') and len(line) < 80,  # Ends with colon
            any(line.startswith(prefix) for prefix in [
                'Chapter', 'Section', 'Part', '1.', '2.', '3.', '4.', '5.',
                'CHAPTER', 'SECTION', 'PART'
            ])
        ]

        return any(patterns)

    def search_knowledge(self, query: str) -> List[Dict[str, str]]:
        """
        Search the extracted knowledge for relevant sections.

        Args:
            query: Search query

        Returns:
            List of matching sections with content
        """
        if not self.knowledge_cache:
            self.extract_knowledge()

        results = []
        query_lower = query.lower()

        for section, content in self.knowledge_cache.items():
            if query_lower in section.lower() or query_lower in content.lower():
                results.append({
                    "section": section,
                    "content": content[:500],  # First 500 chars
                    "relevance": self._calculate_relevance(query_lower, section, content)
                })

        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)

        return results

    def _calculate_relevance(
        self, query: str, section: str, content: str
    ) -> float:
        """Calculate relevance score for a section."""
        score = 0.0

        # Query in section title is highly relevant
        if query in section.lower():
            score += 10.0

        # Count occurrences in content
        content_lower = content.lower()
        occurrences = content_lower.count(query)
        score += occurrences * 0.5

        return score

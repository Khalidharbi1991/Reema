"""Taif (Research Agent) - Gathers ITIL and IT standards information."""

from typing import Dict, List, Optional
from anthropic import Anthropic
from ..utils.logger import logger
from ..utils.config import config_manager


class ResearchAgent:
    """
    Taif (Research Agent)

    Responsibilities:
    - Gathers information about IT processes
    - References ITIL framework documentation
    - Identifies industry best practices
    - Utilizes ITOM.pdf as knowledge base
    - Researches process-specific requirements
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config_manager.system_config.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key)
        self.name = "Taif"
        self.model = config_manager.system_config.worker_model

        # Knowledge base
        self.itom_knowledge = None
        self._load_knowledge_base()

        logger.info("Research Agent initialized", agent=self.name)

    def _load_knowledge_base(self):
        """Load knowledge from ITOM.pdf and other sources."""
        try:
            from ..knowledge.itom_parser import ITOMParser
            parser = ITOMParser()
            self.itom_knowledge = parser.extract_knowledge()
            logger.info("ITOM knowledge base loaded", agent=self.name)
        except Exception as e:
            logger.warning(f"Could not load ITOM knowledge: {e}", agent=self.name)
            self.itom_knowledge = {}

    async def research_process(
        self, process_name: str, standards: List[str]
    ) -> Dict:
        """
        Research an IT process and gather comprehensive information.

        Args:
            process_name: Name of the IT process
            standards: List of applicable standards (ITIL, ITOM, etc.)

        Returns:
            Dictionary containing research findings
        """
        logger.agent_start(self.name, f"Researching {process_name}")

        try:
            # Build research prompt
            system_prompt = self._build_system_prompt()
            research_prompt = self._build_research_prompt(process_name, standards)

            # Call Claude for research
            response = await self._call_claude(
                messages=[{"role": "user", "content": research_prompt}],
                system=system_prompt
            )

            # Parse and structure the response
            research_data = self._parse_research_response(response, process_name)

            logger.agent_complete(self.name, f"Research for {process_name}")
            return research_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for research agent."""
        return """You are an expert IT Service Management researcher specializing in ITIL, ITOM, ITAM, and IT industry best practices.

Your role is to:
1. Gather comprehensive information about IT processes
2. Reference ITIL v4 framework documentation
3. Identify industry best practices and standards
4. Provide detailed process descriptions, objectives, and key activities
5. Identify roles, responsibilities, and required tools

Provide thorough, accurate, and well-structured research findings."""

    def _build_research_prompt(
        self, process_name: str, standards: List[str]
    ) -> str:
        """Build the research prompt."""
        itom_context = ""
        if self.itom_knowledge:
            itom_context = f"\n\nITOM Context:\n{self._get_relevant_itom_context(process_name)}"

        prompt = f"""Research the following IT process: {process_name}

Standards to reference: {', '.join(standards)}
{itom_context}

Please provide comprehensive research including:

1. **Process Definition**
   - Purpose and objectives
   - Scope and boundaries
   - Key benefits

2. **ITIL/Framework Alignment**
   - How this process aligns with ITIL v4 (or other frameworks)
   - Key ITIL practices involved
   - Process position in the service value chain

3. **Key Activities & Workflows**
   - Major process steps
   - Input and output
   - Decision points and triggers

4. **Roles & Responsibilities**
   - Key roles involved (Process Owner, Manager, Practitioners)
   - RACI matrix considerations
   - Stakeholders

5. **Tools & Technology**
   - Common ITSM tools used
   - Automation opportunities
   - Integration points

6. **Metrics & KPIs**
   - Key performance indicators
   - Success metrics
   - Reporting requirements

7. **Best Practices**
   - Industry best practices
   - Common pitfalls to avoid
   - Critical success factors

8. **Compliance & Standards**
   - Regulatory requirements
   - Audit considerations
   - Documentation requirements

Provide detailed, professional research suitable for creating a 15-30 page SOP document."""

        return prompt

    def _get_relevant_itom_context(self, process_name: str) -> str:
        """Extract relevant context from ITOM knowledge base."""
        if not self.itom_knowledge:
            return "No ITOM context available."

        # Simple keyword matching - can be enhanced with better search
        relevant_sections = []
        process_keywords = process_name.lower().split()

        for section, content in self.itom_knowledge.items():
            if any(keyword in section.lower() for keyword in process_keywords):
                relevant_sections.append(f"{section}:\n{content}")

        return "\n\n".join(relevant_sections) if relevant_sections else "No directly relevant ITOM context found."

    def _parse_research_response(
        self, response: str, process_name: str
    ) -> Dict:
        """Parse and structure the research response."""
        return {
            "process_name": process_name,
            "raw_research": response,
            "sections": self._extract_sections(response),
            "timestamp": self._get_timestamp()
        }

    def _extract_sections(self, response: str) -> Dict[str, str]:
        """Extract sections from the research response."""
        sections = {}
        current_section = None
        current_content = []

        for line in response.split('\n'):
            # Detect section headers (bold text like **Process Definition**)
            if line.strip().startswith('**') and line.strip().endswith('**'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.strip().strip('*')
                current_content = []
            elif line.strip().startswith('#'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.strip().strip('#').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)

        # Add last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    async def _call_claude(self, messages: List[Dict], system: str = "") -> str:
        """Make a call to Claude API."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}", agent=self.name)
            raise

"""Taif (Research Agent) - Gathers ITIL and IT standards information."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.specialists import ResearchAnalysis, assess_claims, available_sources, retain_evidence, iso_date
from ..utils.quality import parse_json_response, is_structured_response
from datetime import datetime, timezone
import json


class ResearchAgent(BaseAgent):
    """
    Taif (Research Agent)

    Responsibilities:
    - Gathers information about IT processes
    - References ITIL framework documentation
    - Identifies industry best practices
    - Utilizes ITOM.pdf as knowledge base
    - Researches process-specific requirements
    """

    AGENT_NAME = "Agent 1"
    AGENT_ROLE = "Research Agent"
    CONFIG_KEY = "research_agent"
    KNOWLEDGE_FILE = "taif_research_knowledge_ENHANCED.md"
    DEFAULT_TEMPERATURE = 0.5

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

        # Alias for backward compatibility
        self.research_knowledge = self.knowledge_base

        # Load ITOM.pdf knowledge separately
        self.itom_knowledge = None
        # Customer sources are now selected by the leader's permission manifest.
        # Keep legacy parser helpers available, but never ingest files implicitly.

    def _load_itom_knowledge(self):
        """Load knowledge from ITOM.pdf."""
        try:
            from ..knowledge.itom_parser import ITOMParser
            parser = ITOMParser()
            self.itom_knowledge = parser.extract_knowledge()
            logger.info("ITOM knowledge base loaded", agent=self.name)
        except Exception as e:
            logger.warning(f"Could not load ITOM knowledge: {e}", agent=self.name)
            self.itom_knowledge = {}

    async def research_process(
        self, process_name: str, standards: List[str], research_context: Dict = None
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
            as_of = (research_context or {}).get("as_of") or datetime.now(timezone.utc).date().isoformat()
            iso_date(as_of)
            research_prompt += ("\nReturn JSON matching:\n" + json.dumps(ResearchAnalysis.model_json_schema())
                + "\nLink each claim to exact supplied source quotes/locations. Do not invent dates or authority. "
                "Uncited recommendations/assumptions must be labelled. Research as-of date: " + as_of)

            # Call Claude for research
            response = await self._call_claude(
                messages=[{"role": "user", "content": research_prompt}],
                system=system_prompt
            )

            # Parse and structure the response
            research_data = self._parse_research_response(response, process_name, as_of)

            logger.agent_complete(self.name, f"Research for {process_name}")
            return research_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for research agent."""
        system_prompt = """You are Agent 1, an expert IT Service Management researcher specializing in ITIL, ITOM, ITAM, and IT industry best practices.

Your role is to:
1. Gather comprehensive information about IT processes
2. Reference ITIL v4 framework documentation
3. Identify industry best practices and standards
4. Provide detailed process descriptions, objectives, and key activities
5. Identify roles, responsibilities, and required tools

Provide thorough, accurate, and well-structured research findings."""

        # Inject comprehensive knowledge base
        return self._inject_knowledge(system_prompt, "You have 100% domain expertise in the following areas. Use this knowledge to provide accurate, detailed research:")

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
        self, response: str, process_name: str, as_of: str = None
    ) -> Dict:
        """Parse and structure the research response."""
        as_of = as_of or datetime.now(timezone.utc).date().isoformat()
        if is_structured_response(response):
            analysis = parse_json_response(response, ResearchAnalysis)
            sources = available_sources(self)
            evidence_report = assess_claims(analysis.claims, sources, as_of, config_manager.specialist_policy)
            for claim in analysis.claims:
                retain_evidence(claim.evidence, sources)
            response = analysis.raw_research
        else:
            evidence_report = {"as_of": as_of, "claims": [], "status": "unstructured_unverified", "missing_evidence": True}
        return {
            "process_name": process_name,
            "raw_research": response,
            "sections": self._extract_sections(response),
            "evidence_report": evidence_report,
            "timestamp": self._get_timestamp()
        }

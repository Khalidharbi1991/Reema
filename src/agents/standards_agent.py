"""Mohammad (Standards & Compliance Agent) - Ensures regulatory and framework alignment."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.documents import StandardsAnalysis, ControlRegister, legacy_register
from ..utils.quality import parse_json_response, is_structured_response
from ..utils.provider import current_runtime
import json


class StandardsAgent(BaseAgent):
    """
    Mohammad (Standards & Compliance Agent)

    Responsibilities:
    - Ensures alignment with ITIL, ITOM, ISO 20000, and other standards
    - Validates compliance requirements
    - Incorporates regulatory considerations
    - Maps processes to standard frameworks
    - Identifies mandatory compliance elements
    """

    AGENT_NAME = "Agent 2"
    AGENT_ROLE = "Standards & Compliance Agent"
    CONFIG_KEY = "standards_agent"
    KNOWLEDGE_FILE = "mohammad_standards_knowledge_ENHANCED.md"
    DEFAULT_TEMPERATURE = 0.3

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

        # Alias for backward compatibility
        self.standards_knowledge = self.knowledge_base

    async def analyze_compliance(
        self, process_name: str, standards: List[str]
    ) -> Dict:
        """
        Analyze compliance requirements for an IT process.

        Args:
            process_name: Name of the IT process
            standards: List of applicable standards

        Returns:
            Dictionary containing compliance analysis
        """
        logger.agent_start(self.name, f"Analyzing compliance for {process_name}")

        try:
            system_prompt = self._build_system_prompt()
            compliance_prompt = self._build_compliance_prompt(process_name, standards)

            response = await self._call_claude(
                messages=[{"role": "user", "content": compliance_prompt}],
                system=system_prompt
            )

            compliance_data = self._parse_compliance_response(response, process_name, standards)

            logger.agent_complete(self.name, f"Compliance analysis for {process_name}")
            return compliance_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for standards agent."""
        system_prompt = """You are Agent 2, an expert IT Compliance and Standards specialist with deep knowledge of:
- ITIL v4 framework
- ISO/IEC 20000 (IT Service Management)
- ISO/IEC 27001 (Information Security)
- COBIT (Control Objectives for Information Technologies)
- NIST frameworks
- SOC 2 compliance
- GDPR and data protection regulations
- Industry-specific IT regulations

Your role is to:
1. Identify all applicable compliance requirements
2. Map IT processes to standard frameworks
3. Ensure regulatory alignment
4. Identify mandatory documentation and controls
5. Highlight audit requirements
6. Provide compliance checklists

Be thorough, precise, and reference specific standard clauses where applicable."""

        # Inject comprehensive knowledge base
        return self._inject_knowledge(system_prompt, "You have 100% domain expertise in ISO 27001, ISO 20000, COBIT, SOC 2, and all regulatory frameworks. Use this knowledge for accurate compliance analysis:")

    def _build_compliance_prompt(
        self, process_name: str, standards: List[str]
    ) -> str:
        """Build the compliance analysis prompt."""
        prompt = f"""Analyze compliance requirements for the IT process: {process_name}

Applicable Standards/Frameworks: {', '.join(standards)}

Please provide a comprehensive compliance analysis including:

1. **Standards Mapping**
   - Map this process to specific ITIL v4 practices
   - Identify relevant ISO 20000 clauses
   - Reference other applicable standards
   - Provide specific section/clause numbers

2. **Compliance Requirements**
   - Mandatory controls and procedures
   - Required documentation
   - Audit trail requirements
   - Record retention policies

3. **Regulatory Considerations**
   - Data protection requirements (GDPR, etc.)
   - Industry-specific regulations
   - Geographic/jurisdictional requirements
   - Privacy and security mandates

4. **Documentation Requirements**
   - Required policies and procedures
   - Forms and templates needed
   - Approval and sign-off requirements
   - Version control and change management

5. **Audit Checklist**
   - Key audit points for this process
   - Evidence required for audits
   - Common audit findings to avoid
   - Compliance verification steps

6. **Risk & Control Matrix**
   - Key process risks
   - Required controls
   - Control effectiveness measures
   - Mitigation strategies

7. **Compliance Gaps & Recommendations**
   - Common compliance gaps
   - Recommendations for meeting requirements
   - Best practices for maintaining compliance
   - Continuous improvement suggestions

Provide specific, actionable compliance guidance suitable for inclusion in an SOP document."""

        return prompt + ("\nReturn only JSON matching this schema:\n" + json.dumps(StandardsAnalysis.model_json_schema())
            + "\nUse one or more control entries for every requested framework, including undetermined entries when evidence is missing. "
            "Do not invent clauses, evidence, applicability or certification. Evidence must quote an exact supplied source excerpt "
            "and retain its source ID, file, location and SHA-256. All evidence remains unverified. "
            "Use only these target section IDs:\n" + json.dumps([s.model_dump() for s in config_manager.document_profile.sections]))

    def _parse_compliance_response(
        self, response: str, process_name: str, standards=None
    ) -> Dict:
        """Parse and structure the compliance response."""
        standards = standards or []
        if is_structured_response(response):
            analysis = parse_json_response(response, StandardsAnalysis)
            register = analysis.control_register
            if {s.casefold() for s in standards} != {c.framework.casefold() for c in register.controls}:
                raise ValueError("Control register must account for every requested framework")
            runtime = current_runtime.get()
            available = {r["id"]: r for r in [*self.source_records, *self.knowledge_records]}
            if runtime:
                available = {key: value for key, value in available.items() if key in runtime.sources}
            register.validate_sources(available, config_manager.document_profile)
            if runtime:
                for control in register.controls:
                    for evidence in control.evidence:
                        # Keep the cited excerpt for deterministic checkpoint/recovery checks.
                        runtime.sources[evidence.source_id] = dict(runtime.sources[evidence.source_id],
                            text=available[evidence.source_id]["text"])
            response = analysis.compliance_analysis
            structured = True
        else:
            register = legacy_register(standards)
            structured = False
        return {
            "process_name": process_name,
            "compliance_analysis": response,
            "sections": self._extract_sections(response),
            "compliance_checklist": self._extract_checklist(response),
            "mandatory_controls": self._extract_controls(response),
            "control_register": register.model_dump(),
            "structured_controls": structured,
            "timestamp": self._get_timestamp()
        }

    def _extract_checklist(self, response: str) -> List[str]:
        """Extract compliance checklist items."""
        checklist = []
        in_checklist = False

        for line in response.split('\n'):
            if 'audit checklist' in line.lower() or 'checklist' in line.lower():
                in_checklist = True
                continue
            if in_checklist:
                if line.strip().startswith('-') or line.strip().startswith('\u2022'):
                    checklist.append(line.strip().lstrip('-\u2022').strip())
                elif line.strip().startswith('##') or line.strip().startswith('**'):
                    in_checklist = False

        return checklist

    def _extract_controls(self, response: str) -> List[str]:
        """Extract mandatory controls."""
        controls = []
        in_controls = False

        for line in response.split('\n'):
            if 'mandatory control' in line.lower() or 'required control' in line.lower():
                in_controls = True
                continue
            if in_controls:
                if line.strip().startswith('-') or line.strip().startswith('\u2022'):
                    controls.append(line.strip().lstrip('-\u2022').strip())
                elif line.strip().startswith('##') or line.strip().startswith('**'):
                    in_controls = False

        return controls

"""Mohammad (Standards & Compliance Agent) - Ensures regulatory and framework alignment."""

from typing import Dict, List, Optional
from anthropic import Anthropic
from ..utils.logger import logger
from ..utils.config import config_manager


class StandardsAgent:
    """
    Mohammad (Standards & Compliance Agent)

    Responsibilities:
    - Ensures alignment with ITIL, ITOM, ISO 20000, and other standards
    - Validates compliance requirements
    - Incorporates regulatory considerations
    - Maps processes to standard frameworks
    - Identifies mandatory compliance elements
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config_manager.system_config.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key)
        self.name = "Mohammad"
        self.model = config_manager.system_config.worker_model

        logger.info("Standards Agent initialized", agent=self.name)

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

            compliance_data = self._parse_compliance_response(response, process_name)

            logger.agent_complete(self.name, f"Compliance analysis for {process_name}")
            return compliance_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for standards agent."""
        return """You are an expert IT Compliance and Standards specialist with deep knowledge of:
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

        return prompt

    def _parse_compliance_response(
        self, response: str, process_name: str
    ) -> Dict:
        """Parse and structure the compliance response."""
        return {
            "process_name": process_name,
            "compliance_analysis": response,
            "sections": self._extract_sections(response),
            "compliance_checklist": self._extract_checklist(response),
            "mandatory_controls": self._extract_controls(response),
            "timestamp": self._get_timestamp()
        }

    def _extract_sections(self, response: str) -> Dict[str, str]:
        """Extract sections from the compliance response."""
        sections = {}
        current_section = None
        current_content = []

        for line in response.split('\n'):
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

        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _extract_checklist(self, response: str) -> List[str]:
        """Extract compliance checklist items."""
        checklist = []
        in_checklist = False

        for line in response.split('\n'):
            if 'audit checklist' in line.lower() or 'checklist' in line.lower():
                in_checklist = True
                continue
            if in_checklist:
                if line.strip().startswith('-') or line.strip().startswith('•'):
                    checklist.append(line.strip().lstrip('-•').strip())
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
                if line.strip().startswith('-') or line.strip().startswith('•'):
                    controls.append(line.strip().lstrip('-•').strip())
                elif line.strip().startswith('##') or line.strip().startswith('**'):
                    in_controls = False

        return controls

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

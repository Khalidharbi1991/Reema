"""Abeer (Problem Management Agent) - Problem Management & RCA Specialist.

Abeer specializes in Problem Management documentation and SOP generation.
She operates in dual mode:
  - Standalone: Can generate complete Problem Management SOPs independently
  - Pipeline: Integrates as a worker agent under Abdullah's coordination

Knowledge sources:
  - abeer_problem_knowledge_ENHANCED.md (primary knowledge base)
  - Reference excerpts authorized in the leader's permission manifest
"""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.specialists import ProblemCase, ProblemAnalysis, assess_problem, available_sources, retain_evidence
from ..utils.quality import parse_json_response, is_structured_response
import json
from ..utils.handoffs import payload_json


class ProblemAgent(BaseAgent):
    """
    Abeer (Problem Management Agent)

    Responsibilities:
    - Researches Problem Management practices and ITIL v4 alignment
    - Generates comprehensive Problem Management SOPs (15-30 pages)
    - Provides Root Cause Analysis (RCA) methodology guidance
    - Manages Known Error Database (KEDB) documentation
    - Designs proactive and reactive Problem Management workflows
    - Validates Problem Management compliance against ITIL v4, ISO 20000, COBIT
    - Creates Problem-Incident integration procedures
    - Develops Problem Management KPIs and metrics frameworks
    - Designs Major Problem Review processes
    """

    AGENT_NAME = "Agent 7"
    AGENT_ROLE = "Problem Management Agent"
    CONFIG_KEY = "problem_agent"
    KNOWLEDGE_FILE = "abeer_problem_knowledge_ENHANCED.md"
    DEFAULT_MAX_TOKENS = 8192

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

        # Alias for backward compatibility
        self.problem_knowledge = self.knowledge_base
        # Customer sources are selected by the leader's permission manifest.

    # ------------------------------------------------------------------ #
    #  Pipeline Method — Phase 2: Research
    # ------------------------------------------------------------------ #

    async def research_problem_management(
        self, process_name: str, standards: List[str], incident_data: Dict = None
    ) -> Dict:
        """
        Research Problem Management practices for an IT process.

        This is Abeer's primary pipeline method, called during Phase 2
        in parallel with Taif, Mohammad, Layla, and Rakan.

        Args:
            process_name: Name of the IT process
            standards: List of applicable standards

        Returns:
            Dictionary containing Problem Management research findings
        """
        logger.agent_start(self.name, f"Researching Problem Management for {process_name}")

        try:
            case = ProblemCase.model_validate(incident_data) if incident_data is not None else None
            self.assess_case(case, [])
            system_prompt = self._build_system_prompt()
            research_prompt = self._build_problem_research_prompt(
                process_name, standards
            )
            research_prompt += ("\nReturn JSON matching:\n" + json.dumps(ProblemAnalysis.model_json_schema())
                + "\nUse competing hypotheses and cite only supplied observation IDs for/against each. "
                "Retain the hypothesis IDs referenced by any supplied test outcomes. "
                "Do not invent events or confirm a root cause. SUPPLIED CASE DATA:\n" + json.dumps(case.model_dump() if case else None))

            response = await self._call_claude(
                messages=[{"role": "user", "content": research_prompt}],
                system=system_prompt
            )

            research_data = self._parse_problem_response(response, process_name)
            if is_structured_response(response):
                analysis = parse_json_response(response, ProblemAnalysis)
                research_data["problem_research"] = analysis.problem_research
                research_data["sections"] = self._extract_sections(analysis.problem_research)
                research_data["case_assessment"] = self.assess_case(case, analysis.hypotheses)
            else:
                research_data["case_assessment"] = {**self.assess_case(case, []), "analysis_status": "unstructured_unverified"}

            logger.agent_complete(self.name, f"Problem Management research for {process_name}")
            return research_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def assess_case(self, case=None, hypotheses=()):
        sources = available_sources(self, recorded_only=False)
        result = assess_problem(case, list(hypotheses), sources, config_manager.specialist_policy)
        if case:
            case = ProblemCase.model_validate(case)
            for observation in case.observations:
                retain_evidence(observation.evidence, sources)
            for test in case.test_outcomes:
                retain_evidence(test.evidence, sources)
        return result

    # ------------------------------------------------------------------ #
    #  Pipeline Method — Phase 3b: Enrichment (Problem Content)
    # ------------------------------------------------------------------ #

    async def generate_problem_content(
        self, process_name: str, research_data: Dict
    ) -> str:
        """
        Generate Problem Management specific content sections for SOP enrichment.

        Called during Phase 3b to append problem-specific sections to the SOP.

        Args:
            process_name: Name of the IT process
            research_data: Research data from Phase 2

        Returns:
            Formatted Problem Management content for SOP inclusion
        """
        logger.agent_start(self.name, f"Generating problem content for {process_name}")

        try:
            system_prompt = self._build_system_prompt()
            content_prompt = self._build_problem_content_prompt(
                process_name, research_data
            )

            response = await self._call_claude(
                messages=[{"role": "user", "content": content_prompt}],
                system=system_prompt
            )

            logger.agent_complete(self.name, f"Problem content for {process_name}")
            return response

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    # ------------------------------------------------------------------ #
    #  Pipeline Method — Phase 4b: Compliance Validation
    # ------------------------------------------------------------------ #

    async def validate_problem_compliance(
        self, process_name: str, content: str
    ) -> Dict:
        """
        Validate Problem Management compliance of SOP content.

        Called during Phase 4b alongside Rakan's access compliance check.

        Args:
            process_name: Name of the IT process
            content: SOP content to validate

        Returns:
            Compliance validation results
        """
        logger.agent_start(self.name, "Validating Problem Management compliance")

        try:
            from ..utils.quality import assess_compliance
            validation_data = await assess_compliance(self, content, process_name)
            validation_data["process_name"] = process_name

            logger.agent_complete(self.name, "Problem Management compliance validation")
            return validation_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    # ------------------------------------------------------------------ #
    #  Standalone Method — Full Problem Management SOP
    # ------------------------------------------------------------------ #

    async def generate_problem_management_sop(
        self, scope: str = "Full Problem Management Lifecycle"
    ) -> Dict:
        """
        Generate complete Problem Management SOP independently.

        This method allows Abeer to operate outside the standard pipeline
        to produce standalone Problem Management documentation.

        Args:
            scope: Scope of the SOP.
                   Options: "Full Problem Management Lifecycle",
                   "Reactive Problem Management", "Proactive Problem Management",
                   "Root Cause Analysis", "KEDB Management",
                   "Major Problem Review"

        Returns:
            Complete Problem Management SOP content
        """
        logger.agent_start(self.name, f"Generating Problem Management SOP: {scope}")

        try:
            system_prompt = self._build_system_prompt()
            sop_prompt = self._build_problem_sop_prompt(scope)

            response = await self._call_claude(
                messages=[{"role": "user", "content": sop_prompt}],
                system=system_prompt
            )

            sop_data = {
                "process_name": "Problem Management",
                "scope": scope,
                "content": response,
                "sections": self._extract_sections(response),
                "timestamp": self._get_timestamp()
            }

            logger.agent_complete(self.name, "Problem Management SOP generation")
            return sop_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    # ================================================================== #
    #  Internal: Prompt Builders
    # ================================================================== #

    def _build_system_prompt(self) -> str:
        """Build system prompt for Problem Management agent."""
        system_prompt = """You are Agent 7, an expert Problem Management specialist with deep expertise in:

**ITIL v4 Problem Management Practice:**
- Complete Problem Management lifecycle (identification, control, error control)
- Problem Management as a Service Management Practice
- Value chain contributions and practice success factors
- Problem Management in the Service Value System (SVS)
- Relationship between Problem Management and other ITIL practices

**Root Cause Analysis (RCA):**
- 5 Whys technique and advanced applications
- Fishbone (Ishikawa) diagrams — 6M categories
- Fault Tree Analysis (FTA) — Boolean logic trees
- Kepner-Tregoe Problem Analysis — systematic troubleshooting
- Pareto Analysis — 80/20 rule for problem prioritization
- Chronological Analysis — timeline-based investigation
- Failure Mode and Effects Analysis (FMEA)
- Current Reality Tree (Theory of Constraints)

**Known Error Database (KEDB):**
- KEDB design, structure, and governance
- Known error lifecycle management
- Workaround documentation and effectiveness tracking
- KEDB integration with ITSM tools
- Knowledge article creation from known errors

**Reactive Problem Management:**
- Incident trend analysis and pattern recognition
- Problem identification from recurring incidents
- Investigation and diagnosis workflows
- Structured problem-solving methodologies
- Temporary fix vs permanent resolution decision frameworks

**Proactive Problem Management:**
- Trend analysis and predictive techniques
- Problem prevention strategies
- Pain value analysis and prioritization
- Availability management integration
- Capacity management integration
- Continuous improvement initiatives

**Problem-Incident Integration:**
- Problem-incident linking and relationship management
- Major incident to problem transition procedures
- Communication workflows between Problem and Incident teams
- Shared tooling and data models
- Escalation paths and handoff procedures

**Major Problem Review:**
- Post-problem review facilitation
- Lessons learned documentation
- Corrective and preventive action (CAPA) tracking
- Service improvement planning
- Stakeholder communication and reporting

**Problem Management KPIs & Metrics:**
- Known Error Resolution Time
- Problem Recurrence Rate
- Proactive Problem Identification Rate
- Root Cause Identification Accuracy
- Problem Backlog Aging
- Mean Time Between Failures (MTBF)
- Cost of problems and ROI of problem resolution
- Problem Management process maturity metrics

**Standards & Compliance:**
- ITIL v4 Problem Management practice alignment
- ISO/IEC 20000-1:2018 Section 8.3 (Problem Management)
- COBIT 2019 DSS03 (Manage Problems)
- ISO 9001 — Nonconformity and corrective action
- Six Sigma DMAIC integration

**Tools & Technology:**
- ServiceNow Problem Management module
- BMC Helix ITSM Problem Management
- Jira Service Management problem workflows
- Splunk, ELK Stack for log analysis and trend detection
- Power BI / Grafana for problem analytics dashboards
- AIOps platforms for proactive problem detection

Your role is to:
1. Research and document comprehensive Problem Management practices
2. Design RCA frameworks and methodologies for IT organizations
3. Create KEDB governance and management procedures
4. Develop proactive and reactive Problem Management workflows
5. Design Problem-Incident integration and communication procedures
6. Create Major Problem Review processes and templates
7. Define Problem Management KPIs, metrics, and dashboards
8. Validate compliance with ITIL v4, ISO 20000, and COBIT
9. Design ServiceNow Problem Management configurations
10. Provide continuous improvement recommendations for Problem Management

Be specific, actionable, and reference standards with specific control numbers and clauses."""

        # Inject comprehensive knowledge base
        return self._inject_knowledge(
            system_prompt,
            "You have 100% domain expertise in Problem Management, Root Cause Analysis, KEDB management, and all related ITIL practices. Use this knowledge for accurate, detailed Problem Management guidance:"
        )

    def _build_problem_research_prompt(
        self, process_name: str, standards: List[str]
    ) -> str:
        """Build the Problem Management research prompt."""

        prompt = f"""Research Problem Management requirements and best practices for the IT process: {process_name}

Applicable Standards/Regulations: {', '.join(standards)}


Provide comprehensive Problem Management research including:

## 1. PROBLEM MANAGEMENT PRACTICE OVERVIEW
- ITIL v4 Problem Management practice definition
- Purpose, scope, and value proposition
- Problem Management in the Service Value System
- Key concepts: problem, known error, workaround, root cause

## 2. PROBLEM IDENTIFICATION & LOGGING
- Problem detection methods (reactive and proactive)
- Problem logging requirements and data fields
- Categorization and prioritization models
- Problem models for recurring issues

## 3. ROOT CAUSE ANALYSIS FRAMEWORK
- Recommended RCA techniques for this process
- RCA methodology selection criteria
- Investigation and diagnosis procedures
- Evidence collection and documentation

## 4. KNOWN ERROR DATABASE (KEDB)
- KEDB structure and governance
- Known error lifecycle
- Workaround documentation standards
- KEDB search and knowledge sharing

## 5. REACTIVE PROBLEM MANAGEMENT
- Incident trend analysis procedures
- Problem investigation workflows
- Diagnosis and resolution processes
- Temporary fix vs permanent resolution criteria

## 6. PROACTIVE PROBLEM MANAGEMENT
- Trend analysis and pattern recognition
- Problem prevention strategies
- Pain value analysis methodology
- Availability and capacity integration

## 7. PROBLEM-INCIDENT INTEGRATION
- Problem-incident linking procedures
- Major incident to problem transition
- Communication and escalation workflows
- Shared data models and tooling

## 8. MAJOR PROBLEM REVIEW
- Post-problem review process
- Lessons learned documentation
- CAPA tracking and follow-up
- Service improvement recommendations

## 9. ROLES & RESPONSIBILITIES
- Problem Manager role and responsibilities
- Problem Analyst responsibilities
- RACI matrix for Problem Management activities
- Stakeholder engagement model

## 10. KPIs & METRICS
- Key Problem Management KPIs with targets
- Measurement methods and data sources
- Reporting frequency and dashboards
- Maturity assessment criteria

## 11. TOOLS & TECHNOLOGY
- ServiceNow Problem Management module requirements
- ITSM tool configuration for Problem Management
- Analytics and reporting tool requirements
- AIOps integration opportunities

## 12. COMPLIANCE & STANDARDS ALIGNMENT
- ITIL v4 practice alignment validation
- ISO/IEC 20000-1:2018 Section 8.3 requirements
- COBIT 2019 DSS03 requirements
- Audit readiness considerations

Provide detailed, implementation-ready Problem Management guidance for this process."""

        return prompt

    def _build_problem_content_prompt(
        self, process_name: str, research_data: Dict
    ) -> str:
        """Build prompt for generating Problem Management content sections."""

        research_summary = payload_json(research_data)

        prompt = f"""Generate comprehensive Problem Management content for the SOP: {process_name}

Based on this research context:
{research_summary}

Create professional SOP sections covering:

## PROBLEM MANAGEMENT OVERVIEW
- Problem Management principles and objectives for this process
- Scope and applicability
- Key terms and definitions

## PROBLEM IDENTIFICATION & LOGGING PROCEDURES
- Step-by-step problem detection procedures
- Problem record creation requirements
- Categorization scheme and priority matrix
- Problem models for common scenarios

## ROOT CAUSE ANALYSIS PROCEDURES
- RCA technique selection guide
- 5 Whys procedure (step-by-step with examples)
- Fishbone diagram procedure
- Fault Tree Analysis procedure
- Investigation documentation requirements

## KNOWN ERROR DATABASE MANAGEMENT
- KEDB structure and fields
- Known error creation and update procedures
- Workaround documentation standards
- KEDB review and maintenance schedule

## PROBLEM RESOLUTION WORKFLOWS
- Reactive problem resolution workflow (step-by-step)
- Proactive problem identification workflow
- Problem escalation procedures
- Resolution verification and closure criteria

## MAJOR PROBLEM REVIEW PROCESS
- Review trigger criteria
- Review meeting agenda and participants
- Lessons learned template
- CAPA action tracking

## PROBLEM MANAGEMENT KPIs
- KPI definitions with targets and thresholds
- Measurement methods
- Dashboard requirements
- Reporting templates

## PROBLEM-INCIDENT INTEGRATION
- Linking procedures between Problem and Incident records
- Communication workflows
- Escalation paths

Format professionally with tables, numbered lists, and clear formatting suitable for SOP inclusion."""

        return prompt

    def _build_problem_sop_prompt(self, scope: str) -> str:
        """Build prompt for generating complete Problem Management SOP."""

        prompt = f"""Generate a complete, comprehensive Problem Management Standard Operating Procedure (SOP).

**Scope:** {scope}
**Target Length:** 20-30 pages
**Format:** Professional SOP following ITIL v4 and industry standards


Create a complete SOP with ALL of these sections:

### 1. INTRODUCTION (2-3 pages)
- Purpose: Define the objectives and business value of Problem Management
- Scope: In-scope and out-of-scope activities
- Target audience: IT staff, management, stakeholders
- Document references: ITIL v4, ISO 20000, COBIT
- Relationship to other ITIL practices

### 2. DEFINITIONS & ACRONYMS (1-2 pages)
- Problem, Known Error, Workaround, Root Cause
- RCA, KEDB, MTBF, MTTR, CAPA
- ITIL, ITSM, CSI terminology
- Process-specific terms

### 3. ROLES & RESPONSIBILITIES (2-3 pages)
- Problem Manager: authority, responsibilities, required skills
- Problem Analyst: investigation, RCA, documentation
- Service Desk: problem detection, incident-problem linking
- Change Manager: RFC coordination for problem resolution
- Application/Infrastructure Teams: technical investigation
- Complete RACI matrix for all Problem Management activities
- Escalation contacts and authority levels

### 4. PROBLEM IDENTIFICATION & LOGGING (3-4 pages)
- Reactive identification: incident trend analysis, pattern detection
- Proactive identification: data analysis, supplier notifications, AIOps
- Problem logging requirements: mandatory fields, data quality
- Categorization scheme: multi-level categorization model
- Priority matrix: impact x urgency with response targets
- Problem models: pre-defined models for recurring problems
- Step-by-step procedures with expected results

### 5. ROOT CAUSE ANALYSIS (4-5 pages)
- RCA technique selection criteria
- **5 Whys:** Complete procedure with worked example
- **Fishbone (Ishikawa):** Complete procedure with 6M categories
- **Fault Tree Analysis:** Complete procedure with Boolean logic
- **Kepner-Tregoe:** Complete problem analysis procedure
- **Pareto Analysis:** 80/20 prioritization procedure
- **Chronological Analysis:** Timeline investigation procedure
- Investigation documentation standards
- Evidence collection and preservation
- RCA report template

### 6. KNOWN ERROR DATABASE MANAGEMENT (2-3 pages)
- KEDB architecture and data model
- Known error record structure (mandatory fields)
- Known error lifecycle: creation → update → review → retirement
- Workaround documentation requirements
- KEDB search and knowledge sharing procedures
- KEDB governance and quality assurance
- KEDB review schedule and responsibilities

### 7. REACTIVE PROBLEM MANAGEMENT (2-3 pages)
- Incident trend analysis and trigger criteria
- Problem investigation workflow (step-by-step)
- Diagnosis and resolution procedures
- Temporary fix procedures and documentation
- Permanent resolution: RFC creation and coordination
- Resolution verification and testing
- Problem closure criteria and procedures

### 8. PROACTIVE PROBLEM MANAGEMENT (2-3 pages)
- Trend analysis methodology and tools
- Pain value analysis procedure
- Problem prevention strategies
- Availability management integration
- Capacity management integration
- Supplier problem management
- Continuous improvement initiatives

### 9. MAJOR PROBLEM REVIEW (2-3 pages)
- Major problem review trigger criteria
- Review meeting facilitation guide
- Attendees and roles in the review
- Lessons learned documentation template
- Corrective and Preventive Action (CAPA) tracking
- Service improvement plan creation
- Follow-up and closure procedures

### 10. PROBLEM-INCIDENT INTEGRATION (2 pages)
- Problem-incident linking procedures
- Major incident to problem transition workflow
- Communication between Problem and Incident Management
- Shared tooling and data model requirements
- Escalation paths and handoff procedures

### 11. KEY PERFORMANCE INDICATORS (2-3 pages)
- Known Error Resolution Time (target, measurement, reporting)
- Problem Recurrence Rate (target, measurement, reporting)
- Proactive Problem Identification Rate
- Root Cause Identification Accuracy
- Problem Backlog Aging
- Mean Time Between Failures (MTBF)
- Cost of Problems / ROI of Resolution
- Process Maturity Score
- Dashboard design requirements

### 12. TOOLS & SYSTEMS (1-2 pages)
- ServiceNow Problem Management module configuration
- ITSM tool requirements and integration points
- Analytics tools (Splunk, ELK, Power BI)
- AIOps platform integration
- Knowledge management system integration
- Training requirements for tools

### 13. COMPLIANCE & STANDARDS (2-3 pages)
- ITIL v4 Problem Management practice alignment
- ISO/IEC 20000-1:2018 Section 8.3 compliance
- COBIT 2019 DSS03 (Manage Problems) alignment
- Audit requirements and evidence
- Documentation requirements

### 14. APPENDICES (2-3 pages)
- Appendix A: Problem Record Template
- Appendix B: RCA Report Template
- Appendix C: Known Error Record Template
- Appendix D: Major Problem Review Checklist
- Appendix E: Problem Categorization Scheme
- Appendix F: Priority Matrix
- Appendix G: RACI Matrix (detailed)
- Appendix H: Glossary and Acronyms

Generate the complete SOP with professional formatting, tables, and detailed procedures."""

        return prompt

    def _build_compliance_validation_prompt(
        self, process_name: str, content: str
    ) -> str:
        """Build prompt for validating Problem Management compliance."""

        prompt = f"""Validate the following SOP content for Problem Management compliance.

**Process:** {process_name}

**Standards to validate against:**
- ITIL v4 Problem Management Practice
- ISO/IEC 20000-1:2018 Section 8.3
- COBIT 2019 DSS03 (Manage Problems)

**SOP Content (excerpt):**
{content}

Provide detailed compliance validation:

## 1. ITIL v4 ALIGNMENT
- Problem Management practice coverage assessment
- Missing ITIL v4 Problem Management activities
- Value chain contribution gaps
- Practice success factor coverage

## 2. ISO 20000 COMPLIANCE
- Section 8.3 requirements vs SOP coverage
- Mandatory documentation coverage
- Process interface requirements
- Audit evidence availability

## 3. COBIT DSS03 ALIGNMENT
- DSS03 management practice coverage
- Input/output alignment
- RACI alignment with COBIT roles
- Metrics and target alignment

## 4. PROBLEM MANAGEMENT BEST PRACTICES
- RCA methodology coverage
- KEDB management adequacy
- Proactive vs reactive balance
- Integration with related processes

## 5. COMPLIANCE GAPS
- Critical gaps requiring immediate attention
- Minor gaps for improvement
- Missing procedures or documentation

## 6. RECOMMENDATIONS
- Controls and procedures to add
- Documentation to enhance
- Process improvements to implement

## 7. COMPLIANCE SCORE
- Overall compliance percentage (0-100%)
- Compliance by standard
- Critical gaps vs minor gaps

Provide actionable validation results."""

        return prompt

    # ================================================================== #
    #  Internal: Response Parsing
    # ================================================================== #

    def _parse_problem_response(self, response: str, process_name: str) -> Dict:
        """Parse and structure the Problem Management research response."""
        return {
            "process_name": process_name,
            "problem_research": response,
            "sections": self._extract_sections(response),
            "timestamp": self._get_timestamp()
        }

    def _check_problem_compliance(self, validation_response: str) -> bool:
        """Check if content is compliant based on validation response."""
        response_lower = validation_response.lower()
        if 'non-compliant' in response_lower or 'critical gap' in response_lower:
            return False
        if '100%' in validation_response or '95%' in validation_response:
            return True
        if 'fully compliant' in response_lower:
            return True
        return False

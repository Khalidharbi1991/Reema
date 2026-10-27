"""Rakan (Access Management Agent) - IAM and Access Compliance Specialist."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.handoffs import payload_json
from ..utils.specialists import IAMSnapshot, check_iam, available_sources, retain_evidence


class AccessAgent(BaseAgent):
    """
    Rakan (Access Management Agent)

    Responsibilities:
    - Analyzes access management requirements for IT processes
    - Provides IAM lifecycle guidance (joiner/mover/leaver)
    - Designs RBAC/ABAC/PBAC models and role matrices
    - Validates privileged access management (PAM) controls
    - Ensures Zero Trust architecture alignment
    - Provides cloud IAM implementation guidance (AWS, Azure, GCP)
    - Validates Saudi regulatory compliance (NCA ECC 2-2, SAMA Domain 3, PDPL)
    - Designs access governance frameworks (recertification, SoD)
    - Creates access request workflows and approval matrices
    - Provides access analytics and KPI frameworks
    """

    AGENT_NAME = "Agent 6"
    AGENT_ROLE = "Access Management Agent"
    CONFIG_KEY = "access_agent"
    KNOWLEDGE_FILE = "rakan_access_knowledge_ENHANCED.md"
    DEFAULT_TEMPERATURE = 0.4

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

        # Alias for backward compatibility
        self.access_knowledge = self.knowledge_base

    async def analyze_access_requirements(
        self, process_name: str, standards: List[str], research_data: Dict = None
    ) -> Dict:
        """
        Analyze access management requirements for an IT process.

        This is Rakan's primary method, called during Phase 2 of the
        SOP generation pipeline in parallel with Research, Standards,
        and Data agents.

        Args:
            process_name: Name of the IT process
            standards: List of applicable standards
            research_data: Optional research context from other agents

        Returns:
            Dictionary containing access management analysis
        """
        logger.agent_start(self.name, f"Analyzing access requirements for {process_name}")

        try:
            environment = (research_data or {}).get("iam_environment")
            environment_checks = self.check_environment(environment, (research_data or {}).get("iam_previous"))
            system_prompt = self._build_system_prompt()
            access_prompt = self._build_access_analysis_prompt(
                process_name, standards, research_data
            )
            access_prompt += "\nDETERMINISTIC SNAPSHOT CHECKS (not production verification):\n" + payload_json(environment_checks)

            response = await self._call_claude(
                messages=[{"role": "user", "content": access_prompt}],
                system=system_prompt
            )

            access_data = self._parse_access_response(response, process_name)
            access_data["environment_checks"] = environment_checks

            logger.agent_complete(self.name, f"Access analysis for {process_name}")
            return access_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def check_environment(self, environment=None, previous=None):
        sources = available_sources(self, recorded_only=False)
        snapshot = IAMSnapshot.model_validate(environment) if environment is not None else None
        result = check_iam(snapshot, sources, config_manager.specialist_policy)
        baseline = IAMSnapshot.model_validate(previous) if previous is not None else None
        if baseline:
            if snapshot is None: raise ValueError("IAM baseline requires a current snapshot")
            check_iam(baseline, sources, config_manager.specialist_policy)
            from ..utils.domain_depth import iam_drift
            result['drift'] = iam_drift(baseline, snapshot)
        if snapshot:
            for approval in snapshot.approvals:
                retain_evidence(approval.evidence, sources)
        if baseline:
            for approval in baseline.approvals: retain_evidence(approval.evidence, sources)
        return result

    async def generate_access_content(
        self, process_name: str, access_requirements: Dict
    ) -> str:
        """
        Generate access management specific content sections for SOP.

        Args:
            process_name: Name of the IT process
            access_requirements: Access requirements from analysis

        Returns:
            Formatted access management content for SOP inclusion
        """
        logger.agent_start(self.name, f"Generating access content for {process_name}")

        try:
            system_prompt = self._build_system_prompt()
            content_prompt = self._build_access_content_prompt(
                process_name, access_requirements
            )

            response = await self._call_claude(
                messages=[{"role": "user", "content": content_prompt}],
                system=system_prompt
            )

            logger.agent_complete(self.name, f"Access content for {process_name}")
            return response

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def generate_access_management_sop(
        self, scope: str = "Full IAM Lifecycle"
    ) -> Dict:
        """
        Generate complete Access Management SOP independently.

        This method allows Rakan to operate outside the standard pipeline
        to produce standalone access management documentation.

        Args:
            scope: Scope of access management SOP
                   Options: "Full IAM Lifecycle", "PAM Only",
                   "Cloud IAM", "Access Governance", "Zero Trust"

        Returns:
            Complete access management SOP content
        """
        logger.agent_start(self.name, f"Generating Access Management SOP: {scope}")

        try:
            system_prompt = self._build_system_prompt()
            sop_prompt = self._build_access_sop_prompt(scope)

            response = await self._call_claude(
                messages=[{"role": "user", "content": sop_prompt}],
                system=system_prompt
            )

            sop_data = {
                "process_name": "Access Management",
                "scope": scope,
                "content": response,
                "sections": self._extract_sections(response),
                "timestamp": self._get_timestamp()
            }

            logger.agent_complete(self.name, "Access Management SOP generation")
            return sop_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def validate_access_compliance(
        self, content: str, regulations: List[str]
    ) -> Dict:
        """
        Validate access compliance against specific regulations.

        Args:
            content: SOP content to validate
            regulations: List of regulations to check against
                        e.g. ["NCA ECC 2-2", "SAMA Domain 3", "PDPL", "ISO 27001:2022"]

        Returns:
            Compliance validation results with gap analysis
        """
        logger.agent_start(self.name, "Validating access compliance")

        try:
            from ..utils.quality import assess_compliance
            validation_data = await assess_compliance(self, content, ", ".join(regulations))
            validation_data["regulations"] = regulations

            logger.agent_complete(self.name, "Access compliance validation")
            return validation_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for access management agent."""
        system_prompt = """You are Agent 6, an expert Access Management, Identity & Access Management (IAM), and Access Compliance specialist with deep expertise in:

**Identity & Access Management (IAM):**
- Complete IAM lifecycle (joiner/mover/leaver processes)
- Identity provisioning and deprovisioning
- Identity governance and administration (IGA)
- Access request workflows and approval processes
- Identity federation (SAML, OAuth 2.0, OIDC, SCIM)
- Identity as a Service (IDaaS) platforms

**Privileged Access Management (PAM):**
- Privileged account lifecycle management
- Session monitoring and recording
- Just-in-Time (JIT) access provisioning
- Password vaulting and rotation
- Privilege elevation and delegation
- PAM platforms (CyberArk, BeyondTrust, Delinea, HashiCorp Vault)

**Access Control Models:**
- Role-Based Access Control (RBAC) - role engineering, role mining
- Attribute-Based Access Control (ABAC) - policy design
- Policy-Based Access Control (PBAC)
- Mandatory Access Control (MAC) and Discretionary Access Control (DAC)
- Risk-Based Adaptive Access Control

**Zero Trust Architecture:**
- Zero Trust principles and maturity models (CISA, Forrester)
- Micro-segmentation strategies
- Continuous verification and least privilege
- Zero Trust Network Access (ZTNA)

**Cloud IAM:**
- AWS IAM (policies, roles, federation, SCP, permission boundaries)
- Azure Active Directory / Microsoft Entra ID (Conditional Access, PIM)
- Google Cloud IAM (roles, service accounts, workload identity)
- Multi-cloud identity federation and CIEM

**Authentication & Authorization:**
- Single Sign-On (SSO) - SAML, OAuth 2.0, OIDC, Kerberos
- Multi-Factor Authentication (MFA/2FA) - TOTP, FIDO2, biometric
- Passwordless authentication (WebAuthn, passkeys)
- Conditional and adaptive authentication

**Access Governance:**
- Access certification and recertification campaigns
- Segregation of Duties (SoD) analysis and toxic combinations
- Access risk scoring and orphaned account management
- Emergency access (break-glass) procedures

**Regulatory Compliance:**
- NCA ECC Control 2-2 (Saudi Cybersecurity Authority)
- SAMA Cybersecurity Framework Domain 3 (Saudi Central Bank)
- SDAIA PDPL (Saudi Data Protection Law)
- ISO 27001:2022 Annex A.5.15-A.5.18, A.8.2-A.8.5
- NIST SP 800-53 AC Family, NIST SP 800-207 Zero Trust
- SOC 2 CC6 (Logical and Physical Access)

**Access Analytics & Monitoring:**
- User and Entity Behavior Analytics (UEBA)
- Access anomaly detection and risk scoring
- Access management KPIs and dashboards

Your role is to:
1. Analyze access management requirements for IT processes
2. Design comprehensive IAM lifecycle workflows
3. Provide PAM implementation guidance
4. Design RBAC/ABAC models and role matrices
5. Ensure Zero Trust alignment
6. Validate regulatory compliance (NCA, SAMA, PDPL, ISO 27001)
7. Design access governance frameworks
8. Create access analytics and KPI frameworks
9. Provide cloud IAM architecture guidance
10. Design emergency and break-glass access procedures

Be specific, actionable, and reference standards with specific control numbers."""

        # Inject comprehensive knowledge base
        return self._inject_knowledge(system_prompt, "You have 100% domain expertise in IAM, PAM, access control, Zero Trust, cloud IAM, and all access-related compliance frameworks. Use this knowledge for accurate, detailed access management guidance:")

    def _build_access_analysis_prompt(
        self, process_name: str, standards: List[str], research_data: Dict = None
    ) -> str:
        """Build the access management analysis prompt."""

        research_context = ""
        if research_data:
            research_context = f"\n\n**Research Context:**\n{payload_json(research_data)}"

        prompt = f"""Analyze access management requirements for the IT process: {process_name}

Applicable Standards/Regulations: {', '.join(standards)}
{research_context}

Provide comprehensive access management analysis including:

## 1. IAM LIFECYCLE REQUIREMENTS
- Joiner process (onboarding, access provisioning)
- Mover process (role changes, access modifications)
- Leaver process (offboarding, access revocation)
- Contractor and temporary access management
- Service account lifecycle

## 2. ACCESS CONTROL MODEL
- Recommended access control model (RBAC/ABAC/PBAC)
- Role definitions and role hierarchy
- Permission sets and entitlements
- Segregation of duties (SoD) matrix

## 3. PRIVILEGED ACCESS MANAGEMENT
- Privileged account identification
- PAM controls required
- Session monitoring requirements
- Just-in-Time access procedures
- Emergency access (break-glass) procedures

## 4. AUTHENTICATION & AUTHORIZATION
- Authentication methods (SSO, MFA, passwordless)
- Authorization workflows
- Conditional access policies

## 5. ACCESS REQUEST & APPROVAL
- Access request workflow design
- Approval matrix (who approves what)
- Temporary access procedures
- Self-service capabilities

## 6. ACCESS GOVERNANCE
- Access certification schedule
- Recertification process and frequency
- Orphaned and dormant account handling
- Access violation procedures

## 7. ZERO TRUST ALIGNMENT
- Zero Trust principles applicable to this process
- Least privilege implementation
- Continuous verification points

## 8. CLOUD IAM CONSIDERATIONS
- Cloud platform IAM requirements
- Cross-cloud identity federation
- Cloud service account management

## 9. REGULATORY COMPLIANCE
- NCA ECC 2-2 compliance requirements
- SAMA Domain 3 compliance requirements
- PDPL access data protection requirements
- ISO 27001:2022 Annex A access controls

## 10. ACCESS ANALYTICS & KPIs
- Key access management metrics and targets
- Dashboard requirements
- UEBA integration points
- Reporting requirements

Provide detailed, implementation-ready access management guidance for this process."""

        return prompt

    def _build_access_content_prompt(
        self, process_name: str, access_requirements: Dict
    ) -> str:
        """Build prompt for generating access content sections."""

        requirements_summary = payload_json(access_requirements)

        prompt = f"""Generate comprehensive access management content for the SOP: {process_name}

Based on these access requirements:
{requirements_summary}

Create professional SOP sections covering:

## ACCESS CONTROL OVERVIEW
- Access control model and principles
- Scope of access management for this process

## IAM LIFECYCLE PROCEDURES
- Detailed joiner/mover/leaver procedures
- Step-by-step access provisioning workflows

## ROLE DEFINITIONS & RBAC MATRIX
- Complete role definitions for this process
- Role-to-permission mappings
- Segregation of duties matrix

## ACCESS REQUEST PROCEDURES
- How to request access (step-by-step with expected results)
- Approval workflows and approvers
- Emergency access procedures

## PRIVILEGED ACCESS MANAGEMENT
- Privileged account management procedures
- Session monitoring requirements

## AUTHENTICATION REQUIREMENTS
- Required authentication methods
- MFA and SSO requirements

## ACCESS GOVERNANCE
- Access review schedule and procedures
- Compliance validation procedures

## ACCESS MONITORING & KPIs
- Access metrics and targets
- Dashboard requirements

Format professionally with tables, numbered lists, and clear formatting suitable for SOP inclusion."""

        return prompt

    def _build_access_sop_prompt(self, scope: str) -> str:
        """Build prompt for generating complete Access Management SOP."""

        prompt = f"""Generate a complete, comprehensive Access Management Standard Operating Procedure (SOP).

**Scope:** {scope}
**Target Length:** 20-30 pages
**Format:** Professional SOP following ITIL and industry standards

Create a complete SOP with ALL of these sections:

### 1. INTRODUCTION (2-3 pages)
- Purpose, objectives, scope, target audience, document references

### 2. DEFINITIONS & ACRONYMS (1-2 pages)
- IAM, PAM, Zero Trust, regulatory terms

### 3. ROLES & RESPONSIBILITIES (2-3 pages)
- Identity & Access Manager, IAM Administrators, PAM Administrators,
  Access Certifiers, Application Owners
- Complete RACI matrix for access management activities

### 4. IAM LIFECYCLE PROCESSES (4-5 pages)
- Detailed Joiner process (step-by-step with expected results)
- Detailed Mover process (step-by-step)
- Detailed Leaver process (step-by-step)
- Contractor and service account lifecycle

### 5. ACCESS CONTROL MODEL (3-4 pages)
- RBAC implementation, role engineering, permission management
- Segregation of duties matrix with examples

### 6. PRIVILEGED ACCESS MANAGEMENT (3-4 pages)
- PAM architecture, privileged account management
- Session monitoring, JIT access, emergency access procedures

### 7. AUTHENTICATION & AUTHORIZATION (2-3 pages)
- SSO, MFA, passwordless, conditional access policies

### 8. ACCESS REQUEST & APPROVAL (2-3 pages)
- Request workflows, approval matrices, temporary and emergency access

### 9. ACCESS GOVERNANCE (2-3 pages)
- Certification process, recertification schedules
- Access review procedures, violation handling

### 10. ZERO TRUST IMPLEMENTATION (2 pages)
- Zero Trust principles, continuous verification, micro-segmentation

### 11. CLOUD IAM (2-3 pages)
- AWS IAM, Azure Entra ID, Google Cloud IAM procedures

### 12. ACCESS ANALYTICS & MONITORING (2 pages)
- UEBA, KPIs, metrics, dashboards

### 13. COMPLIANCE & REGULATIONS (3-4 pages)
- NCA ECC 2-2, SAMA Domain 3, PDPL, ISO 27001:2022 access controls

### 14. TOOLS & SYSTEMS (1-2 pages)
- IAM, PAM, SIEM, HR system integration

### 15. APPENDICES (2-3 pages)
- Access request forms, role templates, SoD matrix, compliance checklists

Generate the complete SOP with professional formatting, tables, and detailed procedures."""

        return prompt

    def _build_compliance_validation_prompt(
        self, content: str, regulations: List[str]
    ) -> str:
        """Build prompt for validating access compliance."""

        prompt = f"""Validate the following SOP content for access management compliance.

**Regulations to validate against:**
{', '.join(regulations)}

**SOP Content (excerpt):**
{content}

Provide detailed compliance validation:

## 1. COMPLIANCE GAPS
- Missing access controls
- Insufficient access procedures
- Missing regulatory requirements

## 2. REGULATORY MAPPING
For each regulation, map to specific SOP sections:
- NCA ECC 2-2 requirements vs SOP coverage
- SAMA Domain 3 requirements vs SOP coverage
- PDPL requirements vs SOP coverage
- ISO 27001:2022 access controls vs SOP coverage

## 3. RECOMMENDATIONS
- Controls to add
- Procedures to enhance
- Documentation to include

## 4. COMPLIANCE SCORE
- Overall compliance percentage (0-100%)
- Compliance by regulation
- Critical gaps vs minor gaps

Provide actionable validation results."""

        return prompt

    def _parse_access_response(self, response: str, process_name: str) -> Dict:
        """Parse and structure the access management response."""
        return {
            "process_name": process_name,
            "access_analysis": response,
            "sections": self._extract_sections(response),
            "timestamp": self._get_timestamp()
        }

    def _check_compliance(self, validation_response: str) -> bool:
        """Check if content is compliant based on validation response."""
        response_lower = validation_response.lower()
        if 'non-compliant' in response_lower or 'critical gap' in response_lower:
            return False
        if '100%' in validation_response or '95%' in validation_response:
            return True
        if 'fully compliant' in response_lower:
            return True
        return False

"""Agent 10: end-user computing (EUC) and endpoint management in the SOP pipeline.

When a process selects the "euc" specialist, adds an endpoint deployment analysis
and SOP appendix. Advice to Khalid runs in Claude Code as the reema-agent10-euc
subagent, whose protocol is this one plus a closing. Nothing is executed against
tenants, devices or directories.
"""

from typing import Dict, List

from .base_agent import BaseAgent
from ..utils.handoffs import payload_json
from ..utils.logger import logger


class EUCAgent(BaseAgent):
    AGENT_NAME = "Agent 10"
    AGENT_ROLE = "End-User Computing & Endpoint Management Specialist"
    CONFIG_KEY = "euc_agent"

    # The patch appendix, shared with the Claude Code generate request (scripts/claude_code_generate.py).
    APPENDIX_SECTIONS = (
        ("Deployment Ring Plan", "Table of rings with purpose, entry criteria, sizing rule, soak period and promotion gate"),
        ("Maintenance Windows and Change Freezes", "Window rules in Asia/Riyadh time and freeze periods to confirm"),
        ("Deployment Runbook", "Numbered steps with expected results and validation checks"),
        ("Rollback and Kill Switch", "Rollback or uninstall path with duration, kill-switch steps, and an explicit "
                                     "warning before any irreversible action"),
        ("Change Record Requirements", "Title, business justification, scope, implementation plan, test evidence, "
                                       "rollback plan, risk and impact rating, schedule, communication plan, approvers"),
        ("Compliance Reporting and KPIs", "Metric definitions, data sources and reporting cadence"),
        ("Escalation and Communications", "Escalation path, owners and bilingual communication points"),
    )
    APPENDIX_RULES = ('Keep "[to confirm]" markers for organization-specific values. Do not include credentials, '
                      "tenant identifiers or real user data. Format with tables and numbered lists suitable for SOP "
                      "inclusion.")

    @classmethod
    def appendix_outline(cls, marker):
        return "\n\n".join(f"{marker}{title.upper() if marker == '## ' else title}\n- {detail}"
                             for title, detail in cls.APPENDIX_SECTIONS)

    @classmethod
    def check_appendix(cls, text):
        """A patch appendix written in Claude Code: a valid section body with every required ### heading."""
        import re
        from ..utils.documents import validate_body
        validate_body(text)
        headings = {h.strip().casefold() for h in re.findall(r"(?m)^###\s+(.+?)\s*$", text)}
        missing = [title for title, _ in cls.APPENDIX_SECTIONS if title.casefold() not in headings]
        if missing:
            raise ValueError("The patch appendix is missing these ### headings: " + ", ".join(missing))

    async def analyze_endpoint_requirements(self, process_name: str, standards: List[str]) -> Dict:
        """Phase 2: endpoint deployment, rollback and change requirements for a process."""
        logger.agent_start(self.name, f"Analyzing endpoint requirements for {process_name}")
        try:
            response = await self._call_claude(
                messages=[{"role": "user", "content": self._build_endpoint_analysis_prompt(process_name, standards)}],
                system=self._build_system_prompt())
            logger.agent_complete(self.name, f"Endpoint analysis for {process_name}")
            return {
                "process_name": process_name,
                "endpoint_analysis": response,
                "sections": self._extract_sections(response),
                "timestamp": self._get_timestamp(),
            }
        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def generate_endpoint_content(self, process_name: str, endpoint_requirements: Dict) -> str:
        """Phase 3b: endpoint deployment appendix for the SOP draft."""
        logger.agent_start(self.name, f"Generating endpoint content for {process_name}")
        try:
            response = await self._call_claude(
                messages=[{"role": "user", "content": self._build_endpoint_content_prompt(process_name, endpoint_requirements)}],
                system=self._build_system_prompt())
            logger.agent_complete(self.name, f"Endpoint content for {process_name}")
            return response
        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_endpoint_analysis_prompt(self, process_name: str, standards: List[str]) -> str:
        return f"""Analyze end-user device requirements for the IT process: {process_name}

Applicable Standards/Regulations: {', '.join(standards)}

No fleet data, tenant configuration or calendar has been supplied. Do not invent device counts, group names, dates or product settings; write "[to confirm]" where the organization must supply a value.

## 1. SCOPE AND BLAST RADIUS
- Device types and populations in scope (including shared, kiosk and airport devices) and what is out of scope
- Business units and services affected if a deployment fails

## 2. DEPLOYMENT RING STRATEGY
- Pilot, early, broad and critical/exception rings with entry criteria and target sizing rules
- Soak periods, promotion gates and deadline/grace-period principles

## 3. MAINTENANCE WINDOWS AND CALENDAR
- Asia/Riyadh windows, Sunday–Thursday work week, 24/7 operations
- Change freezes around Ramadan, Hajj, Umrah seasons and Eid (dates to confirm)

## 4. ROLLBACK, KILL SWITCH AND IRREVERSIBLE STEPS
- Rollback or uninstall path and expected duration per change type
- Kill switch (pause ring, unassign, expire deployment)
- Irreversible actions (BitLocker recovery key loss, feature update past its rollback window, wipe or retire) and required warnings

## 5. TOOLING AND PACKAGING CONSIDERATIONS
- Platform responsibilities (Intune, MECM/co-management, Windows Update for Business/Autopatch, WSUS) marked as needing verification for the organization's versions and licensing
- Packaging, detection rules, supersedence and third-party patch handling

## 6. CHANGE ENABLEMENT
- Standard, normal and emergency change criteria, CAB evidence and out-of-band/zero-day handling

## 7. COMPLIANCE REPORTING AND METRICS
- Patch compliance %, mean time to patch, deployment success rate, top failed installs; definitions only, no invented results

## 8. COMMUNICATIONS AND ESCALATION
- Bilingual (Arabic/English) user and management communications, escalation path and owners

## 9. OPEN QUESTIONS
- Facts the organization must confirm before this SOP can be approved"""

    def _build_endpoint_content_prompt(self, process_name: str, endpoint_requirements: Dict) -> str:
        return f"""Generate endpoint deployment content for the SOP: {process_name}

Based on this endpoint analysis:
{payload_json(endpoint_requirements)}

Create professional SOP appendix sections:

{self.appendix_outline("## ")}

{self.APPENDIX_RULES}"""

    def _build_system_prompt(self) -> str:
        """Build the endpoint-engineering protocol shared with the reema-agent10-euc subagent."""
        return """You are Agent 10, a senior Endpoint Management / End-User Computing (EUC) Infrastructure Engineer and IT Service Management specialist with 15+ years in large, regulated enterprises (aviation-grade uptime, 24/7 operations, distributed sites, and airport, kiosk and shared devices).

You support an IT Section Manager who owns Patch Management, Image Management, Software Distribution, RPA, and end-user device technology coordination. Treat the user as a peer, not a beginner.

**Domain expertise:**
- Endpoint platforms: Microsoft Intune, MECM/SCCM (co-management, workloads), Windows Autopilot, WSUS / Windows Update for Business / Windows Autopatch, Entra ID and hybrid join, Group Policy vs. CSP/Settings Catalog, macOS (Intune/Jamf), iOS and Android Enterprise.
- Patch management: monthly Patch Tuesday cadence, out-of-band and zero-day response, deployment rings (pilot, early, broad, critical/exception), deadlines and grace periods, third-party patching, compliance reporting, rollback and uninstall paths.
- Image management: reference image build (MDT/OSD task sequences), thin vs. thick images, driver packs, servicing and in-place upgrades, feature-update planning, Windows 10 to 11 readiness, BitLocker and hardware baselines.
- Software distribution: packaging (MSI, MSIX, Win32/.intunewin, PSADT), detection rules, supersedence, dependencies, silent install switches, legacy App-V, license-aware deployment.
- Scripting and automation: production-quality PowerShell (idempotent, logged), Graph API, KQL/Log Analytics, Proactive Remediations, RPA hand-offs.
- Security and compliance: CIS/Microsoft security baselines, Defender for Endpoint, ASR, LAPS, compliance policies, Conditional Access dependencies, vulnerability-to-patch SLAs.
- ITSM (ITIL 4): change enablement (standard/normal/emergency), CAB submissions, incident and major incident, problem management and RCA, service catalog, SLA/OLA/KPI design, CMDB hygiene, vendor governance and SOW/SLA review.

**Operating protocol:**
1. Frame before advising. For any non-trivial request, open with a short problem frame: objective and success criteria; scope and out of scope; constraints and assumptions (flag any you had to make); risks and blast radius (device and user counts, business units). If a critical fact is missing and a wrong guess is costly, ask one targeted question instead of guessing.
2. Reversibility first. Every recommendation that changes endpoints states the pilot/ring strategy and target group size; the rollback or uninstall path and how long it takes; the kill switch (pause ring, unassign, expire deployment); and what is irreversible (for example BitLocker recovery key loss, a feature update past its rollback window, wipe or retire), with an explicit warning before it.
3. Push back directly. If a request is risky, non-standard or contradicts good practice, say so plainly in one or two lines and offer the safer alternative. No flattery and no hedging filler.
4. Show the reasoning that drives the decision, briefly. Prefer tables and numbered steps over prose.
5. Verify, don't invent. Product behavior, licensing and feature availability change often, and you cannot browse documentation or query tenants here. Mark version- or licensing-dependent statements as needing verification and name the Microsoft Learn or vendor documentation to check. Never fabricate cmdlets, CSP paths, registry keys or Graph endpoints.
6. Advisory only. You cannot run scripts or touch production tenants, devices or Active Directory. Provide scripts for the user to review, explain them and include a -WhatIf or dry-run mode. Never include credentials, tenant secrets or real user data.

**Output standards:**
- Scripts: PowerShell 5.1-compatible unless told otherwise; #Requires, comment-based help, parameter validation, try/catch, a transcript or log at a defined path, and exit codes compatible with Intune/MECM detection.
- Change requests: title, reason/business justification, scope (device count, groups), implementation plan, test evidence, rollback plan, risk and impact rating, schedule/maintenance window, communication plan, approvers.
- Runbooks and KB articles: purpose, prerequisites, numbered steps with expected results, validation, rollback, escalation path, owner, review date.
- RCA: timeline, impact, root cause (5 Whys), contributing factors, corrective vs. preventive actions with owners and dates.
- Status and management updates: bottom line first, then RAG status, key metrics, risks, decisions needed.
- Use metrics where possible (patch compliance %, mean time to patch, deployment success rate, top 10 failed installs, image build time, ticket deflection), calculated only from supplied figures.

**Context:**
- Saudi Arabian enterprise: Asia/Riyadh (UTC+3), work week Sunday to Thursday. Plan maintenance windows, change freezes and communications around business peaks such as Ramadan, Hajj, Umrah seasons and Eid holidays; treat exact dates as needing confirmation.
- Communications may need to be bilingual (Arabic/English) and suitable for senior management."""

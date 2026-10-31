"""Faisal (Review & Quality Agent) - Validates and ensures content quality."""

from typing import Dict, List
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.quality import assess_all
from ..utils.quality import parse_json_response, parse_fenced_json_response, UnparsedReplyError
from ..utils.documents import (CorrectionAssessment, ExistingSopAssessment, LocatedFinding,
                               section_map, locate_findings, sha)
import json


class ReviewAgent(BaseAgent):
    """
    Faisal (Review & Quality Agent)

    Responsibilities:
    - Reviews generated content for accuracy
    - Checks consistency and completeness
    - Validates against ITIL/ITOM standards
    - Suggests improvements and refinements
    - Ensures all required sections are present
    - Verifies technical accuracy
    """

    AGENT_NAME = "Agent 4"
    AGENT_ROLE = "Review & Quality Agent"
    CONFIG_KEY = "review_agent"
    KNOWLEDGE_FILE = "faisal_review_knowledge_ENHANCED.md"
    # Shared with scripts/claude_code_review.py, so the API and Claude Code reviews get the same brief.
    EXISTING_SOP_INSTRUCTIONS = (
        "This is a finished SOP already in use. Find only real problems, each tied to one section: "
        "outdated content (superseded tools, versions, standards or practices), missing steps in a procedure, "
        "vague sections (no owner, timing, threshold or verifiable action), and template gaps inside a section "
        "(for example a RACI table or KPI target that is absent). Use category outdated, missing_step, vague, "
        "template_gap or other. Every issue needs a unique exact quote within its section body; omit start/end "
        "unless the quote repeats. Give an actionable correction. Critical and major issues block use. "
        "Never invent a location or claim compliance.")

    def __init__(self):
        super().__init__()

        # Alias for backward compatibility
        self.review_knowledge = self.knowledge_base

        # Quality thresholds (from config or defaults)
        self.quality_threshold = self.get_config_value("quality_threshold", 85)
        self.completeness_threshold = 90

    async def review_existing(self, content: str) -> Dict:
        """Read-only review of a finished SOP: located, categorized findings; no score or rewrite."""
        logger.agent_start(self.name, "Reviewing a finished SOP")
        profile = config_manager.document_profile
        locations = section_map(content, profile)
        if not locations:
            raise ValueError("This SOP has no top-level sections (## headings or Word Heading 1) to review")

        def located(result):
            # The category is advisory metadata; identity and location use the shared contract.
            return [{**finding, "category": item.category}
                    for item in result.issues
                    for finding in locate_findings(content, [item.model_dump(include=set(LocatedFinding.model_fields))], profile)]

        def validate_excerpt(result, offset, part):
            if offset is not None and any(not offset <= i["start"] < i["end"] <= offset + len(part) for i in located(result)):
                raise ValueError("Review finding is outside its assessed excerpt")
        results, coverage = await assess_all(self, content, ExistingSopAssessment,
            self.EXISTING_SOP_INSTRUCTIONS + " Section locations:\n" + json.dumps(locations),
            result_validator=validate_excerpt)
        issues = list({item["finding_id"]: item for result in results for item in located(result)}.values())
        logger.agent_complete(self.name, f"Finished-SOP review - {len(issues)} findings")
        return {"review_contract": "existing_v1", "document_sha256": sha(content), "issues": issues,
                "summaries": [result.summary for result in results], "coverage": coverage,
                "section_locations": locations, "verification": "unverified"}

    async def recheck_corrections(self, content: str, findings: List[Dict], require_complete: bool = True,
                                  finished_sop: bool = False) -> Dict:
        profile = config_manager.document_profile
        locations = section_map(content, profile, require_complete=require_complete)
        targets = {f["section_id"] for f in findings}
        if not targets <= set(locations):
            raise ValueError("Correction recheck refers to a missing section")
        data = {"original_findings": findings, "revised_sections": {
            key: content[locations[key]["body_start"]:locations[key]["end"]] for key in sorted(targets)}}
        prompt = ("Recheck EVERY original finding against the revised sections. Do not assume a requested edit fixed it. "
                  "For each, give resolved/open, rationale and an exact supporting quote in the same revised section. "
                  "Return only the JSON object, with no text before or after it, matching:\n"
                  + json.dumps(CorrectionAssessment.model_json_schema())
                  + "\nCORRECTION DATA:\n" + json.dumps(data))
        response = await self._reply([{"role": "user", "content": prompt}], system=self._build_system_prompt())
        try:
            parsed = (parse_fenced_json_response if finished_sop else parse_json_response)(response, CorrectionAssessment)
        except ValueError as error:
            raise UnparsedReplyError(str(error), response) from None
        result = parsed.validate_against(content, findings, profile, require_complete)
        return {**result.model_dump(), "document_sha256": sha(content), "verification": "model_assessed"}

    def _build_system_prompt(self) -> str:
        """Build system prompt for review agent."""
        system_prompt = """You are Agent 4, an expert Quality Assurance reviewer for IT documentation with expertise in:
- ITIL v4 framework and IT Service Management best practices
- ISO 20000, ISO 27001, and other IT standards
- Technical writing and documentation standards
- Process documentation quality assessment
- Compliance and regulatory requirements

Your role is to:
1. Review SOP documents for completeness, accuracy, and quality
2. Validate alignment with ITIL and other IT standards
3. Check for technical accuracy and consistency
4. Identify gaps, errors, or areas for improvement
5. Provide constructive feedback and specific recommendations
6. Assign objective quality scores based on defined criteria

Be thorough, objective, and constructive in your reviews."""

        return self._inject_knowledge(
            system_prompt,
            "You have 100% domain expertise in quality assurance, review methodologies, and validation frameworks. Use this knowledge for thorough reviews:"
        )








"""Faisal (Review & Quality Agent) - Validates and ensures content quality."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.quality import Assessment, assess_all
from ..utils.quality import parse_json_response, UnparsedReplyError
from ..utils.documents import (LocatedAssessment, CorrectionAssessment, ExistingSopAssessment, LocatedFinding,
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
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

        # Alias for backward compatibility
        self.review_knowledge = self.knowledge_base

        # Quality thresholds (from config or defaults)
        self.quality_threshold = self.get_config_value("quality_threshold", 85)
        self.completeness_threshold = 90

    async def review_content(self, content: str) -> Dict:
        """
        Review SOP content and provide quality assessment.

        Args:
            content: SOP document content to review

        Returns:
            Dictionary containing review results, quality score, and feedback
        """
        logger.agent_start(self.name, "Reviewing SOP content")

        try:
            locations = section_map(content, config_manager.document_profile)
            def validate_excerpt(result, offset, part):
                located = locate_findings(content, [i.model_dump() for i in result.issues], config_manager.document_profile)
                if offset is not None and any(not offset <= i["start"] < i["end"] <= offset + len(part) for i in located):
                    raise ValueError("Review finding is outside its assessed excerpt")
            results, coverage = await assess_all(self, content, LocatedAssessment,
                "Review technical accuracy, completeness, standards evidence, clarity, RACI, procedures, and document control. "
                "Every issue needs a unique exact quote within its section body. Omit start/end to resolve its location locally; "
                "if the quote repeats, supply exact absolute zero-based start/end offsets. Every issue also needs "
                "a section_id and an actionable correction. Critical and major issues block. Never invent a location. "
                "Section locations:\n" + json.dumps(locations), result_validator=validate_excerpt)
            score = min(result.quality_score for result in results)
            from ..knowledge.retrieval import chunks
            parts = chunks(content, config_manager.system_config.review_chunk_chars)
            for result, (offset, part) in zip(results, parts):
                located = locate_findings(content, [i.model_dump() for i in result.issues], config_manager.document_profile)
                if any(not offset <= item["start"] < item["end"] <= offset + len(part) for item in located):
                    raise ValueError("Review finding is outside its assessed excerpt")
            issues = locate_findings(content, [item.model_dump() for result in results for item in result.issues], config_manager.document_profile)
            feedback = [item for result in results for item in result.recommendations]
            needs_revision = score < self.quality_threshold or any(result.decision != "acceptable" for result in results) or any(item["blocking"] for item in issues)
            review_data = {"quality_score": score, "issues": issues, "feedback": feedback,
                           "recommendations": feedback, "needs_revision": needs_revision,
                           "approval_status": "REQUIRES_REVISION" if needs_revision else "APPROVED",
                           "refined_content": None, "coverage": coverage,
                           "assessments": [result.model_dump() for result in results]}
            review_data["document_sha256"] = sha(content)
            review_data["section_locations"] = locations
            review_data["review_contract"] = "located_v1"

            logger.agent_complete(
                self.name,
                f"Review complete - Quality Score: {review_data.get('quality_score', 0)}"
            )

            return review_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

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
            "This is a finished SOP already in use. Find only real problems, each tied to one section: "
            "outdated content (superseded tools, versions, standards or practices), missing steps in a procedure, "
            "vague sections (no owner, timing, threshold or verifiable action), and template gaps inside a section "
            "(for example a RACI table or KPI target that is absent). Use category outdated, missing_step, vague, "
            "template_gap or other. Every issue needs a unique exact quote within its section body; omit start/end "
            "unless the quote repeats. Give an actionable correction. Critical and major issues block use. "
            "Never invent a location or claim compliance. Section locations:\n" + json.dumps(locations),
            result_validator=validate_excerpt)
        issues = list({item["finding_id"]: item for result in results for item in located(result)}.values())
        logger.agent_complete(self.name, f"Finished-SOP review - {len(issues)} findings")
        return {"review_contract": "existing_v1", "document_sha256": sha(content), "issues": issues,
                "summaries": [result.summary for result in results], "coverage": coverage,
                "section_locations": locations, "verification": "unverified"}

    async def recheck_corrections(self, content: str, findings: List[Dict], require_complete: bool = True) -> Dict:
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
        response = await self._call_claude([{"role": "user", "content": prompt}], system=self._build_system_prompt())
        try:
            parsed = parse_json_response(response, CorrectionAssessment)
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

    def _build_review_prompt(self, content: str) -> str:
        """Build the review prompt."""
        prompt = f"""Please conduct a comprehensive quality review of the following SOP document.

**REVIEW CRITERIA:**

### 1. Completeness (Weight: 25%)
- All 11 required sections present
- Adequate detail in each section
- No missing critical information
- Sufficient length (15-30 pages target)

### 2. Technical Accuracy (Weight: 25%)
- Correct ITIL terminology and concepts
- Accurate process descriptions
- Technically sound procedures
- Correct standards references

### 3. ITIL/Standards Alignment (Weight: 20%)
- Alignment with ITIL v4 framework
- Compliance with cited standards
- Best practices incorporated
- Framework terminology used correctly

### 4. Clarity & Usability (Weight: 15%)
- Clear, professional writing
- Logical structure and flow
- Actionable procedures
- Easy to follow and implement

### 5. Formatting & Structure (Weight: 10%)
- Professional formatting
- Consistent style
- Proper use of headings, tables, lists
- Good organization

### 6. Completeness of Roles & Procedures (Weight: 5%)
- Clear RACI matrix or role definitions
- Detailed step-by-step procedures
- Decision points identified
- Escalation paths defined

---

**DOCUMENT TO REVIEW:**

{content}

---

**REQUIRED OUTPUT FORMAT:**

## Quality Assessment Summary

**Overall Quality Score:** [0-100]

**Section Scores:**
- Completeness: [score]/100
- Technical Accuracy: [score]/100
- ITIL/Standards Alignment: [score]/100
- Clarity & Usability: [score]/100
- Formatting & Structure: [score]/100
- Roles & Procedures: [score]/100

## Detailed Findings

### Strengths
[List 3-5 major strengths]

### Issues Found
[List all issues categorized by severity: Critical, Major, Minor]

### Missing Elements
[List any required sections or content that is missing or incomplete]

### Technical Errors
[List any technical inaccuracies or incorrect information]

### Standards Compliance Issues
[List any deviations from ITIL or other standards]

## Recommendations for Improvement

[Provide 5-10 specific, actionable recommendations prioritized by impact]

## Approval Status

[APPROVED / APPROVED WITH MINOR CHANGES / REQUIRES REVISION]

Provide thorough, constructive feedback that will help improve the document to production quality."""

        return prompt

    def _parse_review_response(self, response: str, original_content: str) -> Dict:
        """Parse and structure the review response."""
        # Extract quality score
        quality_score = self._extract_quality_score(response)

        # Extract section scores
        section_scores = self._extract_section_scores(response)

        # Extract issues and recommendations
        issues = self._extract_issues(response)
        recommendations = self._extract_recommendations(response)

        # Determine if content needs revision
        approval_status = self._extract_approval_status(response)
        needs_revision = quality_score < self.quality_threshold or approval_status != "APPROVED"

        return {
            "quality_score": quality_score,
            "section_scores": section_scores,
            "issues": issues,
            "recommendations": recommendations,
            "needs_revision": needs_revision,
            "approval_status": approval_status,
            "full_review": response,
            "refined_content": original_content if not needs_revision else None,
            "feedback": recommendations
        }

    def _extract_quality_score(self, response: str) -> int:
        """Extract overall quality score from review."""
        import re

        # Look for "Overall Quality Score: XX"
        match = re.search(r'Overall Quality Score.*?(\d+)', response, re.IGNORECASE)
        if match:
            return int(match.group(1))

        raise ValueError("Reviewer returned no quality score")

    def _extract_section_scores(self, response: str) -> Dict[str, int]:
        """Extract section scores."""
        import re

        sections = {}
        section_pattern = r'(Completeness|Technical Accuracy|ITIL/Standards Alignment|Clarity & Usability|Formatting & Structure|Roles & Procedures):?\s*(\d+)'

        matches = re.findall(section_pattern, response, re.IGNORECASE)
        for section_name, score in matches:
            sections[section_name.strip()] = int(score)

        return sections

    def _extract_issues(self, response: str) -> List[Dict[str, str]]:
        """Extract issues from review."""
        issues = []
        in_issues_section = False
        current_severity = None

        for line in response.split('\n'):
            line_lower = line.lower()

            if 'issues found' in line_lower or 'technical errors' in line_lower:
                in_issues_section = True
                continue

            if in_issues_section:
                if 'critical' in line_lower:
                    current_severity = 'critical'
                elif 'major' in line_lower:
                    current_severity = 'major'
                elif 'minor' in line_lower:
                    current_severity = 'minor'
                elif line.strip().startswith('-') or line.strip().startswith('•'):
                    issue_text = line.strip().lstrip('-•').strip()
                    if issue_text:
                        issues.append({
                            "severity": current_severity or "unknown",
                            "description": issue_text
                        })
                elif line.strip().startswith('##'):
                    in_issues_section = False

        return issues

    def _extract_recommendations(self, response: str) -> List[str]:
        """Extract recommendations from review."""
        recommendations = []
        in_recommendations = False

        for line in response.split('\n'):
            if 'recommendations' in line.lower() or 'improvement' in line.lower():
                in_recommendations = True
                continue

            if in_recommendations:
                if line.strip().startswith('-') or line.strip().startswith('•') or line.strip()[0:1].isdigit():
                    rec_text = line.strip().lstrip('-•0123456789.').strip()
                    if rec_text and len(rec_text) > 10:
                        recommendations.append(rec_text)
                elif line.strip().startswith('##'):
                    in_recommendations = False

        return recommendations

    def _extract_approval_status(self, response: str) -> str:
        """Extract approval status from review."""
        response_lower = response.lower()

        if 'requires revision' in response_lower:
            return 'REQUIRES_REVISION'
        elif 'approved with minor changes' in response_lower:
            return 'APPROVED_WITH_CHANGES'
        elif 'approved' in response_lower:
            return 'APPROVED'

        return 'PENDING_REVIEW'

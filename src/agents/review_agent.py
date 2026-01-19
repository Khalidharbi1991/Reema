"""Faisal (Review & Quality Agent) - Validates and ensures content quality."""

from typing import Dict, List, Optional
from anthropic import Anthropic
from ..utils.logger import logger
from ..utils.config import config_manager


class ReviewAgent:
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

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config_manager.system_config.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key)
        self.name = "Faisal"
        self.model = config_manager.system_config.worker_model

        # Quality thresholds
        self.quality_threshold = 85
        self.completeness_threshold = 90

        logger.info("Review Agent initialized", agent=self.name)

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
            system_prompt = self._build_system_prompt()
            review_prompt = self._build_review_prompt(content)

            response = await self._call_claude(
                messages=[{"role": "user", "content": review_prompt}],
                system=system_prompt
            )

            review_data = self._parse_review_response(response, content)

            logger.agent_complete(
                self.name,
                f"Review complete - Quality Score: {review_data.get('quality_score', 0)}"
            )

            return review_data

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """Build system prompt for review agent."""
        return """You are an expert Quality Assurance reviewer for IT documentation with expertise in:
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

{content[:15000]}

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
        needs_revision = quality_score < self.quality_threshold

        # Extract approval status
        approval_status = self._extract_approval_status(response)

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

        # Default to 75 if not found
        logger.warning("Could not extract quality score, defaulting to 75", agent=self.name)
        return 75

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

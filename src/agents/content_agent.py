"""Saad (Content Generation Agent) - Creates detailed SOP documentation."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.handoffs import payload_json
from ..utils.documents import SectionDraft, SectionPatch, section_map, sha
from ..utils.quality import parse_json_response, is_structured_response
from ..utils.diagrams import SequenceFlow, GraphFlow
import json


class ContentAgent(BaseAgent):
    """
    Saad (Content Generation Agent)

    Responsibilities:
    - Creates detailed SOP content (15-30 pages)
    - Writes process descriptions, roles, responsibilities
    - Generates step-by-step procedures
    - Creates process flowcharts and diagrams (draw.io XML generation)
    - Develops all 11 sections of the SOP document
    """

    AGENT_NAME = "Agent 3"
    AGENT_ROLE = "Content Generation Agent"
    CONFIG_KEY = "content_agent"
    KNOWLEDGE_FILE = "saad_content_knowledge_ENHANCED.md"
    DEFAULT_MAX_TOKENS = 8192  # Higher token limit for content generation
    DEFAULT_TEMPERATURE = 0.7

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)

        # Alias for backward compatibility
        self.content_knowledge = self.knowledge_base

        # Load SOP template
        self.sop_template = self._load_sop_template()

    def _load_sop_template(self) -> str:
        """Load the SOP template."""
        try:
            template_path = config_manager.system_config.templates_dir / "sop_template.md"
            if template_path.exists():
                with open(template_path, 'r') as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Could not load SOP template: {e}", agent=self.name)

        # Return default template structure
        return self._get_default_template()

    def _get_default_template(self) -> str:
        """Get default SOP template structure."""
        return """# {process_name} - Standard Operating Procedure

## Document Control
- **Document Title:** {process_name} SOP
- **Version:** 1.0
- **Date:** {date}
- **Owner:** {owner}
- **Status:** Draft

---

## Table of Contents
1. Introduction
2. Definitions & Acronyms
3. Roles & Responsibilities
4. Process Overview
5. Detailed Procedures
6. Process Flow Diagrams
7. Key Performance Indicators (KPIs)
8. Tools & Systems
9. Compliance & Standards
10. Appendices
11. Document Control

---

## 1. Introduction

### 1.1 Purpose
{purpose}

### 1.2 Scope
{scope}

### 1.3 Objectives
{objectives}

---

## 2. Definitions & Acronyms
{definitions}

---

## 3. Roles & Responsibilities
{roles}

---

## 4. Process Overview
{overview}

---

## 5. Detailed Procedures
{procedures}

---

## 6. Process Flow Diagrams
{flowcharts}

---

## 7. Key Performance Indicators (KPIs)
{kpis}

---

## 8. Tools & Systems
{tools}

---

## 9. Compliance & Standards
{compliance}

---

## 10. Appendices
{appendices}

---

## 11. Document Control
{document_control}
"""

    async def generate_sop(
        self, process_name: str, research_data: Dict
    ) -> str:
        """
        Generate complete SOP document.

        Args:
            process_name: Name of the IT process
            research_data: Research findings from Research and Standards agents

        Returns:
            Complete SOP document in Markdown format
        """
        logger.agent_start(self.name, f"Generating SOP for {process_name}")

        try:
            system_prompt = self._build_system_prompt()
            content_prompt = self._build_content_prompt(process_name, research_data)

            response = await self._call_claude(
                messages=[{"role": "user", "content": content_prompt}],
                system=system_prompt
            )

            # Structure the response into a complete SOP
            if is_structured_response(response):
                response = parse_json_response(response, SectionDraft).assemble(process_name, config_manager.document_profile)
            sop_document = self._format_sop_document(response, process_name)

            logger.agent_complete(self.name, f"SOP generation for {process_name}")
            return sop_document

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def refine_content(
        self, content: str, feedback: List[str]
    ) -> str:
        """
        Refine content based on review feedback.

        Args:
            content: Original content
            feedback: List of feedback items

        Returns:
            Refined content
        """
        logger.agent_start(self.name, "Refining content based on feedback")

        try:
            system_prompt = "You are an expert technical writer specializing in IT documentation. Refine the provided content based on the feedback given."

            refinement_prompt = f"""Please refine the following SOP document based on this feedback:

FEEDBACK:
{chr(10).join(f"- {item}" for item in feedback)}

ORIGINAL DOCUMENT:
{content}

Please provide the complete refined document addressing all feedback points."""

            response = await self._call_claude(
                messages=[{"role": "user", "content": refinement_prompt}],
                system=system_prompt
            )

            logger.agent_complete(self.name, "Content refinement")
            return response

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def revise_sections(self, content: str, findings: List[Dict]) -> str:
        """Apply an exact, digest-bound section patch; all other bytes survive."""
        profile = config_manager.document_profile
        locations = section_map(content, profile, require_complete=True)
        targets = {finding["section_id"] for finding in findings}
        if not targets or not targets <= set(locations):
            raise ValueError("Targeted revision needs valid located findings")
        data = {"base_document_sha256": sha(content), "findings": findings,
                "sections": {key: {**locations[key], "body": content[locations[key]["body_start"]:locations[key]["end"]]}
                             for key in sorted(targets)}}
        prompt = ("Correct only these sections and address each finding. Preserve citations, control IDs, constraints and full specialist material. "
                  "Do not add top-level headings or claim approvals. Return JSON matching:\n"
                  + json.dumps(SectionPatch.model_json_schema()) + "\nREVISION DATA:\n" + payload_json(data))
        response = await self._call_claude([{"role": "user", "content": prompt}], system=self._build_system_prompt())
        return parse_json_response(response, SectionPatch).apply(content, targets, profile)

    def _build_system_prompt(self) -> str:
        """Build system prompt for content generation."""
        system_prompt = """You are Agent 3, an expert technical writer and IT Service Management specialist.

Your expertise includes:
- Creating comprehensive Standard Operating Procedures (SOPs)
- Writing clear, professional IT documentation
- Structuring information logically and accessibly
- Creating detailed step-by-step procedures
- Developing RACI matrices and role descriptions
- Creating professional draw.io flowcharts and process flow diagrams (.drawio XML)
- Generating draw.io XML with proper mxCell elements, style strings, and mxGeometry
- Designing swimlane diagrams, decision trees, and multi-phase process flows

Guidelines for SOP creation:
1. Use professional, clear language
2. Be specific and actionable
3. Include all necessary details (15-30 pages target)
4. Follow standard SOP structure (11 sections)
5. Use tables, lists, and formatting for clarity
6. Include examples where helpful
7. Ensure completeness and accuracy
8. Reference relevant standards and frameworks

Create documentation that is immediately usable by IT teams."""

        return self._inject_knowledge(
            system_prompt,
            "You have 100% domain expertise in technical writing, SOP creation, and documentation best practices. Use this knowledge to create professional documentation:"
        )

    def _build_content_prompt(
        self, process_name: str, research_data: Dict
    ) -> str:
        """Build the content generation prompt."""
        research_summary = self._extract_research_summary(research_data)
        compliance_summary = self._extract_compliance_summary(research_data)

        prompt = f"""Create a comprehensive Standard Operating Procedure (SOP) document for: {process_name}

**Target Length:** 15-30 pages
**Format:** Professional SOP following industry standards

**Research Findings:**
{research_summary}

**Compliance Requirements:**
{compliance_summary}

**Required SOP Structure:**

### 1. INTRODUCTION (2-3 pages)
- Purpose and objectives
- Scope and boundaries
- Target audience
- Document applicability

### 2. DEFINITIONS & ACRONYMS (1-2 pages)
- Complete glossary of IT terms
- Acronym definitions
- Process-specific terminology

### 3. ROLES & RESPONSIBILITIES (2-3 pages)
- RACI matrix with Activity followed by role columns; exactly one A and at least one R for each activity (R/A is allowed)
- Detailed role descriptions
- Authority levels
- Escalation paths

### 4. PROCESS OVERVIEW (2-3 pages)
- High-level process description
- Process triggers and inputs
- Process outputs and deliverables
- Success criteria

### 5. DETAILED PROCEDURES (5-8 pages)
- Step-by-step instructions for each major activity
- Decision points and criteria
- Exception handling
- Sub-processes
- Detailed workflows

### 6. PROCESS FLOW DIAGRAMS (2-3 pages)
- Text descriptions of process flows
- Swimlane diagram descriptions
- Decision tree descriptions
- Integration points

### 7. KEY PERFORMANCE INDICATORS (1-2 pages)
- Process metrics and KPIs
- Measurement methods
- Target values
- Reporting frequency
- Dashboard requirements

### 8. TOOLS & SYSTEMS (1-2 pages)
- Required ITSM tools
- System integrations
- Access requirements
- Training needs

### 9. COMPLIANCE & STANDARDS (2-3 pages)
- ITIL/framework alignment
- Regulatory requirements
- Audit requirements
- Documentation requirements

### 10. APPENDICES (2-3 pages)
- Templates and forms
- Checklists
- Reference materials
- Examples and scenarios

### 11. DOCUMENT CONTROL (1 page)
- Version history
- Approval signatures
- Review schedule
- Distribution list

**IMPORTANT:**
- Make this a complete, production-ready SOP
- Include specific, actionable content
- Use professional formatting (headings, tables, lists)
- Provide sufficient detail to achieve 15-30 pages
- Include real-world examples and scenarios
- Reference ITIL and other standards throughout

Generate the complete SOP document now."""

        return prompt + ("\nReturn only a section draft JSON matching:\n" + json.dumps(SectionDraft.model_json_schema())
            + "\nAssemble exactly these configured section IDs; bodies may contain headings at level three and below:\n"
            + payload_json([s.model_dump() for s in config_manager.document_profile.sections])
            + "\nInclude each applicable control ID in square brackets in EVERY target section listed in the control register. "
            "A reference demonstrates traceability, not compliance. Identify missing evidence. "
            "Optional diagrams use a reema-flow fenced JSON sequence or bounded forward graph with lanes and labelled decisions:\n"
            + json.dumps(SequenceFlow.model_json_schema()) + "\nGRAPH SCHEMA:\n" + json.dumps(GraphFlow.model_json_schema()))

    def _extract_research_summary(self, research_data: Dict) -> str:
        """Legacy method name: retain the full research handoffs, including metadata."""
        if not research_data:
            return "No research data available."
        return payload_json({key: value for key, value in research_data.items() if key != "standards"})

    def _extract_compliance_summary(self, research_data: Dict) -> str:
        """Retain every standards field and source identity, without prefix truncation."""
        return payload_json(research_data.get("standards", {})) if research_data else "No compliance data available."

    def _format_sop_document(self, content: str, process_name: str) -> str:
        """Format the generated content into a proper SOP document."""
        # Add metadata header
        from datetime import datetime

        header = f"""---
title: {process_name} - Standard Operating Procedure
version: 1.0
date: {datetime.now().strftime('%Y-%m-%d')}
status: Draft
generated_by: IT Process Documentation System
---

"""
        return header + content

    async def generate_drawio_flowchart(
        self, process_name: str, process_steps: Dict
    ) -> str:
        """
        Generate a draw.io XML flowchart for the given IT process.

        Uses Saad's draw.io mastery knowledge (Section 3) to create
        professional .drawio XML with proper mxCell elements, Customer
        brand color coding, decision diamonds, and multi-phase layout.

        Args:
            process_name: Name of the IT process (e.g., "Incident Management")
            process_steps: Dict with phase names as keys and step lists as values

        Returns:
            Valid .drawio XML string ready to be saved as a .drawio file
        """
        logger.agent_start(self.name, f"Generating draw.io flowchart for {process_name}")

        try:
            system_prompt = self._build_system_prompt()

            flowchart_prompt = f"""Generate a complete, valid draw.io XML flowchart for: {process_name}

**Process Steps:**
{chr(10).join(f"Phase: {phase} - Steps: {', '.join(steps)}" for phase, steps in process_steps.items())}

**Requirements:**
1. Output ONLY valid .drawio XML (mxfile > diagram > mxGraphModel > root > mxCell elements)
2. Use house palette colors: Green #1F3A5F, Gold #FFC107
3. Phase colors: Phase 1=#1565C0, Phase 2=#E65100, Phase 3=#2E7D32, Phase 4=#6A1B9A
4. Start terminators: green (#28A745), End terminators: red (#DC3545)
5. Decision diamonds: Amber (#FFC107) with D1, D2, D3 labels
6. YES paths: green (#28A745), NO paths: red (#DC3545)
7. Standard flow arrows: dark blue (#003366), strokeWidth=2
8. Process shapes: 160x60px, Decision diamonds: 200x100px, Terminators: 120x40px
9. Vertical spacing: 40px between shapes
10. Each phase on a separate <diagram> page
11. Use orthogonal edge routing (edgeStyle=orthogonalEdgeStyle)
12. Include proper mxGeometry with x, y, width, height for every shape
13. All mxCell IDs must be unique
14. Include root cells id="0" and id="1" parent="0" in every diagram

Generate the complete .drawio XML now."""

            response = await self._call_claude(
                messages=[{"role": "user", "content": flowchart_prompt}],
                system=system_prompt
            )

            # Extract XML from response (strip any markdown formatting)
            xml_content = response.strip()
            if xml_content.startswith("```"):
                xml_content = xml_content.split("\n", 1)[1]
                if xml_content.endswith("```"):
                    xml_content = xml_content[:-3].strip()

            logger.agent_complete(self.name, f"draw.io flowchart for {process_name}")
            return xml_content

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

"""Saad (Content Generation Agent) - Creates detailed SOP documentation."""

from typing import Dict, List
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.handoffs import payload_json
from ..utils.documents import SectionBody, SectionDraft, SectionPatch, section_map, sha, validate_body
from ..utils.quality import parse_json_response, parse_fenced_json_response, structured_call, UnparsedReplyError
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

    def __init__(self):
        super().__init__()

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
        Assemble the SOP one configured section at a time, from the text written for each section.

        Sections run in order, and each one is checked as it arrives.

        Args:
            process_name: Name of the IT process
            research_data: Planning data (the control register)

        Returns:
            Complete SOP document in Markdown format
        """
        logger.agent_start(self.name, f"Generating SOP for {process_name}")

        try:
            profile = config_manager.document_profile
            shared = self._build_shared_context(process_name, research_data)
            controls = self._section_controls(research_data)
            written, sections = {}, []
            for number, section in enumerate(profile.sections, 1):
                prompt = self._build_section_prompt(shared, number, section, written, controls.get(section.id, []))

                def check(result, expected=section.id):
                    if result.section_id != expected:
                        raise ValueError(f"Reply was for section {result.section_id!r}")
                    validate_body(result.body)

                try:
                    result = await structured_call(self, prompt, SectionBody, check)
                except (ValueError, RuntimeError) as error:
                    category = ValueError if isinstance(error, ValueError) else RuntimeError
                    raise category(f"Section {number} ({section.title}) failed: {error}") from error
                written[section.id] = result.body
                sections.append(result)
                logger.info(f"Section {number}/{len(profile.sections)} written: {section.title}", agent=self.name)

            document = SectionDraft(sections=sections).assemble(process_name, profile)
            sop_document = self._format_sop_document(document, process_name)

            logger.agent_complete(self.name, f"SOP generation for {process_name}")
            return sop_document

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    FINISHED_SOP_SCOPE = (
        "This is a finished SOP already in use. Make only the change each finding asks for. Do not add requirements, "
        "roles, tools, systems, contacts, time limits or sources that the finding does not ask for, and do not add "
        "source or control IDs. State the change once, in the single most fitting place in the section; do not repeat "
        "it in other paragraphs, tables or notes. Keep all other wording in the section exactly as it is. ")

    async def revise_sections(self, content: str, findings: List[Dict], require_complete: bool = True,
                              finished_sop: bool = False) -> str:
        """Apply an exact, digest-bound section patch; all other bytes survive.

        require_complete=False revises a finished SOP that does not follow the 11-section profile.
        """
        profile = config_manager.document_profile
        locations = section_map(content, profile, require_complete=require_complete)
        targets = {finding["section_id"] for finding in findings}
        if not targets or not targets <= set(locations):
            raise ValueError("Targeted revision needs valid located findings")
        data = {"base_document_sha256": sha(content), "findings": findings,
                "sections": {key: {**locations[key], "body": content[locations[key]["body_start"]:locations[key]["end"]]}
                             for key in sorted(targets)}}
        prompt = ((self.FINISHED_SOP_SCOPE if finished_sop else "")
                  + "Correct only these sections and address each finding. Preserve citations, control IDs, constraints and full specialist material. "
                  "Do not add top-level headings or claim approvals. Return only the JSON object, with no text "
                  "before or after it, matching:\n"
                  + json.dumps(SectionPatch.model_json_schema()) + "\nREVISION DATA:\n" + payload_json(data))
        response = await self._reply([{"role": "user", "content": prompt}], system=self._build_system_prompt())
        try:
            patch = (parse_fenced_json_response if finished_sop else parse_json_response)(response, SectionPatch)
        except ValueError as error:
            raise UnparsedReplyError(str(error), response) from None
        return patch.apply(content, targets, profile, require_complete)

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
3. Include all necessary details (the whole SOP targets 15-30 pages; each request writes one section to its own length target)
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

    # Written early and shared with every later section so terms and RACI stay consistent.
    FOUNDATION_SECTIONS = ("sec-definitions", "sec-roles")
    DIAGRAM_SECTIONS = ("sec-procedures", "sec-flow")
    # Shared with the Claude Code generate request (scripts/claude_code_generate.py).
    SECTION_RULES = ("Write only this section's body: no level one or two headings (the section heading is added "
                     "automatically); use level three and below. Be specific and actionable; use tables, numbered "
                     "steps and real-world examples where useful. Reference relevant standards. Never invent "
                     "signatures or approvals.")

    def _build_shared_context(self, process_name: str, research_data: Dict) -> str:
        """Context repeated verbatim at the start of every section request."""
        profile = config_manager.document_profile
        low, high = config_manager.system_config.page_target
        outline = [{"number": number, "id": section.id, "title": section.display_title or section.title}
                   for number, section in enumerate(profile.sections, 1)]
        return (f"Standard Operating Procedure (SOP) under preparation: {process_name}\n"
                f"Whole-document target: {low}-{high} pages across {len(outline)} sections, "
                "written one section per request.\n\n"
                f"**Research Findings:**\n{self._extract_research_summary(research_data)}\n\n"
                f"**Compliance Requirements:**\n{self._extract_compliance_summary(research_data)}\n\n"
                "ALL SECTIONS:\n" + payload_json(outline))

    @staticmethod
    def _section_controls(research_data: Dict) -> Dict[str, List[str]]:
        """Applicable control IDs per target section, from the standards control register."""
        standards = research_data.get("standards") if isinstance(research_data, dict) else None
        register = standards.get("control_register") if isinstance(standards, dict) else None
        controls = register.get("controls", []) if isinstance(register, dict) else []
        targets = {}
        for control in controls:
            if isinstance(control, dict) and control.get("applicability") == "applicable":
                for section_id in control.get("target_sections", []):
                    targets.setdefault(section_id, []).append(control["id"])
        return targets

    def _build_section_prompt(self, shared: str, number: int, section, written: Dict[str, str],
                              controls: List[str]) -> str:
        """Request one section body; the shared context stays first so prompts share a prefix."""
        profile = config_manager.document_profile
        prompt = shared
        foundation = {key: written[key] for key in self.FOUNDATION_SECTIONS if key in written}
        if foundation:
            prompt += ("\n\nALREADY WRITTEN SECTIONS (reuse these terms, roles and RACI exactly):\n"
                       + payload_json(foundation))
        prompt += (f"\n\nWRITE SECTION {number} of {len(profile.sections)}: "
                   f"{section.display_title or section.title} (id {section.id}).\n"
                   f"Instructions: {section.instructions}\n")
        if section.target_pages:
            prompt += f"Target length: {section.target_pages[0]}-{section.target_pages[1]} pages.\n"
        prompt += self.SECTION_RULES + "\n"
        if controls:
            prompt += ("Include each of these applicable control IDs in square brackets in this section: "
                       + ", ".join(controls) + ". A reference demonstrates traceability, not compliance. "
                       "Identify missing evidence.\n")
        if section.id in self.DIAGRAM_SECTIONS:
            prompt += ("Optional diagrams use a reema-flow fenced JSON sequence or bounded forward graph with lanes "
                       "and labelled decisions:\n" + json.dumps(SequenceFlow.model_json_schema())
                       + "\nGRAPH SCHEMA:\n" + json.dumps(GraphFlow.model_json_schema()) + "\n")
        return (prompt + "Return only JSON matching:\n" + json.dumps(SectionBody.model_json_schema())
                + f'\nSet section_id to "{section.id}".')

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


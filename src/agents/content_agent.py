"""Saad (Content Generation Agent) - Creates detailed SOP documentation."""

from typing import Dict, List, Optional
from anthropic import Anthropic
from ..utils.logger import logger
from ..utils.config import config_manager


class ContentAgent:
    """
    Saad (Content Generation Agent)

    Responsibilities:
    - Creates detailed SOP content (15-30 pages)
    - Writes process descriptions, roles, responsibilities
    - Generates step-by-step procedures
    - Creates process flowcharts and diagrams (text descriptions)
    - Develops all 11 sections of the SOP document
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config_manager.system_config.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key)
        self.name = "Saad"
        self.model = config_manager.system_config.worker_model

        # Load SOP template
        self.sop_template = self._load_sop_template()

        logger.info("Content Agent initialized", agent=self.name)

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

    def _build_system_prompt(self) -> str:
        """Build system prompt for content generation."""
        return """You are an expert technical writer and IT Service Management specialist.

Your expertise includes:
- Creating comprehensive Standard Operating Procedures (SOPs)
- Writing clear, professional IT documentation
- Structuring information logically and accessibly
- Creating detailed step-by-step procedures
- Developing RACI matrices and role descriptions
- Writing process flows and diagrams descriptions

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
- RACI matrix (Responsible, Accountable, Consulted, Informed)
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

        return prompt

    def _extract_research_summary(self, research_data: Dict) -> str:
        """Extract summary from research data."""
        if not research_data:
            return "No research data available."

        summary_parts = []

        if "research" in research_data:
            research = research_data["research"]
            if isinstance(research, dict) and "raw_research" in research:
                summary_parts.append("ITIL/IT Research:\n" + research["raw_research"][:2000])

        return "\n\n".join(summary_parts) if summary_parts else "Research data available but not parsed."

    def _extract_compliance_summary(self, research_data: Dict) -> str:
        """Extract summary from compliance data."""
        if not research_data:
            return "No compliance data available."

        if "standards" in research_data:
            standards = research_data["standards"]
            if isinstance(standards, dict) and "compliance_analysis" in standards:
                return "Compliance Analysis:\n" + standards["compliance_analysis"][:2000]

        return "Compliance data available but not parsed."

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

    async def _call_claude(self, messages: List[Dict], system: str = "") -> str:
        """Make a call to Claude API."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,  # Higher token limit for content generation
                system=system,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}", agent=self.name)
            raise

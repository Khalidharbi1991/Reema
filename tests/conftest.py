"""Shared test fixtures for REEMA test suite."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import tempfile
import os


@pytest.fixture(autouse=True)
def deny_live_http(monkeypatch):
    """The test suite cannot send model prompts or other HTTP requests."""
    import httpx
    def denied(*args, **kwargs):
        raise AssertionError("Live HTTP is forbidden in tests; use a fake provider")
    async def denied_async(*args, **kwargs):
        raise AssertionError("Live HTTP is forbidden in tests; use a fake provider")
    monkeypatch.setattr(httpx.Client, "send", denied)
    monkeypatch.setattr(httpx.AsyncClient, "send", denied_async)


@pytest.fixture
def mock_api_key():
    """Provide a test API key."""
    return "test-api-key-12345"


@pytest.fixture
def temp_knowledge_dir(tmp_path):
    """Create a temporary knowledge directory with sample knowledge files."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    # Create sample knowledge files
    agents = {
        "taif_research_knowledge_ENHANCED.md": "# Taif Research KB\nITIL best practices...",
        "mohammad_standards_knowledge_ENHANCED.md": "# Mohammad Standards KB\nISO 27001...",
        "rakan_access_knowledge_ENHANCED.md": "# Rakan Access KB\nIAM lifecycle...",
        "saad_content_knowledge_ENHANCED.md": "# Saad Content KB\nSOP writing...",
        "layla_data_knowledge_complete.md": "# Layla Data KB\nPower BI...",
        "faisal_review_knowledge_ENHANCED.md": "# Faisal Review KB\nQuality scoring...",
        "bee_format_knowledge_ENHANCED.md": "# Bee Format KB\nPDF formatting...",
        "ahmad_secretary_knowledge_ENHANCED.md": "# Ahmad Secretary KB\nCoordination...",
    }

    for filename, content in agents.items():
        (knowledge_dir / filename).write_text(content)

    return knowledge_dir


@pytest.fixture
def mock_config(tmp_path, temp_knowledge_dir):
    """Mock the config_manager with temp directories."""
    mock_system_config = MagicMock()
    mock_system_config.anthropic_api_key = "test-api-key"
    mock_system_config.project_root = tmp_path
    mock_system_config.output_dir = tmp_path / "output"
    mock_system_config.config_dir = tmp_path / "config"
    mock_system_config.templates_dir = tmp_path / "templates"
    mock_system_config.knowledge_dir = temp_knowledge_dir
    mock_system_config.leader_model = "claude-sonnet-4-6"
    mock_system_config.worker_model = "claude-sonnet-4-6"
    mock_system_config.default_formats = ["pdf", "docx", "markdown", "html"]
    mock_system_config.page_target = (15, 30)

    mock_cm = MagicMock()
    mock_cm.system_config = mock_system_config
    mock_cm.get_agent_config.return_value = {
        "name": "TestAgent",
        "role": "Test Role",
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "temperature": 0.5,
    }
    mock_cm.get_process_definition.return_value = {
        "name": "Incident Management",
        "category": "ITIL Core",
        "complexity": "medium",
    }
    mock_cm.get_standards_for_process.return_value = ["ITIL v4", "ISO 20000"]
    mock_cm.process_definitions = {
        "incident_management": {"name": "Incident Management", "category": "ITIL Core"}
    }

    return mock_cm


@pytest.fixture
def mock_anthropic_client():
    """Mock the Anthropic client to avoid real API calls."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="## Test Response\n\nThis is a test response from Claude.")]
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def sample_sop_content():
    """Provide sample SOP content for testing."""
    return """---
title: Incident Management - Standard Operating Procedure
version: 1.0
date: 2024-01-15
status: Draft
generated_by: IT Process Documentation System
---

# Incident Management - Standard Operating Procedure

## 1. Introduction

### 1.1 Purpose
This document defines the Incident Management process.

### 1.2 Scope
Applies to all IT service incidents.

## 2. Definitions & Acronyms
- **ITIL**: Information Technology Infrastructure Library
- **SLA**: Service Level Agreement
- **MTTR**: Mean Time to Resolve

## 3. Roles & Responsibilities

| Role | Responsible | Accountable | Consulted | Informed |
|------|------------|-------------|-----------|----------|
| Service Desk | X | | | |
| Incident Manager | | X | | |

## 4. Process Overview
The incident management process follows ITIL v4 guidelines.

## 5. Detailed Procedures
Step 1: Incident Detection
Step 2: Incident Logging
Step 3: Categorization
Step 4: Prioritization
Step 5: Investigation
Step 6: Resolution
Step 7: Closure

## 6. Process Flow Diagrams
Detection -> Logging -> Classification -> Resolution -> Closure

## 7. Key Performance Indicators (KPIs)
- Mean Time to Resolve (MTTR): < 4 hours
- First Contact Resolution Rate: > 70%

## 8. Tools & Systems
- ServiceNow
- Jira Service Management

## 9. Compliance & Standards
- ITIL v4 aligned
- ISO 20000 compliant

## 10. Appendices
Template forms and checklists.

## 11. Document Control
Version 1.0 - Initial draft
"""


@pytest.fixture
def sample_research_data():
    """Provide sample research data structure."""
    return {
        "research": {
            "raw_research": "ITIL v4 defines Incident Management as the process to restore normal service operation as quickly as possible...",
            "key_findings": ["ITIL v4 alignment", "Lifecycle approach"]
        },
        "standards": {
            "compliance_analysis": "ISO 20000 compliance requirements met. ITIL v4 framework alignment confirmed.",
            "applicable_standards": ["ITIL v4", "ISO 20000"]
        },
        "data": {
            "analytics_framework": "KPI Dashboard: MTTR, FCR, SLA Compliance, Reopening Rate...",
            "kpis": ["MTTR", "FCR", "SLA Compliance"]
        },
        "access": {
            "access_analysis": "Access requirements: Role-based access to ITSM tool, incident manager elevated permissions...",
            "access_requirements": ["RBAC", "Least Privilege"]
        }
    }


@pytest.fixture
def sample_review_result():
    """Provide sample review result."""
    return {
        "quality_score": 88,
        "section_scores": {
            "Completeness": 90,
            "Technical Accuracy": 85,
            "ITIL/Standards Alignment": 90,
        },
        "issues": [],
        "recommendations": ["Add more detail to KPIs section"],
        "needs_revision": False,
        "approval_status": "APPROVED",
        "refined_content": None,
        "feedback": ["Add more detail to KPIs section"],
        "full_review": "Quality review complete."
    }


@pytest.fixture
def sample_review_result_failing():
    """Provide sample review result that fails quality threshold."""
    return {
        "quality_score": 72,
        "section_scores": {"Completeness": 65},
        "issues": [{"severity": "major", "description": "Missing sections"}],
        "recommendations": ["Add RACI matrix", "Expand procedures"],
        "needs_revision": True,
        "approval_status": "REQUIRES_REVISION",
        "refined_content": None,
        "feedback": ["Add RACI matrix", "Expand procedures"],
        "full_review": "Quality below threshold."
    }

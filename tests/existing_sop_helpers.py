"""Synthetic finished SOPs for the review/revise tests. No customer content."""

import json

from src.utils.validation import REQUIRED_SECTIONS

BODIES = {
    "Introduction": "This SOP covers synthetic incident handling.",
    "Definitions & Acronyms": "- **SLA**: Service Level Agreement",
    "Roles & Responsibilities": "| Role | R | A |\n|---|---|---|\n| Service Desk | X | |\n| Incident Manager | | X |",
    "Process Overview": "Incidents are logged, triaged and resolved.",
    "Detailed Procedures": "### 5.1 Logging\nLog every incident in the tool.\n\n### 5.2 Escalation\nEscalate when needed.",
    "Process Flow Diagrams": "Log, triage, resolve, close.",
    "Key Performance Indicators": "Mean time to resolve under 8 hours.",
    "Tools & Systems": "ServiceNow version 2019.",
    "Compliance & Standards": "Aligned with ITIL 4 practices.",
    "Appendices": "Appendix A: contact list.",
    "Document Control": "Version 1.0, owner IT Service Desk Manager.",
}


def template_sop(bodies=None):
    bodies = {**BODIES, **(bodies or {})}
    parts = ["# Synthetic Incident SOP"]
    for number, title in enumerate(REQUIRED_SECTIONS, 1):
        parts.append(f"## {number}. {title}\n\n{bodies[title]}")
    return "\n\n".join(parts) + "\n"


NON_TEMPLATE_SOP = """# Synthetic Laptop Handover

## Purpose

Hand laptops to new starters.

## Steps

### Collect
Collect the device from stores.

### Escalation
Escalate to the team lead if stock is short.

## Contacts

Service Desk extension 1234.
"""


def build_docx(path, sections, *, image_in=None, title="Synthetic Incident SOP"):
    """A small Word SOP: Heading 1 per section, a branded header and one table."""
    from docx import Document
    from docx.shared import RGBColor
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "SYNTHETIC BRAND HEADER"
    doc.add_paragraph(title, style="Title")
    for heading, paragraphs in sections:
        doc.add_heading(heading, level=1)
        for text in paragraphs:
            if text.startswith("|"):
                rows = [row.strip("|").split("|") for row in text.splitlines() if "---" not in row]
                table = doc.add_table(rows=len(rows), cols=len(rows[0]))
                for r, row in enumerate(rows):
                    for c, value in enumerate(row):
                        table.cell(r, c).text = value.strip()
            elif text.startswith("### "):
                doc.add_heading(text[4:], level=2)
            else:
                run = doc.add_paragraph().add_run(text)
                run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        if image_in == heading:
            from docx.oxml import OxmlElement
            doc.paragraphs[-1]._p.append(OxmlElement("w:pict"))
    doc.save(str(path))
    return path


DOCX_SECTIONS = [
    ("1. Introduction", ["This SOP covers synthetic incident handling."]),
    ("2. Escalation", ["### 2.1 Triggers", "Escalate when needed.", "| Level | Owner |\n|---|---|\n| L1 | Desk |"]),
    ("3. Document Control", ["Version 1.0."]),
]


def assessment(*issues, summary="Synthetic assessment"):
    return json.dumps({"issues": list(issues), "summary": summary})


def issue(section_id, quote, *, category="vague", severity="major", description="Too vague", action="Add a threshold"):
    return {"severity": severity, "description": description, "section_id": section_id, "quote": quote,
            "action": action, "category": category}


def _mocked(worker, reply):
    from unittest.mock import AsyncMock
    worker._call_claude = AsyncMock(side_effect=reply if callable(reply) or isinstance(reply, list) else [reply])
    return worker


def stand_in_review(reply):
    """The Claude Code review worker type, with its assessments from a mock instead of excerpts.json."""
    from src.agents.file_workers import FileReviewWorker
    from src.agents.review_agent import ReviewAgent

    class StandIn(FileReviewWorker):
        review_existing = ReviewAgent.review_existing
    return _mocked(StandIn("unused"), reply)


def stand_in_patch(reply):
    """The Claude Code patch worker type, with its patch from a mock instead of patch.json."""
    from src.agents.file_workers import FilePatchWorker
    return _mocked(FilePatchWorker("unused"), reply)


def stand_in_recheck(reply):
    """The Claude Code recheck worker type, with its recheck from a mock instead of recheck.json."""
    from src.agents.file_workers import FileRecheckWorker
    from src.agents.review_agent import ReviewAgent

    class StandIn(FileRecheckWorker):
        recheck_corrections = ReviewAgent.recheck_corrections
    return _mocked(StandIn("unused"), reply)


def confirm(path):
    """The confirm-read token a prepare step prints for PATH; tests pass it as Khalid's yes."""
    import hashlib
    from pathlib import Path
    from src.utils.read_gate import read_token
    return read_token(hashlib.sha256(Path(path).read_bytes()).hexdigest())

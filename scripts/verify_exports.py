"""Offline synthetic export acceptance test. Never calls a model or reads references."""
import argparse
import asyncio
import json
from pathlib import Path

SAMPLE = """# Service Restoration Procedure

## 1. Introduction
This procedure explains how the service desk records, assigns, and resolves an interruption.
The service owner remains accountable for restoration and for reviewing the closure evidence.

## 2. Definitions & Acronyms
- Incident: an interruption to an agreed service.
- SLA: service level agreement.

## 3. Roles & Responsibilities
The following matrix assigns accountability to each activity. R means responsible, A accountable,
C consulted, and I informed. An empty cell means the role has no assigned responsibility.

| Activity | Service owner | Service desk | Technician |
| --- | --- | --- | --- |
| Record incident | A | R | I |
| Restore service | A | C | R |
| Review closure | A | R | |

## 4. Process Overview
Record the interruption, assess its impact, assign a technician, verify restoration with the requester,
and retain the evidence. Escalate when an assigned activity cannot meet the agreed service target.

## 5. Detailed Procedures
1. Record the affected service, observed symptoms, requester, and detection time.
2. Confirm impact and urgency with the requester and assign the responsible technician.
3. Document each diagnostic action and its result in the incident record.
4. Obtain authorization for any proposed change before applying it.
5. Confirm restoration with the requester and record the verification evidence.
6. Close the record only when the owner accepts the documented outcome.

## 6. Process Flow Diagrams
Record -> Assess -> Assign -> Diagnose -> Restore -> Verify -> Close

## 7. Key Performance Indicators
| Measure | Calculation | Review cadence |
| --- | --- | --- |
| Resolution time | Closure timestamp minus detection timestamp | Weekly |
| Reopened incidents | Reopened records divided by closed records | Monthly |

## 8. Tools & Systems
Use the organization's approved incident register. Access is limited to assigned staff and authorized reviewers.

## 9. Compliance & Standards
Review this procedure against the organization's approved ITIL and ISO 20000 control mappings before adoption.
This example does not assert certification or regulatory compliance.

## 10. Appendices
Record template: service, detection time, impact, urgency, owner, action log, restoration evidence, closure decision.

## 11. Document Control
Version 1.0. The process owner reviews proposed changes and retains a record of approved revisions.
"""


async def verify(directory, formats=("markdown", "html", "docx", "pdf")):
    from src.agents.format_agent import FormatAgent
    from src.utils.validation import validate_sop, validate_output_files
    from docx import Document
    validate_sop(SAMPLE)
    formatter = FormatAgent()
    formatter.output_dir = directory
    outputs = await formatter.convert_to_formats(SAMPLE, list(formats), "Service Restoration")
    validate_output_files(outputs, list(formats))
    if "docx" in outputs:
        doc = Document(outputs["docx"])
        assert any("Document Control" in p.text for p in doc.paragraphs)
        table = doc.tables[0]
        assert table.cell(3, 2).text == "R" and table.cell(3, 3).text == ""
    if "pdf" in outputs:
        from pypdf import PdfReader
        reader = PdfReader(outputs["pdf"])
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        assert "Document Control" in text and "Review closure" in text
        assert len(reader.pages) >= 2
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", action="append", dest="formats")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(verify(args.output, args.formats or ("markdown", "html", "docx", "pdf"))), indent=2))

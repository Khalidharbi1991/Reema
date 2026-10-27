"""Export representative synthetic fixtures locally. No models, references or approval."""

import argparse
import asyncio
import json
from pathlib import Path

from scripts.verify_exports import SAMPLE


def representative_content():
    flow = {"title": "Service restoration workflow", "steps": [
        {"id": "record", "label": "Record the affected service and observed symptoms", "owner": "Service desk"},
        {"id": "assess", "label": "Assess impact urgency and the escalation threshold", "owner": "Incident coordinator"},
        {"id": "assign", "label": "Assign an authorized technician and confirm ownership", "owner": "Service owner"},
        {"id": "diagnose", "label": "Record diagnostic actions and proposed corrective changes", "owner": "Assigned technician"},
        {"id": "verify", "label": "Verify restoration with the requester and retain evidence", "owner": "Technician and requester"},
        {"id": "close", "label": "Review the decision record before closing the incident", "owner": "Service owner"}]}
    content = SAMPLE.replace("Record -> Assess -> Assign -> Diagnose -> Restore -> Verify -> Close",
                             "```reema-flow\n" + json.dumps(flow) + "\n```")
    rows = ["| Record | Evidence retained | Review owner |", "| --- | --- | --- |"]
    for number in range(1, 35):
        rows.append(f"| Incident {number:02d} | The action log records the decision, outcome and verification evidence for service restoration. | Service owner |")
    content = content.replace("Record template: service, detection time, impact, urgency, owner, action log, restoration evidence, closure decision.",
        "Retain the following review records. The table continues across pages with its header repeated.\n\n" + "\n".join(rows))
    content = content.replace("Version 1.0.", "Version 1.0. Status pending human approval.")
    return content


async def verify(directory, formats):
    from src.utils.validation import validate_sop
    from src.utils.export_quality import inspect_export
    from src.formatters import DOCXFormatter, HTMLFormatter, MarkdownFormatter
    content = representative_content()
    validate_sop(content)
    types = {"docx": DOCXFormatter, "html": HTMLFormatter, "markdown": MarkdownFormatter}
    if "pdf" in formats:
        from src.formatters import PDFFormatter
        types["pdf"] = PDFFormatter
    from src.utils.validation import FORMATS
    outputs, checks = {}, {}
    directory.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        path = directory / ("Service_Restoration_Example" + FORMATS[fmt])
        if path.exists():
            raise FileExistsError("Use a new QA directory to preserve previous artifacts")
        await types[fmt]().convert(content, path, "Service Restoration")
        checks[fmt] = inspect_export(fmt, path, content)
        outputs[fmt] = str(path.resolve())
    (directory / ("checks-" + "-".join(formats) + ".json")).write_text(json.dumps(checks, indent=2) + "\n")
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", action="append", choices=["pdf", "docx", "html", "markdown"], dest="formats")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(verify(args.output, args.formats or ["pdf", "docx", "html", "markdown"])), indent=2))

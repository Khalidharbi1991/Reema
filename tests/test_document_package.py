"""Located document behavior with synthetic model responses and no live HTTP."""

import json
import re
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.agents import ContentAgent, FormatAgent
from src.utils.config import config_manager, ConfigManager
from src.utils.documents import (ControlRegister, SectionDraft, SectionPatch, section_map, sha, control_coverage, locate_findings, CorrectionAssessment)
from src.utils.diagrams import extract_flows
from src.utils.export_quality import inspect_export
from tests.test_phase01 import catalog


def control(**overrides):
    item = {"id": "CTRL-LOG", "framework": "ITIL v4", "clause": "Local evidence retention",
            "requirement": "Retain the decision record", "applicability": "applicable",
            "rationale": "The workflow records a decision", "target_sections": ["sec-procedures"], "evidence": []}
    return {**item, **overrides}


def finding(content, quote="Step 1: Incident Detection", **overrides):
    start = content.index(quote)
    return {"severity": "major", "description": "Define an explicit owner", "section_id": "sec-procedures",
            "quote": quote, "start": start, "end": start + len(quote), "action": "Assign the service desk", **overrides}


def flow():
    return {"title": "Service restoration", "steps": [
        {"id": "record", "label": "Record the incident", "owner": "Service desk"},
        {"id": "restore", "label": "Restore and verify the service", "owner": "Technician"}]}


def patch_data(content, section_id="sec-procedures", body="The service desk records the incident."):
    locations = section_map(content, config_manager.document_profile, require_complete=True)
    return {"base_document_sha256": sha(content), "patches": [{"section_id": section_id,
        "base_section_sha256": locations[section_id]["sha256"], "body": body}]}


@pytest.mark.parametrize("change", ["duplicate", "swap"])
def test_profile_keeps_mandatory_sections_and_unique_ids(catalog, change):
    data = catalog.document_profile.model_dump()
    if change == "duplicate":
        data["sections"][0]["id"] = data["sections"][1]["id"]
    else:
        data["sections"][0]["id"], data["sections"][1]["id"] = data["sections"][1]["id"], data["sections"][0]["id"]
    import yaml
    (catalog.system_config.config_dir / "document_profile.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="mandatory sections"):
        ConfigManager(catalog.system_config)


def test_control_coverage_is_located_and_does_not_claim_compliance(sample_sop_content):
    profile = config_manager.document_profile
    register = ControlRegister(controls=[control()])
    missing = control_coverage(sample_sop_content + "\n[CTRL-LOG]", register, {}, profile)
    assert missing["errors"]  # A reference in the wrong section cannot satisfy coverage.
    example = sample_sop_content.replace("Step 1:", "```text\n[CTRL-LOG]\n```\nStep 1:")
    assert control_coverage(example, register, {}, profile)["errors"]
    content = sample_sop_content.replace("Step 1:", "[CTRL-LOG] Step 1:")
    result = control_coverage(content, register, {}, profile)
    assert not result["errors"] and result["warnings"]
    assert result["controls"][0]["evidence_status"] == "missing"
    assert result["controls"][0]["semantic_coverage"] == "requires_human_verification"


@pytest.mark.parametrize("change", ["unknown", "location", "hash", "quote", "target", "duplicate"])
def test_control_evidence_cannot_invent_provenance(change):
    source = {"source": "policy.md", "location": "paragraph 2", "sha256": "a" * 64, "text": "Retain the decision record."}
    evidence = {"source_id": "SRC-policy", **{k: source[k] for k in ("source", "location", "sha256")}, "quote": source["text"]}
    item = control(evidence=[evidence])
    if change == "unknown": evidence["source_id"] = "SRC-absent"
    if change == "location": evidence["location"] = "paragraph 3"
    if change == "hash": evidence["sha256"] = "b" * 64
    if change == "quote": evidence["quote"] = "Invented requirement"
    if change == "target": item["target_sections"] = ["unknown-section"]
    controls = [item, item] if change == "duplicate" else [item]
    with pytest.raises(ValueError):
        ControlRegister(controls=controls).validate_sources({"SRC-policy": source}, config_manager.document_profile)


@pytest.mark.asyncio
def requested_section(messages):
    return re.search(r'Set section_id to "(sec-[a-z0-9-]+)"', messages[-1]["content"]).group(1)


async def test_actual_content_assembles_in_config_order_and_preserves_payload_tail():
    agent = ContentAgent(api_key="")
    async def reply(messages, system=""):
        return json.dumps({"section_id": requested_section(messages), "body": "Content for " + requested_section(messages)})
    agent._call_claude = AsyncMock(side_effect=reply)
    document = await agent.generate_sop("Example", {"research": {"raw_research": "x" * 15000 + "UNIQUE_TAIL"}})
    assert list(section_map(document, config_manager.document_profile, require_complete=True)) == [s.id for s in config_manager.document_profile.sections]
    prompts = [call.args[0][0]["content"] for call in agent._call_claude.await_args_list]
    assert len(prompts) == len(config_manager.document_profile.sections)
    assert all("UNIQUE_TAIL" in prompt for prompt in prompts)


@pytest.mark.parametrize("change", ["missing", "duplicate", "empty", "heading"])
def test_section_assembly_rejects_incomplete_or_structurally_unsafe_data(change):
    items = [{"section_id": s.id, "body": "Body"} for s in config_manager.document_profile.sections]
    if change == "missing": items.pop()
    if change == "duplicate": items.append(items[0])
    if change == "empty": items[0]["body"] = " "
    if change == "heading": items[0]["body"] = "## Extra section\nText"
    with pytest.raises(ValueError):
        SectionDraft(sections=items).assemble("Example", config_manager.document_profile)


@pytest.mark.asyncio
async def test_targeted_revision_keeps_every_unaffected_byte_and_specialist_tail(sample_sop_content):
    content = sample_sop_content + "\n\n## Specialist material\n" + "Evidence " * 1500 + "FINAL_SPECIALIST_TAIL\n"
    data = patch_data(content)
    agent = ContentAgent(api_key="")
    agent._call_claude = AsyncMock(return_value=json.dumps(data))
    result = await agent.revise_sections(content, locate_findings(content, [finding(content)], config_manager.document_profile))
    old = section_map(content, config_manager.document_profile)
    target = old["sec-procedures"]
    assert result.startswith(content[:target["body_start"]])
    assert result.endswith(content[target["end"]:])
    assert "FINAL_SPECIALIST_TAIL" in result and "The service desk records" in result


@pytest.mark.parametrize("change", ["document", "section", "wrong_target", "extra", "heading"])
def test_stale_or_overbroad_section_patch_is_rejected(sample_sop_content, change):
    data = patch_data(sample_sop_content)
    if change == "document": data["base_document_sha256"] = "0" * 64
    if change == "section": data["patches"][0]["base_section_sha256"] = "0" * 64
    if change == "wrong_target": data["patches"][0]["section_id"] = "sec-tools"
    if change == "extra": data["patches"].append(deepcopy(data["patches"][0]))
    if change == "heading": data["patches"][0]["body"] = "## Replace another section"
    with pytest.raises(ValueError):
        SectionPatch.model_validate(data).apply(sample_sop_content, {"sec-procedures"}, config_manager.document_profile)


def test_major_findings_block_even_high_score_and_ids_are_stable(sample_sop_content):
    issues = locate_findings(sample_sop_content, [finding(sample_sop_content)], config_manager.document_profile)
    assert issues == locate_findings(sample_sop_content, [finding(sample_sop_content)], config_manager.document_profile)
    assert issues[0]["blocking"] and issues[0]["finding_id"].startswith("F-")
    from src.utils.handoffs import ReviewResult
    with pytest.raises(ValueError, match="Contradictory"):
        ReviewResult.from_legacy({"quality_score": 99, "approval_status": "APPROVED", "issues": issues})


def test_unique_quotes_resolve_locally_but_ambiguous_or_half_specified_locations_fail(sample_sop_content):
    issue = finding(sample_sop_content)
    issue.pop("start")
    issue.pop("end")
    located = locate_findings(sample_sop_content, [issue], config_manager.document_profile)[0]
    assert sample_sop_content[located["start"]:located["end"]] == issue["quote"]
    ambiguous = sample_sop_content.replace(issue["quote"], issue["quote"] + "\n" + issue["quote"])
    with pytest.raises(ValueError, match="exactly one"):
        locate_findings(ambiguous, [issue], config_manager.document_profile)
    issue["start"] = located["start"]
    with pytest.raises(ValueError, match="invalid section"):
        locate_findings(sample_sop_content, [issue], config_manager.document_profile)


@pytest.mark.parametrize("change", ["missing", "duplicate", "location", "quote"])
def test_correction_rechecks_cannot_drop_or_relocate_findings(sample_sop_content, change):
    findings = locate_findings(sample_sop_content, [finding(sample_sop_content)], config_manager.document_profile)
    entry = {"finding_id": findings[0]["finding_id"], "status": "resolved", "rationale": "Owner named", "section_id": "sec-procedures", "quote": findings[0]["quote"]}
    entries = [entry]
    if change == "missing": entries = []
    if change == "duplicate": entries.append(entry)
    if change == "location": entry["section_id"] = "sec-tools"
    if change == "quote": entry["quote"] = "No support"
    with pytest.raises(ValueError):
        CorrectionAssessment(corrections=entries).validate_against(sample_sop_content, findings, config_manager.document_profile)


@pytest.mark.parametrize("change", ["unknown_field", "too_many", "duplicate", "unclosed", "unicode"])
def test_sequence_diagram_validation_rejects_unsafe_or_unsupported_data(change):
    data = flow()
    if change == "unknown_field": data["url"] = "file:///etc/passwd"
    if change == "too_many": data["steps"] *= 4
    if change == "duplicate": data["steps"][1]["id"] = data["steps"][0]["id"]
    if change == "unicode": data["title"] = "Unsupported \u200b label"
    content = "```reema-flow\n" + json.dumps(data) + ("" if change == "unclosed" else "\n```\n")
    with pytest.raises(ValueError):
        extract_flows(content)


@pytest.mark.asyncio
async def test_diagrams_render_to_all_formats_and_exports_check_real_content(tmp_path, sample_sop_content):
    content = sample_sop_content.replace("Detection -> Logging -> Classification -> Resolution -> Closure",
        "```reema-flow\n" + json.dumps(flow()) + "\n```")
    from src.utils.validation import validate_sop
    validate_sop(content)  # A valid diagram is substantive content in its section.
    formatter = FormatAgent()
    formatter.output_dir = tmp_path
    outputs = await formatter.convert_to_formats(content, ["html", "docx", "pdf", "markdown"], "Synthetic Example")
    assert all(c["status"] == "passed" for c in formatter.last_export_checks.values())
    assert "<svg" in Path(outputs["html"]).read_text() and "&lt;svg" not in Path(outputs["html"]).read_text()
    from docx import Document
    assert len(Document(outputs["docx"]).inline_shapes) == 1
    Path(outputs["markdown"]).write_text("Valid file but missing document")
    with pytest.raises(ValueError, match="heading"):
        inspect_export("markdown", outputs["markdown"], content)


@pytest.mark.asyncio
async def test_shared_table_widths_and_docx_rows_keep_evidence_readable(tmp_path):
    from scripts.verify_document_package import representative_content
    from docx import Document
    from bs4 import BeautifulSoup
    content = representative_content()
    formatter = FormatAgent()
    formatter.output_dir = tmp_path
    outputs = await formatter.convert_to_formats(content, ["docx", "html"], "Example")
    doc = Document(outputs["docx"])
    table = doc.tables[-1]
    assert table.columns[1].width > table.columns[0].width * 2
    assert all(r._tr.xpath('./w:trPr/w:cantSplit') for r in table.rows)
    assert doc.styles['Caption'].font.bold is False
    soup = BeautifulSoup(Path(outputs["html"]).read_text(), 'html.parser')
    assert len(soup.find_all('colgroup')) == len(doc.tables)
    assert not any('accountable,' == p.text for p in doc.paragraphs)



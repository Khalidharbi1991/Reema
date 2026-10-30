"""Targeted revision of finished SOPs (`reema revise`). Mocked provider only."""

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from lxml import etree
from rich.console import Console
from typer.testing import CliRunner

from src.agents.content_agent import ContentAgent
from src.agents.leader_agent import LeaderAgent
from src.agents.review_agent import ReviewAgent
from src.utils.approvals import read_record
from src.utils.config import config_manager
from src.utils.documents import section_map, sha, assert_only_targets_changed
from src.utils.existing_sops import (load_sop, resolve_sections, instruction_findings, review_findings, W)
from tests.existing_sop_helpers import (template_sop, NON_TEMPLATE_SOP, build_docx, DOCX_SECTIONS, assessment, issue)

PROFILE = config_manager.document_profile


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "output_dir", tmp_path / "output")
    return tmp_path / "output"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patch_reply(content, bodies):
    locations = section_map(content, PROFILE)
    return json.dumps({"base_document_sha256": sha(content), "patches": [
        {"section_id": key, "body": body, "base_section_sha256": locations[key]["sha256"]} for key, body in bodies.items()]})


def recheck_reply(findings, quote, status="resolved"):
    return json.dumps({"corrections": [{"finding_id": f["finding_id"], "status": status, "rationale": "Checked",
                                        "section_id": f["section_id"], "quote": quote} for f in findings]})


def leader_with(content_reply, recheck):
    content, review = ContentAgent(api_key=""), ReviewAgent(api_key="")
    content._call_claude = AsyncMock(side_effect=content_reply if callable(content_reply) else [content_reply])
    review._call_claude = AsyncMock(side_effect=recheck if callable(recheck) else [recheck])
    leader = LeaderAgent(api_key="")
    leader.register_worker("ContentAgent", content)
    leader.register_worker("ReviewAgent", review)
    return leader, content, review


NEW_ESCALATION = "### 5.1 Logging\nLog every incident in the tool.\n\n### 5.2 Escalation\nEscalate P1 incidents to the Incident Manager within 15 minutes."


def test_instruction_resolves_by_title_or_sub_heading():
    content = template_sop()
    assert resolve_sections(content, PROFILE, "fix the escalation part in my incident SOP") == ["sec-procedures"]
    assert resolve_sections(content, PROFILE, "anything", ["Tools & Systems"]) == ["sec-tools"]
    assert resolve_sections(content, PROFILE, "anything", ["sec-kpis"]) == ["sec-kpis"]
    with pytest.raises(ValueError, match="--section"):
        resolve_sections(content, PROFILE, "make it better")
    with pytest.raises(ValueError, match="No section 'Budget'"):
        resolve_sections(content, PROFILE, "x", ["Budget"])


@pytest.mark.asyncio
async def test_markdown_revision_changes_only_the_target_section(tmp_path, output_root):
    path = tmp_path / "incident.md"
    path.write_text(template_sop())
    before = digest(path)
    source = load_sop(path)
    findings = instruction_findings(source.content, PROFILE, "Add a 15 minute P1 escalation rule", ["sec-procedures"])
    leader, content, review = leader_with(patch_reply(source.content, {"sec-procedures": NEW_ESCALATION}),
                                          lambda *a, **k: recheck_reply(findings, "within 15 minutes"))
    outputs = await leader.revise_existing(source, findings, allow_external_ai=True, origin={"instruction": "x"})
    revised = Path(outputs["markdown"]).read_text()
    assert revised == template_sop({"Detailed Procedures": NEW_ESCALATION})
    old, new = section_map(source.content, PROFILE), section_map(revised, PROFILE)
    assert all(source.content[old[k]["start"]:old[k]["end"]] == revised[new[k]["start"]:new[k]["end"]]
               for k in old if k != "sec-procedures")
    record = read_record(Path(leader.context["delivery"]["approval_record"]))
    assert record.status == "awaiting_human_approval" and record.reviewer is None and record.quality_score == 100
    run = Path(leader.context["run_dir"])
    assert "+Escalate P1 incidents" in (run / "changes.md").read_text()
    assert json.loads((run / "run.json").read_text())["full_profile_checks"] is True
    assert digest(path) == before
    assert content._call_claude.await_count == 1 and review._call_claude.await_count == 1


@pytest.mark.asyncio
async def test_patch_touching_another_section_is_refused(tmp_path, output_root):
    path = tmp_path / "incident.md"
    path.write_text(template_sop())
    source = load_sop(path)
    findings = instruction_findings(source.content, PROFILE, "Fix escalation", ["sec-procedures"])
    sneaky = patch_reply(source.content, {"sec-procedures": NEW_ESCALATION, "sec-tools": "ServiceNow Xanadu."})
    leader, _, review = leader_with(sneaky, "{}")
    with pytest.raises(ValueError, match="exactly the requested sections"):
        await leader.revise_existing(source, findings, allow_external_ai=True)
    review._call_claude.assert_not_awaited()
    run = Path(leader.context["run_dir"])
    assert json.loads((run / "run.json").read_text())["status"] == "failed" and not (run / "approval.json").exists()


def test_preservation_gate_catches_an_unaffected_change():
    content = template_sop()
    with pytest.raises(ValueError, match="unaffected section"):
        assert_only_targets_changed(content, content.replace("ServiceNow version 2019.", "Changed."), {"sec-procedures"}, PROFILE)
    with pytest.raises(ValueError, match="unaffected section"):
        assert_only_targets_changed(content, content.replace("# Synthetic Incident SOP", "# Renamed"), {"sec-procedures"}, PROFILE)


@pytest.mark.asyncio
async def test_open_blocking_finding_fails_the_run(tmp_path, output_root):
    path = tmp_path / "incident.md"
    path.write_text(template_sop())
    source = load_sop(path)
    findings = instruction_findings(source.content, PROFILE, "Fix escalation", ["sec-procedures"])
    leader, _, _ = leader_with(patch_reply(source.content, {"sec-procedures": NEW_ESCALATION}),
                               lambda *a, **k: recheck_reply(findings, "within 15 minutes", "open"))
    with pytest.raises(ValueError, match="remain open"):
        await leader.revise_existing(source, findings, allow_external_ai=True)
    assert not (Path(leader.context["run_dir"]) / "approval.json").exists()


@pytest.mark.asyncio
async def test_revision_requires_consent(tmp_path, output_root, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "allow_external_ai", False)
    path = tmp_path / "incident.md"
    path.write_text(template_sop())
    source = load_sop(path)
    findings = instruction_findings(source.content, PROFILE, "Fix escalation", ["sec-procedures"])
    leader, content, _ = leader_with("{}", "{}")
    with pytest.raises(PermissionError):
        await leader.revise_existing(source, findings)
    content._call_claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_template_sop_revises_with_relaxed_checks(tmp_path, output_root):
    path = tmp_path / "handover.md"
    path.write_text(NON_TEMPLATE_SOP)
    source = load_sop(path)
    [target] = resolve_sections(source.content, PROFILE, "fix the escalation part")
    findings = instruction_findings(source.content, PROFILE, "Name the stores contact", [target])
    body = "### Collect\nCollect the device from stores (contact: Stores Lead).\n\n### Escalation\nEscalate to the team lead if stock is short."
    leader, _, _ = leader_with(patch_reply(source.content, {target: body}),
                               lambda *a, **k: recheck_reply(findings, "Stores Lead"))
    outputs = await leader.revise_existing(source, findings, allow_external_ai=True)
    assert Path(outputs["markdown"]).read_text() == NON_TEMPLATE_SOP.replace(
        "Collect the device from stores.", "Collect the device from stores (contact: Stores Lead).")
    assert json.loads((Path(leader.context["run_dir"]) / "run.json").read_text())["full_profile_checks"] is False


def body_xml(path):
    from docx import Document
    return [etree.tostring(child) for child in Document(str(path)).element.body]


@pytest.mark.asyncio
async def test_docx_splice_keeps_other_sections_and_branding(tmp_path, output_root):
    path = build_docx(tmp_path / "incident.docx", DOCX_SECTIONS)
    before = digest(path)
    source = load_sop(path)
    [target] = resolve_sections(source.content, PROFILE, "fix the escalation part")
    findings = instruction_findings(source.content, PROFILE, "Add a P1 trigger", [target])
    body = "### 2.1 Triggers\nEscalate P1 incidents within 15 minutes.\n\n| Level | Owner |\n|---|---|\n| L1 | Desk |\n| L2 | Incident Manager |"
    leader, _, _ = leader_with(patch_reply(source.content, {target: body}),
                               lambda *a, **k: recheck_reply(findings, "within 15 minutes"))
    outputs = await leader.revise_existing(source, findings, allow_external_ai=True)
    original, spliced = body_xml(path), body_xml(outputs["docx"])
    # Title + section 1 (heading and paragraph) and the section 2 heading are byte-identical XML.
    assert spliced[:4] == original[:4]
    # Section 3 heading, paragraph and the final section properties are unchanged.
    assert spliced[-3:] == original[-3:]
    from docx import Document
    doc = Document(outputs["docx"])
    assert doc.sections[0].header.paragraphs[0].text == "SYNTHETIC BRAND HEADER"
    assert [p.text for p in doc.paragraphs if p.style.name == "Heading 2"] == ["2.1 Triggers"]
    assert doc.tables[0].rows[2].cells[1].text == "Incident Manager"
    reread = load_sop(outputs["docx"]).content
    assert "Escalate P1 incidents within 15 minutes." in reread and "Version 1.0." in reread
    assert digest(path) == before
    assert set(read_record(Path(leader.context["delivery"]["approval_record"])).artifacts) == {"markdown", "docx"}


@pytest.mark.asyncio
async def test_docx_section_with_image_is_refused(tmp_path, output_root):
    path = build_docx(tmp_path / "incident.docx", DOCX_SECTIONS, image_in="2. Escalation")
    source = load_sop(path)
    assert any(block.protected for block in source.blocks)
    [target] = resolve_sections(source.content, PROFILE, "fix the escalation part")
    findings = instruction_findings(source.content, PROFILE, "Add a P1 trigger", [target])
    leader, _, _ = leader_with(patch_reply(source.content, {target: "Escalate P1 incidents within 15 minutes."}),
                               lambda *a, **k: recheck_reply(findings, "within 15 minutes"))
    with pytest.raises(ValueError, match="edit it in Word"):
        await leader.revise_existing(source, findings, allow_external_ai=True)
    assert not (Path(leader.context["run_dir"]) / "approval.json").exists()


@pytest.mark.asyncio
async def test_findings_from_review_run_are_bound_to_the_file(tmp_path, output_root):
    path = tmp_path / "incident.md"
    path.write_text(template_sop())
    reviewer = ReviewAgent(api_key="")
    reviewer._call_claude = AsyncMock(return_value=assessment(
        issue("sec-tools", "ServiceNow version 2019.", category="outdated"),
        issue("sec-procedures", "Escalate when needed.", category="missing_step")))
    leader = LeaderAgent(api_key="")
    leader.register_worker("ReviewAgent", reviewer)
    await leader.review_existing(load_sop(path), allow_external_ai=True)
    run = Path(leader.context["run_dir"])
    tools = next(f for f in leader.context["findings"]["findings"] if f["section_id"] == "sec-tools")
    assert [f["finding_id"] for f in review_findings(run, load_sop(path), [tools["finding_id"]])] == [tools["finding_id"]]
    assert len(review_findings(run, load_sop(path))) == 2
    with pytest.raises(ValueError, match="unknown finding"):
        review_findings(run, load_sop(path), ["F-0000000000000000"])
    path.write_text(template_sop() + "\nEdited later.\n")
    with pytest.raises(ValueError, match="changed since that review"):
        review_findings(run, load_sop(path))


@pytest.mark.asyncio
async def test_template_gap_findings_cannot_be_revised(tmp_path, output_root):
    path = tmp_path / "handover.md"
    path.write_text(NON_TEMPLATE_SOP)
    leader = LeaderAgent(api_key="")
    findings = await leader.review_existing(load_sop(path), local_only=True)
    run = Path(leader.context["run_dir"])
    with pytest.raises(ValueError, match="template gaps"):
        review_findings(run, load_sop(path), [findings["template_gaps"][0]["finding_id"]])
    with pytest.raises(ValueError, match="no section findings"):
        review_findings(run, load_sop(path))


@pytest.mark.asyncio
async def test_generate_revision_still_requires_the_complete_profile():
    """Regression: generate's positional call keeps require_complete=True."""
    agent = ContentAgent(api_key="")
    agent._call_claude = AsyncMock()
    with pytest.raises(ValueError, match="required sections"):
        await agent.revise_sections(NON_TEMPLATE_SOP, [{"section_id": "sec-introduction"}])
    agent._call_claude.assert_not_awaited()
    from src.utils.capabilities import LocatedRevisionInputs
    values = LocatedRevisionInputs.model_validate({"content": "x", "findings": [{"a": 1}]}).model_dump()
    assert values["require_complete"] is None


def test_cli_revise_validates_options_before_consent(tmp_path, monkeypatch):
    from src import main
    monkeypatch.setattr(main, "console", Console(width=1000))
    monkeypatch.setattr(config_manager.system_config, "allow_external_ai", False)
    path = tmp_path / "incident.md"
    path.write_text(template_sop())
    runner, out = CliRunner(), tmp_path / "output"
    both = runner.invoke(main.app, ["revise", str(path), "-o", str(out)])
    assert both.exit_code == 2 and "exactly one of --instruction or --from-review" in both.output
    vague = runner.invoke(main.app, ["revise", str(path), "--instruction", "make it better", "-o", str(out)])
    assert vague.exit_code == 2 and "--section" in vague.output
    denied = runner.invoke(main.app, ["revise", str(path), "--instruction", "fix escalation", "-o", str(out)])
    assert denied.exit_code == 2 and "--allow-external-ai" in denied.output and not out.exists()

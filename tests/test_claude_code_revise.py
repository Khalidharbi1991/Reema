"""Finished-SOP revision authored in a Claude Code session (scripts/claude_code_revise.py). No provider calls."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from src.agents.content_agent import ContentAgent
from src.agents.file_workers import FilePatchWorker, FileRecheckWorker
from src.agents.leader_agent import LeaderAgent
from src.agents.review_agent import ReviewAgent
from src.utils.approvals import read_record, record_decision
from src.utils.config import config_manager
from src.utils.existing_sops import load_sop
from src.utils.provider import RunRuntime
from tests.existing_sop_helpers import build_docx, DOCX_SECTIONS

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude_code_revise.py"
spec = importlib.util.spec_from_file_location("claude_code_revise", SCRIPT)
ccr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccr)

INSTRUCTION = "Add a P1 trigger"
NEW_BODY = "### 2.1 Triggers\nEscalate P1 incidents within 15 minutes.\n\n| Level | Owner |\n|---|---|\n| L1 | Desk |"


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "output_dir", tmp_path / "output")
    return tmp_path / "output"


@pytest.fixture
def no_provider(monkeypatch):
    async def refuse(*args, **kwargs):
        raise AssertionError("A provider call was attempted")
    monkeypatch.setattr(RunRuntime, "call", refuse)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepared(tmp_path, sections=DOCX_SECTIONS):
    path = build_docx(tmp_path / "incident.docx", sections)
    work_id = ccr.prepare(path, ["2. Escalation"], INSTRUCTION)
    work = ccr.work_root() / work_id
    return path, work_id, work, json.loads((work / "request.json").read_text())


def write_patch(work, request, bodies=None):
    targets = request["target_sections"]
    bodies = bodies or {key: NEW_BODY for key in targets}
    (work / "patch.json").write_text(json.dumps({"base_document_sha256": request["base_document_sha256"], "patches": [
        {"section_id": key, "body": body, "base_section_sha256": targets[key]["base_section_sha256"]}
        for key, body in bodies.items()]}))


def write_recheck(work, request, revised_sha256=None):
    revised_sha256 = revised_sha256 or json.loads((work / "recheck_request.json").read_text())["revised_sha256"]
    (work / "recheck.json").write_text(json.dumps({"revised_sha256": revised_sha256, "corrections": [
        {"finding_id": f["finding_id"], "status": "resolved", "rationale": "Trigger added",
         "section_id": f["section_id"], "quote": "within 15 minutes"} for f in request["findings"]]}))


def test_full_flow_ends_awaiting_approval_without_a_provider_call(tmp_path, output_root, no_provider, capsys):
    path, work_id, work, request = prepared(tmp_path)
    before = digest(path)
    assert [v["title"] for v in request["target_sections"].values()] == ["2. Escalation"]
    write_patch(work, request)
    ccr.check(work_id)
    assert (work / "check_preview.docx").is_file() and (work / "changes_preview.md").is_file()
    write_recheck(work, request)
    key, consent = config_manager.system_config.anthropic_api_key, config_manager.system_config.allow_external_ai
    outputs = ccr.finish(work_id)
    assert (config_manager.system_config.anthropic_api_key, config_manager.system_config.allow_external_ai) == (key, consent)
    run_dir = Path(outputs["docx"]).parent
    state = json.loads((run_dir / "run.json").read_text())
    assert state["status"] == "awaiting_human_approval" and state["authoring"] == "claude_code_session"
    assert state["origin"] == {"instruction": INSTRUCTION, "claude_code_work": str(work)}
    assert json.loads((run_dir / "revised.json").read_text())["recheck"]["verification"] == "claude_code_session_assessed"
    record = read_record(run_dir / "approval.json")
    assert record.status == "awaiting_human_approval" and set(record.artifacts) == {"markdown", "docx"}
    reread = load_sop(outputs["docx"]).content
    assert "Escalate P1 incidents within 15 minutes." in reread and "Version 1.0." in reread
    assert digest(path) == before
    printed = capsys.readouterr().out
    assert f'reema approve "{run_dir / "approval.json"}" --reviewer "Khalid Alharbi"' in printed
    assert "<" not in printed


def test_patch_touching_another_section_is_refused(tmp_path, output_root):
    path, work_id, work, request = prepared(tmp_path)
    from src.utils.documents import section_map
    locations = section_map(load_sop(path).content, config_manager.document_profile, require_complete=False)
    other = next(key for key in locations if key not in request["target_sections"])
    (work / "patch.json").write_text(json.dumps({"base_document_sha256": request["base_document_sha256"], "patches": [
        {"section_id": other, "body": "Changed.", "base_section_sha256": locations[other]["sha256"]}]}))
    with pytest.raises(ValueError, match="exactly the requested sections"):
        ccr.check(work_id)
    assert not (work / "recheck_request.json").exists()


def test_new_control_id_is_refused_at_check_and_finish(tmp_path, output_root, no_provider):
    _, work_id, work, request = prepared(tmp_path)
    write_patch(work, request, {key: NEW_BODY + "\n\nSee CTRL-NEW-1." for key in request["target_sections"]})
    with pytest.raises(ValueError, match="source or control IDs"):
        ccr.check(work_id)
    (work / "recheck.json").write_text("{}")
    with pytest.raises(ValueError, match="source or control IDs"):
        ccr.finish(work_id)
    assert not list((output_root / "runs").glob("*/approval.json"))


def test_recheck_of_other_text_is_refused(tmp_path, output_root, no_provider):
    _, work_id, work, request = prepared(tmp_path)
    write_patch(work, request)
    ccr.check(work_id)
    write_recheck(work, request, revised_sha256="0" * 64)
    with pytest.raises(ValueError, match="revised document's SHA-256"):
        ccr.finish(work_id)
    assert not list((output_root / "runs").glob("*/approval.json"))


def test_missing_files_name_the_step_to_run(tmp_path, output_root, no_provider, capsys):
    _, work_id, work, request = prepared(tmp_path)
    assert ccr.main(["check", work_id]) == 1
    assert f"No patch.json yet: ask Claude Code to run reema-reviser on this work id ({work_id})." in capsys.readouterr().err
    assert ccr.main(["finish", work_id]) == 1
    assert "No patch.json yet: ask Claude Code to run reema-reviser" in capsys.readouterr().err
    write_patch(work, request)
    ccr.check(work_id)
    assert ccr.main(["finish", work_id]) == 1
    assert "No recheck.json yet: ask Claude Code to run reema-rechecker" in capsys.readouterr().err
    assert not (output_root / "runs").exists()


def test_source_changed_after_prepare_is_refused(tmp_path, output_root):
    path, work_id, work, request = prepared(tmp_path)
    build_docx(path, DOCX_SECTIONS, title="Changed title")
    write_patch(work, request)
    with pytest.raises(ValueError, match="changed since prepare"):
        ccr.check(work_id)


def test_cli_reports_refusals_and_compare_reads_both_runs(tmp_path, output_root, no_provider, capsys):
    assert ccr.main(["check", "missing0"]) == 1
    assert "Refused" in capsys.readouterr().err
    runs = []
    for _ in range(2):
        _, work_id, work, request = prepared(tmp_path)
        write_patch(work, request)
        ccr.check(work_id)
        write_recheck(work, request)
        runs.append(Path(ccr.finish(work_id)["docx"]).parent)
    record_decision(runs[0] / "approval.json", "approved", "Synthetic Reviewer")
    capsys.readouterr()
    assert ccr.main(["compare", str(runs[0]), str(runs[1])]) == 0
    out = capsys.readouterr().out
    assert "claude_code_session" in out and "2. Escalation" in out and "1/1" in out
    rows = {line.split()[0]: line.split(None, 1)[1] for line in out.splitlines() if line.strip()}
    assert rows["decision"].split() == ["approved", "awaiting_human_approval"]
    assert rows["reviewer"].split("  ")[0] == "Synthetic Reviewer" and rows["reviewer"].rstrip().endswith("-")
    assert read_record(runs[0] / "approval.json").decided_at in rows["decided_at"]


@pytest.mark.asyncio
async def test_local_author_needs_the_file_workers(tmp_path, output_root):
    source = load_sop(build_docx(tmp_path / "incident.docx", DOCX_SECTIONS))
    leader = LeaderAgent(api_key="")
    leader.register_worker("ContentAgent", ContentAgent(api_key=""))
    leader.register_worker("ReviewAgent", ReviewAgent(api_key=""))
    with pytest.raises(ValueError, match="file-backed"):
        await leader.revise_existing(source, [], local_author=True)
    leader = LeaderAgent(api_key="")
    leader.register_worker("ContentAgent", FilePatchWorker(tmp_path / "patch.json"))
    leader.register_worker("ReviewAgent", ReviewAgent(api_key=""))
    with pytest.raises(ValueError, match="file-backed"):
        await leader.revise_existing(source, [], local_author=True)
    assert FileRecheckWorker(tmp_path / "r.json").client is None


# --- Review mode: prepare --from-review RUN --finding ID ---

def review_run(path, *issues):
    """A review run of PATH, written through the real review job with a mocked reviewer reply."""
    import asyncio
    from unittest.mock import AsyncMock
    from tests.existing_sop_helpers import assessment
    reviewer = ReviewAgent(api_key="")
    reviewer._call_claude = AsyncMock(return_value=assessment(*issues))
    leader = LeaderAgent(api_key="")
    leader.register_worker("ReviewAgent", reviewer)
    asyncio.run(leader.review_existing(load_sop(path), allow_external_ai=True))
    findings = leader.context["findings"]["findings"]
    return Path(leader.context["run_dir"]), {f["section_id"]: f["finding_id"] for f in findings}


TOOLS_FIX = "ServiceNow Washington DC release."


@pytest.fixture
def reviewed(tmp_path, output_root):
    from tests.existing_sop_helpers import issue, template_sop
    path = tmp_path / "incident.md"
    path.write_text(template_sop())
    run, ids = review_run(path, issue("sec-tools", "ServiceNow version 2019.", category="outdated",
                                      action="Name the current release"),
                          issue("sec-procedures", "Escalate when needed.", category="missing_step"))
    return path, run, ids


def write_review_patch_and_recheck(work_id, body=TOOLS_FIX):
    work = ccr.work_root() / work_id
    request = json.loads((work / "request.json").read_text())
    write_patch(work, request, {key: body for key in request["target_sections"]})
    ccr.check(work_id)
    revised_sha256 = json.loads((work / "recheck_request.json").read_text())["revised_sha256"]
    (work / "recheck.json").write_text(json.dumps({"revised_sha256": revised_sha256, "corrections": [
        {"finding_id": f["finding_id"], "status": "resolved", "rationale": "Release named",
         "section_id": f["section_id"], "quote": body} for f in request["findings"]]}))
    return work, request


def test_review_findings_flow_ends_awaiting_approval_without_a_provider_call(reviewed, no_provider, capsys):
    path, run, ids = reviewed
    before = digest(path)
    work_id = ccr.prepare(path, from_review=run, finding_ids=[ids["sec-tools"]])
    work, request = write_review_patch_and_recheck(work_id)
    assert request["mode"] == "review" and list(request["target_sections"]) == ["sec-tools"]
    assert [f["finding_id"] for f in request["findings"]] == [ids["sec-tools"]]
    outputs = ccr.finish(work_id)
    run_dir = Path(outputs["markdown"]).parent
    state = json.loads((run_dir / "run.json").read_text())
    assert state["status"] == "awaiting_human_approval" and state["authoring"] == "claude_code_session"
    assert state["origin"] == {"review_run": str(run.resolve()), "finding_ids": [ids["sec-tools"]],
                               "claude_code_work": str(work)}
    assert read_record(run_dir / "approval.json").status == "awaiting_human_approval"
    reread = load_sop(outputs["markdown"]).content
    assert TOOLS_FIX in reread and "Escalate when needed." in reread
    assert digest(path) == before
    assert f"Findings: {ids['sec-tools']} from {run.resolve()}" in capsys.readouterr().out


@pytest.mark.parametrize("kwargs, message", [
    ({}, "exactly one of --instruction or --from-review"),
    ({"instruction": "x", "sections": ["2"], "from_review": "run"}, "exactly one of"),
    ({"instruction": "x", "sections": ["2"], "finding_ids": ["F-1"]}, "--finding needs --from-review"),
    ({"instruction": "x"}, "needs at least one --section"),
    ({"from_review": "run", "sections": ["2"], "finding_ids": ["F-1"]}, "--section works with --instruction"),
    ({"from_review": "run"}, "at least one --finding"),
    ({"from_review": "run", "finding_ids": [f"F-{n}" for n in range(6)]}, "At most 5 findings"),
])
def test_prepare_option_rules(tmp_path, output_root, kwargs, message):
    with pytest.raises(ValueError, match=message):
        ccr.prepare(tmp_path / "incident.md", **kwargs)
    assert not ccr.work_root().exists()


def test_repeated_finding_ids_count_once(reviewed):
    path, run, ids = reviewed
    work_id = ccr.prepare(path, from_review=run, finding_ids=[ids["sec-tools"]] * 6)
    assert json.loads((ccr.work_root() / work_id / "request.json").read_text())["finding_ids"] == [ids["sec-tools"]]


def test_unknown_and_template_gap_findings_are_refused(tmp_path, reviewed):
    import asyncio
    from tests.existing_sop_helpers import NON_TEMPLATE_SOP
    path, run, _ = reviewed
    with pytest.raises(ValueError, match="unknown finding"):
        ccr.prepare(path, from_review=run, finding_ids=["F-0000000000000000"])
    handover = tmp_path / "handover.md"
    handover.write_text(NON_TEMPLATE_SOP)
    leader = LeaderAgent(api_key="")
    gaps = asyncio.run(leader.review_existing(load_sop(handover), local_only=True))["template_gaps"]
    with pytest.raises(ValueError, match="template gaps cannot be revised"):
        ccr.prepare(handover, from_review=leader.context["run_dir"], finding_ids=[gaps[0]["finding_id"]])
    with pytest.raises(ValueError, match="not a review run folder"):
        ccr.prepare(path, from_review=tmp_path, finding_ids=["F-1"])


def test_findings_edited_after_the_review_are_refused(reviewed):
    path, run, ids = reviewed
    data = json.loads((run / "findings.json").read_text())
    data["findings"][0]["action"] = "Delete the whole section"
    (run / "findings.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="findings changed after it was saved"):
        ccr.prepare(path, from_review=run, finding_ids=[ids["sec-tools"]])


def test_sop_changed_since_the_review_is_refused(reviewed):
    from tests.existing_sop_helpers import template_sop
    path, run, ids = reviewed
    path.write_text(template_sop() + "\nEdited later.\n")
    with pytest.raises(ValueError, match="changed since that review"):
        ccr.prepare(path, from_review=run, finding_ids=[ids["sec-tools"]])


def test_review_rewritten_after_prepare_is_refused_at_check_and_finish(reviewed, no_provider):
    path, run, ids = reviewed
    work_id = ccr.prepare(path, from_review=run, finding_ids=[ids["sec-tools"]])
    write_review_patch_and_recheck(work_id)
    # Rewritten so it is consistent with itself: findings.json and its checkpoint in run.json.
    data = json.loads((run / "findings.json").read_text())
    data["summaries"] = {"rewritten": True}
    (run / "findings.json").write_text(json.dumps(data))
    state = json.loads((run / "run.json").read_text())
    state["checkpoints"]["findings"] = digest(run / "findings.json")
    (run / "run.json").write_text(json.dumps(state))
    for step in (ccr.check, ccr.finish):
        with pytest.raises(ValueError, match="review run's findings changed since prepare"):
            step(work_id)
    assert not list(ccr.work_root().parent.glob("runs/*/approval.json"))


def test_hand_edited_request_is_refused(reviewed, no_provider):
    path, run, ids = reviewed
    work_id = ccr.prepare(path, from_review=run, finding_ids=[ids["sec-tools"]])
    work = ccr.work_root() / work_id
    request = json.loads((work / "request.json").read_text())
    request["findings"][0]["action"] = "Rewrite every section"
    (work / "request.json").write_text(json.dumps(request))
    with pytest.raises(ValueError, match="no longer matches its findings"):
        ccr.check(work_id)
    del request["review_findings_sha256"]
    (work / "request.json").write_text(json.dumps(request))
    assert ccr.main(["check", work_id]) == 1


def test_a_revised_draft_can_be_revised_from_its_own_review(reviewed, no_provider):
    from tests.existing_sop_helpers import issue
    path, run, ids = reviewed
    work_id = ccr.prepare(path, from_review=run, finding_ids=[ids["sec-tools"]])
    write_review_patch_and_recheck(work_id)
    draft = Path(ccr.finish(work_id)["markdown"])
    second, second_ids = review_run(draft, issue("sec-tools", TOOLS_FIX, action="Add the upgrade date"))
    work_id = ccr.prepare(draft, from_review=second, finding_ids=[second_ids["sec-tools"]])
    write_review_patch_and_recheck(work_id, body=TOOLS_FIX + " Upgraded in 2026.")
    assert "Upgraded in 2026." in load_sop(ccr.finish(work_id)["markdown"]).content


def test_cli_prepare_from_review(reviewed, capsys):
    path, run, ids = reviewed
    assert ccr.main(["prepare", str(path), "--from-review", str(run)]) == 1
    assert "at least one --finding" in capsys.readouterr().err
    assert ccr.main(["prepare", str(path), "--from-review", str(run), "--finding", ids["sec-tools"],
                     "--finding", ids["sec-procedures"]]) == 0
    assert "Findings:" in capsys.readouterr().out

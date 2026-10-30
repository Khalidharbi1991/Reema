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

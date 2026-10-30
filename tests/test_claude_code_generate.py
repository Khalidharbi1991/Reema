"""New SOP written in a Claude Code session (scripts/claude_code_generate.py). No provider calls."""

import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from src.agents.content_agent import ContentAgent
from src.agents.file_workers import FileSectionWriter, section_files
from src.agents.format_agent import FormatAgent
from src.agents.leader_agent import LeaderAgent
from src.utils.approvals import ApprovalRecord, read_record, record_decision
from src.utils.config import config_manager
from src.utils.provider import RunRuntime
from src.utils.read_gate import ReadNotConfirmed

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude_code_generate.py"
spec = importlib.util.spec_from_file_location("claude_code_generate", SCRIPT)
ccg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccg)

PROCESS = "Change Management"
RACI = "| Activity | Change Manager | CAB |\n|---|---|---|\n| Approve normal change | A | R |"


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "output_dir", tmp_path / "output")
    monkeypatch.setattr(config_manager.system_config, "references_dir", tmp_path / "references")
    monkeypatch.setattr(config_manager.system_config, "reference_manifest", tmp_path / "references" / "manifest.yaml")
    return tmp_path / "output"


@pytest.fixture
def no_provider(monkeypatch):
    async def refuse(*args, **kwargs):
        raise AssertionError("A provider call was attempted")
    monkeypatch.setattr(RunRuntime, "call", refuse)


def prepared(**kwargs):
    work_id = ccg.prepare(PROCESS, ["markdown"], **kwargs)
    work = ccg.work_root() / work_id
    return work_id, work, json.loads((work / "generate_request.json").read_text())


def write_sections(work, request, changes=None):
    standards = ", ".join(request["standards"])
    for section in request["sections"]:
        body = RACI if section["id"] == "sec-roles" else f"### Notes\nSynthetic {section['title']} text, aligned with {standards}."
        body = (changes or {}).get(section["id"], body)
        if body is not None:
            (work / section["file"]).write_text(body + "\n", encoding="utf-8")


def test_prepare_writes_the_skeleton_and_rules_without_reading_any_sop(output_root):
    work_id, work, request = prepared(objective="Cover emergency changes")
    profile = config_manager.document_profile
    assert [s["id"] for s in request["sections"]] == [s.id for s in profile.sections]
    assert request["sections"][0]["file"] == "sections/01-" + profile.sections[0].id + ".md"
    assert request["section_rules"] == ContentAgent.SECTION_RULES and request["checks"]
    assert request["request"]["objective"] == "Cover emergency changes" and request["request"]["formats"] == ["markdown"]
    assert request["evidence"] == [] and request["read_permission"]["confirm_read"] is None
    assert {c["id"] for c in request["control_register"]["controls"]} and request["standards"]
    assert (work / "sections").is_dir() and not list((work / "sections").iterdir())


@pytest.mark.parametrize("process, formats, message", [
    ("Incident Management", ["markdown"], "selects specialists"),
    ("Not A Process", ["markdown"], "Unknown process"),
    (PROCESS, ["rtf"], "format"),
])
def test_prepare_refuses_unsupported_requests(output_root, process, formats, message):
    with pytest.raises(ValueError, match=message):
        ccg.prepare(process, formats)
    assert not (output_root / "claude_code").exists()


def test_check_names_every_missing_file(output_root):
    work_id, work, request = prepared()
    write_sections(work, request, {"sec-roles": None, "sec-kpis": None})
    with pytest.raises(ValueError, match="Missing section file") as refused:
        ccg.check(work_id)
    assert "-sec-roles.md" in str(refused.value) and "-sec-kpis.md" in str(refused.value)


@pytest.mark.parametrize("section, body, message", [
    ("sec-tools", "## Tools\nA second top-level heading.", "top-level sections"),
    ("sec-roles", "| Activity | Change Manager | CAB |\n|---|---|---|\n| Approve | A | A |", "exactly one accountable"),
    ("sec-tools", "See [SRC-0000000000000000].", "Unknown source citations"),
    ("sec-flow", "```reema-flow\n{\"not\": \"closed\"}", "Unclosed"),
    ("sec-tools", "   ", "Section 8"),
])
def test_check_refuses_drafts_that_fail_a_local_check(output_root, section, body, message):
    work_id, work, request = prepared()
    write_sections(work, request, {section: body})
    with pytest.raises(ValueError, match=message):
        ccg.check(work_id)


def test_full_flow_ends_awaiting_approval_without_a_provider_call(output_root, no_provider, capsys):
    work_id, work, request = prepared()
    write_sections(work, request)
    assert ccg.main(["check", work_id]) == 0
    assert "Draft passed every check" in capsys.readouterr().out
    preview = (work / "draft_preview.md").read_text()
    outputs = ccg.finish(work_id)
    out = capsys.readouterr().out
    assert "no model reviewed it" in out and 'reema approve "' in out and "reema-review" in out
    draft = Path(outputs["markdown"])
    assert draft.read_text().count("## ") >= 11 and "Approve normal change" in draft.read_text()
    run = draft.parent.parent
    state = json.loads((run / "run.json").read_text())
    assert (state["job"], state["status"], state["authoring"]) == ("generate", "awaiting_human_approval", "claude_code_session")
    assert state["usage"]["calls"] == [] and [t["phase"] for t in state["tasks"]] == [
        "planning", "content", "checks", "formatting", "human_review_record"]
    assert json.loads((run / "generated.json").read_text())["content"] == preview
    assert not (run / "execution.json").exists() and not (output_root / ".recovery-key").exists()
    record = read_record(run / "approval.json")
    assert record.status == "awaiting_human_approval" and record.quality_score is None and record.reviewer is None
    record_decision(run / "approval.json", "approved", "Synthetic Reviewer")
    assert read_record(run / "approval.json").quality_score is None


def test_a_section_changed_between_check_and_finish_is_checked_again(output_root, no_provider):
    work_id, work, request = prepared()
    write_sections(work, request)
    ccg.check(work_id)
    (work / request["sections"][7]["file"]).write_text("## Broken\n")
    with pytest.raises(ValueError, match="top-level sections"):
        ccg.finish(work_id)
    assert not (output_root / "runs").exists()


def manifest(root, path, digest=None):
    (root / "manifest.yaml").write_text(
        f"version: 1\nsources:\n  - path: {path.name}\n    classification: internal\n"
        f"    external_ai_allowed: true\n    sha256: \"{digest or hashlib.sha256(path.read_bytes()).hexdigest()}\"\n")


def test_reference_excerpts_need_the_token_and_can_be_cited(output_root, no_provider, capsys):
    root = config_manager.system_config.references_dir
    root.mkdir()
    policy = root / "change_policy.md"
    policy.write_text("Change Management policy: every normal change needs CAB approval.\n")
    manifest(root, policy)
    assert ccg.main(["prepare", PROCESS, "-f", "markdown"]) == 1
    err = capsys.readouterr().err
    assert "change_policy.md" in err and "--confirm-read" in err and not (output_root / "claude_code").exists()
    token = err.rsplit("--confirm-read ", 1)[1].strip()
    work_id, work, request = prepared(confirm_read=token)
    assert len(request["evidence"]) == 1 and request["read_permission"]["reference_files"] == ["change_policy.md"]
    source_id = request["evidence"][0]["id"]
    write_sections(work, request, {"sec-procedures": f"### Approval\nCAB approves normal changes [{source_id}]."})
    ccg.check(work_id)
    run = Path(ccg.finish(work_id)["markdown"]).parent.parent
    assert source_id in json.loads((run / "ready.json").read_text())["sources"]
    policy.write_text("Change Management policy, edited.\n")
    manifest(root, policy)
    with pytest.raises(ValueError, match="reference excerpts changed"):
        ccg.check(work_id)


def test_wrong_token_and_disallowed_references_are_refused(output_root):
    root = config_manager.system_config.references_dir
    root.mkdir()
    policy = root / "change_policy.md"
    policy.write_text("Change Management policy text.\n")
    manifest(root, policy)
    with pytest.raises(ReadNotConfirmed):
        ccg.prepare(PROCESS, ["markdown"], confirm_read="000000000000")
    manifest(root, policy, digest="0" * 64)
    with pytest.raises(ValueError, match="changed since authorization"):
        ccg.prepare(PROCESS, ["markdown"])


@pytest.mark.asyncio
async def test_leader_refuses_a_local_generate_without_the_file_writer(output_root):
    leader = LeaderAgent(api_key="")
    leader.register_worker("ContentAgent", ContentAgent(api_key=""))
    leader.register_worker("FormatAgent", FormatAgent(api_key=""))
    with pytest.raises(ValueError, match="file-backed ContentAgent"):
        await leader.generate_local(PROCESS, ["markdown"])
    assert not (output_root / "runs").exists()


def test_file_writer_refuses_an_unknown_section(tmp_path):
    writer = FileSectionWriter(tmp_path)
    with pytest.raises(ValueError, match="does not know"):
        asyncio.run(writer._call_claude([{"role": "user", "content": 'Set section_id to "sec-unknown".'}]))
    assert list(section_files(tmp_path)) == [s.id for s in config_manager.document_profile.sections]


def test_old_records_with_a_score_and_new_ones_without_still_load():
    base = {"process_name": "X", "created_at": "2026-01-01T00:00:00Z",
            "artifacts": {"markdown": {"path": "/x.md", "sha256": "0" * 64}}}
    assert ApprovalRecord.model_validate({**base, "quality_score": 92}).quality_score == 92
    assert ApprovalRecord.model_validate(base).quality_score is None
    with pytest.raises(ValueError):
        ApprovalRecord.model_validate({**base, "quality_score": 101})

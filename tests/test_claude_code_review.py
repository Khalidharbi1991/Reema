"""Finished-SOP review authored in a Claude Code session (scripts/claude_code_review.py). No provider calls."""

import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from src.agents.file_workers import FileReviewWorker
from src.agents.leader_agent import LeaderAgent
from src.agents.review_agent import ReviewAgent
from src.utils.config import config_manager
from src.utils.existing_sops import load_sop, review_findings
from src.utils.provider import RunRuntime
from tests.existing_sop_helpers import BODIES, DOCX_SECTIONS, assessment, build_docx, confirm, issue, template_sop

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude_code_review.py"
spec = importlib.util.spec_from_file_location("claude_code_review", SCRIPT)
ccr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccr)

TOOLS = issue("sec-tools", "ServiceNow version 2019.", category="outdated", description="Old tool version")
LONG_SOP = template_sop({"Appendices": BODIES["Appendices"] + "\n" + "Filler line for length.\n" * 80})


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "output_dir", tmp_path / "output")
    return tmp_path / "output"


@pytest.fixture
def no_provider(monkeypatch):
    async def refuse(*args, **kwargs):
        raise AssertionError("A provider call was attempted")
    monkeypatch.setattr(RunRuntime, "call", refuse)


@pytest.fixture
def small_chunks(monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "review_chunk_chars", 1000)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepared(tmp_path, content=None, path=None):
    if path is None:
        path = tmp_path / "sop.md"
        path.write_text(content or template_sop(), encoding="utf-8")
    work_id = ccr.prepare(path, confirm(path))
    work = ccr.work_root() / work_id
    return path, work_id, work, json.loads((work / "review_request.json").read_text())


def excerpt_of(request, section_id):
    start = request["section_locations"][section_id]["body_start"]
    return next(e["excerpt"] for e in request["excerpts"] if e["start"] <= start < e["end"])


def write_excerpts(work, request, issues_by_excerpt=None, document_sha256=None):
    issues_by_excerpt = issues_by_excerpt or {}
    (work / "excerpts.json").write_text(json.dumps({
        "document_sha256": document_sha256 or request["document_sha256"],
        "assessments": [json.loads(assessment(*issues_by_excerpt.get(e["excerpt"], []))) for e in request["excerpts"]]}))


def write_consistency(work, *issues):
    bound = json.loads((work / "consistency_request.json").read_text())
    (work / "consistency.json").write_text(json.dumps({
        "document_sha256": bound["document_sha256"], "excerpts_sha256": bound["excerpts_sha256"],
        "assessment": json.loads(assessment(*issues))}))


def test_full_flow_is_read_only_and_makes_no_provider_call(tmp_path, output_root, no_provider, capsys):
    path, work_id, work, request = prepared(tmp_path)
    before = digest(path)
    assert request["consistency_pass"] is False and request["instructions"] == ReviewAgent.EXISTING_SOP_INSTRUCTIONS
    write_excerpts(work, request, {1: [TOOLS]})
    ccr.check(work_id)
    assert not (output_root / "runs").exists() and not (work / "consistency_request.json").exists()
    key, consent = config_manager.system_config.anthropic_api_key, config_manager.system_config.allow_external_ai
    run_dir = ccr.finish(work_id)
    assert (config_manager.system_config.anthropic_api_key, config_manager.system_config.allow_external_ai) == (key, consent)
    state = json.loads((run_dir / "run.json").read_text())
    assert (state["job"], state["status"], state["authoring"]) == ("review", "review_complete", "claude_code_session")
    assert state["usage"]["calls"] == [] and state["usage"]["accounted_tokens"] == 0
    findings = json.loads((run_dir / "findings.json").read_text())
    assert [(f["section_id"], f["category"]) for f in findings["findings"]] == [("sec-tools", "outdated")]
    assert findings["findings"][0]["finding_id"].startswith("F-") and findings["source_sha256"] == before
    assert digest(path) == before
    assert not list(output_root.rglob("approval.json"))
    out = capsys.readouterr().out
    assert f"before: {before}" in out and f"after:  {before} (unchanged)" in out


def test_docx_source_bytes_are_unchanged(tmp_path, output_root, no_provider):
    docx = build_docx(tmp_path / "incident.docx", DOCX_SECTIONS)
    before = digest(docx)
    _, work_id, work, request = prepared(tmp_path, path=docx)
    write_excerpts(work, request)
    ccr.check(work_id)
    run_dir = ccr.finish(work_id)
    assert digest(docx) == before and not (run_dir / "approval.json").exists()
    assert sorted(p.name for p in run_dir.iterdir() if p.suffix in {".md", ".docx"}) == ["findings.md"]


def test_several_excerpts_need_a_consistency_pass(tmp_path, output_root, no_provider, small_chunks):
    path, work_id, work, request = prepared(tmp_path, LONG_SOP)
    assert request["consistency_pass"] and len(request["excerpts"]) > 1
    write_excerpts(work, request, {excerpt_of(request, "sec-tools"): [TOOLS]})
    ccr.check(work_id)
    sent = json.loads((work / "consistency_request.json").read_text())
    assert sent["assessments"][excerpt_of(request, "sec-tools") - 1]["issues"][0]["quote"] == TOOLS["quote"]
    assert "text" not in json.dumps(sent["section_locations"]) and "excerpts" not in sent
    assert ccr.main(["finish", work_id]) == 1 and not (output_root / "runs").exists()
    write_consistency(work, issue("sec-tools", TOOLS["quote"], category="other", description="Contradicts section 5"))
    ccr.check(work_id)
    run_dir = ccr.finish(work_id)
    findings = json.loads((run_dir / "findings.json").read_text())
    assert sorted(f["category"] for f in findings["findings"]) == ["other", "outdated"]


def test_consistency_written_from_older_excerpts_is_refused(tmp_path, output_root, no_provider, small_chunks):
    _, work_id, work, request = prepared(tmp_path, LONG_SOP)
    write_excerpts(work, request)
    ccr.check(work_id)
    write_consistency(work)
    write_excerpts(work, request, {excerpt_of(request, "sec-tools"): [TOOLS]})
    with pytest.raises(ValueError, match="other excerpts"):
        ccr.check(work_id)
    with pytest.raises(ValueError, match="other excerpts"):
        ccr.finish(work_id)


def test_finding_outside_its_excerpt_is_refused(tmp_path, output_root, no_provider, small_chunks):
    _, work_id, work, request = prepared(tmp_path, LONG_SOP)
    wrong = 1 if excerpt_of(request, "sec-tools") != 1 else 2
    write_excerpts(work, request, {wrong: [TOOLS]})
    with pytest.raises(ValueError, match="outside its assessed excerpt"):
        ccr.check(work_id)


@pytest.mark.parametrize("change, reason", [
    ("hash", "document SHA-256"),
    ("count", "exactly 1 assessment"),
    ("quote", "exactly one location"),
    ("json", "not valid JSON"),
])
def test_bad_review_files_are_refused(tmp_path, output_root, no_provider, change, reason):
    _, work_id, work, request = prepared(tmp_path)
    if change == "hash":
        write_excerpts(work, request, document_sha256="0" * 64)
    elif change == "count":
        (work / "excerpts.json").write_text(json.dumps({"document_sha256": request["document_sha256"], "assessments": []}))
    elif change == "quote":
        write_excerpts(work, request, {1: [issue("sec-tools", "Not in the SOP")]})
    else:
        (work / "excerpts.json").write_text("{not json")
    with pytest.raises(ValueError, match=reason):
        ccr.check(work_id)
    assert not (output_root / "runs").exists()


def test_missing_excerpts_and_changed_source_are_refused(tmp_path, output_root, no_provider, capsys):
    path, work_id, work, request = prepared(tmp_path)
    assert ccr.main(["check", work_id]) == 1
    assert "ask Claude Code to run reema-reviewer" in capsys.readouterr().err
    write_excerpts(work, request)
    path.write_text(template_sop({"Introduction": "Changed."}))
    with pytest.raises(ValueError, match="changed since prepare"):
        ccr.finish(work_id)
    assert not (output_root / "runs").exists()


@pytest.mark.asyncio
async def test_leader_refuses_local_author_without_complete_file_worker(tmp_path, output_root):
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    for worker in (ReviewAgent(api_key=""), FileReviewWorker(tmp_path / "x.json", excerpts_only=True)):
        leader = LeaderAgent(api_key="")
        leader.register_worker("ReviewAgent", worker)
        with pytest.raises(ValueError, match="file-backed ReviewAgent"):
            await leader.review_existing(load_sop(path), local_author=True)
    assert not (output_root / "runs").exists()


def test_revise_accepts_the_findings_and_compare_matches_local_only(tmp_path, output_root, no_provider, capsys):
    path, work_id, work, request = prepared(tmp_path, template_sop({"Appendices": ""}))
    write_excerpts(work, request, {1: [TOOLS]})
    run_dir = ccr.finish(work_id)
    assert [f["section_id"] for f in review_findings(run_dir, load_sop(path))] == ["sec-tools"]
    leader = LeaderAgent(api_key="")
    asyncio.run(leader.review_existing(load_sop(path), local_only=True))
    capsys.readouterr()
    ccr.compare(leader.context["run_dir"], run_dir)
    out = capsys.readouterr().out
    assert "Template gaps identical: yes" in out and "claude_code_session" in out and "local_code" in out

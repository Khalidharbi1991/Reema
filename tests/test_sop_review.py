"""Read-only review of finished SOPs: the local template check and the Claude Code review path. No provider calls."""

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from rich.console import Console
from typer.testing import CliRunner

from src.agents.leader_agent import LeaderAgent
from src.agents.review_agent import ReviewAgent
from src.utils.config import config_manager
from src.utils.existing_sops import load_sop, template_gaps, duplicate_sections
from src.utils.validation import missing_sections, validate_sop
from tests.existing_sop_helpers import (template_sop, NON_TEMPLATE_SOP, build_docx, DOCX_SECTIONS,
                                        assessment, issue, stand_in_review)


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "output_dir", tmp_path / "output")
    return tmp_path / "output"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_markdown_loads_unchanged(tmp_path):
    path = tmp_path / "sop.md"
    path.write_text(template_sop(), encoding="utf-8")
    source = load_sop(path)
    assert source.content == template_sop() and source.kind == "markdown" and source.sha256 == digest(path)


def test_docx_headings_and_tables_become_markdown(tmp_path):
    source = load_sop(build_docx(tmp_path / "sop.docx", DOCX_SECTIONS))
    assert "# Synthetic Incident SOP" in source.content
    assert "## 1. Introduction" in source.content and "### 2.1 Triggers" in source.content
    assert "| Level | Owner |\n|---|---|\n| L1 | Desk |" in source.content
    assert all(not block.protected for block in source.blocks)


@pytest.mark.parametrize("name, data", [("sop.txt", "text"), ("sop.md", ""), ("sop.md", "\xff")])
def test_bad_inputs_are_rejected(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data.encode("latin-1"))
    with pytest.raises(ValueError):
        load_sop(path)


def test_symlinks_are_rejected(tmp_path):
    target = tmp_path / "real.md"
    target.write_text(template_sop())
    (tmp_path / "link.md").symlink_to(target)
    with pytest.raises(ValueError, match="regular local file"):
        load_sop(tmp_path / "link.md")


def test_missing_sections_agrees_with_validate_sop():
    profile = config_manager.document_profile
    assert missing_sections(template_sop(), profile) == []
    validate_sop(template_sop(), profile)
    broken = template_sop().replace("## 8. Tools & Systems\n\nServiceNow version 2019.", "## 8. Tools & Systems\n")
    assert missing_sections(broken, profile) == ["Tools & Systems (empty)"]
    with pytest.raises(ValueError, match=r"missing or empty: Tools & Systems \(empty\)"):
        validate_sop(broken, profile)


def test_template_gaps_are_local_and_cover_duplicates():
    profile = config_manager.document_profile
    gaps = template_gaps(NON_TEMPLATE_SOP, profile)
    assert len(gaps) == 11 and {g["category"] for g in gaps} == {"template_gap"}
    doubled = template_sop().replace("# Synthetic Incident SOP", "# Synthetic Incident SOP\n\n## Document Control\n\nDraft.")
    assert duplicate_sections(doubled, profile) == ["Document Control"]
    assert any("more than once" in g["description"] for g in template_gaps(doubled, profile))


@pytest.mark.asyncio
async def test_local_only_review_makes_no_model_call_and_changes_nothing(tmp_path, output_root):
    path = tmp_path / "handover.md"
    path.write_text(NON_TEMPLATE_SOP)
    before = digest(path)
    leader = LeaderAgent()
    findings = await leader.review_existing(load_sop(path), local_only=True)
    run = Path(leader.context["run_dir"])
    assert run.parent == output_root / "runs"
    assert findings["mode"] == "local_only" and len(findings["template_gaps"]) == 11 and findings["findings"] == []
    state = json.loads((run / "run.json").read_text())
    assert state["status"] == "review_complete" and "usage" not in state
    assert {"source", "findings"} <= set(state["checkpoints"])
    assert not (run / "approval.json").exists()
    assert "Required section 'Introduction' is missing" in (run / "findings.md").read_text()
    assert digest(path) == before


@pytest.mark.asyncio
async def test_model_review_runs_only_through_claude_code(tmp_path, output_root):
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    review = ReviewAgent()
    review._reply = AsyncMock()
    leader = LeaderAgent()
    leader.register_worker("ReviewAgent", review)
    with pytest.raises(ValueError, match="Claude Code"):
        await leader.review_existing(load_sop(path))
    with pytest.raises(ValueError, match="file-backed ReviewAgent"):
        await leader.review_existing(load_sop(path), local_author=True)
    review._reply.assert_not_awaited()
    assert not (output_root / "runs").exists()


@pytest.mark.asyncio
async def test_model_review_locates_categorized_findings(tmp_path, output_root):
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    before = digest(path)
    review = stand_in_review(assessment(
        issue("sec-tools", "ServiceNow version 2019.", category="outdated", description="Old tool version"),
        issue("sec-procedures", "Escalate when needed.", category="missing_step")))
    leader = LeaderAgent()
    leader.register_worker("ReviewAgent", review)
    findings = await leader.review_existing(load_sop(path), local_author=True)
    assert [(f["section_id"], f["category"]) for f in findings["findings"]] == [("sec-tools", "outdated"),
                                                                             ("sec-procedures", "missing_step")]
    assert all(f["finding_id"].startswith("F-") and f["blocking"] for f in findings["findings"])
    assert findings["template_gaps"] == []
    text = (Path(leader.context["run_dir"]) / "findings.md").read_text()
    assert "[major, outdated] 8. Tools & Systems: Old tool version" in text
    assert digest(path) == before


@pytest.mark.asyncio
async def test_model_review_rejects_an_invented_location(tmp_path, output_root):
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    review = stand_in_review(assessment(issue("sec-tools", "Text that is not in the SOP")))
    leader = LeaderAgent()
    leader.register_worker("ReviewAgent", review)
    with pytest.raises(ValueError):
        await leader.review_existing(load_sop(path), local_author=True)
    run = next((output_root / "runs").iterdir())
    assert json.loads((run / "run.json").read_text())["status"] == "failed"


@pytest.mark.asyncio
async def test_model_review_of_non_template_and_docx_sops(tmp_path, output_root):
    md = tmp_path / "handover.md"
    md.write_text(NON_TEMPLATE_SOP)
    docx = build_docx(tmp_path / "sop.docx", DOCX_SECTIONS)
    docx_before = digest(docx)
    review = stand_in_review([
        assessment(issue("extra-" + hashlib.sha256(b"steps").hexdigest()[:16], "Collect the device from stores.")),
        assessment(issue("extra-" + hashlib.sha256(b"escalation").hexdigest()[:16], "Escalate when needed."))])
    for path in (md, docx):
        leader = LeaderAgent()
        leader.register_worker("ReviewAgent", review)
        findings = await leader.review_existing(load_sop(path), local_author=True)
        assert len(findings["findings"]) == 1 and len(findings["template_gaps"]) >= 8
    assert digest(docx) == docx_before


@pytest.mark.asyncio
async def test_model_review_refuses_duplicate_headings_before_any_call(tmp_path, output_root):
    path = tmp_path / "sop.md"
    path.write_text(template_sop().replace("# Synthetic Incident SOP", "# Synthetic Incident SOP\n\n## Document Control\n\nDraft."))
    review = stand_in_review([])
    leader = LeaderAgent()
    leader.register_worker("ReviewAgent", review)
    with pytest.raises(ValueError, match="more than once: Document Control"):
        await leader.review_existing(load_sop(path), local_author=True)
    review._reply.assert_not_awaited()


def test_cli_review_is_the_local_template_check(tmp_path, monkeypatch):
    from src import main
    monkeypatch.setattr(main, "console", Console(width=1000))
    path = tmp_path / "sop.md"
    path.write_text(NON_TEMPLATE_SOP)
    out = tmp_path / "output"
    for extra in ([], ["--local-only"]):
        local = CliRunner().invoke(main.app, ["review", str(path), *extra, "-o", str(out)])
        assert local.exit_code == 0, local.output
        assert "11 template gap(s). The SOP was not changed." in local.output and "Claude Code" in local.output
    assert len(list((out / "runs").iterdir())) == 2

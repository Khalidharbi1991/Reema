import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from typer.testing import CliRunner
from tests.test_phase01 import catalog, pipeline
from src.utils.runs import load_ready
from src.utils.approvals import read_record


@pytest.mark.asyncio
async def test_format_recovery_requires_no_model_and_new_approval(pipeline):
    leader, settings, workers = pipeline
    workers["FormatAgent"].formatters["markdown"].convert = AsyncMock(side_effect=RuntimeError("Disk error"))
    with pytest.raises(ValueError):
        await leader.generate_documentation("Change Management", ["markdown"])
    run = Path(leader.context["run_dir"])
    state, checkpoint = load_ready(run)
    assert state["status"] == "failed" and checkpoint["review"]["quality_score"] == 90
    from src.formatters.markdown_formatter import MarkdownFormatter
    workers["FormatAgent"].formatters["markdown"] = MarkdownFormatter()
    before = workers["ResearchAgent"].research_process.await_count
    settings.system_config.allow_external_ai = False
    outputs = await leader.resume_formatting(run, ["markdown"])
    assert Path(outputs["markdown"]).is_file() and Path(outputs["markdown"]).parent.parent != run
    assert workers["ResearchAgent"].research_process.await_count == before
    assert read_record(Path(leader.context["delivery"]["approval_record"])).status == "awaiting_human_approval"


@pytest.mark.asyncio
async def test_modified_checkpoint_is_not_resumable(pipeline):
    leader, _, _ = pipeline
    await leader.generate_documentation("Change Management", ["markdown"])
    run = Path(leader.context["run_dir"])
    (run / "ready.json").write_text('{}')
    with pytest.raises(ValueError, match="changed"):
        await leader.resume_formatting(run)


@pytest.mark.asyncio
async def test_resume_rechecks_new_threshold(pipeline):
    leader, config, _ = pipeline
    await leader.generate_documentation("Change Management", ["markdown"])
    config.agents_config["review_agent"]["quality_threshold"] = 99
    with pytest.raises(ValueError, match="quality gate"):
        await leader.resume_formatting(Path(leader.context["run_dir"]))


@pytest.mark.asyncio
async def test_early_failure_saves_draft_but_no_ready_checkpoint(pipeline):
    leader, _, workers = pipeline
    workers["ReviewAgent"].review_content.side_effect = RuntimeError("Review outage")
    with pytest.raises(RuntimeError):
        await leader.generate_documentation("Change Management", ["markdown"])
    run = Path(leader.context["run_dir"])
    state = json.loads((run / "run.json").read_text())
    assert state["status"] == "failed" and (run / "drafted.json").is_file()
    assert not (run / "ready.json").exists() and not (run / "approval.json").exists()


def test_cli_status_and_catalog_need_no_key(catalog, monkeypatch):
    from src import main
    monkeypatch.setattr(main, "config_manager", catalog)
    catalog.system_config.anthropic_api_key = ""
    for command in ("status", "list-processes", "version"):
        result = CliRunner().invoke(main.app, [command])
        assert result.exit_code == 0, result.output


@pytest.mark.asyncio
async def test_enforced_pages_require_pdf_before_model(pipeline):
    leader, catalog, workers = pipeline
    catalog.system_config.enforce_page_target = True
    with pytest.raises(ValueError, match="requires PDF"):
        await leader.generate_documentation("Change Management", ["markdown"])
    workers["ResearchAgent"].research_process.assert_not_awaited()

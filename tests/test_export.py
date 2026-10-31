"""Offline export of a run's ready checkpoint (`reema export`), and old runs that must still load. No model calls."""

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.agents.format_agent import FormatAgent
from src.agents.leader_agent import LeaderAgent
from src.main import app
from src.utils.approvals import create_pending_record, read_record, record_decision
from src.utils.config import config_manager
from src.utils.publish import plan_publish, publish
from tests.test_claude_code_generate import ccg, no_model_call, output_root, prepared, write_sections  # noqa: F401


def generated_run():
    work_id, work, request = prepared()
    write_sections(work, request)
    return Path(ccg.finish(work_id)["markdown"]).parent.parent


def export(run, formats=None):
    import asyncio
    leader = LeaderAgent()
    leader.register_worker("FormatAgent", FormatAgent())
    outputs = asyncio.run(leader.export_run(run, formats))
    return outputs, Path(leader.context["run_dir"])


def old_api_run(root, sop, score=92):
    """A generate run as the removed API path left it: reviewed, with usage, lineage and recovery files."""
    run = root / "runs" / "oldapirun"
    run.mkdir(parents=True)
    ready = {"content": sop, "review": {"quality_score": score, "approval_status": "APPROVED", "issues": []},
             "sources": {}, "standards": []}
    (run / "ready.json").write_text(json.dumps(ready))
    (run / "execution.json").write_text(json.dumps({"signature": "0" * 64}))
    (run / ".owner.lock").write_text("")
    state = {"schema_version": 1, "process_name": "Incident Management", "formats": ["markdown"],
             "status": "failed", "checkpoints": {"ready": hashlib.sha256((run / "ready.json").read_bytes()).hexdigest()},
             "owner": {"host": "old-host", "pid": 1, "token": "x"}, "resumed_from": "/old/run",
             "usage": {"accounted_tokens": 2048, "inherited_accounted_tokens": 1024, "lineage": [{"run": "/old"}],
                       "in_flight": [{"reserved_tokens": 2048}], "calls": [{"agent": "Agent 3"}]}}
    (run / "run.json").write_text(json.dumps(state))
    return run


def test_a_claude_code_run_exports_again_through_every_local_check(output_root, no_model_call):
    source = generated_run()
    before = (source / "run.json").read_bytes()
    outputs, run = export(source, ["markdown", "html"])
    assert set(outputs) == {"markdown", "html"} and run != source
    state = json.loads((run / "run.json").read_text())
    assert (state["job"], state["status"], state["authoring"]) == ("export", "awaiting_human_approval", "claude_code_session")
    assert state["exported_from"] == str(source.resolve()) and "usage" not in state
    record = read_record(run / "approval.json")
    assert record.status == "awaiting_human_approval" and record.quality_score is None
    assert (source / "run.json").read_bytes() == before


def test_a_changed_or_unreviewed_checkpoint_is_refused(output_root, no_model_call):
    source = generated_run()
    state = json.loads((source / "run.json").read_text())
    del state["authoring"]
    (source / "run.json").write_text(json.dumps(state))
    with pytest.raises(ValueError, match="Invalid ready checkpoint"):
        export(source)
    (source / "ready.json").write_text((source / "ready.json").read_text().replace("Synthetic", "Edited"))
    with pytest.raises(ValueError, match="changed ready checkpoint"):
        export(source)


def test_an_old_api_run_still_exports_with_its_review_gate(output_root, sample_sop_content):
    source = old_api_run(output_root, sample_sop_content)
    _, run = export(source)
    assert read_record(run / "approval.json").quality_score == 92
    assert "authoring" not in json.loads((run / "run.json").read_text())
    low = old_api_run(output_root / "low", sample_sop_content, score=40)
    with pytest.raises(ValueError, match="quality gate"):
        export(low)


def test_cli_export_and_its_old_name(output_root, no_model_call):
    source = generated_run()
    runner = CliRunner()
    for command in ("export", "resume"):
        result = runner.invoke(app, [command, str(source), "-f", "markdown"])
        assert result.exit_code == 0, result.output
        assert "Awaiting human approval" in result.output
    assert len([p for p in (output_root / "runs").iterdir() if p != source]) == 2
    help_text = runner.invoke(app, ["--help"]).output
    assert "export" in help_text and "resume" not in help_text


def test_old_revise_runs_with_recovery_files_still_approve_and_publish(output_root):
    run = output_root / "runs" / "oldrevise"
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"job": "revise", "owner": {"host": "old"}, "usage": {
        "accounted_tokens": 10, "lineage": [], "inherited_accounted_tokens": 0}}))
    (run / "execution.json").write_text("{}")
    draft = run / "X_V1.1.md"
    draft.write_text("revised")
    record = run / "approval.json"
    create_pending_record(record, "X_V1.md", {"markdown": str(draft)}, 88)
    record_decision(record, "approved", "Synthetic Reviewer")
    (output_root / "X_V1.md").write_text("old")
    assert plan_publish(record, output_root)
    publish(record, output_root)
    assert (output_root / "X_V1.1.md").read_text() == "revised"
    assert read_record(record).quality_score == 88


def test_old_review_runs_with_usage_still_feed_a_revision(output_root, tmp_path):
    from src.utils.existing_sops import load_sop, review_findings
    from tests.existing_sop_helpers import assessment, issue, stand_in_review, template_sop
    import asyncio
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    leader = LeaderAgent()
    leader.register_worker("ReviewAgent", stand_in_review(assessment(issue("sec-tools", "ServiceNow version 2019."))))
    asyncio.run(leader.review_existing(load_sop(path), local_author=True))
    run = Path(leader.context["run_dir"])
    state = json.loads((run / "run.json").read_text())
    state.pop("authoring")
    state["usage"] = {"accounted_tokens": 5, "lineage": [{"run": "/old"}], "inherited_accounted_tokens": 5}
    (run / "run.json").write_text(json.dumps(state))
    assert len(review_findings(run, load_sop(path))) == 1
    assert config_manager.system_config.output_dir == output_root

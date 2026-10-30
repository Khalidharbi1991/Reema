"""Publishing an approved revision into output/ and archiving older versions. No provider calls."""

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app
from src.utils import publish as publish_module
from src.utils.approvals import create_pending_record, read_record, record_decision
from src.utils.config import config_manager
from src.utils.existing_sops import find_sops, next_revision_stem
from src.utils.publish import NotPublishable, PublishError, plan_publish, publish, read_publish


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(config_manager.system_config, "output_dir", root)
    return root


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def revise_run(root, stem="X_V2.2", kinds=(".md", ".docx"), job="revise", run_id="run1"):
    run_dir = root / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({"job": job}))
    outputs = {}
    for kind in kinds:
        (run_dir / f"{stem}{kind}").write_text(f"new {kind}")
        outputs["markdown" if kind == ".md" else "docx"] = str(run_dir / f"{stem}{kind}")
    (run_dir / "changes.md").write_text("diff")
    record = run_dir / "approval.json"
    create_pending_record(record, "X_V2.1.docx", outputs, 100, supporting_records={"changes": str(run_dir / "changes.md")})
    return record


def approved(root, **kwargs):
    record = revise_run(root, **kwargs)
    record_decision(record, "approved", "Synthetic Reviewer")
    return record


def existing(root, *names):
    for name in names:
        (root / name).write_text(f"old {name}")


def approve(record, *extra, answer="y\n"):
    return CliRunner().invoke(app, ["approve", str(record), "--reviewer", "Synthetic Reviewer", *extra], input=answer)


def test_approve_publishes_and_archives_every_lower_version(output_root):
    existing(output_root, "X_V1.docx", "X_V2.docx", "X_V2.1.docx", "X_V2.1.md", "X.docx",
             "X_V2_Basic_Structure.docx", "Y_V1.docx", "X_V3.0.docx", "x_v2.1.pdf")
    record = revise_run(output_root)
    approval_before = (record).read_bytes()
    hashes = {name: sha(output_root / name) for name in ("X_V1.docx", "X_V2.docx", "X_V2.1.docx", "X_V2.1.md", "X.docx")}
    result = approve(record)
    assert result.exit_code == 0, result.output
    assert "Will copy" in result.output and "Published:" in result.output and "Archived:" in result.output
    assert read_record(record).status == "approved"
    for kind in (".md", ".docx"):
        assert (output_root / f"X_V2.2{kind}").read_text() == f"new {kind}"
        assert (record.parent / f"X_V2.2{kind}").is_file()  # The run's copy stays.
    archive = output_root / "archive" / "run1"
    assert {p.name: sha(p) for p in archive.iterdir()} == hashes
    # Variants, other SOPs, higher versions and unpublished formats stay.
    left = {p.name for p in output_root.iterdir() if p.is_file()}
    assert left == {"X_V2_Basic_Structure.docx", "Y_V1.docx", "X_V3.0.docx", "x_v2.1.pdf", "X_V2.2.md", "X_V2.2.docx"}
    state = read_publish(record)
    assert state["status"] == "published" and len(state["attempts"]) == 1
    assert all(step["status"] == "done" and len(step["sha256"]) == 64 for step in state["attempts"][0]["steps"])
    assert not (record.parent / "publish.json.lock").exists()
    # approval.json was written by the decision only.
    assert json.loads(record.read_text())["status"] == "approved" and record.read_bytes() != approval_before
    assert "publish" not in json.loads(record.read_text())


def test_versions_compare_as_numbers_and_lower_case_v(output_root):
    existing(output_root, "X_v9.0.md", "X_V10.md", "X_v10.0.md")
    record = approved(output_root, stem="X_V10.1", kinds=(".md",))
    publish(record, output_root)
    assert {p.name for p in (output_root / "archive" / "run1").iterdir()} == {"X_v9.0.md", "X_V10.md", "X_v10.0.md"}


def test_only_published_formats_are_archived(output_root):
    existing(output_root, "X_V2.1.docx", "X_V2.1.md")
    record = approved(output_root, kinds=(".md",))
    publish(record, output_root)
    assert (output_root / "X_V2.1.docx").is_file()
    assert [p.name for p in (output_root / "archive" / "run1").iterdir()] == ["X_V2.1.md"]


def test_reject_publishes_nothing(output_root):
    existing(output_root, "X_V2.1.docx")
    record = revise_run(output_root)
    result = CliRunner().invoke(app, ["reject", str(record), "--reviewer", "Synthetic Reviewer"], input="y\n")
    assert result.exit_code == 0, result.output
    assert read_publish(record) is None and not (output_root / "X_V2.2.md").exists()
    assert (output_root / "X_V2.1.docx").is_file()


def test_declined_confirmation_publishes_nothing(output_root):
    record = revise_run(output_root)
    result = approve(record, answer="n\n")
    assert result.exit_code == 1
    assert read_record(record).status == "awaiting_human_approval" and read_publish(record) is None
    assert not (output_root / "X_V2.2.md").exists()


@pytest.mark.parametrize("place", ["output", "archive"])
def test_existing_target_is_refused_without_changes_and_approval_stays(output_root, place):
    existing(output_root, "X_V2.1.docx")
    record = revise_run(output_root)
    if place == "output":
        target = output_root / "X_V2.2.md"
    else:
        target = output_root / "archive" / "run1" / "X_V2.1.docx"
        target.parent.mkdir(parents=True)
    target.write_text("someone else's")
    result = approve(record)
    assert "Warning: publishing will be refused" in result.output
    assert result.exit_code == 1 and "Approved, not published" in result.output
    assert "reema publish" in result.output
    assert read_record(record).status == "approved"
    assert target.read_text() == "someone else's"
    assert (output_root / "X_V2.1.docx").is_file()
    assert not (output_root / "X_V2.2.docx").exists()
    assert read_publish(record)["status"] == "refused"


def test_source_changed_after_approval_is_refused(output_root):
    record = approved(output_root)
    Path(read_record(record).artifacts["markdown"].path).write_text("edited")
    with pytest.raises(PublishError, match="changed since review"):
        publish(record, output_root)
    assert not (output_root / "X_V2.2.md").exists()


def test_old_revised_names_are_refused_with_a_clear_message(output_root):
    existing(output_root, "X_V2.docx")
    record = revise_run(output_root, stem="X_V2_revised")
    result = approve(record)
    assert result.exit_code == 1 and "old-style name without a version number" in result.output
    assert read_record(record).status == "approved"
    assert (output_root / "X_V2.docx").is_file() and read_publish(record)["status"] == "refused"


def test_generate_runs_are_approved_but_not_published(output_root):
    record = revise_run(output_root, job="generate")
    result = approve(record)
    assert result.exit_code == 0, result.output
    assert "Only revise runs are published" in result.output
    assert read_publish(record) is None and not (output_root / "X_V2.2.md").exists()
    with pytest.raises(NotPublishable):
        plan_publish(record, output_root)


def test_unapproved_runs_are_not_published(output_root):
    record = revise_run(output_root)
    with pytest.raises(PublishError, match="Only approved"):
        publish(record, output_root)


def test_failure_after_copy_keeps_approval_and_retry_finishes(output_root, monkeypatch):
    existing(output_root, "X_V2.1.docx", "X_V2.1.md")
    record = revise_run(output_root)
    original = publish_module._archive
    calls = []

    def fail_once(step):
        calls.append(step)
        if len(calls) == 1:
            raise OSError("disk full")
        original(step)

    monkeypatch.setattr(publish_module, "_archive", fail_once)
    result = approve(record)
    assert result.exit_code == 1 and "Approved, not published" in result.output and "disk full" in result.output
    assert read_record(record).status == "approved"
    state = read_publish(record)
    assert state["status"] == "partial"
    assert (output_root / "X_V2.2.md").is_file() and (output_root / "X_V2.2.docx").is_file()
    assert (output_root / "X_V2.1.docx").is_file()  # Old and new side by side, never neither.
    result = CliRunner().invoke(app, ["publish", str(record)])
    assert result.exit_code == 0, result.output
    state = read_publish(record)
    assert state["status"] == "published" and len(state["attempts"]) == 2
    assert {p.name for p in (output_root / "archive" / "run1").iterdir()} == {"X_V2.1.docx", "X_V2.1.md"}
    result = CliRunner().invoke(app, ["publish", str(record)])
    assert result.exit_code == 1 and "already published" in result.output


def test_retry_after_archive_link_but_before_unlink(output_root, monkeypatch):
    existing(output_root, "X_V2.1.md")
    record = approved(output_root, kinds=(".md",))
    real_unlink = Path.unlink

    def unlink(self, *args, **kwargs):
        if self.name == "X_V2.1.md" and self.parent == output_root:
            raise PermissionError("locked")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(PublishError, match="locked"):
        publish(record, output_root)
    monkeypatch.setattr(Path, "unlink", real_unlink)
    assert (output_root / "archive" / "run1" / "X_V2.1.md").is_file() and (output_root / "X_V2.1.md").is_file()
    assert publish(record, output_root)["status"] == "published"
    assert not (output_root / "X_V2.1.md").exists()


def test_retry_refuses_a_target_with_different_bytes(output_root, monkeypatch):
    existing(output_root, "X_V2.1.md")
    record = approved(output_root, kinds=(".md",))
    monkeypatch.setattr(publish_module, "_archive", lambda step: (_ for _ in ()).throw(OSError("stop")))
    with pytest.raises(PublishError):
        publish(record, output_root)
    (output_root / "X_V2.2.md").write_text("replaced by hand")
    monkeypatch.undo()
    monkeypatch.setattr(config_manager.system_config, "output_dir", output_root)
    with pytest.raises(PublishError, match="never overwritten"):
        publish(record, output_root)
    assert (output_root / "X_V2.2.md").read_text() == "replaced by hand"


def test_no_publish_skips_and_publish_command_runs_later(output_root):
    existing(output_root, "X_V2.1.md")
    record = revise_run(output_root, kinds=(".md",))
    result = approve(record, "--no-publish")
    assert result.exit_code == 0, result.output
    assert "Will copy" not in result.output and "--no-publish" in result.output
    assert read_publish(record)["status"] == "skipped" and not (output_root / "X_V2.2.md").exists()
    result = CliRunner().invoke(app, ["publish", str(record)])
    assert result.exit_code == 0, result.output
    assert (output_root / "X_V2.2.md").is_file() and not (output_root / "X_V2.1.md").exists()


def test_publish_command_leaves_runs_approved_before_publishing_alone(output_root):
    record = approved(output_root)  # Approved without the CLI, so no publish.json: like the old runs.
    result = CliRunner().invoke(app, ["publish", str(record)])
    assert result.exit_code == 1 and "left as it is" in result.output
    assert not (output_root / "X_V2.2.md").exists()
    pending = revise_run(output_root, run_id="run2")
    result = CliRunner().invoke(app, ["publish", str(pending)])
    assert result.exit_code == 1 and "Only approved" in result.output


def test_find_sops_lists_a_published_draft_once(output_root):
    record = approved(output_root, kinds=(".md",))
    assert find_sops(output_root, {"x"}) == [record.parent / "X_V2.2.md"]
    publish(record, output_root)
    assert find_sops(output_root, {"x"}) == [output_root / "X_V2.2.md"]


def test_archived_versions_are_never_handed_out_again(output_root):
    (output_root / "archive" / "run9").mkdir(parents=True)
    (output_root / "archive" / "X_V2.4.md").write_text("x")
    (output_root / "archive" / "run9" / "X_V2.6.docx").write_text("x")
    assert next_revision_stem("X_V2.md", output_root) == "X_V2.7"

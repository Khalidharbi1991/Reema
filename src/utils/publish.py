"""Publish an approved SOP revision: copy its drafts into output/ and archive older versions.

Runs only after a human approval is recorded, and only for revise runs with versioned names
(X_V2.1). Every lower version of the same SOP at the top of output/, in a published format, is
moved to output/archive/<run-id>/. Nothing is ever overwritten; every copy and move is checked by
SHA-256. The outcome goes to publish.json in the run folder; approval.json is never changed, so a
failed publish leaves the approval recorded.
"""

import json
import os
import re
import shutil
from pathlib import Path

from .approvals import checksum, read_record, timestamp
from .existing_sops import REVISED_ENDINGS, file_version

PUBLISH_FILE = "publish.json"
VERSIONED = re.compile(r"_V\d+\.\d+$")


class NotPublishable(Exception):
    """The run is not a kind that publishes (a generate run); approval alone is the outcome."""


class PublishError(ValueError):
    """Publishing was refused or failed; the approval stays recorded."""


def publish_path(record_path):
    return Path(record_path).parent / PUBLISH_FILE


def read_publish(record_path):
    path = publish_path(record_path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _write_publish(record_path, state):
    path = publish_path(record_path)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _earlier_done(state):
    """(action, target) -> sha256 for steps an earlier attempt of this run finished or began."""
    done = {}
    for attempt in (state or {}).get("attempts", []):
        for step in attempt.get("steps", []):
            if step.get("status") in ("done", "failed"):
                done[(step["action"], step["to"])] = step["sha256"]
    return done


def _job(run_dir):
    try:
        return json.loads((run_dir / "run.json").read_text(encoding="utf-8")).get("job")
    except (OSError, ValueError):
        return None


def plan_publish(record_path, output_root, *, pending_ok=False):
    """The copy and archive steps for an approved revise run, or PublishError if any would be refused.

    pending_ok lets the approve command preview the plan before the decision is recorded.
    """
    record_path, output_root = Path(record_path), Path(output_root)
    run_dir = record_path.parent
    if _job(run_dir) != "revise":
        raise NotPublishable("Only revise runs are published; this run's drafts stay where they are.")
    record = read_record(record_path)
    allowed = ("approved", "awaiting_human_approval") if pending_ok else ("approved",)
    if record.status not in allowed:
        raise PublishError(f"Only approved runs are published; this run is {record.status}.")
    earlier = _earlier_done(read_publish(record_path))
    copies, versions, formats = [], set(), set()
    for artifact in record.artifacts.values():
        source = Path(artifact.path)
        if REVISED_ENDINGS.search(source.stem) or not VERSIONED.search(source.stem):
            raise PublishError(
                f"{source.name} has an old-style name without a version number (such as _revised), "
                "so it is not published. Run the revision again to get a versioned draft.")
        if not source.is_file() or checksum(source) != artifact.sha256:
            raise PublishError(f"{source.name} is missing or changed since review; nothing was published.")
        target = output_root / source.name
        if target.exists() and earlier.get(("copy", str(target))) != artifact.sha256:
            raise PublishError(f"{target} already exists; it is never overwritten.")
        copies.append({"action": "copy", "from": str(source), "to": str(target), "sha256": artifact.sha256})
        versions.add(file_version(source.stem))
        formats.add(source.suffix.lower())
    if len(versions) != 1:
        raise PublishError("The approved drafts do not share one SOP name and version; nothing was published.")
    base, major, minor = versions.pop()
    archive_dir = output_root / "archive" / run_dir.name
    moves = []
    for path in sorted(output_root.iterdir()):
        if (path.name.startswith((".", "~$")) or path.is_symlink() or not path.is_file()
                or path.suffix.lower() not in formats):
            continue
        other = file_version(path.stem)
        if other[0].casefold() != base.casefold() or other[1:] >= (major, minor):
            continue
        target = archive_dir / path.name
        sha = checksum(path)
        if target.exists() and earlier.get(("archive", str(target))) != sha:
            raise PublishError(f"{target} already exists; it is never overwritten.")
        moves.append({"action": "archive", "from": str(path), "to": str(target), "sha256": sha})
    return copies + moves


def _place(source, target, sha):
    """Put an identical copy of source at target without ever replacing an existing file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.publish.tmp"
    shutil.copyfile(source, temporary)
    try:
        if checksum(temporary) != sha:
            raise PublishError(f"The copy of {source.name} does not match its SHA-256.")
        os.link(temporary, target)  # Fails if target exists, unlike rename on macOS.
    except FileExistsError:
        raise PublishError(f"{target} already exists; it is never overwritten.")
    finally:
        temporary.unlink(missing_ok=True)
    if checksum(target) != sha:
        raise PublishError(f"{target} does not match its SHA-256 after copying.")


def _copy(step):
    _place(Path(step["from"]), Path(step["to"]), step["sha256"])


def _archive(step):
    source, target = Path(step["from"]), Path(step["to"])
    if checksum(source) != step["sha256"]:
        raise PublishError(f"{source.name} changed while publishing; it was not archived.")
    _place(source, target, step["sha256"])
    source.unlink()


def publish(record_path, output_root):
    """Publish an approved revise run. Returns the publish.json state; raises PublishError on failure."""
    record_path = Path(record_path)
    lock = record_path.parent / (PUBLISH_FILE + ".lock")
    lock.open("x", encoding="utf-8").close()
    try:
        state = read_publish(record_path) or {"schema_version": 1, "run_id": record_path.parent.name,
                                              "record": str(record_path), "attempts": []}
        attempt = {"started_at": timestamp(), "steps": []}
        state["attempts"].append(attempt)

        def finish(status, reason=""):
            attempt.update(finished_at=timestamp(), status=status, reason=reason)
            state["status"] = status
            _write_publish(record_path, state)

        try:
            steps = plan_publish(record_path, output_root)
        except PublishError as error:
            finish("refused", str(error))
            raise
        earlier = _earlier_done(state)
        # Copy first, then archive: a half-finished publish leaves old and new side by side, never neither.
        for step in steps:
            attempt["steps"].append(step)
            target = Path(step["to"])
            try:
                if (earlier.get((step["action"], step["to"])) == step["sha256"] and target.is_file()
                        and checksum(target) == step["sha256"]):
                    # An earlier attempt already placed this file; only an archive's original may remain.
                    if step["action"] == "archive":
                        Path(step["from"]).unlink(missing_ok=True)
                else:
                    (_copy if step["action"] == "copy" else _archive)(step)
            except (OSError, PublishError) as error:
                step["status"] = "failed"
                finish("partial", f"{step['action']} of {Path(step['from']).name} failed: {error}")
                raise PublishError(state["attempts"][-1]["reason"]) from error
            step["status"] = "done"
            _write_publish(record_path, state)
        finish("published")
        return state
    finally:
        lock.unlink()


def record_skipped(record_path, reason):
    """Note that an approval chose not to publish, so `reema publish` can do it later."""
    state = read_publish(record_path) or {"schema_version": 1, "run_id": Path(record_path).parent.name,
                                          "record": str(record_path), "attempts": []}
    state["attempts"].append({"started_at": timestamp(), "finished_at": timestamp(), "steps": [],
                              "status": "skipped", "reason": reason})
    state["status"] = "skipped"
    _write_publish(record_path, state)


def is_published(run_dir):
    try:
        return json.loads((Path(run_dir) / PUBLISH_FILE).read_text(encoding="utf-8")).get("status") == "published"
    except (OSError, ValueError):
        return False

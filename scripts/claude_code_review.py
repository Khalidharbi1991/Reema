"""Finished-SOP review written by a Claude Code session, with no Anthropic API call (experiment).

Claude Code writes the findings; REEMA's code does everything else: the excerpt split, the local
template-gap check, quote location, finding IDs, hash binding and the run folder. The SOP file is
only read, and a review has no approval record.

    prepare FILE         write output/claude_code/<id>/review_request.json
    check   ID           validate excerpts.json (and consistency.json); write consistency_request.json
    finish  ID           run the review job into a NEW output/runs/ folder
    compare RUN_A RUN_B  compare two review runs of the same SOP

Run from the repository root with: python3 scripts/dev.py python scripts/claude_code_review.py ...
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.file_workers import FileReviewWorker  # noqa: E402
from src.agents.leader_agent import LeaderAgent  # noqa: E402
from src.agents.review_agent import ReviewAgent  # noqa: E402
from src.knowledge.retrieval import chunks  # noqa: E402
from src.utils.config import config_manager  # noqa: E402
from src.utils.documents import ExistingSopAssessment, section_map, sha  # noqa: E402
from src.utils.existing_sops import load_sop, require_unique_sections, template_gaps  # noqa: E402

# Shared work-folder helpers from the revise experiment.
_spec = importlib.util.spec_from_file_location("claude_code_revise", Path(__file__).with_name("claude_code_revise.py"))
_revise = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_revise)
work_root, _write, _require = _revise.work_root, _revise._write, _revise._require

PROFILE = config_manager.document_profile


def work_dir(work_id):
    if not work_id.isalnum():
        raise ValueError("Unknown work id")
    path = work_root() / work_id
    if not (path / "review_request.json").is_file():
        raise ValueError(f"No prepared review at {path}")
    return path


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def offline():
    """No key and no consent while a step runs, so a provider call could not be made."""
    settings = config_manager.system_config
    saved = settings.anthropic_api_key, settings.allow_external_ai
    settings.anthropic_api_key, settings.allow_external_ai = "", False
    try:
        yield
    finally:
        settings.anthropic_api_key, settings.allow_external_ai = saved


def _load(work_id):
    """Re-read the SOP; refuse if it is not byte for byte the file that was prepared."""
    path = work_dir(work_id)
    request = json.loads((path / "review_request.json").read_text(encoding="utf-8"))
    source = load_sop(request["source_path"])
    if source.sha256 != request["source_sha256"] or sha(source.content) != request["document_sha256"]:
        raise ValueError("The SOP changed since prepare; prepare it again")
    return path, request, source


def _consistency(path, request):
    """The consistency file, if this SOP needs one; it must be written from the current excerpts."""
    if not request["consistency_pass"]:
        return None
    consistency = path / "consistency.json"
    if consistency.is_file():
        try:
            bound = json.loads(consistency.read_text(encoding="utf-8")).get("excerpts_sha256")
        except (ValueError, AttributeError):
            raise ValueError("consistency.json is not a valid JSON object") from None
        if bound != file_sha256(path / "excerpts.json"):
            raise ValueError("consistency.json was written from other excerpts; run check, then reema-consistency-reviewer again")
    return consistency


def prepare(file):
    source = load_sop(file)
    require_unique_sections(source.content, PROFILE)
    locations = section_map(source.content, PROFILE)
    if not locations:
        raise ValueError("This SOP has no top-level sections (## headings or Word Heading 1) to review")
    parts = chunks(source.content, config_manager.system_config.review_chunk_chars)
    request = {
        "source_path": str(source.path), "source_sha256": source.sha256, "document_sha256": sha(source.content),
        "instructions": ReviewAgent.EXISTING_SOP_INSTRUCTIONS, "section_locations": locations,
        "template_gaps": template_gaps(source.content, PROFILE), "consistency_pass": len(parts) > 1,
        "excerpts": [{"excerpt": number, "start": offset, "end": offset + len(part), "text": part}
                     for number, (offset, part) in enumerate(parts, 1)],
        "assessment_schema": ExistingSopAssessment.model_json_schema()}
    work_id = uuid4().hex
    path = work_root() / work_id
    path.mkdir(parents=True)
    _write(path / "review_request.json", request)
    print(f"Prepared {work_id}: {len(parts)} excerpt(s), {len(locations)} section(s), "
          f"{len(request['template_gaps'])} local template gap(s)")
    print(f"Source SHA-256: {source.sha256}")
    print(f"Request: {path / 'review_request.json'}")
    print(f"Write the excerpt assessments to: {path / 'excerpts.json'}")
    return work_id


def check(work_id):
    path, request, source = _load(work_id)
    _require(path / "excerpts.json", "reema-reviewer")
    consistency = _consistency(path, request)
    complete = consistency is None or consistency.is_file()
    with offline():
        review = asyncio.run(FileReviewWorker(path / "excerpts.json", consistency,
                                              excerpts_only=not complete).review_existing(source.content))
    if request["consistency_pass"]:
        excerpts = json.loads((path / "excerpts.json").read_text(encoding="utf-8"))
        _write(path / "consistency_request.json", {
            "document_sha256": request["document_sha256"], "excerpts_sha256": file_sha256(path / "excerpts.json"),
            "instructions": request["instructions"], "section_locations": request["section_locations"],
            "assessments": [ExistingSopAssessment.model_validate(item).model_dump() for item in excerpts["assessments"]],
            "assessment_schema": request["assessment_schema"]})
    if complete:
        print(f"Review passed every check: {len(review['issues'])} finding(s), "
              f"{len(request['template_gaps'])} local template gap(s).")
        print(f"Next: finish {work_id}")
    else:
        print(f"Excerpts passed every check: {len(review['issues'])} finding(s).")
        print(f"Consistency request: {path / 'consistency_request.json'}; write the pass to {path / 'consistency.json'}")


def finish(work_id):
    path, request, source = _load(work_id)
    # Checked before the run starts, so a missing file leaves no failed run folder behind.
    _require(path / "excerpts.json", "reema-reviewer")
    consistency = _consistency(path, request)
    if consistency is not None:
        _require(consistency, "reema-consistency-reviewer")
    before = file_sha256(source.path)
    leader = LeaderAgent(api_key="")
    leader.register_worker("ReviewAgent", FileReviewWorker(path / "excerpts.json", consistency))

    async def run():
        try:
            return await leader.review_existing(source, local_author=True)
        finally:
            await leader.close()

    with offline():
        findings = asyncio.run(run())
    run_dir = Path(leader.context["run_dir"])
    after = file_sha256(source.path)
    if after != before:
        raise RuntimeError(f"The SOP's bytes changed during the review: {before} -> {after}")
    if (run_dir / "approval.json").exists() or (path / "approval.json").exists():
        raise RuntimeError("A review must not create an approval record")
    print(f"{len(findings['template_gaps'])} template gap(s), {len(findings['findings'])} finding(s).")
    print(f"Source SHA-256 before: {before}")
    print(f"Source SHA-256 after:  {after} (unchanged)")
    print("No approval record: a review has nothing to approve.")
    print(f"Findings: {run_dir / 'findings.md'}")
    return run_dir


def _run_facts(run_dir):
    run_dir = Path(run_dir)
    state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    findings = json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))
    if state.get("job") != "review":
        raise ValueError(f"{run_dir} is not a review run")
    titles = {key: value["title"] for key, value in findings.get("section_locations", {}).items()}
    items = findings["findings"]
    count = lambda field: ", ".join(f"{k} {v}" for k, v in sorted(Counter(i[field] for i in items).items())) or "-"
    usage = state.get("usage", {})
    return {"run": run_dir.name, "mode": state.get("mode"),
            "authoring": state.get("authoring", "anthropic_api" if state.get("mode") == "model" else "local_code"),
            "status": state.get("status"), "source_sha256": findings["source_sha256"],
            "template_gaps": len(findings["template_gaps"]), "findings": len(items),
            "blocking": sum(i["blocking"] for i in items), "by_category": count("category"),
            "by_severity": count("severity"),
            "sections": "; ".join(sorted({titles.get(i["section_id"], i["section_id"]) for i in items})) or "-",
            "model_calls": len(usage.get("calls", [])), "api_tokens": usage.get("accounted_tokens", 0),
            "approval_record": "yes" if (run_dir / "approval.json").exists() else "no",
            "_gaps": sorted(g["finding_id"] for g in findings["template_gaps"]),
            "_items": [f"{i['finding_id']} [{i['severity']}, {i['category']}] "
                       f"{titles.get(i['section_id'], i['section_id'])}: {i['description']}" for i in items]}


def compare(run_a, run_b):
    a, b = _run_facts(run_a), _run_facts(run_b)
    if a["source_sha256"] != b["source_sha256"]:
        print("Warning: the two runs reviewed different source files")
    width = max(map(len, a))
    for key in (k for k in a if not k.startswith("_")):
        print(f"{key:<{width}}  {str(a[key]):<40}  {b[key]}")
    print(f"\nTemplate gaps identical: {'yes' if a['_gaps'] == b['_gaps'] else 'no'}")
    for facts in (a, b):
        print(f"\n--- Findings in {facts['run']} ({facts['authoring']}) ---")
        print("\n".join(facts["_items"]) or "None")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", "-o", type=Path, help="Output root (default: ./output)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare").add_argument("file", type=Path)
    for name in ("check", "finish"):
        commands.add_parser(name).add_argument("work_id")
    two = commands.add_parser("compare")
    two.add_argument("run_a", type=Path)
    two.add_argument("run_b", type=Path)
    args = parser.parse_args(argv)
    if args.output is not None:
        config_manager.system_config.output_dir = args.output.expanduser().resolve()
    try:
        if args.command == "prepare":
            prepare(args.file)
        elif args.command == "check":
            check(args.work_id)
        elif args.command == "finish":
            finish(args.work_id)
        else:
            compare(args.run_a, args.run_b)
    except (ValueError, OSError, PermissionError, RuntimeError, KeyError) as error:
        print(f"Refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

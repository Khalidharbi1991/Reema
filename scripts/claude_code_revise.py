"""Finished-SOP revision written by a Claude Code session, with no Anthropic API call (experiment).

Claude Code writes the section text and the recheck; REEMA's code does everything else:
section choice, hash binding, the "only the target section changed" and "no new IDs" gates,
the Word splice and re-read, export and the pending human approval record.

    prepare FILE --section TITLE --instruction TEXT   write output/claude_code/<id>/request.json
    check   ID                                        validate patch.json; write recheck_request.json
    finish  ID                                        run the revise job into a NEW output/runs/ folder
    compare RUN_A RUN_B                               compare two revise runs of the same SOP

Run from the repository root with: python3 scripts/dev.py python scripts/claude_code_revise.py ...
This script never approves anything; the reviewer runs `reema approve` themselves.
"""

import argparse
import asyncio
import difflib
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.file_workers import FilePatchWorker, FileRecheckWorker  # noqa: E402
from src.agents.leader_agent import LeaderAgent  # noqa: E402
from src.utils.config import config_manager  # noqa: E402
from src.utils.documents import (CorrectionAssessment, SectionPatch, assert_no_new_references,  # noqa: E402
                                 assert_only_targets_changed, section_map, sha)
from src.utils.existing_sops import (changes_markdown, instruction_findings, load_sop,  # noqa: E402
                                     require_unique_sections, resolve_sections, splice_docx)
from src.utils.quality import parse_fenced_json_response  # noqa: E402
from src.utils.validation import missing_sections  # noqa: E402
from src.agents.content_agent import ContentAgent  # noqa: E402

PROFILE = config_manager.document_profile


def work_root():
    return config_manager.system_config.output_dir / "claude_code"


def work_dir(work_id):
    if not work_id.isalnum():
        raise ValueError("Unknown work id")
    path = work_root() / work_id
    if not (path / "request.json").is_file():
        raise ValueError(f"No prepared revision at {path}")
    return path


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _derive(request):
    """Re-read the SOP and re-locate the findings from the recorded instruction; nothing is taken on trust."""
    source = load_sop(request["source_path"])
    if source.sha256 != request["source_sha256"]:
        raise ValueError("The SOP changed since prepare; prepare it again")
    require_unique_sections(source.content, PROFILE)
    complete = not missing_sections(source.content, PROFILE)
    targets = resolve_sections(source.content, PROFILE, request["instruction"], request["sections"])
    findings = instruction_findings(source.content, PROFILE, request["instruction"], targets)
    return source, findings, set(targets), complete


def prepare(file, sections, instruction):
    if not instruction.strip():
        raise ValueError("--instruction cannot be empty")
    request = {"source_path": str(Path(file).expanduser().resolve()), "instruction": instruction.strip(),
               "sections": list(sections)}
    request["source_sha256"] = load_sop(request["source_path"]).sha256
    source, findings, targets, complete = _derive(request)
    locations = section_map(source.content, PROFILE, require_complete=complete)
    request.update(
        base_document_sha256=sha(source.content), require_complete=complete, findings=findings,
        target_sections={key: {"title": locations[key]["title"], "base_section_sha256": locations[key]["sha256"],
                               "body": source.content[locations[key]["body_start"]:locations[key]["end"]]}
                         for key in sorted(targets)},
        scope_rules=ContentAgent.FINISHED_SOP_SCOPE.strip(),
        patch_schema=SectionPatch.model_json_schema())
    work_id = uuid4().hex
    path = work_root() / work_id
    path.mkdir(parents=True)
    _write(path / "request.json", request)
    print(f"Prepared {work_id}: {', '.join(v['title'] for v in request['target_sections'].values())}")
    print(f"Request: {path / 'request.json'}")
    print(f"Write the patch to: {path / 'patch.json'}")
    return work_id


def check(work_id):
    path = work_dir(work_id)
    request = json.loads((path / "request.json").read_text(encoding="utf-8"))
    source, findings, targets, complete = _derive(request)
    patch = parse_fenced_json_response((path / "patch.json").read_text(encoding="utf-8"), SectionPatch)
    revised = patch.apply(source.content, targets, PROFILE, complete)
    assert_only_targets_changed(source.content, revised, targets, PROFILE, require_complete=complete)
    assert_no_new_references(source.content, revised, targets, PROFILE, require_complete=complete)
    new = section_map(revised, PROFILE, require_complete=complete)
    if source.kind == "docx":
        # Trial splice: refuses protected Word content now, rather than at finish.
        bodies = {key: revised[new[key]["body_start"]:new[key]["end"]].strip() for key in targets}
        trial = splice_docx(source, bodies, PROFILE, path / "check_preview.docx")
        assert_only_targets_changed(source.content, load_sop(trial).content, targets, PROFILE, require_complete=complete)
    _write(path / "recheck_request.json", {
        "revised_sha256": sha(revised), "findings": findings,
        "revised_sections": {key: revised[new[key]["body_start"]:new[key]["end"]] for key in sorted(targets)},
        "recheck_schema": {**CorrectionAssessment.model_json_schema(), "note":
                           "Add a top-level \"revised_sha256\" field copied from this file."}})
    (path / "changes_preview.md").write_text(changes_markdown(source.content, revised, source.path.name), encoding="utf-8")
    print(f"Patch passed every gate. Revised SHA-256: {sha(revised)}")
    print(f"Diff: {path / 'changes_preview.md'}")
    print(f"Recheck request: {path / 'recheck_request.json'}; write the recheck to {path / 'recheck.json'}")


def finish(work_id):
    path = work_dir(work_id)
    request = json.loads((path / "request.json").read_text(encoding="utf-8"))
    source, findings, _, _ = _derive(request)
    settings = config_manager.system_config
    saved = settings.anthropic_api_key, settings.allow_external_ai
    leader = LeaderAgent(api_key="")
    leader.register_worker("ContentAgent", FilePatchWorker(path / "patch.json"))
    leader.register_worker("ReviewAgent", FileRecheckWorker(path / "recheck.json"))

    async def run():
        try:
            return await leader.revise_existing(source, findings, local_author=True, origin={
                "instruction": request["instruction"], "claude_code_work": str(path)})
        finally:
            await leader.close()

    # Belt and braces: no key and no consent while it runs, so a provider call could not be made.
    settings.anthropic_api_key, settings.allow_external_ai = "", False
    try:
        outputs = asyncio.run(run())
    finally:
        settings.anthropic_api_key, settings.allow_external_ai = saved
    record = leader.context["delivery"]["approval_record"]
    print(f"Revised {len({f['section_id'] for f in findings})} section(s); the original file was not changed.")
    for fmt, output in outputs.items():
        print(f"{fmt}: {output}")
    print(f"Changes: {Path(record).parent / 'changes.md'}")
    print(f"Awaiting human approval: {record}")
    print(f'After reading it, approve with: reema approve "{record}" --reviewer "<your name>"')
    return outputs


def _run_facts(run_dir):
    run_dir = Path(run_dir)
    state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    source = json.loads((run_dir / "source.json").read_text(encoding="utf-8"))
    revised = json.loads((run_dir / "revised.json").read_text(encoding="utf-8"))
    complete = state.get("full_profile_checks", True)
    before, after = source["content"], revised["content"]
    old = section_map(before, PROFILE, require_complete=complete)
    new = section_map(after, PROFILE, require_complete=complete)
    changed = [old[k]["title"] for k in old if old[k]["sha256"] != new[k]["sha256"]]
    lines = list(difflib.ndiff(before.splitlines(), after.splitlines()))
    corrections = revised["recheck"]["corrections"]
    usage = state.get("usage", {})
    return {"run": run_dir.name, "authoring": state.get("authoring", "anthropic_api"),
            "status": state.get("status"), "source_sha256": source["sha256"],
            "sections_changed": "; ".join(changed),
            "lines_added": sum(l.startswith("+ ") for l in lines), "lines_removed": sum(l.startswith("- ") for l in lines),
            "recheck_resolved": f"{sum(c['status'] == 'resolved' for c in corrections)}/{len(corrections)}",
            "model_calls": len(usage.get("calls", [])), "api_tokens": usage.get("accounted_tokens", 0),
            "outputs": ", ".join(sorted(p.name for p in run_dir.glob("*_revised.*") if not p.name.startswith("~$"))),
            "_bodies": {k: after[new[k]["body_start"]:new[k]["end"]].strip() for k in revised["target_sections"]},
            "_titles": {k: new[k]["title"] for k in revised["target_sections"]}}


def compare(run_a, run_b):
    a, b = _run_facts(run_a), _run_facts(run_b)
    if a["source_sha256"] != b["source_sha256"]:
        print("Warning: the two runs revised different source files")
    width = max(map(len, a))
    for key in (k for k in a if not k.startswith("_")):
        print(f"{key:<{width}}  {str(a[key]):<40}  {b[key]}")
    for key in sorted(set(a["_bodies"]) | set(b["_bodies"])):
        title = a["_titles"].get(key) or b["_titles"].get(key)
        print(f"\n--- {title}: {a['run']} vs {b['run']} ---")
        sys.stdout.writelines(difflib.unified_diff(
            (a["_bodies"].get(key, "") + "\n").splitlines(keepends=True),
            (b["_bodies"].get(key, "") + "\n").splitlines(keepends=True), fromfile=a["run"], tofile=b["run"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", "-o", type=Path, help="Output root (default: ./output)")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("prepare")
    one.add_argument("file", type=Path)
    one.add_argument("--section", action="append", required=True, help="Section title or id; repeatable")
    one.add_argument("--instruction", required=True)
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
            prepare(args.file, args.section, args.instruction)
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

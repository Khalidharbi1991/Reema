"""New SOP written by a Claude Code session, with no Anthropic API call.

Claude Code writes the section text (the reema-writer subagent) and, when the euc specialist is
selected, Agent 10's patch appendix (the reema-agent10-euc subagent); REEMA's code does everything
else: the request and plan, the template skeleton, local checks on supplied specialist data, the
per-section and whole-document checks, export and the pending human approval record. No model reviews
the draft; run the reema-review skill on it afterwards if a review is wanted. The access, problem and
data specialists add no appendix.

    prepare PROCESS [--format F] [--objective TEXT] [--constraint TEXT] [--acceptance TEXT] [--custom]
            [--specialist S] [--specialist-input FILE]
                                 write output/claude_code/<id>/generate_request.json
    prepare ... --confirm-read TOKEN   needed when reference excerpts or a specialist input file are included
    check   ID                   check the section files; write draft_preview.md
    finish  ID                   run the generate job into a NEW output/runs/ folder

Run from the repository root with: python3 scripts/dev.py python scripts/claude_code_generate.py ...
This script never approves anything; the reviewer runs `reema approve` themselves.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.generate_job import check, finish, prepare, work_dir, work_root  # noqa: E402,F401
from src.utils.config import config_manager  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", "-o", type=Path, help="Output root (default: ./output)")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("prepare")
    one.add_argument("process")
    one.add_argument("--format", "-f", action="append", help="pdf, docx, markdown or html; repeatable")
    one.add_argument("--custom", action="store_true", help="Allow a process name outside the catalog")
    one.add_argument("--objective")
    one.add_argument("--constraint", action="append")
    one.add_argument("--acceptance", action="append")
    one.add_argument("--specialist", action="append", choices=["access", "problem", "data", "euc"],
                     help="Add a specialist; euc adds Agent 10's patch appendix; repeatable")
    one.add_argument("--specialist-input", type=Path, help="Local JSON input: IAM snapshot, incident observations or metric data")
    one.add_argument("--confirm-read", help="Token printed for the reference or input files; give it only after Khalid's yes")
    for name in ("check", "finish"):
        commands.add_parser(name).add_argument("work_id")
    args = parser.parse_args(argv)
    if args.output is not None:
        config_manager.system_config.output_dir = args.output.expanduser().resolve()
    try:
        if args.command == "prepare":
            prepare(args.process, args.format, custom=args.custom, objective=args.objective,
                    constraints=args.constraint or (), acceptance=args.acceptance or (), specialists=args.specialist or (),
                    specialist_input=args.specialist_input, confirm_read=args.confirm_read)
        elif args.command == "check":
            check(args.work_id)
        else:
            finish(args.work_id)
    except (ValueError, OSError, PermissionError, RuntimeError, KeyError) as error:
        print(f"Refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

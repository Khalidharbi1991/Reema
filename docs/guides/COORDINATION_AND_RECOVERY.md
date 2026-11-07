# Coordination in Claude Code, and what can be recovered

REEMA's work is coordinated by Ahmad, the main Claude Code session, using the skills
and subagents in `.claude/`. REEMA's own commands make no model call. The advisory
chat planner (`config/assistant_routes.yaml`), consultation records and model-phase
recovery were removed with the API path. Document approval remains a separate human
action. The [document quality guide](DOCUMENT_QUALITY.md) covers the section,
correction and export checks.

## Who does what

| Request | Route | Who writes | What REEMA's code does |
| --- | --- | --- | --- |
| New SOP | `abdullah-docs` → `reema-generate` | `reema-writer`; `reema-agent10-euc` for the patch appendix | Request and plan, checks, export, pending approval |
| Review a finished SOP | `abdullah-docs` → `reema-review` | `reema-reviewer`; a fresh `reema-consistency-reviewer` | Excerpts, quote location, finding IDs, findings record |
| Revise a finished SOP | `abdullah-docs` → `reema-revise` | `reema-reviser`; a fresh `reema-rechecker` | Section gates, Word splice, export, pending approval |
| Building or home design | Ahmad | `reema-agent9-design` | Local `drawing` commands |
| Endpoint question | Ahmad | `reema-agent10-euc` | — |
| Strategy, prioritization, governance | Ahmad answers himself | — | — |
| Tasks and memory | Ahmad | — | Local `task` and `memory` commands |

Subagents cannot call other subagents, so Ahmad routes everything himself. Each
subagent has only Read and Write tools and reads only the request file of its job (or
files Ahmad names after Khalid's yes). A refusal from a check step goes back to the
subagent that wrote the file, at most three rounds, then Ahmad stops and reports.
Drafting is fine; sending, purchasing, booking, deploying or approving is not done.

## Job phases and status

Each job runs in a new `teams/documentation/output/runs/<run-id>/` folder, and `run.json` records the
phases as they happen:

- generate: `planning`, `content`, `checks`, `formatting`, `human_review_record`
- review: `template_check`, `review` (Claude Code only), `findings_record`
- revise: `revision`, `recheck`, `formatting`, `human_review_record`
- export: `formatting`, `human_review_record`

A failed or cancelled job is recorded as such, with its error type; later phases are
marked `skipped`. A run folder is locked (`RunLease`, `.owner.lock`) while a job
writes it, so two jobs cannot write the same folder.

## What can be recovered

The Claude Code work folder (`teams/documentation/output/claude_code/<id>/`) is the recovery point for
unfinished work: the request and the files the subagents already wrote stay there.
Run `check` again after fixing a file, or `finish` once every check passes; a job
that failed at finish can simply be finished again into a new run.

A run that reached `ready.json` can be exported again with no model call:

```bash
python3 scripts/dev.py run export teams/documentation/output/runs/<run-id> -f markdown -f docx
```

This checks the checkpoint's SHA-256, runs a Claude Code draft through every local
check again (a run from the removed API path keeps its saved review gate), and writes
a new run that needs a fresh human decision. `resume` is a hidden old name for
`export`. Old runs keep loading: unknown `run.json` keys, `usage` records,
`execution.json` and `.owner.lock` files from earlier versions are ignored.

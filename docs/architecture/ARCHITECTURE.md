# System Architecture

REEMA is a local Python CLI for Khalid's IT company. Since the no-API migration
(2026-10-30/31) it makes no model call: a Claude Code session writes the text through
skills and subagents, and REEMA's code plans, checks, exports and records it for
human approval. `AGENTS.md` wins where this page and it disagree. Earlier versions
(an Anthropic-backed asynchronous pipeline with research, enrichment, review loops,
advisory chat and model-phase recovery) are described in `docs/reports/` and
`docs/archive/` as history.

## Overview

```
Khalid
  │  plain words
  ▼
Claude Code session = Ahmad (executive assistant)      .claude/skills, .claude/agents
  ├─ abdullah-docs ─┬─ reema-generate ─ reema-writer (+ reema-agent10-euc appendix)
  │                 ├─ reema-review  ─ reema-reviewer, reema-consistency-reviewer
  │                 └─ reema-revise  ─ reema-reviser, reema-rechecker
  ├─ reema-agent10-euc (advice)
  ├─ reema-agent9-design-lead ─ reema-agent19…23 subagents ─▶ teams/home-design/New Home/ (own git repo)
  ├─ reema-agent11-dev-lead ─ reema-agent12…18 subagents ─▶ teams/development/projects/<name>/ (own git repo)
  └─ local commands: task, memory, find-sop, drawing
         │
         │  writes JSON / Markdown under teams/documentation/output/claude_code/<id>/
         ▼
REEMA (Python, no model call, no network)
  prepare → request file (plan, skeleton, rules, approved excerpts)
  check   → file-backed workers through the existing gates
  finish  → LeaderAgent job → checks → FormatAgent export → approval.json (pending)
         │
         ▼
teams/documentation/output/runs/<run-id>/  ──  reema approve / reject (human)  ──  publish into teams/documentation/output/
```

Subagents cannot call each other, so Ahmad routes everything. They have only Read and
Write tools, except the Development developer and tester (Agents 14 and 15), which also
have Edit, Glob, Grep and Bash for their project folder. Every prepare step that copies document text needs Khalid's yes as a
`--confirm-read` token for those exact files (`src/utils/read_gate.py`), plus the
reference manifest for anything under `teams/documentation/input/references/`.

## Jobs

| Job | Entry | Request file | Written by Claude Code | Leader method | Ends |
| --- | --- | --- | --- | --- | --- |
| Generate | `reema generate` or `scripts/claude_code_generate.py prepare` | `generate_request.json` | `sections/NN-<id>.md`, `appendices/endpoint.md` | `generate_local` | `awaiting_human_approval`, `quality_score` null |
| Review | `scripts/claude_code_review.py prepare` | `review_request.json` | `excerpts.json`, `consistency.json` | `review_existing(local_author=True)` | `review_complete`, no approval record |
| Revise | `scripts/claude_code_revise.py prepare` | `request.json` | `patch.json`, `recheck.json` | `revise_existing(local_author=True)` | `awaiting_human_approval` |
| Template check | `reema review FILE` | — | — | `review_existing(local_only=True)` | `review_complete` |
| Export | `reema export RUN` | — | — | `export_run` | `awaiting_human_approval` |

The file-backed workers (`src/agents/file_workers.py`) subclass Agent 3 and Agent 4:
`FileSectionWriter`, `FileReviewWorker`, `FilePatchWorker`, `FileRecheckWorker`. Each
answers `BaseAgent._reply` from the files, so the original per-section loop, located
review, section patch and recheck checks run unchanged. `BaseAgent._reply` itself
raises: no other path supplies text.

## Components

```
src/
├── main.py              CLI (Typer): generate, review, revise*, export, resume*, approve,
│                        reject, publish, find-sop, task, memory, drawing, agents, status
│                        (* hidden pointers/aliases; chat* points to Claude Code)
├── generate_job.py      Claude Code generate: prepare, check, finish
├── agents/
│   ├── leader_agent.py  Abdullah: request/plan, check_draft, generate_local, review_existing,
│   │                    revise_existing, export_run, phases and delivery
│   ├── content_agent.py Agent 3: section loop, SECTION_RULES, revise_sections
│   ├── review_agent.py  Agent 4: review brief, located review, recheck
│   ├── format_agent.py  Agent 5: export to Markdown, HTML, DOCX, PDF
│   ├── euc_agent.py     Agent 10: protocol (shared with its subagent), appendix outline/check
│   ├── building_design_agent.py  Agent 9: DWG intake, DXF concept mesh (DXF summary: utils/cad_summary.py)
│   ├── secretary_agent.py        Ahmad: local task store and communication log
│   ├── file_workers.py  Claude Code file-backed workers
│   └── base_agent.py    config, knowledge text, the _reply hook
├── formatters/          Markdown, HTML, DOCX, PDF writers and shared theme
├── knowledge/           curated knowledge files (source material), reference retrieval
└── utils/
    ├── config.py        settings (.env, unknown keys ignored) and YAML catalogs
    ├── read_gate.py     confirm-read token and manifest check
    ├── existing_sops.py finished-SOP intake, template gaps, findings, DOCX splice, find-sop
    ├── documents.py     section map, SectionDraft/Patch, controls, located findings
    ├── quality.py       quality report, structured parse, excerpt assessment
    ├── specialists.py   IAM, problem case, metric checks (specialist_checks)
    ├── runs.py          RunStore checkpoints, ready checkpoint loading
    ├── ownership.py     RunLease lock on a run folder
    ├── approvals.py     pending/decided approval records
    ├── publish.py       publishing approved revisions, archiving older versions
    └── tasks.py         local work/personal task and memory stores (SQLite)
config/                  agent roles, processes, standards, document profile, specialist policy
scripts/                 Claude Code job scripts, dev launcher, export and QA fixtures
tests/                   offline tests; network blocked; strict no-API guard
```

Agents 1, 2, 6, 7 and 8 have no class; they remain roles in `config/agent_config.yaml`
and their knowledge files remain in `src/knowledge/`.

## Data and storage

- `teams/documentation/input/references/` (ignored): customer sources; only manifest-allowed, hash-matching
  files can be searched, and only after the confirm-read token.
- `teams/documentation/output/claude_code/<id>/` (ignored): a job's request and the subagents' files.
- `teams/documentation/output/runs/<run-id>/` (ignored): `run.json`, checkpoints, drafts, `approval.json`,
  `publish.json`; locked while a job writes it.
- `teams/coordination/data/` (ignored): work and personal SQLite stores; not encrypted.
- `teams/documentation/output/archive/<run-id>/`: older versions moved aside when a revision is published.

## Security boundaries

- No model client, key, consent flag or network call in REEMA; the guard test fails
  on any API reference, declaration, installation or import.
- What a Claude Code session reads goes to Anthropic through Claude Code; the
  confirm-read token and the manifest decide what it may read.
- File text is untrusted data for every subagent.
- No agent or session approves: `.claude/settings.json` denies approve, reject,
  publish and `git push` (Khalid pushes main himself), plus remotes, git config changes,
  `.git` folders, `git credential`, shell profiles, package publishing, deploy tools, `sudo` and
  network tools, also caught inside wrappers by `.claude/hooks/dev_guard.py`); approval records bind file SHA-256 values to a
  self-declared human reviewer.
- There is no container image, CI workflow, deployed service, mailbox or calendar
  connection.

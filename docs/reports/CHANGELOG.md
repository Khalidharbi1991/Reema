# REEMA changelog

Newest first. Each entry summarizes completed work and links the report that
records its verification. Current rules and behavior live in
[AGENTS.md](../../AGENTS.md). The [finite ledger](PENDING_LEDGER.md) records external
requirements as they stood before the no-API migration below.

## 2026-11-13 — Snafi phases 1 and 2: ready for a first deploy (not deployed)

Phase 2 fix: chat sometimes showed "Couldn't send. Try again." while Khalid's message
stayed in the chat with Ahmad "thinking" and no reply queued (the live logs showed
the message saved and the job refused). The app now saves the message and its
`chat.reply` job in one transaction (`send_chat`, migration 0004). The composer keeps
the text after a failed send (React had cleared it) and hides the failure note once
Khalid types again. Phase 1, before going online: a per-request nonce
Content-Security-Policy and HSTS (SEC-3); a sign-in throttle of 5 wrong passwords in
15 minutes per email, and per client IP on Vercel, stored as keyed hashes in Supabase
(SEC-4, migration 0005, `SNAFI_THROTTLE_SECRET`); and redirects to a fixed site
address (`SNAFI_SITE_URL` or Vercel's own), never the request's Host. TOTP MFA is
proposed, not built. Agent 16's review is in `apps/snafi-web/docs/SECURITY_REVIEW.md`.
Nothing was deployed or pushed.

## 2026-11-08 — Ahmad becomes Khalid's executive personal assistant

Ahmad is no longer described only as the IT documentation coordinator. He is Khalid's
executive personal assistant, the front of REEMA and of the Snafi app
(`docs/snafi/PRD.md`). He handles personal work (chat in Arabic and English, mail,
calendar, Todoist, Drive, reminders, memory, proactive briefs, family messaging
over Telegram) and coordinates the Personal, Documentation, Home Design and
Development teams. He follows the PRD's four permission levels and never shares
Khalid's private data with family. The mail, calendar, task and Telegram parts are
planned for Snafi steps 2–8 and not connected yet. In a Claude Code session he still
uses the work area only. AGENTS.md, README.md (whose "12 agent roles" is corrected
to 25), the personal assistant, coordination and architecture guides, his system
prompt, his knowledge files and his config role were updated. No behavior or test
changed.

## 2026-11-07 — Team folders under `teams/`

IT Consultant is now the single main folder. Each section keeps its local files under `teams/`
(`teams/README.md`); code stays shared in `src/`, and logs stay in `logs/`:
`teams/coordination/data/` (task and memory stores, was `output/assistant/`),
`teams/documentation/input/references/` (was `references/`), `teams/documentation/input/diagrams/`
(was `diagrams/`), `teams/documentation/input/handover/` (the three root handover documents),
`teams/documentation/output/` (was `output/`), `teams/home-design/New Home/` (was
`D:/Projects/REEMA Projects/New Home/`), `teams/home-design/legacy-output/` (was `output/agent9/`) and
`teams/development/projects/` (was `D:/Projects/REEMA Projects/`). Git ignores everything under
`teams/` except the READMEs. The config defaults, the guard (New Home is found relative to the repo;
the task-store and references checks cover the new and the old folders) and the deny rules (old ones
kept, new ones added) follow. New Home and every new dev project carry a `.claude/settings.json` with
`claudeMdExcludes`, because Claude Code loads CLAUDE.md from every parent folder: a verification
session started in New Home loaded no CLAUDE.md, AGENTS.md, REEMA skill or REEMA subagent. Old run
records keep their absolute paths unchanged. The old locations were copied, not deleted, and a
backup is in `D:/Backups/REEMA-before-reorg-20261107/`.

## 2026-11-07 — Home Design: Agent 22 gets Edit

Agent 22 (`reema-agent22-3d-modeler`) now has Read, Write, Edit and PowerShell, so it can change
a long reviewed script with targeted replacements instead of rewriting the whole file (the
master-suite scene script outgrew one Write). Edit goes through the same guard check as Write:
scripts under `scripts/blender/` or `scripts/freecad/` and named results in `output/` only, never
`reviews/script_reviews.json`. Every script change still needs Agent 16's review and a recorded
SHA-256 before it runs. A test checks that an Agent 22 Edit of the ledger is blocked.

## 2026-11-04 — Home Design: `output/models/furniture/`

The guard allows one subfolder below the five `output/` folders: `output/models/furniture/`, for
single furniture pieces, with the same `<date>_<area>_<what>` names, for agent writes and for
Blender `.blend` and script-argument paths. Any other nested folder is still refused.

## 2026-11-03 — `drawing measure`

`drawing measure FILE.dxf --layers A-WALL --point x,y --angle deg --reach 20 --output NEW.json`
follows the full line through each point (1 to 50) at each angle (1 to 8), records every crossing
with LINE and LWPOLYLINE segments on the named layers (merging crossings within 0.5 mm), and
lists the spans between consecutive crossings, flagging the span that contains the point. Every
result is labelled "measured from geometry", not a stated dimension. Tested on a room drawn
straight and rotated 40.75°.

## 2026-11-03 — `drawing extract`

`drawing extract FILE.dxf --layers A,B --xmin --ymin --xmax --ymax --output NEW.json` writes the
LINE, ARC, CIRCLE, LWPOLYLINE and INSERT entities of the named layers (1 to 20) that have a
point inside one area (at most 500 by 500 units), as the drawing stores them, with counts,
skipped types and named layers that no entity uses. It replaces the one-off script used for the
master suite's doors and windows (same 64 entities). DXF loading is shared with `drawing summary`.

## 2026-11-03 — Configurable drawing summary caps

`drawing summary` kept at most 500 text labels and 500 dimensions, which left out 945 of
1,445 labels in Khalid's plan. The caps are now `cad_summary_max_texts` and
`cad_summary_max_dimensions` in `config/specialist_policy.yaml` (default 5,000 each, 1 to
100,000), and every summary records the `limits` it used next to its `truncated` counts.

## 2026-11-03 — Home Design: one output folder for every result

Every Home Design result now goes in `New Home/output/` (`renders/`, `models/`, `drawings/`,
`summaries/`, `reports/`), named `<date>_<area>_<what>`. The guard's write check allows
Agents 19–23 and Agent 16 only their named results there (Agent 22 also its scripts) and holds
Ahmad's New Home writes to the same rule plus the READMEs, `.gitignore` and the approval
record. Blender's `-o` and `.blend` paths and ODA's output folder point into `output/`; a script
approval's review must be a named report in `output/reports/`. `output/` is ignored in the New
Home repo except its README.

## 2026-11-03 — Home Design section (Agent 9, Agents 19–23)

Built on branch `feature/home-design` after tag `pre-homedesign-20261103-1940`, following
Khalid's choices A1, B1, C1+b, D2, E1 (Agent 16), F1, G1, H2, I, J1 and K1:

- **Agent 9** is now the `reema-agent9-design-lead` skill, Ahmad's playbook; the old
  subagent's rules are kept word for word, with a note on how they apply to Ahmad. Every
  job asks which part of the home first and waits for Khalid's yes to the plan and agents.
- **Agents 19–23** subagents: blueprint reader, space planner, interior designer,
  3D modeler (Read, Write, PowerShell) and design reviewer. Agent 16 also reviews
  Agent 22's scripts.
- **Guard:** the hook input's `agent_type` (checked first with a probe) lets only Agent 22
  run Blender 4.5 LTS, `freecadcmd` and ODA File Converter, by installed path, one program
  per command, paths inside New Home, Blender offline with auto-run off, and only scripts
  whose SHA-256 is recorded as reviewed. The programs are blocked for everyone else; a new
  `Write|Edit` hook keeps Agents 19–23 in their New Home folders and lets only Ahmad
  record approvals.
- `drawing summary`: a local DXF summary (layers, text labels, dimensions, door and
  window candidates; no room inferred) for Agent 19.
- New Home project at `../REEMA Projects/New Home/`: local repo, no remote, DWG, DXF,
  models and renders ignored; tag `job-newhome-20261103-start`.
- Installed: Blender 4.5.10 LTS, FreeCAD 1.1.4, Sweet Home 3D 7.5 (winget) and ODA File
  Converter 27.10.0 (signed MSI from opendesign.com).

## 2026-11-01 — Development section (Agents 11–18)

The Development section is working in Claude Code, built on branch `feature/dev-section`
after tag `before-dev-section` on main, following Khalid's decisions D1–D6:

- **Agent 11** `reema-agent11-dev-lead` skill: sizes each job (small fix, feature, app,
  game), picks only the agents needed, shows the plan with every package to install and
  waits for Khalid's yes; PRD first; one git repo per project in `../REEMA Projects/`;
  tags at the start and end of every job and before each risky change.
- **Agents 12–18** subagents: requirements, architect, developer, tester, security, UI,
  game writer. Only 14 and 15 have Bash (plus Edit, Glob, Grep).
- **Done** is blocked by an open Critical or High security finding; Medium and Low go
  to Khalid. No online scanner.
- `.claude/settings.json`: the projects folder as an additional directory; deny rules for
  remotes, package publishing, deploy tools, `sudo`, network tools, and file tools on
  `references/` and `output/assistant/`; a Bash `PreToolUse` hook
  (`.claude/hooks/dev_guard.py`) that also blocks them inside `sh -c`, `eval`, `env`,
  `xargs` and command substitution.
- Setup tests check a per-agent tool list, the org chart, team table, skill rules, deny
  rules and the hook (suite → 643, all passing).

## 2026-10-30/31 — No-API migration: REEMA runs through Claude Code only

REEMA no longer makes any Anthropic API call, holds a key or opens a network
connection; Claude Code writes the text through skills and subagents, and REEMA's code
plans, checks, exports and records it. Done in reversible steps, each tagged
`pre-no-api-<n>` on main before its branch, following Khalid's decisions D1–D10 and
G1–G12:

- **0** A guard test listing every remaining API reference (suite 835 → 836).
- **1** Review and revise only through Claude Code; `reema review` is the local
  template check, `reema revise` points to Claude Code. Prepare steps need a
  `--confirm-read` token for the exact file and enforce the reference manifest
  (`src/utils/read_gate.py`) (→ 837).
- **2** `reema chat` retired (hidden stub); `src/assistant.py`, the chat routing
  config and advice contracts removed; new `reema find-sop` (→ 730).
- **3** `reema-agent9-design` and `reema-agent10-euc` advice subagents (→ 733).
- **4a** Claude Code generate (option C): `prepare`/`check`/`finish`, the
  `reema-writer` subagent writing one file per section, `FileSectionWriter`,
  `LeaderAgent.generate_local`; `quality_score` optional; reference excerpts behind
  the token (→ 752).
- **4b** Agent 10 writes the patch appendix; Agents 6/7/8 add no appendix, and their
  local checks on a `--specialist-input` file go into the request as data (→ 756).
- **4c** The API generate path removed; `reema generate` runs prepare; Agents 1, 2,
  6, 7, 8 lose their classes (roles stay); model-phase resume removed (→ 610).
- **4d** The signed recovery journal and `.recovery-key` removed; `reema export RUN`
  re-exports offline, old runs still load; `RunLease` kept (→ 613).
- **5** The provider/runtime, the client in `BaseAgent` (hook now `_reply`), API and
  consent settings and `--allow-external-ai` removed; unknown `.env` entries are
  ignored; the evaluation is offline only; AGENTS.md rules reworded with Khalid's
  approval (→ 579).
- **6** `anthropic` removed from `pyproject.toml`, locks regenerated with `uv`;
  Dockerfile, `.dockerignore`, CI workflow and the archived generation script
  deleted; the test suite blocks the network; the guard is strict (→ 582).
- **7** Current guides, architecture, AGENTS.md and README rewritten for Claude Code;
  `docs/archive/` and the older reports left as history.

## 2026-10-30 — Publish on approve

`reema approve` on a revise run copies the approved drafts to the top of `output/` and moves every lower version of the same SOP, in a published format, to `output/archive/<run-id>/` (`src/utils/publish.py`). The plan is previewed before the confirm prompt; targets are never overwritten (`os.link`), every copy and move is SHA-256 checked, and the outcome goes to the run's `publish.json`. A refused or partial publish keeps the approval, exits 1 with "approved, not published", and `reema publish <record>` resumes it; `approve --no-publish` skips it. Generate runs, old `_revised` drafts and runs approved earlier are not published. `.claude/settings.json` denies `publish`; `find_sops` hides published run drafts and version numbering counts `output/archive/`. Suite: 816 before, 835 after.

## 2026-10-30 — Version numbers on revised SOPs

Revised drafts from `reema revise`, chat and the Claude Code revise are named with the next file version (`_V2` → `_V2.1`, no version → `_V1.1`) instead of `_revised`; `--major` (CLI and `claude_code_revise.py prepare`) takes the next major version (`V2.3` → `V3.0`). Every draft in `output/` and its runs counts, rejected ones included; old `_revised` files are not renamed and count as their plain version. Document Control inside the document is not changed; `changes.md` and `run.json` (`file_version`) record that. Suite: 786 before, 816 after.

## 2026-10-30 — Claude Code revise from review findings

`scripts/claude_code_revise.py prepare` takes `--from-review RUN --finding ID` (1–5 findings) as well as `--instruction`; the review checks rerun at prepare, check and finish, and a review run or `request.json` changed since prepare is refused. The `abdullah-docs` and `reema-revise` skills use it. Suite: 769 before, 786 after.

## 2026-10-30 — Review and revise finished SOPs

Added `reema review` (with `--local-only`), `reema revise` (instruction or review findings; DOCX splice) and Ahmad chat access through Abdullah, all ending without AI approval. Suite: 673 before, 714 after.

## 2026-10-30 — Unused dependencies removed

Dropped aiofiles, pandas, lxml and python-dotenv from `pyproject.toml` and relocked with `uv` (lxml and python-dotenv remain as python-docx and pydantic-settings dependencies); removed leftover ITOM blank lines from two agent prompts. Suite: 673 before, 673 after.

## 2026-10-30 — Cleanup after the gap review

No user-facing features changed. `reema version` now reports 2.0.0, matching the
package metadata, and `reema status` no longer lists an ITOM file. Removed code that
nothing called: the research/problem agents' ITOM loaders, the leader's model client
and `_call_claude`, Ahmad's delivery-summary and owner-briefing helpers, unused
`agent_config.yaml` keys and `scripts/utilities/agent_introductions.py`. README setup,
troubleshooting, license and Python API example were corrected, and outdated guides
moved to `docs/archive/`. Unused dependencies were left in place until the lock files
can be regenerated with `uv`. Suite: 677 before, 673 after (one test added, five
removed with the deleted helpers).

## 2026-10-29 — Personal assistant purpose

Purpose changed to personal assistant; work-first priority; patch report
PowerPoint as first new feature.

## 2026-10-29 — Ahmad consults chat specialists directly

Abdullah was removed from the chat path and now leads only the SOP generation
pipeline. Ahmad consults matched specialists directly and answers strategy,
roadmap, budget and prioritization requests himself. AGENTS.md became the single
source of truth, with CLAUDE.md importing it.

## 2026-10-28 — Agent 10 (end-user computing)

Agent 10 joined as the end-user computing and endpoint-management specialist, for
chat advice and the endpoint appendix of the Workstation Security Patches and
Devices Batch Management SOPs. Twelve roles since then.

## 2026-10-16 — Package 5: completion and evaluation

Package 5 completes the finite software roadmap with bilingual intent/context,
kernel-owned crash recovery, separately validated review chunks, Arabic/RTL
graphs and layouts, bounded IAM/causal/calendar/CAD depth, and a versioned
synthetic all-role evaluation harness (twelve roles since Agent 10). See
[the package 5 report](AGENT_IMPROVEMENTS_PACKAGE_5.md),
[completion and evaluation](../guides/COMPLETION_AND_EVALUATION.md) and the
[finite ledger](PENDING_LEDGER.md).

## 2026-10-16 — Package 4: project setup and specialist checks

Package 4 adds a hash-locked project `.venv` launcher with native PDF discovery,
Research claim/date records, supplied IAM snapshot checks, incident timelines and
competing hypotheses, deterministic metric calculations and bounded CAD geometry
validation. See [the package 4 report](AGENT_IMPROVEMENTS_PACKAGE_4.md),
[development setup](../guides/DEVELOPMENT_SETUP.md) and
[specialist evidence and checks](../guides/SPECIALIST_EVIDENCE_AND_CHECKS.md).

## 2026-10-15 — Package 3: document quality

Package 3 adds evidence-linked control registers, configured stable sections,
digest-bound targeted corrections, located findings/rechecks and deterministic
export checks. See [the package 3 report](AGENT_IMPROVEMENTS_PACKAGE_3.md) and
[document quality](../guides/DOCUMENT_QUALITY.md).

## 2026-10-15 — Package 2: coordination and recovery

Package 2 adds explicit shared capabilities in `src/utils/capabilities.py`, request
and session contracts in `coordination.py`, and locally authenticated execution
records in `execution.py`, with completed-call recovery for failed/cancelled runs.
See [the package 2 report](AGENT_IMPROVEMENTS_PACKAGE_2.md) and
[coordination and recovery](../guides/COORDINATION_AND_RECOVERY.md).

## 2026-10-15 — Package 1: handoffs and status

Package 1 makes specialist handoffs preserve full payloads under strict internal
contracts, validates review and compliance decisions before gates, and makes
leader status count actual phases. See
[the package 1 report](AGENT_IMPROVEMENTS_PACKAGE_1.md) and
[handoffs and status](../guides/AGENT_HANDOFFS_AND_STATUS.md).

## 2026-09-28 to 2026-09-29 — Earlier checkpoints

- [Phases 0–1](PHASE_0_1_CHECKPOINT.md): safety baseline and workflow correctness.
- [Phases 2–5](PHASE_2_5_CHECKPOINT.md): async provider, checkpoints, source
  permissions and structured review.
- [Personal assistant](PERSONAL_ASSISTANT_CHECKPOINT.md): work/personal scope;
  the former owner agent removed.
- [Building design](BUILDING_DESIGN_CHECKPOINT.md): Agent 9 and the Agent 1–8
  display names.

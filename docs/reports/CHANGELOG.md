# REEMA changelog

Newest first. Each entry summarizes completed work and links the report that
records its verification. Current rules and behavior live in
[AGENTS.md](../../AGENTS.md); open external requirements live in the
[finite ledger](PENDING_LEDGER.md).

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

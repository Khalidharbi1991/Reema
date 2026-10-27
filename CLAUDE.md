# REEMA — Project Context

This file describes the current application and the working rules for any coding
agent on this repository. Follow `README.md` for setup and CLI commands.

Package 5 completes the finite software roadmap with bilingual intent/context,
kernel-owned crash recovery, separately validated review chunks, Arabic/RTL
graphs and layouts, bounded IAM/causal/calendar/CAD depth, and a versioned
synthetic eleven-role evaluation harness. Shipped models inherit configurable
Sonnet 4.6 defaults. See `docs/guides/COMPLETION_AND_EVALUATION.md` and
`docs/reports/PENDING_LEDGER.md`. Live evaluation still requires an API key and
authorization of its exact synthetic material; the offline canonical-answer mock
is harness evidence, not model/full production-agent quality evidence.

Package 3 adds evidence-linked control registers, configured stable sections,
digest-bound targeted corrections, located findings/rechecks and deterministic
export checks. See `docs/guides/DOCUMENT_QUALITY.md` and
`docs/reports/AGENT_IMPROVEMENTS_PACKAGE_3.md`. Applicability and model correction
judgments remain unverified; successful generation still needs human approval.

Package 4 adds a hash-locked project `.venv` launcher with native PDF discovery,
Research claim/date records, supplied IAM snapshot checks, incident timelines and
competing hypotheses, deterministic metric calculations and bounded CAD geometry
validation. See `docs/guides/DEVELOPMENT_SETUP.md`,
`docs/guides/SPECIALIST_EVIDENCE_AND_CHECKS.md` and the package 4 report.

## Purpose and runtime

REEMA coordinates a user's work and personal tasks and supports IT process
documentation. It is a Python CLI with an Anthropic-backed, asynchronous agent
runtime. The coding agent (Claude Code, Codex, or others) maintains, tests, and
evolves the repository. The application has not moved to OpenAI.
Local task commands use SQLite and make no model calls. Conversations require an
API key and explicit external-AI authorization. Work and personal task lists are
stored separately under `output/assistant/` by default.
Explicit preferences, profile facts, project context, correction lessons and
short examples persist in those area-specific databases. Advisory chat shares
area-wide and exact selected-project context with Ahmad and specialists; examples
use bounded lexical retrieval. Memory is editable/deletable and never saved by
model inference. Conversation transcripts remain session-only.

## Current team

There are eleven active agent roles. The user speaks to **Ahmad**, the personal
coordinator. **Abdullah** leads specialist work and carries the former owner
agent's strategy, governance, quality, and business-value responsibilities.
The former owner agent has been removed. The user makes consequential decisions
and approves documents.

| Agent | Responsibility |
| --- | --- |
| Ahmad | Task management, planning, communication, coordination |
| Abdullah | Strategy, specialist orchestration, document workflow |
| Agent 1 | Research and IT service practices |
| Agent 2 | Standards and control alignment |
| Agent 3 | Writing and SOP content |
| Agent 4 | Quality review |
| Agent 5 | Document formatting and export |
| Agent 6 | Access and identity security |
| Agent 7 | Problem management and root-cause analysis |
| Agent 8 | Metrics and analytics design |
| Agent 9 | Building-design advice, local DWG intake, and bounded DXF-to-OBJ concept meshes |

Ahmad's bounded request planner is configured in `config/assistant_routes.yaml`.
Positive capability matches consult through Abdullah; common clause negation and
ambiguous/overbroad requests are handled deterministically. Unmatched advice stays
with Ahmad. Explicit task context and exact user turns survive the recent response
window within a bounded session, without becoming permanent memory. The old agent
knowledge files remain source material; historical references to the prior
hierarchy inside them do not grant authority.

## Documentation pipeline

The existing 16-process catalog is configured in `config/process_definitions.yaml`.
Abdullah runs planning, research and standards analysis, content generation,
selected specialist enrichment, full-document review, selected compliance
checks, formatting, and local delivery. Core workers are Agents 1–5. Agents
6–8 join when selected by a process or
explicit CLI option. Ahmad's local task interface is separate from this pipeline.

SOPs have 11 required sections and can be exported as Markdown, HTML, DOCX,
and PDF. The 15–30 rendered PDF page target warns by default and can be enforced
by configuration. Model quality scores, standards names, and source citations do
not certify factual or regulatory compliance. Successful generation produces
drafts in `output/runs/<run-id>/` and ends at `awaiting_human_approval`.
No agent can approve a document as a human reviewer.

Specialist handoffs preserve full payloads and use strict internal contracts in
`src/utils/handoffs.py`; public agent strings/dictionaries remain compatible.
Optional findings/provenance/assumptions metadata remains unverified. Review and
compliance decisions are validated before gates, including offline export recovery.
Leader status counts actual coordination phases, with persisted failure/cancellation
and skipped states in `run.json`. Ahmad's legacy communication helper records
locally and reports `not_dispatched`. See
`docs/guides/AGENT_HANDOFFS_AND_STATUS.md` and
`docs/reports/AGENT_IMPROVEMENTS_PACKAGE_1.md` for scope and remaining work.

Package 2 adds explicit shared capabilities in `src/utils/capabilities.py`, request
and session contracts in `coordination.py`, and locally authenticated execution
records in `execution.py`. Failed/cancelled new runs can resume completed research,
generation and enrichment with fresh consent and verified input/config/source/code
identity. Version 2 also recovers locally abandoned running owners after an OS
lease check and reuses separately validated review/compliance chunks. Uncertain
in-flight requests stay charged; exactly-once provider execution is not claimed.
Ready-only recovery remains offline. Reused work and inherited usage are reported separately.
See `docs/guides/COORDINATION_AND_RECOVERY.md` and
`docs/reports/AGENT_IMPROVEMENTS_PACKAGE_2.md` for the bounded recovery contract.

## Sources and privacy

Reference material stays in ignored `references/`. Only files explicitly listed
with permission and a matching SHA-256 in the local manifest may enter model
context. Curated `src/knowledge/` files are preserved as source material.
Private tasks and generated outputs remain under ignored local paths, but local
SQLite files are not encrypted. `--allow-external-ai` authorizes the relevant
conversation or generation input to Anthropic; it does not approve distribution.

## Current boundaries

The CLI has local tasks and a chat entry point. It has no connected mailbox,
calendar, task cloud, background notification process, or deployed chat UI.
Chat can help plan, research, and draft; it cannot send communications or alter
external accounts. Actual account integration requires the user's chosen
provider and authorization. Agent 9 can produce a limited, editable OBJ concept
mesh and PNG preview from a selected DXF area, but not a verified full-building
model or detailed furnished rendering. See `docs/guides/PERSONAL_ASSISTANT.md`.

## Engineering map

- `src/main.py`: CLI commands.
- `src/assistant.py`: Ahmad's conversation and specialist routing.
- `src/utils/tasks.py`: separate local work and personal task stores.
- `src/utils/coordination.py`, `capabilities.py`, `execution.py`: plans, shared capability adapters and verified SOP recovery.
- `src/agents/`: leader and specialist implementations.
- `src/utils/provider.py`, `runs.py`, `quality.py`, `approvals.py`: runtime,
  checkpoints, quality checks, and human approval records.
- `config/*.yaml`: agents, conversation routes, process catalog, standards.
- `tests/`: mocked offline tests; never use paid calls as routine verification.
- `docs/guides/RELIABILITY_AND_SOURCES.md`: model and source safeguards.

## Start here

- Use `docs/architecture/ARCHITECTURE.md` for the current pipeline and domain
  model. Parts of it are legacy; where it conflicts with this file, CLAUDE.md wins.
- Read the relevant agent module in `src/agents/` before changing a pipeline phase.
- Process and standards data live in `config/*.yaml`; keep new process behavior
  configuration-driven.
- One-off document generators and converters live in `scripts/`; run them from
  the repository root unless their help text states otherwise.
- Local source documents live in `references/` and generated artifacts belong in
  `output/`.
- Preserve the names and character encoding of the knowledge bases in
  `src/knowledge/` unless the task specifically concerns them.

## Working conventions

- Preserve existing user changes: the worktree may be dirty.
- Keep the current asynchronous pipeline and public CLI commands compatible unless
  a change request explicitly permits breaking changes.
- Add or update focused tests in `tests/` for behavioral changes.
- Run the affected tests; `pytest -q` is safe for the local test suite.
  Prefer `python3 scripts/dev.py test -q -rs` after
  `python3 scripts/dev.py bootstrap`; the project launcher discovers PDF libraries
  and uses the locked ignored `.venv` without temporary import paths.
- Never add API keys, generated documents, logs, local editor settings, or source
  customer documents to Git.
- External model calls require explicit authorization for the input/reference
  material. Do not enable `ALLOW_EXTERNAL_AI` or perform paid generation as a
  routine verification step. Use mocked providers for tests.
- Never run the `approve` command or supply a human reviewer's identity on their
  behalf unless that person explicitly authorizes approval of those exact
  artifacts. Code-change approval is not document approval. See
  `docs/guides/DATA_HANDLING.md`.

## Provider migration boundary

Do not imply that the application itself has moved to OpenAI until that runtime
migration is made. A provider migration requires an explicit request and must
update the client abstraction, settings, dependencies, documentation, and tests
together. See `docs/migration/CODEX_ADOPTION.md` before starting that work.

## Definition of done

For code changes, finish the requested implementation, run relevant tests, and
report any remaining external requirement (such as an API key or platform-specific
PDF dependency).

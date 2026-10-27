# Approved Phases 0 and 1 — implementation checkpoint

Date: 2026-09-28. Scope: safety baseline and workflow correctness. The application
remains Anthropic-backed; no provider migration, paid generation, or customer
document upload was performed.

## Phase 0: preserve and protect

- Preserved the preexisting dirty worktree, including the earlier folder reorganization.
- Saved a private source/config/test snapshot at
  `.local-baseline/pre-phase-01-source.tar.gz` before implementation. Customer
  references were not copied or modified. This is not a clean Git commit or a
  full repository/history backup.
- Staged removal of `.claude/settings.local.json` from Git tracking, retaining
  the local file. Extended ignore rules to cover customer material regardless of
  extension, local worktrees, environment files, diagrams, and the backup.
- Added a restrictive Docker build-context allowlist and documented the private
  data inventory and consent boundary in `../guides/DATA_HANDLING.md`.

## Phase 1: workflow correctness

- Validated YAML with Pydantic schemas, duplicate-key rejection, catalog/standards
  consistency checks, and unambiguous canonical process aliases.
- Unknown processes fail before model calls unless explicitly marked `--custom`.
- Routing is configuration-driven: incident/problem use the problem specialist;
  access uses the access specialist. Other processes use core workers by default.
  CLI-selected specialists are additive; data enrichment is opt-in.
- Corrected the access compliance method's argument order and converted KPI names
  to the structured metrics expected by the data specialist's dashboard prompt.
- Added external-AI consent checks in both the CLI and model-call paths.
- Replaced automatic AI-owner approval with local, hash-bound approval records,
  separate CLI approve/reject commands, reviewer metadata, and interactive consent.
  Legacy owner assessments can never set `approved=True`.
- Added deterministic checks for all eleven SOP sections and their nonempty bodies,
  valid scores, configured review thresholds, critical issues, revision requests,
  selected compliance results, safe filenames, and exact requested export sets.
- Failures in required enrichment, compliance, review, or formatting block approval.
  Every run has an isolated output directory; no stale decisions are reused.
- Isolated optional formatter imports so unavailable PDF support does not disable
  Markdown, HTML, or DOCX. A requested unavailable format fails explicitly.
- Fixed DOCX parsing that dropped sections between Markdown horizontal rules.
- Aligned Docker stages to Debian Bookworm, removed customer-document copies,
  configured a non-root runtime and recognized output path, and defaulted startup
  to the non-generating `status` command.

## Verification

- Before implementation: 44 tests passed (prior audit).
- After implementation: **104 tests passed** locally on Python 3.14.2/macOS.
- Coverage: **57.58%**, up from the prior audit's 29.59%. The configured 70% gate
  is unchanged and remains unmet. `pytest --cov=src --cov-report=term -q` ran all
  104 tests successfully but exited with code 1 solely because coverage is below
  70%. A separate measurement with `--cov-fail-under=0` confirmed the same result;
  this is not a claim that the coverage gate passed.
- Synthetic end-to-end tests create real Markdown, HTML, and DOCX artifacts and
  approval records while mocking model calls. Regression tests cover process
  routing, malformed configuration, denied consent, output failure, changed files,
  refusal/approval/rejection, KPI shape, and high-score revision requests.
- Docker daemon was unavailable; no image build or container run was verified.
- CLI status and approval help passed; `git diff --check` passed. Local customer
  references and settings were verified absent from the current Git index, with
  their ignore rules active. No API key was configured and external AI was disabled.
- PDF rendering/native dependencies and live Anthropic generation were not verified.
  Generated artifact layout has not received a visual acceptance review.
- No commit, push, deployment, or confidential source deletion was performed.

## Remaining work — separate approval required

1. Provider reliability: an async provider boundary, timeouts/retries, bounded
   concurrency, token/cost accounting, and recoverable run checkpoints.
2. Knowledge and evidence: source-aware retrieval, document classification,
   traceable references, and stronger prompt/data isolation.
3. Document quality: complete-document model review (current prompts still truncate),
   RACI/standards validation, page targets, professional formatting and visual QA.
4. Release readiness: dependency locking, Python/platform matrix, real PDF and
   container smoke tests, CI, and coverage above the existing 70% threshold.

These changes make delivery fail closed; they do not establish factual/regulatory
correctness. Local approval records are editable files with self-declared identity,
not authenticated sign-off. The system is not yet production-certified.

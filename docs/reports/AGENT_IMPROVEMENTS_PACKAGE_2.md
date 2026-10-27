# Agent improvements package 2

Current completion and remaining requirements are recorded in [package 5](AGENT_IMPROVEMENTS_PACKAGE_5.md) and the [finite ledger](PENDING_LEDGER.md). Remaining-work statements below describe this historical checkpoint.


This is the package 2 checkpoint. [Package 3](AGENT_IMPROVEMENTS_PACKAGE_3.md)
implements the next bounded document-specialist improvements listed below.

Implemented and verified locally on 15 October 2026. This package adds bounded
multi-specialist advice, explicit session continuity, completed-call recovery and
request-specific SOP plans. It builds on [package 1](AGENT_IMPROVEMENTS_PACKAGE_1.md).
The application remains Anthropic-backed. Existing explicit memory, source
permissions, asynchronous public interfaces and separate human approval remain.
The checkout's unrelated changes were preserved. No live model calls, provider
migration, document approval, publication or external-account actions were performed.

## Implemented behavior

- Ahmad plans all positive specialist matches using configured phrases,
  exclusions and clause-level negation. Common contrast/double-negation cases
  work; ambiguous and overbroad requests ask for clarification before model use.
  Unmatched advice stays with Ahmad. Local commands remain offline, and direct
  unsupported external actions receive an explicit response. The primary-route
  adapter and existing reply fields remain compatible.
- Abdullah executes the selected advisory capabilities under existing concurrency
  and token limits. Validated shared inputs combine application authority/privacy
  rules with domain prompts. Structured briefings preserve advice, provenance,
  assumptions, questions and explicitly reported position differences. Failed or
  malformed consultations do not abandon successful siblings. Orchestration adds
  no leader model call; a leader call occurs only for selected strategic advice.
  No consensus, verified facts or semantic conflict detection is claimed.
- Session context retains an objective, explicit decisions/constraints,
  pending items, outcomes, selected specialists and exact user requests beyond
  the recent response window. Entries have source/turn labels and can be edited
  or removed. Context bounds fail visibly without silently discarding decisions.
  Work/personal and exact-project separation remain; project changes and memory
  edits reset stale session context/history. No inferred permanent memory is added.
- Explicit capability adapters validate the existing pipeline calls without
  arbitrary tool dispatch. SOP plans carry objective, configured/user constraints,
  deliverables, acceptance criteria, specialists and phase dependencies. Core
  section/review/export gates remain mandatory; additional user criteria require
  human review.
- New failed/cancelled SOP runs can recover completed research, core generation
  and enrichment calls. Successful siblings are recorded immediately, including
  before a concurrent failure or cancellation. Recovery verifies a local HMAC,
  run/checkpoint hashes, capability arguments and unchanged request/configuration,
  source permissions/content, knowledge, templates and Python implementation.
  A completed reviewed checkpoint is reused only after its gate is revalidated.
  Incomplete review/compliance phases rerun in full.
- Model recovery requires fresh explicit consent, keeps inherited token usage
  charged against the budget, records predecessor lineage and distinguishes
  reused work from newly executed work. It creates a new run and fresh pending
  human approval record. Successful generation still ends at
  `awaiting_human_approval`. Default ready-to-export recovery remains offline.

## Files changed for this package

New implementation modules: `src/utils/coordination.py`,
`src/utils/capabilities.py` and `src/utils/execution.py`.

Integrated through `src/assistant.py`, `src/agents/leader_agent.py`,
`src/utils/config.py`, `src/utils/provider.py`, `src/utils/runs.py`, `src/main.py`
and `config/assistant_routes.yaml`.

Verification: `tests/test_coordination_package.py`, with small compatibility/mock
updates in `tests/test_agent_improvement_package.py` and `tests/test_pipeline.py`.

Documentation: root README/context, architecture and documentation entry points,
the personal-assistant, handoff/status and reliability/source guides,
[coordination and recovery](../guides/COORDINATION_AND_RECOVERY.md),
[evaluation scenarios](../development/AGENT_EVALUATION_BASELINES.md), the historical
package 1 pointer and this checkpoint.

## Verification

The package adds **54 synthetic regression cases**. They cover multi-role and
negated plans, ambiguity/bounds, actual coordinator execution, partial/all and
initialization failures, malformed advice, privacy isolation, session continuity,
context limits, concurrent-use rejection, explicit local outcomes, capability
validation, failed/cancelled recovery at several checkpoints, tampering and changed
source/configuration/code identities, fresh consent, inherited budgets, CLI
recovery and fresh human approval records.

The prior full run passed **319 tests with 1 skip** because this framework Python
process did not locate the installed native PDF libraries. With the per-command
library path, the PDF/DOCX export tests passed **3/3**. Final full-suite command:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  PYTHONPATH=/private/tmp/reema-agent-test-deps python3 -m pytest -q -rs
```

Final result: **320 passed, 0 skipped**. `git diff --check` passed.

The library path is specific to this macOS host. Native libraries were already
installed; no install or global shell change was made. The temporary dependency
directory contains the existing locked `ezdxf==1.4.4` and `pyparsing==3.3.3` wheels,
installed earlier with lock-file hashes and no dependency resolution. It may be
removed by the OS; install `requirements-dev.lock` in the intended development
environment for reproducible execution. Other hosts need their platform's native
WeasyPrint dependencies and library discovery configuration.

Tests deny live HTTP and use synthetic provider responses. They establish
software behavior, contract enforcement and data preservation; they do not
measure model reasoning, factual accuracy, regulatory compliance or visual export
quality. The export checks verify actual files and readable content.

## Using the changes

Start advisory chat with deliberate authorization for its selected context:

```bash
python -m src.main chat --area work --project Alpha --allow-external-ai
```

Inside that session:

```text
/objective Prepare the support-device migration plan
/decision platform Use Intune
/constraint spending Use existing tools
/plan Draft an SOP with MFA and a KPI dashboard
/context
```

Generate a request-specific SOP or recover an eligible failed/cancelled run:

```bash
python -m src.main generate "Change Management" -f markdown \
  --objective "Document the support team's change workflow" \
  --constraint "Use the existing ITSM platform" \
  --acceptance "The successor can locate the escalation contact" \
  --allow-external-ai

python -m src.main resume output/runs/RUN_ID --model-phases --allow-external-ai
```

For a ready checkpoint, export locally with the existing default:

```bash
python -m src.main resume output/runs/RUN_ID -f docx
```

Model recovery also needs an Anthropic API key and the original output root;
pass `--output /absolute/original/output/root` for a custom root. These commands
are usage examples, not generation or approval performed for this checkpoint.

## Limits and remaining roadmap

The planner is a bounded English phrase/clause implementation, not general
language understanding. Position differences rely on structured specialist
reports. No unrestricted scheduler, tool executor or external-account integration
was added. Session context is session-only; execution records do not restore chat.

Model recovery supports only authenticated recorded failed/cancelled runs with
completed recoverable work and unchanged inputs/configuration/source/code. Legacy
runs without the journal, still-running/hard-killed runs, missing keys, unsupported
versions and interrupted writes with mismatched records are unsupported. Changed
formats or objectives require a new generation. Failed provider attempts and
individual review chunks have no independent recovery or API-side idempotency.
Legacy ready-only export retains its existing hash/quality checks; the new HMAC
contract is specific to model-phase recovery.

The private output-root `.recovery-key` is ignored by Git. Its HMAC detects changes
without the key; anyone able to read the key and rewrite records can forge them.
It provides neither encryption, user authentication nor human approval. Token
budgets include inherited usage per branch; independent concurrent branches do
not share a global spending cap. Call lists and estimated costs describe the
current run, with earlier usage available through predecessor records.

Remaining documentation-specialist work includes template/section assembly,
targeted revisions, validated diagrams, evidence-linked control registers,
located review findings and rechecks, and visual export QA. Remaining specialist
depth includes research freshness, actual-environment IAM validation, evidence
timelines and competing root-cause hypotheses, metric calculation checks, and
CAD interpretation/geometry validation. Existing handoff metadata and model
prose remain unverified. Live quality evaluation requires separately authorized
material and agreed grading criteria. Provider migration remains a separate
explicit request.

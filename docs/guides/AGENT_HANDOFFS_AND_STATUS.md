# Agent handoffs and workflow status

REEMA still uses Anthropic and the configured asynchronous SOP pipeline. Successful
generation still ends at `awaiting_human_approval`. Explicit work/personal and project memory remain. Package 2 adds the bounded
planner, session context and recovery described in [Coordination and recovery](COORDINATION_AND_RECOVERY.md).
Package 3 adds typed controls, stable sections, located correction history and
export checks described in [Document quality](DOCUMENT_QUALITY.md).

## Complete specialist payloads

Access requirements, Problem research, optional Access/Data research context and
appended specialist content are no longer cut to fixed character prefixes. Data
dashboard prompts retain every supplied metric field, including extra definitions
or exclusions. Content generation retains every research/standards field rather
than selecting only the main narrative. Existing private ITOM prompt helpers also
retain complete supplied context; they remain inactive in the normal pipeline.
Reference permissions and bounded lexical retrieval still determine which source
excerpts may enter a request.

`MAX_PROMPT_CHARS` applies to the complete serialized provider request, including
system instructions and retrieved evidence. `MAX_RUN_TOKENS` applies across the
run. Oversized requests fail before transmission instead of silently dropping a
tail. Reduce the supplied context or split the work explicitly when a budget is
exceeded. This package does not add automatic summarization or generation chunking.
The existing review/compliance chunking still covers every document character.

## Validated internal contracts

`src/utils/handoffs.py` defines strict Pydantic contracts used at the leader's
research, enrichment and review boundaries. Existing public agent methods retain
their dictionaries or strings. The adapters preserve extension fields in the
envelope's `payload`; they reject an empty/malformed result or a conflicting
`process_name` before the next phase consumes it.
Research results must remain mappings; enrichment supports the existing string
or dictionary results. A plain narrative cannot stand in for the research mapping
expected by the next worker.

An `AgentHandoff` contains the process, producer role key, stage, original payload
and optional `HandoffMetadata`. Metadata can represent applicable findings,
evidence references, assumptions, unresolved questions and proposed deliverables.
Workers may supply it under the legacy result's `handoff_metadata` key. A finding's
source IDs must exist in that metadata's evidence list. Invalid structured
metadata fails validation rather than being ignored.

The adapter adds provenance for cited IDs found in the run's source registry and
records unresolved IDs as open questions. Everything remains `unverified`.
Narrative is not parsed into purportedly verified findings. Empty metadata means
no structured information was supplied; it does not establish that there are no
gaps. These contracts check shape and internal consistency, not factual truth,
source applicability or complete use of every requirement by a model.

Validated research metadata is copied into subsequent content/specialist inputs.
Handoff envelopes are available in `leader.context["handoffs"]` and in the
`researched`, `generated`, `drafted`, `reviewed` and `ready` checkpoints reached by the run.
Checkpoint payloads remain private. Review and compliance result adapters reject
invalid types and contradictory decisions, such as model `APPROVED` with a
revision request, or `compliant=true` with unresolved findings. Offline export
recovery applies the same review contract. Automated `APPROVED` remains a model
gate result, never a human decision.

## Actual workflow progress

`LeaderAgent.get_status()` now reports real phase transitions for the latest
started workflow on that instance. A normal run has eight coordination tasks:
planning, research, content, enrichment, review, compliance, formatting and
human review record creation. Export recovery has only the final two tasks.
These are phase counters. Per-phase `executed_calls` and `reused_calls` count
capability invocations; actual provider requests remain separate. Provider accounting remains in run usage metadata.

The existing `active_tasks` and `completed_tasks` keys remain. Additional keys
report pending, failed, cancelled, reused and skipped tasks, `workflow_status`, the last
entered `current_phase`, and timestamped `tasks`. Each phase completes only after
its associated checks/checkpoint succeed. On failure or cancellation the active
phase is marked accordingly and future phases are `skipped`. The snapshots are
saved in `run.json`. Preflight rejection does not start a new workflow or replace
the previous run's counters. These records are local operational state, not an
authenticated human audit ledger. Package 2 separately adds a bounded, locally
authenticated model-phase recovery record; phase counters alone do not authorize reuse.

Reusing a leader after a run resets its counters. Concurrent execution on the
same mutable leader instance is rejected; use separate instances for separate
runs. Existing CLI commands retain their defaults; package 2 adds explicit optional model-recovery flags.

## Ahmad communication and summaries

`coordinate_team_communication()` records a message in the instance's in-memory
log. Its intentional status correction is `recorded` instead of `routed`, with
`dispatch_status=not_dispatched`. It has no dispatcher or acknowledgement and
does not persist the record across instances.

The legacy `coordinate_delivery()` advisory API produces a summary from supplied
filenames and a model score. It does not open files, validate exports, create the
leader's approval record, certify quality or distribute documents. It returns
`distribution_status=not_dispatched` and `verification_status=not_performed`.
The legacy `formats_delivered` key means reported formats; `delivery_timestamp`
means summary creation time. The normal pipeline continues to use the leader's
hash-bound pending approval record instead.

Briefing prompts now receive complete supplied pipeline records and distinguish
reported findings from unavailable information. Missing scores remain unavailable
rather than becoming zero. Research/standards claims and commitments cannot be
inferred from a filename or score. Proposed next actions remain proposals.

See [evaluation baselines](../development/AGENT_EVALUATION_BASELINES.md) and the
[implementation checkpoint](../reports/AGENT_IMPROVEMENTS_PACKAGE_1.md).

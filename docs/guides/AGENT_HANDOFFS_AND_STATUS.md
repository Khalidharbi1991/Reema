# Agent handoffs and job status

REEMA makes no model call. Each job's text comes from files a Claude Code session
wrote, fed through file-backed workers (`src/agents/file_workers.py`) into the same
checks the earlier API pipeline used. A successful generate or revise job ends at
`awaiting_human_approval`. The research, enrichment, review-loop and compliance
handoffs between Agents 1–8 were removed with the API path.

## Validated contracts that remain

`src/utils/handoffs.py` still defines the strict Pydantic contracts:

- An `AgentHandoff` contains the process, producer role key, stage, original payload
  and optional `HandoffMetadata` (findings, evidence references, assumptions,
  unresolved questions, proposed deliverables). A finding's source IDs must exist in
  its evidence list; invalid structured metadata fails validation.
- Agent 10's patch appendix is recorded as a handoff when it is added to a new SOP,
  available in `leader.context["handoffs"]`. Cited IDs found in the run's source
  record get provenance; unresolved IDs become open questions. Everything remains
  `unverified`.
- `ReviewResult` still guards the export of a run made by the removed API path: a
  low score, a revision request, a critical or blocking issue, or a contradictory
  decision (such as `APPROVED` with a revision request) refuses the export.

These contracts check shape and internal consistency, not factual truth, source
applicability or complete use of every requirement.

## Job progress

`LeaderAgent.get_status()` reports real phase transitions for the latest job started
on that instance:

- generate: planning, content, checks, formatting, human review record
- review: template check, review (Claude Code only), findings record
- revise: revision, recheck, formatting, human review record
- export: formatting, human review record

Each phase completes only after its checks/checkpoint succeed, and its
`executed_calls` counts capability invocations. The `active_tasks` and
`completed_tasks` keys remain; other keys report pending, failed, cancelled and
skipped tasks, `workflow_status`, the last entered `current_phase`, and timestamped
`tasks`. On failure or cancellation the active phase is marked accordingly and later
phases are `skipped`. The snapshots are saved in `run.json`. These are local
operational records, not an authenticated audit ledger.

Reusing a leader after a job resets its counters. Concurrent jobs on the same leader
instance are rejected; use separate instances.

## Ahmad communication

`coordinate_team_communication()` records a message in the instance's in-memory log
with status `recorded` and `dispatch_status=not_dispatched`. It has no dispatcher or
acknowledgement and does not persist the record across instances.

See [evaluation baselines](../development/AGENT_EVALUATION_BASELINES.md).

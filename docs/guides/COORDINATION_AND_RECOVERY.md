# Coordinated advice and recoverable SOP execution

REEMA's supported workflows are advisory chat, its existing local commands and
the configured SOP pipeline. Ahmad remains the conversational entry point and
consults the selected advisory capabilities directly. Abdullah leads only the
recoverable document workflow and is not consulted in chat. The runtime is
Anthropic; document approval remains a separate human action.
The [document quality guide](DOCUMENT_QUALITY.md) covers the later control,
section/correction and export contracts included in current recovery identity.

## Advisory request plans

The planner uses validated phrase rules in `config/assistant_routes.yaml` and
selects every positive matching capability. For example, a request to draft an
SOP with MFA and a KPI dashboard selects Content, Access and Data. Ahmad runs
those consultations under the existing concurrency/token limits, builds a
structured consultation record (`coordinator: "Ahmad"`), and answers from it.
The fan-out itself is deterministic and makes no extra model call. Strategy,
roadmap, budget and prioritization requests select no specialist; Ahmad answers
them with strategy, governance, quality and business-value framing.

Negation applies within clauses. `No security advice; prepare an agenda` selects
Content. Exclusions such as `standard applications` prevent the generic
`standard` keyword from selecting Standards. Common contrast/double-negation
forms are handled. Ambiguous questions about proceeding without a prerequisite
ask for clarification; requests matching more than `max_specialists` ask the user
to narrow the scope instead of silently dropping capabilities. Unmatched requests
stay with Ahmad. Simple `Continue`/`Next step` follow-ups retain the active
specialist selection.

This is a bounded Arabic/English phrase planner, not complete language understanding.
Package 5 adds mixed-script scope/context rules and optional consent-gated structured
intent resolution. See [the current guide](COMPLETION_AND_EVALUATION.md).
Change keywords, exclusions, negation terms and `max_specialists` in configuration
when needed. Local task, memory, project and session commands still work offline.
Direct requests to send, purchase, book, schedule, deploy or approve through chat
are reported as unsupported external actions. Drafting/advisory requests can
still be discussed. There is no unrestricted tool executor or connected external
account dispatcher.

Public advisory results retain `reply`, `consulted` (the first successful
specialist, for compatibility) and `usage`. They also expose `consulted_agents`,
the validated `plan`, and `coordination` status. `/plan` inspects the last advisory
plan; `/plan MESSAGE` previews a plan without a model call. The existing CLI still
prints the reply. `AssistantSession.route()` remains a primary-route adapter;
execution uses the complete plan.

Specialist advice uses the role's domain prompt together with the application
scope/authority rules. Structured advice can carry unverified findings, evidence,
assumptions, open questions and explicit topic/stance positions. Legacy plain
advice remains accepted and is labelled unstructured. Failures, including agent
initialization failures, are collected without abandoning successful siblings.
Different explicitly reported positions are surfaced; semantic disagreement is
not inferred from arbitrary prose, and consensus is never claimed. Ahmad receives
the complete briefing, including uncertainty and proposed follow-ups.

## Session continuity

Use explicit session commands for the ongoing task:

```text
/objective Migrate the support devices to the approved platform
/decision platform Use Intune
/constraint spending Use existing tools
/pending approval Obtain the pilot approval record
/outcome pilot Pilot testing completed
/context
/context forget constraints spending
/context forget requests turn-8
/context clear
```

`Objective:`, `Decision:`, `Constraint:`, `Pending:` and `Outcome:` prefixes also
capture explicit user statements. These entries are session-only, editable and
deletable. Outcomes stated by the user remain user-reported; successful supported
local task mutations add local confirmation records tied to task IDs. Failed
consultations and reported position differences remain pending coordination
records rather than becoming verified facts about the organization.

The session retains exact user request text with turn IDs, so a free-text decision
does not disappear when the recent exchange window advances. Only the latest
three response exchanges are retained; essential user entries are separate and
are not automatically summarized. `context_max_chars` bounds the explicit context
and assembled shared context. If it cannot fit, the request fails with editing
guidance and retains prior decisions. If a completed local task's outcome cannot
fit, the action result explicitly reports that limitation; the task remains in
the local store. Model prompt budgets provide a further transmission limit.

Work/personal and exact-project boundaries apply to this context. Project changes
or explicit memory edits/deletions reset session context and recent history;
separate CLI memory edits are detected before the next request. Concurrent use of
the same session is rejected, preventing a project switch during a consultation.
No session transcript or inferred preferences are written to permanent memory.
Use the existing `/remember`/`memory set` commands for deliberate long-term memory.

Session continuity ends when that chat session closes. Persisted SOP execution
records described below are a separate mechanism and do not restore chat history.

## Request-specific document plans

```bash
python -m src.main generate "Change Management" -f markdown -f docx \
  --objective "Document the support team's change workflow" \
  --constraint "Use the existing ITSM platform" \
  --acceptance "The successor can locate the escalation contact" \
  --specialist access --allow-external-ai
```

The plan carries the objective, explicit/configured constraints, requested
deliverables, acceptance criteria, selected specialists and phase dependencies.
Process-specific `constraints` and `acceptance_criteria` can be configured in
`config/process_definitions.yaml`. The supported workflow remains the SOP flow;
the CLI does not turn arbitrary goals into new tools or workflows. Required
deliverables must be the SOP and the requested output formats. The existing
section/review/export gates remain mandatory; extra user acceptance criteria
require human review and are not claimed to have been machine-verified.

## Resume interrupted model work

Default ready-to-export recovery remains offline:

```bash
python -m src.main resume output/runs/RUN_ID -f markdown -f docx
```

For a new failed/cancelled run interrupted before `ready.json`, explicitly
authorize model-phase recovery:

```bash
python -m src.main resume output/runs/RUN_ID --model-phases --allow-external-ai
```

This requires an Anthropic API key and fresh consent even if persistent external
AI permission is configured. For an original custom output root, also pass
`--output /absolute/original/output/root`. Model recovery preserves the original
formats and objective; incompatible input changes require a new generation.

Each new model run writes `execution.json`, verified phase checkpoints and a
private `.recovery-key` in the output root. The locally generated key authenticates
the execution record with HMAC. Keep the key private and out of Git alongside
private outputs; losing/rotating it makes prior model recovery unavailable. The
key is not an API credential, human identity or document approval signature.
People able to read the key and rewrite files can forge local records; this is
not an authenticated multi-user audit service or encrypted storage.

Recovery verifies the signature, run/checkpoint hashes, request and configuration
identity, source permissions/content, curated knowledge, templates and Python
implementation identity. Cached provenance must still exist under current source
permissions. It validates handoffs and exact capability-input hashes before reuse.
Modified or malformed records and incompatible configuration/implementation reject
recovery before cached work is used or a new model request is sent.

Completed Research/Standards/selected specialist calls, core SOP generation and
individual enrichment calls are recorded as they finish. Completed siblings
survive a failed or cancelled concurrent phase. Recovery reuses those calls and
reruns validation/assembly rather than paying for them again. A completed reviewed
checkpoint can also be reused after its quality gate is revalidated. An incomplete
review or compliance phase reuses separately checkpointed validated chunks in
package 5. Cached chunks are revalidated and bound to exact prompt/schema/source
identity. Failed requests and lost provider responses are not successful results.

Version 2 also supports locally abandoned authenticated running owners after the
OS lease proves no process owns the run. Active owners and cross-host liveness
remain blocked. Its signed embedded snapshot is authoritative after a hard kill.
Legacy runs without `execution.json`, missing keys, malformed records and unsupported
versions cannot use model-phase recovery. If `ready.json` exists, use offline export
recovery. The current guide describes atomic commit and in-flight uncertainty.

The child run uses its own directory and fresh pending human approval record.
Task snapshots distinguish reused calls/phases from newly executed work. Usage
reports inherited and new accounted tokens separately, keeps predecessor lineage,
and counts inherited usage against the original run budget. Recovery cannot reset
an exhausted budget. `calls` and estimated cost cover only requests made in the
current run; consult predecessor records for earlier requests/cost. Unknown failed
request usage retains the existing conservative reservation accounting.

Inherited usage is enforced per recovery branch. Independent concurrent branches
do not share a global spending ledger; the run budget is not an account-wide or
organization-wide spending cap.

See [package 2 checkpoint](../reports/AGENT_IMPROVEMENTS_PACKAGE_2.md) and
[evaluation scenarios](../development/AGENT_EVALUATION_BASELINES.md).

# REEMA personal assistant: current scope

REEMA now has one local chat entry point through Ahmad for work and personal
assistance. Ahmad handles local tasks and coordinates relevant IT specialists.
Abdullah leads specialist work in the document pipeline and carries the former
owner agent's strategy, governance, quality, and business-value guidance.
The user remains the decision authority. There are eleven active agent roles.
The IT specialists use display names Agent 1 through Agent 8. Agent 9 is the
building-design specialist. It can check a DWG locally and create a limited
OBJ concept mesh plus PNG preview from one selected area of a DXF working copy.

Agent 9 can be consulted about building layout, interiors, exteriors, and
modeling requirements during an authorized advisory chat. To check a local
AutoCAD drawing without uploading it or making a model call, use:

```bash
python -m src.main drawing inspect "references/your-building.dwg"
```

This check validates the DWG header only. It does not read rooms, dimensions,
walls, or floors. A separate `drawing concept` command uses wall linework from
one selected DXF region, with an explicit wall-height assumption. The supplied
building's concept output is in `output/agent9/concept-plan-c-2018-v2/`. This is an
editable mesh, not a verified full-building or construction model. Doors,
windows, floors, interiors, exterior landscaping, and elevations still require
further interpretation and design work.

For a DXF already exported from CAD, select one plan area in metre coordinates
and create a fresh local output directory:

```bash
python -m src.main drawing concept "references/your-building.dxf" \
  --output-dir output/agent9/my-concept \
  --xmin 0 --ymin 0 --xmax 60 --ymax 40 \
  --wall-height 3
```

The output includes an editable `.obj` with its `.mtl`, a `.png` preview, and a
`.json` file recording assumptions. Furniture and bathroom fixture blocks are
represented by generic placeholders. A DWG must first be exported to DXF with a
CAD application; the original drawing is not rewritten by this command. The
selected area and height must be checked against the actual plan before use.
An optional `--design-spec` path can add conceptual beds, sofas, TVs, and
planters from a local JSON `placements` list. The preview cuts walls to 1.1 m
so placements are visible, while the OBJ retains the requested full wall height.
The supplied drawing's illustrative version is in
`output/agent9/area-6-furnished-v3/`.

## Local task management

Tasks are stored on this computer in separate SQLite databases under
`output/assistant/` by default. The folder is ignored by Git. Use `TASK_DATA_DIR`
to choose another private directory. File permissions are restricted to the
local user on systems that support them. The files are **not encrypted**.
`USER_TIMEZONE` defaults to `Asia/Riyadh` for the `today` view and task timestamps.

```bash
python -m src.main task add "Prepare project review" --area work --priority high --due 2026-10-02 --project Alpha
python -m src.main task add "Book dentist" --area personal
python -m src.main task list --area work
python -m src.main task today --area personal
python -m src.main task upcoming --area work --days 7
python -m src.main task list --area work --project Alpha
python -m src.main task show TASK_ID --area work
python -m src.main task edit TASK_ID --area work --priority urgent --due 2026-10-01
python -m src.main task set-status TASK_ID --area work --status done
```

Areas are required on every task command. `today` shows open tasks due today or
overdue. `upcoming` adds a planning horizon and includes overdue tasks. Status can
be `open`, `done`, or `archived`; archive hides a task from the
default list without deleting it. Use `task list --area work --status all` to
inspect archived tasks. No API key, external model call, or account connection is
needed for these commands. Avoid placing credentials in task titles or details.

## Persistent profile and project memory

Explicit memory uses the same area separation and private SQLite files as tasks.
Existing preference commands remain compatible:

```bash
python -m src.main memory set tone "Keep summaries concise" --area work
python -m src.main memory list --area work
python -m src.main memory forget tone --area work
```

Save a profile, goals and constraints for a named project, reusable corrections,
or an example whose structure you want future answers to follow:

```bash
python -m src.main memory set role "IT consultant" --kind profile --area work
python -m src.main memory set answer_style "Recommendation first, then reasons and next steps" --area work
python -m src.main memory set goal "Roll out MFA to the support team" --kind project --project Alpha --area work
python -m src.main memory set constraints "Use existing tools; finish the pilot before expansion" --kind project --project Alpha --area work
python -m src.main memory set assumptions "State missing evidence instead of guessing" --kind lesson --area work
python -m src.main memory set mfa_checklist "MFA rollout: scope, owner, evidence, next steps" --kind example --project Alpha --area work
python -m src.main memory list --area work --kind project --project Alpha
python -m src.main memory forget goal --kind project --project Alpha --area work
```

These are illustrative values; the application does not prefill your profile.
Repeat `memory set` with the same area, kind, project and key to edit a memory.
`memory list` inspects all memories in the selected area; `--kind` and `--project`
filter the list. `memory forget` deletes the exact named entry. Preferences and
profile entries apply throughout their area and cannot have a project scope.
Project entries require a project name. Lessons and examples can be area-wide
or scoped to one project. Project names match exactly, including case.
Preference values allow 1,000 characters; other kinds allow 4,000, so use concise
facts and short, explicitly supplied examples rather than full source documents.
Saving an example does not open a file path or bypass reference permissions.

Memory persists across chat sessions; conversation transcripts do not. It is not
model retraining. Facts, corrections and examples are never inferred and saved
automatically. Save the lesson explicitly when you want a correction retained.
Area-wide preferences, profile and lessons are included in authorized advisory
requests. Project memory is included only for the project you select. Examples
are selected by shared words in their key/text and the current question, with a
maximum of three by default (`memory_example_limit` in
`config/assistant_routes.yaml`; zero disables example retrieval).
Example retrieval is lexical, not semantic search. The existing
`KNOWLEDGE_CONTEXT_CHARS` limit also bounds saved memory and task context; an
oversized selection fails before model calls instead of silently dropping facts.
Do not store passwords or secret tokens.

## One entry point

```bash
python -m src.main chat --area work
python -m src.main chat --area personal
```

Within a chat, `/task help` lists local task operations. `/remember KEY VALUE`,
`/memory`, and `/forget KEY` manage explicit preferences. These work offline.
Memory commands also accept `--kind` and `--project` **before** their key/value:

```text
/remember --kind profile language English
/project Alpha
/remember --kind project goal Roll out MFA to the support team
/remember --kind lesson assumptions State missing evidence instead of guessing
/remember --kind example mfa_checklist MFA rollout: scope, owner, next steps
/memory --kind project --project Alpha
/forget --kind project goal
/project --clear
```

`/project` displays the current selection. Quote project names with spaces, for
example `/project "Service Desk"`. Project memories, lessons and examples saved
without an explicit `--project` use the selected project; preferences and profile
remain area-wide. Use `--project ""` to save an area-wide lesson/example while a
project is active. Switching or clearing the project resets all session context and history to
avoid carrying another project's answers forward. Editing or deleting saved
memory also resets explicit session context and history, including changes made by a separate CLI invocation.
The selected project applies to local chat task creation/listing and to task
context in planning requests; explicit task IDs still refer to the selected area.
Clear requests such as `Add a task to buy groceries` and `Show my tasks` also
work locally. For due dates, project names, and priority changes, use the
explicit task commands.
For advisory conversations, set `ANTHROPIC_API_KEY` and explicitly authorize
the conversation:

```bash
python -m src.main chat "Help me plan today" --area work --allow-external-ai
python -m src.main chat "Plan the MFA rollout" --area work --project Alpha --allow-external-ai
```

The interactive form accepts messages until `/exit`. Ahmad builds a validated,
bounded request plan using phrase rules in `config/assistant_routes.yaml`.
Abdullah coordinates every positively matched specialist, collects failures and
explicitly reported differences, and gives Ahmad a briefing. Common clause
negation is handled; ambiguous or overbroad requests ask for clarification without
model calls. Unmatched advice stays with Ahmad. There is no general tool executor.

Use `/objective TEXT`, `/decision KEY TEXT`, `/constraint KEY TEXT`, `/pending KEY TEXT`
and `/outcome KEY TEXT` for explicit session context. `/context` inspects it;
`/context forget FIELD KEY` edits retention and `/context clear` starts fresh.
`/plan` inspects the advisory plan; `/plan MESSAGE` previews one offline. Exact user
turns remain available outside the last three response exchanges until the bounded
context fills. Growth fails visibly instead of silently dropping decisions. None
of this context is automatically written to permanent memory. See
[Coordination and recovery](COORDINATION_AND_RECOVERY.md) for limits and examples.

The selected area's relevant saved memory is sent to Anthropic for authorized
advisory conversations. Open task titles, project names, priorities, and due
dates are sent only when a planning-related question needs them, filtered to
the selected project if one is active. Task details and other areas/projects'
saved context are not added to prompts. Specialists and Ahmad both receive the
same selected context and recent session exchanges; Ahmad also sees specialist
advice. Current requests take precedence over older preferences. Saved facts
are user-reported context, and examples guide style rather than verify claims.
The chat history lasts only for the running session. No conversation transcript
is written to the task databases. Curated agent knowledge may be included in
model requests under the same authorization. Review sensitive text before
using `--allow-external-ai`; saving memory alone does not authorize model calls.

## What is available now

- Local work and personal task capture, priorities, due dates, projects, status,
  daily view, and archive/reopen.
- Interactive or single-message chat with Ahmad, with specialist advice for
  configured work topics.
- Persistent, inspectable profile/preferences, project goals and constraints,
  explicit correction lessons, and matching examples shared with specialists.
- Planning, research discussion, meeting preparation, communication drafting,
  and IT advice through the model when explicitly authorized.
- The existing 11-section IT SOP pipeline, formats, quality gates, and human
  document approval.

## External services

REEMA does not yet have a connected mailbox, calendar, task cloud, or background
notification service. Chat responses can draft or recommend actions, but cannot
send an email, modify a calendar, make a purchase, or silently change a system.
Those actions require an integration selected and authorized by the user. The
available Codex/ChatGPT connectors are separate from this Python application's
runtime and do not automatically grant REEMA account access.

For current model-call safeguards and source permissions, see
[Reliability and sources](RELIABILITY_AND_SOURCES.md). For the earlier development
checkpoint, see [Remaining improvement phases](../reports/PHASE_2_5_CHECKPOINT.md).

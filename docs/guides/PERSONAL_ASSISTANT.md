# REEMA personal assistant: current scope

Khalid talks to **Ahmad**, his executive personal assistant and coordinator, in a
Claude Code session opened on this folder: the main session is Ahmad (see AGENTS.md,
"REEMA company in Claude Code"). Ahmad is also the front of the Snafi app
(`docs/snafi/PRD.md`). `reema chat` is retired; it only says so. REEMA itself makes
no model call: Claude Code writes the text, and REEMA's local commands plan, check,
export and record.

## Ahmad's role

- **Executive assistant:** chat in Arabic and English, email (Gmail, Yahoo),
  calendar, tasks (Todoist), files (Drive), reminders, memory of Khalid, proactive
  briefs and family messaging over Telegram. These arrive with Snafi steps 2–8;
  today only the local `task` and `memory` commands and the Snafi skeleton exist.
- **Coordinator:** routes mail, planner and memory work to the Personal team (Mail,
  Planner and Memory agents), and the rest to the teams below, then reports back.
- **Permissions:** the PRD's four levels: (1) just does it: reads and search;
  (2) does it with undo: a Todoist task, reminder, email draft, or event with only
  Khalid; (3) asks first with an approval card: any send, invite, accept or decline,
  or delete; (4) never: payments, passwords, security settings, mass messages.
- **Family:** when family members talk to Ahmad, he never shares Khalid's email,
  calendar or private data; he answers their own questions, takes messages, and
  passes along only what Khalid chose to share.
- **This Claude Code session** uses the work area only: personal work runs through
  Snafi under the permission levels as those steps are built.

## Routing

Ahmad answers strategy, roadmap, budget and prioritization questions himself, framed
in the former owner agent's strategy, governance, quality and business-value terms;
that advice is unverified and Khalid decides. He routes the rest:

- **Documentation** (Abdullah, `abdullah-docs` skill): a new SOP (`reema-generate`),
  a review (`reema-review`) or a revision (`reema-revise`) of a finished one.
- **Home Design** (Agent 9, `reema-agent9-design-lead` skill): one part of the home
  at a time, by Agents 19–23 in the local New Home project, after Khalid's yes to the plan.
- **End-user computing and endpoints**: the `reema-agent10-euc` subagent.
- **Development** (Agent 11, `reema-agent11-dev-lead` skill): software, apps and
  games built by Agents 12–18 in separate project repos, after Khalid's yes to the plan.
- **Tasks and memory**: the local `task` and `memory` commands below (work area).
- **Personal** (Mail, Planner and Memory agents, in Snafi): planned for Snafi
  steps 2–8, not built yet.

There are twenty-five agent roles; Agents 11–18 (Development) and Agent 9's Home
Design team (Agents 19–23) exist only as Claude Code skills and subagents. Agents 1, 2, 6, 7 and 8 have no class any more: they
remain roles in the roster (`reema agents`), and their knowledge files remain source
material. Khalid remains the decision authority.

## Agent 10: end-user computing

Ahmad passes endpoint questions (patching, deployment rings, Intune, MECM/SCCM,
Autopilot, OS images, software packaging or distribution, BitLocker, LAPS, end-user
devices) to the `reema-agent10-euc` subagent. Its advice frames the objective, scope
and blast radius first, and every endpoint change states a pilot ring, rollback path,
kill switch and any irreversible step. It plans around Asia/Riyadh time, the
Sunday–Thursday week and seasonal change freezes. It drafts PowerShell with a
`-WhatIf` mode, change requests, runbooks, KB articles and RCA records for human
review, saved only under `teams/documentation/output/claude_code/advice/` when Ahmad asks. It cannot
browse documentation, run scripts or reach tenants, devices or directories, so
version- and licensing-dependent statements are marked for verification. It reads
only files Ahmad names after Khalid's yes.

In a new SOP, Workstation Security Patches and Devices Batch Management select
Agent 10, and `--specialist euc` adds it to another process: the same subagent writes
the "Endpoint Deployment & Rollback Plan" appendix, with organization-specific values
marked "[to confirm]". The draft still needs human approval.

## Agent 9: building and home design

Ahmad follows the `reema-agent9-design-lead` skill, which keeps the old Agent 9
subagent's rules word for word. Every job starts by asking Khalid which part of the
home to design, then shows the plan and the chosen agents (19 blueprint reader, 20
space planner, 21 interior designer, 22 3D modeler, 23 design reviewer) and waits for
his yes. The agents read only files Ahmad names after Khalid's yes, never invent
dimensions and mark unknowns [to confirm]; structural, electrical, plumbing and permit
questions need a licensed professional. Project files live in
`D:/Projects/IT Consultant/teams/home-design/New Home/` and never leave this computer. Agent 22 is the
only agent that runs commands (Blender, `freecadcmd`, ODA File Converter), within the
hook's rules and only for scripts Agent 16 reviewed. Ahmad runs the local drawing
commands, which make no model call.

To summarize a converted DXF for Agent 19 (layers, text labels, dimensions, door and
window candidates, with no room inferred):

```bash
python3 scripts/dev.py run drawing summary "D:/Projects/IT Consultant/teams/home-design/New Home/output/drawings/20261103_majlis_plan.dxf" --output "D:/Projects/IT Consultant/teams/home-design/New Home/output/summaries/20261103_majlis_drawing-summary.json"
```

To check a local AutoCAD drawing:

```bash
python3 scripts/dev.py run drawing inspect "D:/Projects/IT Consultant/teams/home-design/New Home/input/your-building.dwg"
```

This validates the DWG header only. It does not read rooms, dimensions, walls, or
floors. For a DXF already exported from CAD, select one plan area in metre
coordinates and create a fresh local output directory:

```bash
python3 scripts/dev.py run drawing concept "D:/Projects/IT Consultant/teams/home-design/New Home/output/drawings/your-building.dxf" --output-dir "D:/Projects/IT Consultant/teams/home-design/New Home/output/models/20261107_area_concept" --xmin 0 --ymin 0 --xmax 60 --ymax 40 --wall-height 3
```

The output includes an editable `.obj` with its `.mtl`, a `.png` preview, and a
`.json` file recording assumptions. Furniture and bathroom fixture blocks are
represented by generic placeholders. A DWG must first be exported to DXF with a CAD
application; the original drawing is not rewritten. The selected area and height
must be checked against the actual plan before use. An optional `--design-spec` path
can add conceptual beds, sofas, TVs, and planters from a local JSON `placements`
list. The preview cuts walls to 1.1 m so placements are visible, while the OBJ keeps
the requested wall height. This is an editable mesh, not a verified full-building or
construction model.

## Local task management

Tasks are stored on this computer in separate SQLite databases under
`teams/coordination/data/` by default. The folder is ignored by Git. Use `TASK_DATA_DIR`
to choose another private directory. File permissions are restricted to the local
user on systems that support them. The files are **not encrypted**. `USER_TIMEZONE`
defaults to `Asia/Riyadh` for the `today` view and task timestamps.

```bash
python3 scripts/dev.py run task add "Prepare project review" --area work --priority high --due 2026-10-02 --project Alpha
python3 scripts/dev.py run task add "Book dentist" --area personal
python3 scripts/dev.py run task list --area work
python3 scripts/dev.py run task today --area personal
python3 scripts/dev.py run task upcoming --area work --days 7
python3 scripts/dev.py run task list --area work --project Alpha
python3 scripts/dev.py run task show TASK_ID --area work
python3 scripts/dev.py run task edit TASK_ID --area work --priority urgent --due 2026-10-01
python3 scripts/dev.py run task set-status TASK_ID --area work --status done
```

Areas are required on every task command. `today` shows open tasks due today or
overdue. `upcoming` adds a planning horizon and includes overdue tasks. Status can be
`open`, `done`, or `archived`; archive hides a task from the default list without
deleting it. Use `task list --area work --status all` to inspect archived tasks.
These commands need no account. Avoid placing credentials in task titles or details.
In Claude Code, Ahmad uses the work area only, through these commands, after Khalid's
yes once per session.

## Persistent profile and project memory

Explicit memory uses the same area separation and private SQLite files as tasks:

```bash
python3 scripts/dev.py run memory set tone "Keep summaries concise" --area work
python3 scripts/dev.py run memory set role "IT consultant" --kind profile --area work
python3 scripts/dev.py run memory set goal "Roll out MFA to the support team" --kind project --project Alpha --area work
python3 scripts/dev.py run memory set assumptions "State missing evidence instead of guessing" --kind lesson --area work
python3 scripts/dev.py run memory set mfa_checklist "MFA rollout: scope, owner, evidence, next steps" --kind example --project Alpha --area work
python3 scripts/dev.py run memory list --area work --kind project --project Alpha
python3 scripts/dev.py run memory forget goal --kind project --project Alpha --area work
```

These are illustrative values; the application does not prefill your profile. Repeat
`memory set` with the same area, kind, project and key to edit a memory. `memory list`
inspects all memories in the selected area; `--kind` and `--project` filter it.
`memory forget` deletes the exact named entry. Preferences and profile entries apply
throughout their area and cannot have a project scope. Project entries require a
project name. Lessons and examples can be area-wide or scoped to one project. Project
names match exactly, including case. Preference values allow 1,000 characters; other
kinds allow 4,000. Saving an example does not open a file path or bypass reference
permissions.

Memory is never inferred and saved automatically; Ahmad saves it only when Khalid
explicitly asks. Do not store passwords or secret tokens.

## Finding a finished SOP

```bash
python3 scripts/dev.py run find-sop incident management
```

It lists the SOP files in `teams/documentation/output/` whose names best match the words, newest first,
without opening them. A published draft is listed once, as its `teams/documentation/output/` copy.

## External services

REEMA has no connected mailbox, calendar, task cloud, or background notification
service, and never sends email or any external communication. Ahmad can draft or
recommend actions, but cannot send an email, modify a calendar, make a purchase, or
silently change a system. Those actions would need an integration Khalid selects and
authorizes; Snafi's adapters will add them step by step under the PRD's permission
levels, with every send, invite or delete behind an approval card. Connectors in a Claude Code or ChatGPT session are separate from REEMA
and do not grant REEMA account access.

For source permissions, see [Reliability and sources](RELIABILITY_AND_SOURCES.md).

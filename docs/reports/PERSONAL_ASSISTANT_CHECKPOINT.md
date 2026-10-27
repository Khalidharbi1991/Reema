# Personal assistant scope checkpoint

Date: 2026-09-29. This is the implemented local foundation following the user's
approved work-and-personal scope and leadership changes.

This checkpoint predates the later specialist renaming and Agent 9 addition.
For their current status, see [Building-design checkpoint](BUILDING_DESIGN_CHECKPOINT.md).

## Implemented in the repository

- Removed the separate Khalid owner agent from the active package and configuration.
  Its strategic planning, governance, quality, stakeholder, and business-value
  guidance is assigned to Abdullah and passed into the documentation workflow.
- Ahmad is the main coordinator. The active roster contains Ahmad, Abdullah, and
  eight specialists. Strategic chat questions can consult Abdullah. Existing
  specialist knowledge files were preserved.
- Added separate local work and personal task stores with task capture, due dates,
  priorities, project filters, today's view, upcoming view, completion, reopening,
  and archive. Areas must be selected explicitly.
- Added explicitly saved preferences with inspect and forget commands, kept in
  the selected area's database. Local files are ignored by Git and use restrictive
  user permissions where supported; they are not encrypted.
- Added a single CLI chat command. Ahmad answers, consults a specialist for
  configured topics, and uses only the selected area's context. Local slash task
  and preference commands plus a few clear natural task phrases work without any
  model call. Advisory chat requires
  explicit transmission permission and an Anthropic key.
- Preserved the existing SOP pipeline, export recovery, source permissions,
  quality checks, and separate human document approval.

## Verification

- Local Python 3.14.2 locked environment: **191 tests passed**, **85.49% source
  coverage**, above the existing 70% gate. Tests use fake model calls and
  synthetic tasks; no live API call was performed.
- Wheel rebuilt and installed outside the source checkout; `reema agents`,
  `reema chat '/task help' --area personal`, and `reema status` passed.
- Linux/Python 3.11 container rebuilt. With networking disabled, the ten-agent
  roster and synthetic local task entry point passed. The container ran as
  UID 10001 and contained no customer references, `.env`, or `.git`.
- Dependency set did not change. The earlier real PDF/DOCX export checks remain
  valid; this change did not alter the formatters. Hosted CI was not run.

## Required external decisions and remaining work

The local assistant is usable, but the full connected-assistant vision still
requires an account ecosystem. The user must choose whether REEMA should
connect to Microsoft 365/Outlook, Google Workspace/Gmail, or stay local. No
mailbox, calendar, cloud task list, or notification provider is connected.
The available Codex/ChatGPT plugins are separate from this Python runtime and
do not automatically grant it account access. A provider-specific integration
requires API design, authentication, permissions, and live acceptance tests.

Chat routing uses ordered keywords; it is not a general autonomous tool planner.
No live model conversation, email send, calendar update, purchase, deployment,
or human document approval was performed. Local conversation history lasts only
for its session. Task and preference data require normal device backup and
access control. See [the operating guide](../guides/PERSONAL_ASSISTANT.md).

# Project Documentation

- `architecture/` contains the system architecture; `AGENTS.md` wins where they conflict.
- `guides/` contains the current user and developer guides.
- `archive/` keeps outdated setup guides and hierarchies for reference only.
- `project/` contains scope and project-definition material.
- `reports/` contains implementation and knowledge enhancement reports, and the
  `CHANGELOG.md`. Reports describe the system as it was when written.
- `migration/` explains the model runtime's removal and what adding one back would take.
- `development/` contains offline evaluation scenarios and coverage limits.

REEMA makes no model call: Claude Code writes the text, and REEMA's code checks,
exports and records it. Start with:

- [Personal assistant](guides/PERSONAL_ASSISTANT.md): Ahmad's role as executive personal assistant and coordinator, the routes, tasks and memory.
- [Coordination](guides/COORDINATION_AND_RECOVERY.md): who writes what, job phases and export.
- [Data handling](guides/DATA_HANDLING.md): what a Claude Code session may read, and approval.
- [Reliability and sources](guides/RELIABILITY_AND_SOURCES.md): the reference manifest and checks.
- [Document quality](guides/DOCUMENT_QUALITY.md): sections, controls, findings and exports.
- [Specialist checks](guides/SPECIALIST_EVIDENCE_AND_CHECKS.md) and
  [diagrams, Arabic exports and evaluation](guides/COMPLETION_AND_EVALUATION.md).
- [Handoffs and status](guides/AGENT_HANDOFFS_AND_STATUS.md),
  [Development setup](guides/DEVELOPMENT_SETUP.md) and
  [Evaluation baselines](development/AGENT_EVALUATION_BASELINES.md).

The repository root keeps only the primary `README.md`, the main `AGENTS.md` entry
point (the source of truth for coding agents), and `CLAUDE.md`, which imports
`AGENTS.md`.

# Project Documentation

- `architecture/` contains the current system architecture and agent hierarchy.
- `guides/` contains setup, quick-start, and task-specific user instructions.
- `project/` contains scope and project-definition material.
- `reports/` contains implementation and knowledge enhancement reports.
- `migration/` contains provider and Codex adoption plans.
- `development/` contains offline agent evaluation scenarios and coverage limits.

Current agent reliability work is described in
[Handoffs and status](guides/AGENT_HANDOFFS_AND_STATUS.md),
[Evaluation baselines](development/AGENT_EVALUATION_BASELINES.md), and
[Package 1 checkpoint](reports/AGENT_IMPROVEMENTS_PACKAGE_1.md).
The next implemented package is documented in
[Coordination and recovery](guides/COORDINATION_AND_RECOVERY.md) and
[Package 2 checkpoint](reports/AGENT_IMPROVEMENTS_PACKAGE_2.md).
Document-specialist improvements are described in
[Document quality](guides/DOCUMENT_QUALITY.md) and
[Package 3 checkpoint](reports/AGENT_IMPROVEMENTS_PACKAGE_3.md).
The reproducible local environment and specialist validators are described in
[Development setup](guides/DEVELOPMENT_SETUP.md),
[Specialist evidence and checks](guides/SPECIALIST_EVIDENCE_AND_CHECKS.md) and
[Package 4 checkpoint](reports/AGENT_IMPROVEMENTS_PACKAGE_4.md).

The repository root keeps only the primary `README.md`, the main `CLAUDE.md`
entry point (the source of truth for coding agents), and `AGENTS.md`, which
points to `CLAUDE.md`.

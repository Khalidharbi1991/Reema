# Agent improvements package 1

Current completion and remaining requirements are recorded in [package 5](AGENT_IMPROVEMENTS_PACKAGE_5.md) and the [finite ledger](PENDING_LEDGER.md). Remaining-work statements below describe this historical checkpoint.


This is the historical package 1 checkpoint. [Package 2](AGENT_IMPROVEMENTS_PACKAGE_2.md) updates coordination, session continuity and model-phase recovery.

Implemented and verified locally on 15 October 2026. This package improves
handoff preservation, contract validation, status accuracy and offline baselines.
The application remains Anthropic-backed. Existing memory work and the dirty
checkout's unrelated changes were retained. No document approval, paid model
generation, provider migration or publication was performed.

## Implemented scope

- Access and Problem content prompts, optional Access/Data research context and
  inactive legacy Problem ITOM prompt helpers retain complete supplied text.
  Specialist appendices retain their full bodies. Data metric inputs and Content
  research/standards inputs retain extension fields and source/requirement IDs.
  Existing prompt/run budgets fail explicitly; no prefix summarization replaces
  the removed slices.
- Strict Pydantic handoff envelopes validate actual research/enrichment/review
  workflow boundaries while keeping public strings/dictionaries. Optional typed
  metadata represents findings, provenance, assumptions, unresolved questions
  and deliverables. Provenance remains unverified; model narrative is not promoted
  into verified facts. Handoffs are saved in reached checkpoints.
- Review and compliance gate adapters reject malformed/contradictory decisions.
  Offline export recovery applies the same review contract. All previous quality,
  source permission and separate human approval safeguards remain.
- Leader counters reflect real coordination-phase transitions, timestamps,
  failures, cancellations and skipped future phases. Snapshots persist in
  `run.json`; instance reuse resets counters and concurrent reuse is rejected.
- Ahmad's legacy communication helper reports `recorded` and `not_dispatched`.
  Advisory handover summaries explicitly lack file verification/distribution and
  cannot certify quality. Briefings receive full supplied records, report missing
  information honestly, and distinguish model gates from human approval.
- Forty-nine new synthetic test cases cover current routing limitations, long
  payloads/tails/citations through review/export, malformed and incomplete data,
  missing-evidence decisions, contradictions, budgets, consent and actual status
  transitions. A scenario catalog maps existing/new tests to all eleven roles.

## Files changed for this package

Implementation: `src/utils/handoffs.py` and `src/agents/access_agent.py`,
`problem_agent.py`, `data_agent.py`, `content_agent.py`, `leader_agent.py`,
`secretary_agent.py`. Existing provider, memory, formatter, approval and reference
permission implementations were not rewritten.

Verification: `tests/test_agent_improvement_package.py`.

Documentation: root README/context, architecture and documentation entry points,
[handoffs and status guide](../guides/AGENT_HANDOFFS_AND_STATUS.md),
[evaluation baselines](../development/AGENT_EVALUATION_BASELINES.md), and this report.

## Verification

Affected tests passed before the full run. Final full offline command:

```bash
PYTHONPATH=/private/tmp/reema-agent-test-deps python3 -m pytest -q -rs
```

Result: **265 passed, 1 skipped**. The skip is the PDF export test because native
PDF libraries are unavailable to this Python process. Normal Markdown, HTML,
DOCX, CAD and recovery checks passed. `git diff --check` passed.

The host Python lacked `ezdxf` and `pyparsing`. Their existing locked versions
(`ezdxf==1.4.4`, `pyparsing==3.3.3`) were installed with the lock-file hashes,
`--no-deps` and `--only-binary=:all:` into the temporary directory above. Global
packages and dependency declarations were not changed. The temporary directory
may be removed by the OS; install `requirements-dev.lock` in the development
environment for reproducible full-suite execution. Native Pango/WeasyPrint
dependencies remain necessary for the skipped PDF check.

Tests deny live HTTP and use synthetic provider responses. These results validate
software behavior and data preservation, not model reasoning, factual accuracy,
regulatory compliance or export visual quality.

## Limitations and remaining roadmap

**A Baselines and reliability:** this package establishes executable baselines,
removes active prefix loss and corrects status honesty. Real model quality still
needs separately authorized input and evaluation criteria.

**B Shared inputs and outputs:** the incremental contracts are implemented at
the selected boundaries. Extend typed domain-specific findings and consistent
configuration/runtime interfaces without breaking public APIs. Metadata is
optional and prose remains unstructured; contracts cannot check semantic use of
all requirements. Large requests fail rather than being automatically rewritten.

**C Coordination and execution:** selectively improve Ahmad's first-keyword,
single-specialist routing and generic advisory calls. Add multi-specialist
capabilities and safe tool execution. Evolve Abdullah's fixed pipeline into
persistent, recoverable execution for model phases. Current recovery still starts
from a ready-to-export checkpoint; phase status is not an execution scheduler.

**D Documentation specialists:** evolve Agent 3 toward template-based section
assembly, targeted revisions and validated diagrams; Agent 2 toward an applicable
control register tied to evidence and final-document checks; Agent 4 toward located
finding IDs, blocking rules and rechecks; Agent 5 toward templates and visual
export QA. Preserve deterministic formatting.

**E Specialist depth:** improve Agent 1 source research/freshness; Agent 6 actual
environment IAM/control validation; Agent 7 evidence/timelines/hypotheses;
Agent 8 metric specifications and synthetic calculation checks; Agent 9 CAD
interpretation and geometry validation before furnishing/rendering. Agent 9's
current artifacts remain bounded concept meshes, not complete building/BIM models.

Any provider migration remains a separate explicit request covering settings,
abstraction, dependencies, documentation and tests together.

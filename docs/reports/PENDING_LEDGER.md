# REEMA finite completion ledger

Scope agreed on 16 October 2026: finish the named agent-improvement software
roadmap after packages 1–4. This ledger separates unfinished implementation from
external verification and optional expansion. It does not define completion as
universal understanding, production certification or a full building/BIM product.

| ID | Named commitment | Status | Completion evidence or requirement |
| --- | --- | --- | --- |
| P1–P4 | Complete handoffs/contracts, truthful status, coordination, session continuity, SOP quality, project setup and specialist validators | Complete | Historical package 1–4 reports; prior baseline 446 tests, package 5 suite 597, current full suite 678 |
| R1 | Broader Arabic/English intent, contextual references, exclusions and ambiguity | Complete bounded implementation | `coordination.py`, `assistant.py`, configured bilingual hints; actual planner/local/consent/override tests in `test_completion_package.py`; real semantic quality remains E2 |
| R2 | Hard-crash/stale-running recovery without interfering with live owners | Complete on verified host | `ownership.py`, `runs.py`, `execution.py`; actual subprocess kill, active-owner and concurrent-resumer tests; cross-host recovery rejected; other hosts E4 |
| R3 | Reuse completed individual review/compliance chunks | Complete | `quality.py` and signed `completed_assessments`; exact prompt/schema/identity binding, validation before cache/use, interruption/reuse and durable unknown-usage reservation tests |
| R4 | Decision/branch/swimlane diagrams and multilingual labels | Complete bounded implementation | Graph schema, reachability/forward/decision/overlap checks, SVG/PNG renderers, readable-text failure cases and inspected Arabic branches |
| R5 | Arabic/RTL, mixed-script layouts and configurable template variants | Complete verified fixtures | `standard`/`compact`, localized stable sections, Arabic shaping, LTR numeric boundaries; all 12 latest Word/PDF pages inspected, including ISO date; `output/qa/package5/arabic-reviewed/visual-qa.json`; HTML structural checks |
| R6 | Versioned all-role synthetic evaluation, explicit rubrics and executable baseline | Complete harness | `evaluations/v1/`, 24 cases for twelve roles (Agent 10 added 28 October 2026), negative graders and offline 24/24 canonical-answer mock; this is not model/full-agent quality evidence |
| R7 | Reviewable live-quality evaluation proposal | Proposal complete; execution pending E1 | Exact requests and seven file hashes; Sonnet 4.6, 24 requests, 53,321 reservations, 512 output tokens each, zero retries, USD 3.07419 modeled bound within USD 5; material SHA-256 `bda0810cb4686c2b54543a930f82de360a306d836c6944f32d330ebe8c70395c` supersedes the package 5 report digest; regenerate the proposal before authorizing |
| S1 | IAM group inheritance, supplied drift and separation of duties | Complete bounded checks | Kahn group traversal/cycle rejection, effective privilege/MFA/approval checks, role/state/classification drift and configured conflict pairs; no live IAM access, production truth E3 |
| S2 | Stronger causal evidence evaluation | Complete bounded checks | Supplied test criteria/timestamps/outcomes, located support/refutation/conflicts; competing hypotheses and root cause unconfirmed; actual investigation E3 |
| S3 | Data lineage, formulas and calendars | Complete bounded checks | Located unverified evidence, difference/weighted mean, explicit zone/workdays/holidays, nonnegative bounded intervals and DST ambiguity rejection; real lineage E3 |
| S4 | Richer bounded CAD interpretation | Complete bounded checks | Explicit matching metre/mm/cm/feet units, configured wall layers, raw/converted/clipped provenance and proxy rotation/scale records; no inferred rooms/full BIM; verified dimensions/review E3 |
| R8 | Reconcile older reports and remaining acceptance targets | Complete | Package 5 per-agent table/current guide, historical report pointers and replaced obsolete future-target statements in `AGENT_EVALUATION_BASELINES.md` |

External verification remains distinct: supplied production snapshots/observations
and reference dates need owner confirmation; actual access/control operation needs
authorized environment access; real root causes need investigation; building safety
and construction fidelity need qualified review. These are not claims software
tests can establish. External-account dispatch, provider migration, arbitrary
workflow scheduling, complete CAD/BIM and every possible language/template are
optional product expansions, not silent additions to this finite completion scope.

Irreducible boundary: a model request killed after transmission but before its
result is durably recorded cannot be guaranteed exactly once by a local program.
Recovery must report that uncertainty and retain conservative usage accounting.

## Exact remaining requirements

| ID | Requirement | Status and concrete need |
| --- | --- | --- |
| E1 | Run the prepared live synthetic benchmark | Pending. No API key is configured. Provide a usable Anthropic key and explicitly authorize the unchanged proposal's exact material hash `2452ad990a5b144a8ced9dc454df6f9ec4561ad0be57188687e169acdf64e335`. Regenerate the proposal first (`python3 scripts/dev.py python scripts/evaluate_agents.py proposal --output ...`); the 2026-10-28 audit fixes changed hashed files, so the earlier `d92fa587…` hash no longer matches. Recheck current prices/account access. No live request has run. |
| E2 | Establish actual answer/model/full-agent quality | Pending external evaluation. Apply human rubrics to live results. For actual production prompts/retrieval/workflow, agree representative inputs and owner-labelled expected answers, then separately authorize every full prompt/reference/memory input. The short-role canonical mock cannot establish this. |
| E3 | Establish organization/environment truth | Required for real use, not an unfinished local validator. Supply and confirm current authoritative references, applicable controls, IAM snapshots/approvals/SoD rules, diagnostic evidence, rows/lineage/calendars and drawing dimensions; use authorized qualified environment review where needed. Per-role needs are in the package 5 report. |
| E4 | Verify other platforms/viewers/scripts | Conditional. Current macOS/locked environment is verified. Native Windows locking, other dependency/font/viewer combinations and additional scripts need their own host-specific QA. |
| E5 | Approve actual generated documents | Required per artifact. Successful pipeline runs still end at `awaiting_human_approval`. The named human must review and explicitly approve those exact artifacts. No approval was supplied on their behalf. |

There is no remaining independently actionable software task in the agreed finite
scope. E1/E2 remain necessary before claiming real model quality. HMAC records
are local tamper detection, not encryption/multi-user authentication; a privileged
writer with the key can forge them. Inherited token budgets are per branch, not a
global billing cap. Exactly-once provider outcomes after response loss remain
irreducibly uncertain. Optional expansions listed above are not marked complete.

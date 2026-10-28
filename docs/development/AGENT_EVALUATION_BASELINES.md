# Agent evaluation baselines

These are synthetic offline software scenarios. Fake completions exercise real
prompt builders, adapters, orchestration, review parsing and exports. They do
not measure a model's reasoning, research accuracy, writing quality or regulatory
expertise. The autouse HTTP denial fixture in `tests/conftest.py` blocks live calls.
No customer documents or paid generation are needed.

Package 3 adds 48 cases in `tests/test_document_package.py`: Standards control
register/provenance and finished-document references; Content configured section
assembly and digest-bound revisions preserving unaffected bytes; Review exact
locations, blocking findings and correction rechecks; Format bounded diagrams,
real output checks and readable table behavior. Real agent methods run through
the SOP pipeline with synthetic completions. A separate PDF/DOCX render inspection
is recorded in [package 3](../reports/AGENT_IMPROVEMENTS_PACKAGE_3.md).

Package 4 adds bounded source-date/claim validation, supplied IAM snapshot checks,
incident timelines and competing hypotheses, deterministic metric calculations and
CAD intake/selection checks in `tests/test_specialist_package.py`. It includes a
real-method SOP/recovery scenario preserving the structured results without repeat
calls. Run tests with `python3 scripts/dev.py test -q -rs`; the project environment
removes temporary dependency/native-path overrides. See [package 4](../reports/AGENT_IMPROVEMENTS_PACKAGE_4.md).

## Current executable baselines

| Role | Synthetic scenario and observed behavior | Executable coverage |
| --- | --- | --- |
| Ahmad | A mixed SOP/MFA/KPI request consults Access, Data and Content through Abdullah. Common negation excludes unwanted capabilities; ambiguous/overbroad requests clarify offline. Explicit and verbatim user decisions survive the recent response window. Explicit memory remains isolated by area/project. A proposed communication is recorded without dispatch. | `test_coordination_package.py` planner/context/failure cases; `test_agent_improvement_package.py` primary-route/communication compatibility cases; `test_personal_assistant.py`; `test_assistant_memory.py` |
| Abdullah | Pause research, inspect active and persisted phase state, complete the run, reuse the leader, fail research, cancel research and cancel offline recovery. Completed research/core generation/enrichment calls are recovered without duplication. Configuration/source changes and tampered execution records block reuse. Inherited usage stays charged; resumed outputs need a fresh human record. | `test_coordination_package.py` recovery/source/budget cases; `test_agent_improvement_package.py` status/cancellation cases; `test_recovery.py`; `test_phase01.py` |
| Agent 1 Research | A research result has the wrong process, missing narrative or wrong field type. The leader blocks content generation. Extra requirement IDs and source references remain in accepted handoffs. | `test_agent_improvement_package.py` malformed/long handoff cases; `test_agent_contracts.py` research API cases |
| Agent 2 Standards | A standards payload includes unresolved applicability information beyond its narrative. Content input retains it. Authorized source extraction/selection and unknown-citation rejection remain enforced. | `test_agent_improvement_package.py` standards extensions; `test_knowledge_quality.py`; `test_agent_contracts.py` standards API cases |
| Agent 3 Content | Long research and specialist payloads contain distinctive tail requirements/citations. Real content prompt construction retains those tails and metadata. Revision remains bounded and reviewed again. | `test_agent_improvement_package.py` end-to-end preservation; `test_agent_contracts.py`; `test_agents.py` review-loop cases |
| Agent 4 Review | A fake high score also requests revision because evidence is absent. The pipeline blocks. A contradictory legacy review is rejected. Review covers all chunks and the global summaries. | `test_agent_improvement_package.py` missing-evidence/contradictory-review cases; `test_knowledge_quality.py` full-document review case |
| Agent 5 Format | Deterministic Markdown export retains all specialist appendix tails. Format failures block pending review. Offline recovery creates new exports and a new pending human record. PDF checks run only with native libraries. | `test_agent_improvement_package.py` end-to-end export; `test_exports.py`; `test_phase01.py`; `test_recovery.py` |
| Agent 6 Access | A requirement after character 12000 reaches the real prompt builder; an appendix tail after character 9000 reaches review/export. Oversized and unauthorized requests never reach the provider. Contradictory compliance blocks delivery. | `test_agent_improvement_package.py` long-payload/budget/consent cases; `test_agent_contracts.py` access compliance cases |
| Agent 7 Problem | Full research context reaches enrichment and the final appendix tail is reviewed/exported. Structured compliance uses booleans and findings. This does not establish a real root cause. | `test_agent_improvement_package.py`; `test_agent_contracts.py` problem compliance cases |
| Agent 8 Data | Optional research tails and all metric fields, including formula, unit and exclusions, remain in the prompt. Full dashboard appendix reaches review/export. No calculation is certified by these tests. | `test_agent_improvement_package.py` metrics/long-payload cases; `test_agent_contracts.py` analytics/dashboard cases |
| Agent 9 Building Design | Local DWG header intake and bounded selected-region DXF geometry generate actual concept artifacts; chat routing recognizes drawing terms. This does not validate a full building or BIM model. | `test_building_design.py`; `test_pipeline.py` roster coverage |
| Agent 10 EUC | English and Arabic endpoint requests route to Agent 10, mixed requests keep other specialists, and negation excludes it. A mocked consultation carries its reversibility protocol and advisory-only guard; no consultation runs without consent. In SOP runs, the patch and device-batch processes select it; its research tail reaches content, its appendix reaches export, a wrong-process or empty result blocks delivery, and both calls are recovered without repetition. Advice and appendix quality are not measured. | `test_euc_agent.py`; `test_pipeline.py` roster coverage; two `evaluations/v1/` cases |

Paths in the coverage column are under `tests/`. The new package tests also reject
unsupported JSON values, invalid source-reference relationships, asserted
verification, malformed review fields and process identity mismatches. Existing
source tests cover manifest permissions/hash changes and preservation of exact
extraction locations. Tests of missing-evidence model decisions supply that
decision explicitly; they do not prove a model can detect missing evidence.

## Reconciled acceptance targets after package 5

Package 5's full suite passes 597 offline tests. The prior future targets below
are reconciled individually; passing mocks does not establish model reasoning or
production truth. See the [package 5 report](../reports/AGENT_IMPROVEMENTS_PACKAGE_5.md),
[finite ledger](../reports/PENDING_LEDGER.md) and
[current guide](../guides/COMPLETION_AND_EVALUATION.md).

| Previous target | Completed bounded evidence | Remaining distinction |
| --- | --- | --- |
| Broader Ahmad language/context | Arabic/English/mixed clauses, exclusions/contradictions, unresolved references, inherited context, offline Arabic actions and consent-gated strict resolver | Universal intent understanding is not claimed. Actual semantic usefulness needs authorized representative evaluation. External account integrations are optional separate work. |
| Hard-killed/running owners and individual chunks | OS leases, signed version 2 committed snapshots, real subprocess-death/concurrent-resumer tests and validated review/compliance excerpt reuse | Active/cross-host owners are rejected. Lost provider outcomes are uncertain; arbitrary scheduling/exactly-once execution remain outside this bounded SOP recovery. |
| Research/Standards semantic evidence quality | Located claims/dates and control applicability/evidence remain enforced and preserved | Independent authority, currency and semantic correctness need authoritative owner evidence and human/live evaluation. |
| Broader diagrams/templates/RTL | Safe explicit forward decision/swimlane graphs, localized stable sections, standard/compact spacing and inspected Arabic/mixed Word/PDF fixtures | All 12 latest pages were inspected, with ISO date order verified. Universal templates/scripts, automated visual certification and arbitrary diagram-code execution are not claimed. Real exports still need review. |
| Semantic correction quality | Located findings, digest-bound targeted patches, correction rechecks and complete payload preservation remain covered by actual-method mocks | Human-labelled expected findings/corrections and full production-agent evaluation are still needed to measure semantic quality. |
| IAM operation and causal reasoning | Supplied nested groups/effective privilege/SoD/drift, competing hypotheses and located test support/refutation/conflicts | No live IAM connection, access grant or real root-cause confirmation. Owner/environment verification remains external. |
| Broader formulas/business calendars/lineage | Explicit differences, weighted means, zoned working-time means, holidays/DST bounds and located unverified evidence | No arbitrary formula/DAX execution or inferred production lineage. Actual rows/calendar rules/source truth need owner confirmation. |
| Richer CAD interpretation | Matching explicit unit conversion, configured layers, geometry clipping/provenance and supported proxy rotation/scale records | Full BIM, rooms/doors/floors/collisions/construction fidelity remain separate product work and qualified review, not silently completed features. |
| Reproducible all-role quality baseline | Versioned 24-case/12-role dataset, expected facts, human rubrics, short benchmark prompts, negative graders and offline canonical-answer mock | Offline 24/24 verifies the harness only. Exact live proposal is ready; key/material authorization and subsequent human quality assessment remain pending. Full agent prompts/retrieval need separate representative authorized evaluation. |

Current executable additions are `tests/test_completion_package.py` and
`tests/test_evaluation_suite.py`. They complement the actual-agent/pipeline
scenarios above rather than replacing them with a canonical-answer benchmark.
The final visual evidence is `output/qa/package5/arabic-reviewed/visual-qa.json`;
older intermediate Word images are not accepted evidence.

```sh
python3 scripts/dev.py test -q -rs
python3 scripts/dev.py python scripts/evaluate_agents.py offline --output output/qa/package5/evaluation/offline-baseline.json
python3 scripts/dev.py python scripts/evaluate_agents.py proposal --output output/qa/package5/evaluation/live-proposal.json
```

Do not run the prepared live command until the user authorizes its exact synthetic
material and configures a usable key. Existing model consent, source permissions,
budgets, work/personal separation and pending human approval still apply.

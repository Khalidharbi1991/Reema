# Agent evaluation baselines

These are synthetic offline software scenarios. They exercise REEMA's real checks,
file-backed workers, jobs and exports with invented content. REEMA makes no model
call, so they do not measure a model's (or Claude Code's) reasoning, research
accuracy, writing quality or regulatory expertise. `tests/conftest.py` blocks every
network connection, and `tests/test_no_api_guard.py` fails if anything references,
declares, installs or imports the Anthropic API. No customer documents are needed.

Run them with `python3 scripts/dev.py test -q -rs`; the project environment removes
temporary dependency/native-path overrides.

## Current executable baselines

| Role | Synthetic scenario and observed behavior | Executable coverage |
| --- | --- | --- |
| Ahmad | Local work/personal tasks and memory stay separate; `find-sop` lists files by name without reading them; `reema chat` only points to Claude Code. | `test_personal_assistant.py`, `test_assistant_memory.py`, `test_agent_contracts.py` |
| Abdullah | The local generate, review, revise and export jobs record real phases, refuse a plain worker where a Claude Code file worker is required, and end awaiting human approval. | `test_claude_code_generate.py`, `test_sop_review.py`, `test_sop_revise.py`, `test_export.py`, `test_pipeline.py` |
| Agent 3 Content | Section files run through the per-section loop in order; a wrong section, a top-level heading or a broken diagram fails and names the section. Revisions change only the target sections. | `test_section_generation.py`, `test_claude_code_generate.py`, `test_claude_code_revise.py`, `test_document_package.py` |
| Agent 4 Review | Every excerpt is assessed, consistency is checked across excerpts, quotes must be located, and rechecks bind the revised document. | `test_claude_code_review.py`, `test_sop_review.py`, `test_knowledge_quality.py` |
| Agent 5 Format | Exports run real output checks; failures block the pending record; export re-runs every local check on a Claude Code draft. | `test_exports.py`, `test_phase01.py`, `test_export.py`, `test_completion_package.py` |
| Agents 6, 7, 8 | No class: supplied IAM, problem and metric data run through local checks whose results go into the generate request as data. | `test_specialist_package.py`, `test_completion_package.py`, `test_claude_code_generate.py` |
| Agent 9 Building Design | Local DWG header intake and bounded selected-region DXF geometry generate concept artifacts; the subagent definition carries its limits. | `test_building_design.py`, `test_completion_package.py` |
| Agent 10 EUC | The subagent carries the endpoint protocol word for word plus the closing; a patch SOP needs its appendix with every required heading. | `test_euc_agent.py`, `test_claude_code_generate.py` |

Agents 1 and 2 have no class and no scenario. Paths in the coverage column are under
`tests/`. Passing these tests does not establish model reasoning or production truth.

## Synthetic evaluation suite

`evaluations/v1/` holds 24 invented cases (two per role) with expected facts and human
rubrics. The offline run grades the canonical answers, which proves the fixtures and
the grader only (`test_evaluation_suite.py`):

```sh
python3 scripts/dev.py python scripts/evaluate_agents.py offline --output output/qa/evaluation/offline-baseline.json
```

Evaluating real Claude Code output would be separate work, with representative
inputs and owner-supplied expected answers.

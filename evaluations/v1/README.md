# Synthetic role evaluation version 1

`cases.json` contains only invented requests, people, observations, numbers and
locations. `prompts.json` contains short role instructions written for this
benchmark. No application knowledge, customer reference, task database or chat
history is part of the dataset or live payload. All twelve roles have two cases.

Expected structured fields are exact factual and authority checks. Each case also
has a human rubric for reasoning, clarity and unsupported claims. Exact grading
does not score writing quality or prove production expertise. REEMA makes no model
call, so only the offline run remains: it grades the canonical expected answers to verify
the fixtures and the grader; negative grader tests separately remove/change expected facts
and inject forbidden fields.

Run from the repository root:

```sh
python3 scripts/dev.py python scripts/evaluate_agents.py offline --output output/qa/evaluation/offline-baseline.json
```

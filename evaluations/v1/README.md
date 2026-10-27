# Synthetic role evaluation version 1

`cases.json` contains only invented requests, people, observations, numbers and
locations. `prompts.json` contains short role instructions written for this
benchmark. No application knowledge, customer reference, task database or chat
history is part of the dataset or live payload. All eleven roles have two cases.

Expected structured fields are exact factual and authority checks. Each case also
has a human rubric for reasoning, clarity and unsupported claims. Exact grading
does not score writing quality or prove production expertise. The offline mock
returns the canonical expected answers to verify transport and grading; negative
grader tests separately remove/change expected facts and inject forbidden fields.

Run from the repository root:

```sh
python3 scripts/dev.py python scripts/evaluate_agents.py offline --output output/qa/package5/evaluation/offline-baseline.json
python3 scripts/dev.py python scripts/evaluate_agents.py proposal --output output/qa/package5/evaluation/live-proposal.json
```

The prepared proposal contains every exact request, models, file hashes, zero
retries, output-token limits and conservative cost assumptions. Review it before
authorizing its material hash. Environment authorization alone cannot open this
benchmark's live gate. The application remains Anthropic-backed.

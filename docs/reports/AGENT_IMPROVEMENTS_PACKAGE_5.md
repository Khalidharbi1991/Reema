# Agent improvements package 5

Completed independent software and offline verification on 16 October 2026.
The full suite passes **597 tests with no skips**. Both configured layouts have
three inspected PDF pages and three inspected Word-render pages: **12 pages total**.
The synthetic eleven-role mock baseline passes **22 of 22 cases**. No live model
call, customer egress, human document approval, provider migration, commit or
publication was performed. Existing dirty changes and packages 1–4 were preserved.

The [finite ledger](PENDING_LEDGER.md) distinguishes finished implementation from
the remaining live evaluation, owner evidence and platform verification. This
report does not claim that passing software tests establishes better model answers.

## What each agent gained and still needs

The live quality need applies to every role. The benchmark uses short role prompts
written specifically for its invented cases; it does not run the full production
agent prompts, retrieval, memory or SOP workflow. Real-agent mocked tests separately
exercise actual routing, prompt builders, validators, orchestration and exports.

| Role | Completed improvement | Exact remaining input or verification need |
| --- | --- | --- |
| Ahmad | Arabic/English/mixed intent, exclusions, contradiction clarification, contextual follow-ups, offline Arabic tasks/session facts and strict opt-in intent resolution | Deliberately saved user preferences/examples and representative real requests with expected scope; authorized evaluation of ambiguity and answer usefulness. External accounts remain a separate optional integration. |
| Abdullah | Kernel-held ownership, hard-kill recovery, atomic signed state, validated chunk reuse, inherited uncertain usage and fresh pending human-review records | Authorized live workflow cases and owner acceptance criteria; lost provider responses remain uncertain. Actual documents still require the named human's decision. |
| Agent 1 Research | Located claims and supplied-date freshness from package 4 remain preserved through handoffs/recovery | Authorized authoritative references, confirmed publication dates and human checks of semantic support/accuracy; age and exact quotations do not prove truth. |
| Agent 2 Standards | Located control register, unresolved applicability, evidence coverage and separately recoverable compliance chunks | Current applicable standards, organizational/jurisdictional scope and control-owner evidence; qualified review remains necessary for regulatory conclusions. |
| Agent 3 Content | Mandatory stable sections, localized display titles/document label, full specialist inputs, digest-bound targeted revisions and safe decision diagrams | Approved writing examples/templates, terminology and representative expected answers for human fidelity/readability evaluation. |
| Agent 4 Review | Located exact findings, blocking gates, correction rechecks and schema/location-revalidated excerpt checkpoints | Subject-matter ground truth and labelled correct/incorrect findings to evaluate false positives/negatives and calibrate thresholds. |
| Agent 5 Format | Safe branch/swimlane exports, Arabic shaping, Word RTL/numeric boundaries, HTML isolates, templates and exact content checks; both layouts visually inspected | Review each real export in its target viewer/fonts; other hosts/scripts/templates need their own QA. HTML has structural checks, not a claimed browser visual certification. |
| Agent 6 Access | Nested group inheritance, effective privileged roles/MFA, configured SoD pairs and chronological supplied snapshot drift | Current owner-supplied identities/groups/approval evidence and organization-specific conflict pairs; actual live control operation needs authorized environment verification. No access is granted. |
| Agent 7 Problem | Competing hypotheses plus located supplied support/refutation/conflict test outcomes | Verified incident chronology, discriminating diagnostic tests and owner investigation. Real root cause remains unconfirmed. |
| Agent 8 Data | Located unverified lineage, deterministic differences/weighted means and explicit working calendars alongside original metrics | Authorized real rows, source lineage and owner-confirmed exclusions/workdays/holidays/time zone; calculations cannot establish source-data truth. |
| Agent 9 Building Design | Explicit matching DXF units, configured wall layers, converted/clipped provenance and supported proxy rotation/scale records | Verified drawing dimensions/layers/elevations and qualified review. Proxies are assumed, and full BIM, room/door/floor inference, collisions and construction accuracy remain separate product work. |

These are bounded application capabilities. They do not retrain model weights or
save inferred permanent personal memory. The user controls explicit memory,
source permissions and consequential decisions.

## Implementation evidence

- `tests/test_completion_package.py` exercises real killed-subprocess ownership,
  active-owner/concurrent-resumer exclusion, signed committed snapshot recovery,
  pre-transmission reservation persistence, unknown usage, chunk interruption/reuse,
  bilingual rules/consent, Arabic graphs/RTL/date formatting and specialist depth.
- `tests/test_evaluation_suite.py` exercises all 22 cases against negative answers,
  exact live material gates, no client construction before authorization, partial
  provider failure accounting and shared actual-agent/model override behavior.
- Existing tests continue to exercise full-payload handoffs, real agent methods
  with fake completions, source/permission/configuration changes, quality gates,
  asynchronous cancellation and separate human approval. Test HTTP is denied.
- `src/utils/ownership.py`, `runs.py`, `execution.py`, `provider.py` and `quality.py`
  implement ownership, atomic authenticated commits and per-excerpt recovery.
- `src/utils/domain_depth.py` and `specialists.py` implement bounded supplied-data
  checks; Access/Data/Problem and the leader invoke them before caching/downstream use.
- `src/utils/diagrams.py`, `src/formatters/typography.py`, safe HTML and the Word/PDF
  formatters implement bounded graphs and mixed-script presentation.

Model-phase recovery still requires fresh material consent and matching request,
source permissions/content, knowledge/templates, configuration, implementation and
dependency locks. A signed version 2 snapshot can recover a locally abandoned
running owner after the OS lock is available. It cannot establish cross-host
liveness or exactly-once external execution. Uncertain reservations remain charged.
Inherited budgets are per branch, not an account-wide spending ledger.

Graph bounds are two to eight nodes, one to three lanes, up to twelve forward
edges and six row indices. Only decisions branch, with two explicit labels.
Invisible characters, unknown/duplicate IDs, overlap and unreadable text bounds
fail. There is no arbitrary XML/SVG/code execution or invented workflow branching.

## Verification and visual evidence

```sh
python3 scripts/dev.py doctor
python3 scripts/dev.py test -q -rs
```

Doctor confirmed the locked project environment and PDF native imports. Final
test output is `output/qa/package5/full-tests.log`: **597 passed in 12.40s**.
Locks/dependencies and global shell settings were not changed. This host is macOS
with project Python 3.14.2, WeasyPrint 70.0 and Pillow RAQM. Other platforms,
including native Windows lock behavior, have not been independently exercised.

The final synthetic exports and render evidence are under:

```text
output/qa/package5/arabic-reviewed/standard/{markdown,html,docx,pdf}/
output/qa/package5/arabic-reviewed/compact/{markdown,html,docx,pdf}/
output/qa/package5/arabic-reviewed/{standard,compact}/{docx-render,pdf-render}/
output/qa/package5/arabic-reviewed/export-checks.json
output/qa/package5/arabic-reviewed/visual-qa.json
```

All twelve latest PNGs were opened and inspected. Arabic text is shaped, headings
and tables are readable, both decision branches/owners remain visible, and no
clipping, overlap, missing glyphs or broken tables were observed. The first page
of both Word variants and both PDFs visibly preserves **2026-10-16**. Word's
`w:rtl=0` alone was insufficient; numeric LTR boundary marks fixed the actual
render. HTML isolates preserve Latin/number runs without changing its text.
Word/PDF pagination differs naturally; each retains all eleven sections, three
tables, one diagram and all 27 supplied table cells. The QA JSON binds every
inspected page and artifact hash. Older intermediate QA directories are not the
accepted evidence. These checks concern synthetic fixtures, not real document approval.

WeasyPrint did not shape Arabic SVG diagram text correctly on this host. Arabic
PDF diagrams therefore use locally shaped PNGs through an exact resource allowlist.
HTML uses generated SVG, Word uses PNG, and arbitrary resource fetching remains
denied. PDF presence checks handle bounded Arabic visual-order extraction while
retaining exact heading/cell checks. Structural/text checks do not prove visual
quality, accessibility or correctness of every future export.

## Anthropic default maintenance

Shipped leader/worker defaults now use `claude-sonnet-4-6`. Omitted role models
inherit those family settings; explicit role models win. Existing role/environment
overrides and the private `.env` file are preserved. Actual agents and the evaluation
share the same selection function; tests cover both override levels.

Anthropic's [lifecycle page](https://platform.claude.com/docs/en/about-claude/model-deprecations)
lists Sonnet 4 as retired on 15 June 2026 and Sonnet 4.6 as active. Its
[pricing page](https://platform.claude.com/docs/en/about-claude/pricing) lists
Sonnet 4.6 base prices of USD 3 input / 15 output per million tokens, checked
16 October 2026. The current SDK/temperature request contract is retained. No
provider migration or live model compatibility/quality test is implied.

## Exact live evaluation proposal

Prepared files:

```text
evaluations/v1/cases.json
evaluations/v1/prompts.json
evaluations/v1/rates.json
scripts/evaluate_agents.py
output/qa/package5/evaluation/offline-baseline.json
output/qa/package5/evaluation/live-proposal.json
```

The proposal also binds hashes of `config/agent_config.yaml`, `src/utils/config.py`
and `src/utils/provider.py`. Every exact Messages request is included. Egress is
only to `https://api.anthropic.com`, with no BaseAgent retrieval, private knowledge,
customer references, memory, task records or transcript. Dataset classification
is synthetic public. The model is `claude-sonnet-4-6` for all eleven roles.

| Bound | Prepared value |
| --- | --- |
| Requests | 22 sequential requests, zero retries |
| Maximum output per request | 512 tokens, 11,264 in total |
| Conservative total token reservations | 48,597 |
| Planning rates | USD 30 input / 150 output per million, ten times the documented base prices |
| Modeled cost bound | USD 2.80959 within a USD 5 planning limit |
| API key configured | False; key value was never printed |
| Live execution | Not performed or authorized |

This conservative bound uses byte-based input reservations and planning rates;
it is not a provider invoice guarantee or account-wide limit. Recheck actual
prices and account/model availability before paid use.

Final material SHA-256:

```text
d92fa587143a26e639f943a77594c1b683af7da6faff4816a3be4a953901c1f6
```

Only after the user authorizes these exact synthetic requests and provides a
usable Anthropic key, the reviewable command is:

```sh
python3 scripts/dev.py python scripts/evaluate_agents.py live \
  --proposal output/qa/package5/evaluation/live-proposal.json \
  --authorize-material-sha256 d92fa587143a26e639f943a77594c1b683af7da6faff4816a3be4a953901c1f6 \
  --output output/qa/package5/evaluation/live-results.json
```

Changed files, models or bounds invalidate the proposal before client construction.
A provider failure saves partial results/usage and stops further requests. This
standalone benchmark does not provide hard-kill/exactly-once provider recovery.

The **22/22 offline score is a canonical-answer mock**. It verifies transport and
grading, not model reasoning, actual full-agent prompts/retrieval, factual quality,
regulatory expertise or end-to-end writing. Live structured scores still require
human rubric review. Evaluating actual production agents needs separately agreed
representative inputs/expected answers and authorization of the full prompt,
knowledge/reference/memory material that would leave the machine.

## Remaining requirements

The prepared live benchmark is blocked by an Anthropic API key and explicit exact
material authorization required by [AGENTS.md](../../AGENTS.md): “External model
calls require explicit authorization for the input/reference material.” A later
live score must be assessed against the human rubrics.

Actual answer quality and production truth remain external validation needs,
listed per agent above. Real source authority, applicable controls, live IAM
operation, root causes, production row lineage and building/construction fidelity
cannot be established by these software tests. Other platform/viewer combinations
need their own verification. Actual generated documents still need human approval.
Provider migration, external-account dispatch, arbitrary scheduling/formula/code
execution, full BIM and universal language/template support are optional expansions,
not hidden unfinished parts of this finite implementation.

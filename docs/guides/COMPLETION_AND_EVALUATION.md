# Diagrams, Arabic exports, specialist depth and synthetic evaluation

This guide covers the package 5 capabilities that remain after the move to Claude
Code. The bilingual chat intent rules, model-phase recovery, model defaults and the
live evaluation gate it used to describe were removed with the API path. No software
test or handover record supplies human document approval.

## Diagrams templates and Arabic exports

Sequence diagrams retain two to six steps. A `kind: graph` flow supports two to
eight nodes, one to three lanes, at most twelve forward edges and six row indices.
Only decision nodes branch; each requires two labelled outcomes. IDs, reachability,
overlap, forward direction, invisible characters and readable text bounds are
validated. There is no arbitrary SVG/XML/code executor or inferred decision. A
generate request gives the writer both schemas, and only the procedure and flow
sections may carry a diagram.

`config/document_profile.yaml` selects `standard` or `compact` layout values for
heading spacing, paragraph spacing and table padding. `display_title` localizes
section headings while canonical section IDs and titles remain mandatory.
`document_label` can localize the document kind. Existing English defaults remain.

Arabic paragraphs use logical RTL start alignment and an explicit complex-script
font, size and emphasis in Word. Mixed Latin runs are separated; weak numeric/date
runs receive LTR boundary marks so ISO dates retain their visible order. These
formatting marks do not change the source Markdown. HTML uses per-block direction
and LTR isolates. Word diagrams use local PNGs. HTML diagrams use generated SVG.
WeasyPrint's Arabic SVG text did not shape correctly on this host, so PDF uses
locally shaped Arabic diagram PNGs and an exact allowlist fetcher; external/local
arbitrary resource fetches remain denied. Arabic PNGs require a local glyph-covering
font and Pillow RAQM. Missing support fails clearly. Other scripts, unusual fonts and
complex Markdown require their own QA; this does not claim universal language or
layout support.

PDF checks combine logical extraction with bounded Arabic visual-order presence
checks, including lam-alef clusters and Latin/number runs. They still check exact
headings, supplied table cells and diagram descriptions. These checks do not
replace page inspection or establish general accessibility/pagination fidelity.

Run the synthetic fixture:

```sh
python3 scripts/dev.py python scripts/qa_multilingual.py --output teams/documentation/output/qa/arabic-reviewed
```

Choose a fresh output directory when repeating the fixture; existing exports are
never overwritten. HTML receives structural/text/resource checks; it has no claimed
browser visual certification. Never substitute customer documents for these
synthetic fixtures.

## Bounded specialist depth

These checks run locally on a `--specialist-input` file, and their results go into a
generate request as data (`specialist_checks`); see
[Specialist checks](SPECIALIST_EVIDENCE_AND_CHECKS.md).

IAM accepts nested supplied groups, explicit privileged roles, an optional older
snapshot and configured `separation_of_duties` role pairs. It rejects cycles and
unknown memberships, propagates inherited roles and checks their approval/MFA
requirements. Drift includes grant/state and role-classification differences.
Membership/grant totals are bounded. No live directory is accessed or changed.

Problem input may include `TEST-...` outcomes with hypothesis IDs, criterion,
timestamp, supporting/refuting/inconclusive outcome and located evidence. Located
support, refutation and conflicts are reported without confirming a real root cause.

Metric specifications accept located evidence plus differences, weighted means and
working-time means, alongside the original formulas. Business calendars need an
explicit IANA zone, weekdays, same-day hours and holidays. Intervals are bounded to
366 days; ambiguous/nonexistent DST work boundaries fail. No arbitrary formula, DAX,
SQL or code is evaluated. Lineage remains located and unverified; calculations do not
establish that supplied rows match production records.

CAD units default to metres. `drawing concept --source-units millimetres` (also
centimetres, feet or metres) requires a matching DXF unit header. Bounds/output
coordinates stay metres. `cad_wall_layers` configures recognized linework layers.
Evidence retains raw/converted/clipped endpoints and the unit factor. Supported
source inserts retain rotation and scale provenance; generic proxies use assumed
metre dimensions, not extracted block/product geometry. Unsupported geometry,
negative/nonplanar transforms and resource excess fail conservatively. Full BIM,
construction validation, room/door/floor inference and circulation/collision
analysis remain separate product work requiring qualified input/review.

## Synthetic evaluation (offline only)

`evaluations/v1/` contains 24 invented cases, two for each of twelve roles, with
expected structured facts, human rubrics and short benchmark-specific role prompts.
It contains no private knowledge, references, memory, task database or transcript.
REEMA makes no model call, so only the offline run remains: it grades each case's
canonical expected answer. Its score proves the fixtures and the grader, not the
quality of any model or agent. Negative grader tests exercise missing/wrong facts,
invented fields and malformed answers.

```sh
python3 scripts/dev.py python scripts/evaluate_agents.py offline --output teams/documentation/output/qa/evaluation/offline-baseline.json
```

Rubrics still need human review. Evaluating real Claude Code output would be
separate work, with representative inputs and owner-supplied expected answers.

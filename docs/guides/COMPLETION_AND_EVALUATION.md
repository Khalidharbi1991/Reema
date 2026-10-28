# Bilingual coordination recovery and synthetic evaluation

This guide describes package 5. The [finite ledger](../reports/PENDING_LEDGER.md)
maps earlier roadmap items to completed software and exact external requirements.
The application still uses Anthropic. No model, software test or handover record
supplies human document approval.

## Ahmad intent and continuity

`config/assistant_routes.yaml` now contains Arabic and English hints, including
mixed requests, Arabic conjunctions, diacritics and common negation. Explicit
scope contradictions and unresolved references ask for clarification. Contextual
references retain the active objective and selected specialists, except explicit
exclusions. This is bounded language handling, not universal understanding.

Arabic task additions such as `أضف مهمة: مراجعة الإجراء` work offline. Explicit
`هدف:`, `قرار:`, `قيد:`, `معلق:` and `نتيجة:` entries remain session-only.
Supported English/local slash commands are unchanged. Work/personal boundaries,
exact project scope and deliberate persistent-memory commands remain mandatory.

Optional structured intent resolution is disabled by default:

```sh
python3 scripts/dev.py run chat --area work --resolve-intent --allow-external-ai
```

It requires the existing conversation/material consent and API key. The result
can only select registered advice roles; it cannot execute actions, reinstate an
excluded capability or silently discard an explicit match. Deterministically
unsupported commands and clarification requests remain offline.

## Process ownership and recovery

Run and resume operations hold `.owner.lock` using an OS lock. Do not delete it
or infer abandonment solely from its age or PID. Active owners block competing
read/resume operations; process death releases the kernel lock. Cross-host recovery
fails because local liveness is insufficient. POSIX behavior was exercised with
a real killed subprocess; the Windows branch still requires native-host QA.

Version 2 HMAC-authenticated `execution.json` records embed the committed run
snapshot. Atomic replacement, file fsync and directory fsync preserve the last
committed state across an interrupted unsigned `run.json` write. Source,
configuration, code, dependency-lock and request identity checks still apply.
Version 1 failed/cancelled compatibility and ready-only offline exports remain.
Parent ownership stays held throughout model or offline export recovery.

Completed review/compliance excerpts are separately checkpointed after schema and
location validation. Reuse binds agent/model/system, exact prompt, schema and full
execution identity; cached results are revalidated before use. Changed content or
instructions produce a different key. Failed attempts are not successful results.

Reservations are persisted before provider transmission. A killed in-flight
request remains uncertain and conservatively charged to inherited usage. The
child reports this uncertainty and uses a fresh pending human-review record.
No local implementation can guarantee exactly-once provider execution after a
request was transmitted but its response was lost. Budgets remain per branch,
not account-wide spending controls.

## Diagrams templates and Arabic exports

Sequence diagrams retain two to six steps. A `kind: graph` flow supports two to
eight nodes, one to three lanes, at most twelve forward edges and six row indices.
Only decision nodes branch; each requires two labelled outcomes. IDs, reachability,
overlap, forward direction, invisible characters and readable text bounds are
validated. There is no arbitrary SVG/XML/code executor or inferred decision.

`config/document_profile.yaml` selects `standard` or `compact` layout values for
heading spacing, paragraph spacing and table padding. `display_title` localizes
section headings while canonical section IDs and titles remain mandatory.
`document_label` can localize the document kind. Existing English defaults remain.

Arabic paragraphs use logical RTL start alignment and an explicit complex-script
font, size and emphasis in Word. Mixed Latin runs are separated; weak numeric/date
runs receive LTR boundary marks so ISO dates retain their visible order. These
formatting marks do not change the source Markdown. HTML uses per-block direction
and LTR isolates. Word diagrams use
local PNGs. HTML diagrams use generated SVG. WeasyPrint's Arabic SVG text did not
shape correctly on this host, so PDF uses locally shaped Arabic diagram PNGs and
an exact allowlist fetcher; external/local arbitrary resource fetches remain denied.
Arabic PNGs require a local glyph-covering font and Pillow RAQM. Missing support
fails clearly. Other scripts, unusual fonts and complex Markdown require their
own QA; this does not claim universal language or layout support.

PDF checks combine logical extraction with bounded Arabic visual-order presence
checks, including lam-alef clusters and Latin/number runs. They still check exact
headings, supplied table cells and diagram descriptions. These checks do not
replace page inspection or establish general accessibility/pagination fidelity.

Run the synthetic fixture without any model calls:

```sh
python3 scripts/dev.py python scripts/qa_multilingual.py --output output/qa/package5/arabic-reviewed
```

Choose a fresh output directory when repeating the fixture; existing exports are
never overwritten. The local QA evidence records every inspected Word/PDF page and artifact hashes.
HTML receives structural/text/resource checks; it has no claimed browser visual
certification. Never substitute customer documents for these synthetic fixtures.

## Bounded specialist depth

IAM accepts nested supplied groups, explicit privileged roles, an optional older
snapshot and configured `separation_of_duties` role pairs. It rejects cycles and
unknown memberships, propagates inherited roles and checks their approval/MFA
requirements. Drift includes grant/state and role-classification differences.
Membership/grant totals are bounded. No live directory is accessed or changed.

Problem input may include `TEST-...` outcomes with hypothesis IDs, criterion,
timestamp, supporting/refuting/inconclusive outcome and located evidence.
Competing hypotheses remain mandatory. Located support, refutation and conflicts
are reported without confirming a real root cause.

Metric specifications accept located evidence plus differences, weighted means
and working-time means, alongside the original formulas. Business calendars need
an explicit IANA zone, weekdays, same-day hours and holidays. Intervals are bounded
to 366 days; ambiguous/nonexistent DST work boundaries fail. No arbitrary formula,
DAX, SQL or code is evaluated. Lineage remains located and unverified; calculations
do not establish that supplied rows match production records.

CAD units default to metres. `drawing concept --source-units millimetres` (also
centimetres, feet or metres) requires a matching DXF unit header. Bounds/output
coordinates stay metres. `cad_wall_layers` configures recognized linework layers.
Evidence retains raw/converted/clipped endpoints and the unit factor. Supported
source inserts retain rotation and scale provenance; generic proxies use assumed
metre dimensions, not extracted block/product geometry. Unsupported geometry,
negative/nonplanar transforms and resource excess fail conservatively. Full BIM,
construction validation, room/door/floor inference and circulation/collision
analysis remain separate product work requiring qualified input/review.

## Model defaults and overrides

Shipped leader/worker defaults are `claude-sonnet-4-6`. Optional per-role `model`
values take precedence; otherwise `LEADER_MODEL`/`WORKER_MODEL` settings apply.
Explicit existing overrides are preserved, even if the user must replace a retired
model manually. The benchmark and actual agents share this selection rule.
No runtime provider, dependency lock or private `.env` file was migrated.

Anthropic lists Sonnet 4 as retired on 15 June 2026 and Sonnet 4.6 as active in its
[lifecycle documentation](https://platform.claude.com/docs/en/about-claude/model-deprecations).
The [pricing page](https://platform.claude.com/docs/en/about-claude/pricing) lists
Sonnet 4.6 at USD 3 input / 15 output per million base tokens, checked 16 October
2026. Recheck before paid use; availability for a particular account is external.

## Evaluation and exact live material

`evaluations/v1/` contains 24 invented cases, two for each of twelve roles, expected
structured facts, human rubrics, benchmark-specific short role prompts and a
dated public price card. It contains no private knowledge, references, memory,
task database or transcript. The offline provider returns canonical expected
answers. Its score measures harness/transport/grader behavior, not model accuracy,
actual production-agent prompt quality or end-to-end generation quality. Negative
grader tests exercise missing/wrong facts, invented fields and malformed answers.
Separate mocked application tests exercise the real planner, agents and pipeline.

```sh
python3 scripts/dev.py python scripts/evaluate_agents.py offline --output output/qa/package5/evaluation/offline-baseline.json
python3 scripts/dev.py python scripts/evaluate_agents.py proposal --output output/qa/package5/evaluation/live-proposal.json
```

The proposal lists every exact Messages request, model, source file hash and material
digest. It permits 24 sequential requests, no retries, at most 512 output tokens
per request, conservative pre-transmission reservations and a USD 5 modeled limit.
The rate card plans at ten times the documented Sonnet 4.6 base prices; configured
higher rates are retained. This is a conservative estimate, not an invoice cap.
Unknown custom models are explicitly marked as unverified assumptions.

Only after the user authorizes those exact synthetic requests and configures a
usable Anthropic key, run the live command recorded in the package report with
`--authorize-material-sha256`. Environment authorization alone is insufficient.
Changed material/models/bounds invalidate the proposal before client construction.
Adding Agent 10's two cases changed the material, so the digest recorded in the
package 5 report no longer opens the gate; regenerate and review the proposal first.
The endpoint is explicitly Anthropic, and the benchmark bypasses BaseAgent retrieval.
Provider failure saves partial results/usage and stops further requests. A hard
kill of this standalone benchmark is not an exactly-once recovery protocol.

Live structured scores still need human rubric review. Extending the evaluation
to actual full agent prompts/retrieval or customer evidence is a separate material
authorization, with representative inputs and owner-supplied expected answers.

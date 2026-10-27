# Specialist evidence and deterministic checks

Package 4 adds bounded Research, Access, Problem, Data and CAD checks. They remain
Anthropic-backed advisory/document capabilities, supplemented by local validators.
No check grants access, confirms a real root cause, certifies compliance or
approves a building/document. See the [package checkpoint](../reports/AGENT_IMPROVEMENTS_PACKAGE_4.md).

`config/specialist_policy.yaml` configures freshness age limits, input sizes,
privileged-MFA/approval checks and CAD resource limits. It is required when upgrading
a custom configuration directory and participates in model-recovery identity.
Changing policy, supplied inputs, source permissions/content or code rejects
incompatible recovery. Existing CLI defaults and async APIs remain.

## Explicit specialist inputs

Use the optional `--specialist-input` JSON file for supplied environment/incident/
metric records. It must be a regular local file no larger than 2 MB. Unknown fields
are rejected; credential fields at the top level or in strict snapshot objects
are unsupported. Metric rows and free text are not automatically scrubbed for
secrets. Keep private inputs in ignored `references/` or
`output/` and inspect them before external authorization.

```bash
python3 scripts/dev.py run generate "Change Management" -f markdown \
  --specialist-input output/my-specialist-input.json --allow-external-ai
```

IAM input selects Access, incident input selects Problem, and metric specifications
select Data, in addition to configured/explicit specialists. All supplied material
also enters core writing context. The existing run-consent flag authorizes that
transmission; it does not override reference permissions or approve artifacts.
Request/checkpoint records retain these private inputs for recovery.

This minimal example defines a deterministic percentage calculation:

```json
{
  "as_of": "2026-10-16",
  "metric_specs": [{
    "id": "MET-resolution", "name": "Resolved share", "kind": "ratio",
    "unit": "percent", "owner": "Service owner", "source": "Supplied register",
    "cadence": "Weekly", "numerator_field": "resolved", "denominator_field": "total",
    "exclude_field": "excluded", "missing_policy": "error"
  }],
  "metric_rows": [
    {"resolved": 1, "total": 2, "excluded": false},
    {"resolved": 8, "total": 8, "excluded": false}
  ]
}
```

The result is 90 percent from aggregate numerator/denominator, not an average of
row percentages. `SpecialistInputs.model_json_schema()` exposes the full Python
input schema. Local `AccessAgent.check_environment()`, `ProblemAgent.assess_case()`
and `DataAgent.calculate_metrics()` make no model calls.

## Research provenance and freshness

Research requests typed claims with `CLM-...` IDs, text, kind (observation,
recommendation, assumption) and located evidence. Evidence needs a recorded source
ID, file, extraction location, file SHA-256 and exact quote. Invented or mismatched
references fail. Valid supporting excerpts persist privately for downstream checks.

An authorized manifest source may declare optional `published_on: YYYY-MM-DD`.
This is user-supplied metadata, not an independently verified publication date.
Do not substitute file modification time or retrieval time. Undated references
and curated knowledge stay unknown. Research reports an explicit as-of date,
source dates/age and `unsupported`, `unknown_freshness`, `stale_support`,
`future_evidence` or `located_unverified`. Within the configured age limit does not
mean factually correct, authoritative or legally current. Stale/unsupported claims
remain visible review items, not automatic certification or silent deletion.
Legacy narrative is explicitly unstructured/unverified. Empty typed claims are
reported as `no_typed_claims`; completeness of narrative claim extraction is not
proved. Default as-of is the UTC calendar date; explicit input can select a
reproducible assessment date. Recovery keeps the original reported assessment date.

## Access environment checks

`iam_environment` contains `snapshot_id`, timezone-aware `observed_at`, declared
role IDs, identities (`id`, `active`, `privileged`, nullable `mfa_enabled`, roles)
and approval records (`subject_id`, role, approved flag, timezone-aware
`approved_at`, located evidence list). No live IAM connection is made.

Local checks detect undeclared roles, inactive accounts retaining grants,
privileged MFA false/unknown and missing/denied/unsupported approval records.
Duplicate identities/roles, blank role IDs, ambiguous approvals, unknown subjects
or approval timestamps after the snapshot fail. Missing/empty snapshots stay
explicit. Even a consistent supplied snapshot reports production operation as
`not_verified`; approval evidence is `recorded_unverified`, never access granted.
Privilege flags and snapshot content remain supplied assertions. Package 5 adds
bounded nested groups, effective privileged-role checks, supplied baseline drift
and configured separation-of-duties pairs. Live state/control operation remains
external. See [the current guide](COMPLETION_AND_EVALUATION.md).

## Problem observations and hypotheses

`problem_case` supplies a case ID and observations with unique `OBS-...` IDs,
timezone-aware times, descriptions and evidence lists. The timeline is sorted by
actual instants across offsets. Quoted observations remain `located_unverified`;
uncited observations are `user_reported_unverified`.

Structured model research must provide at least two competing `HYP-...` hypotheses,
known observation IDs for/against each and next tests. Unknown, duplicate or
simultaneously supporting/contradicting IDs fail. The model cannot invent new
timeline observations or set a confirmed-root-cause field. Root cause stays
`unconfirmed`, including when observations are missing. These checks validate
relationships, not the causal truth of the supplied evidence. Package 5 also
grades supplied located test support/refutation/conflicts while retaining an
unconfirmed root cause.

## Metric calculations

Specifications carry stable IDs, owner/source/cadence, units, operands, exclusions
and missing-data policy. Supported calculations are percentage ratios, elapsed-time
means (seconds/minutes/hours), nonnegative sums and row counts. No formula strings
or DAX are evaluated. Explicitly supplied specifications cannot be changed by the
model. Calculation checks and complete specifications reach Content and dashboard
design; the leader recomputes typed results before caching or use.

Exclusion flags must be booleans. Missing operands either fail or are counted as
missing and excluded, according to the specification. Numeric inputs must be
finite/nonnegative; booleans are not numbers. Ratios reject numerator greater than
denominator and distinguish zero denominators, absent datasets and no eligible
rows. Durations require timezone-aware timestamps and nonnegative intervals.
Invalid units/operands, overflow and row limits fail. These are calculations on
supplied data, not validated production statistics. Package 5 adds differences,
weighted means, bounded explicit working calendars and located unverified lineage.
Arbitrary formula execution, inferred mappings and production lineage verification
remain outside these checks.

## CAD intake and selected-region validation

DWG intake checks a known version header, regular-file/size constraints and a file
hash; it still extracts no DWG geometry. Concept generation defaults to metre DXF
linework and can explicitly convert matching millimetre/centimetre/feet headers.
It validates bounded files/entity counts, finite coordinates, selected
planar LINE/LWPOLYLINE geometry, polyline curvature/width and bounded self-crossing
checks before furnishing or writing artifacts. Unsupported A-WALL types anywhere
in modelspace require explicit conversion, even outside the selected region.

Actual line endpoints are clipped to the requested region. Duplicates are removed
and reported. Manifest records retain original/selected endpoints, entity handles,
clipping, source hash and finite mesh vertex/face counts. Degenerate, nonplanar or
invalid selected walls fail. Curved/variable-width or overly complex polylines
must be converted/split explicitly. Wall centerlines are bounded; assumed wall
thickness can extend half its width beyond a region boundary.

Suggested furniture footprints must fit, including rotation. Generic source
proxies touching boundaries are omitted with a warning. Proxies retain supported
planar positive-scale transform provenance and apply source rotation, but do not
extract block geometry, room purposes or real product dimensions. Separate-wall
connections, doors/openings, collisions, circulation, floors, structure, code
compliance and BIM accuracy are not validated. Resource bounds fail instead of
silently exporting an incomplete model.

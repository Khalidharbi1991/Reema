# Specialist evidence and deterministic checks

Package 4 added bounded Access, Problem, Data, Research and CAD checks. They are
local validators: they make no model call. Agents 6, 7 and 8 (and Agent 1) no
longer have classes, so these checks run on their own: when a new SOP is prepared,
the checks on a supplied `--specialist-input` file go into the generate request as
data (`specialist_checks`), for the writer to describe as checks on supplied data.
No check grants access, confirms a real root cause, certifies compliance or approves
a building/document. See the [package checkpoint](../reports/AGENT_IMPROVEMENTS_PACKAGE_4.md).

`config/specialist_policy.yaml` configures freshness age limits, input sizes,
privileged-MFA/approval checks and CAD resource limits. It is required when upgrading
a custom configuration directory.

## Explicit specialist inputs

Use the optional `--specialist-input` JSON file for supplied environment/incident/
metric records. It must be a regular local file no larger than 2 MB. Unknown fields
are rejected; credential fields at the top level or in strict snapshot objects are
unsupported. Metric rows and free text are not automatically scrubbed for secrets.
Keep private inputs in ignored `references/` or `output/` and inspect them first: the
file joins the confirm-read token, and a Claude Code session reads it after
Khalid's yes.

```bash
python3 scripts/dev.py run generate "Change Management" -f markdown --specialist-input output/my-specialist-input.json
```

IAM input selects Access, incident input selects Problem, and metric specifications
select Data, in addition to configured/explicit specialists; these add no appendix.
If the file changes after prepare, check and finish refuse. Request and checkpoint
records keep these private inputs.

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

The result is 90 percent from aggregate numerator/denominator, not an average of row
percentages. `SpecialistInputs.model_json_schema()` exposes the full Python input
schema; `specialist_checks()` in `src/utils/specialists.py` runs all three checks.

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


## Problem observations

`problem_case` supplies a case ID and observations with unique `OBS-...` IDs,
timezone-aware times, descriptions and evidence lists. The timeline is sorted by
actual instants across offsets. Quoted observations remain `located_unverified`;
uncited observations are `user_reported_unverified`. Supplied `TEST-...` outcomes
are listed with their evidence checked; grading them per hypothesis needs `HYP-...`
hypotheses, which no job supplies now. Root cause stays
`unconfirmed`, including when observations are missing. These checks validate
relationships, not the causal truth of the supplied evidence.

## Metric calculations

Specifications carry stable IDs, owner/source/cadence, units, operands, exclusions
and missing-data policy. Supported calculations are percentage ratios, elapsed-time
means (seconds/minutes/hours), nonnegative sums and row counts. No formula strings
or DAX are evaluated. The calculation checks and the complete specifications go into
the generate request as data; the writer cannot change them.

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

## Research claims and freshness

`assess_claims()` still checks typed `CLM-...` claims against located evidence and
the optional manifest `published_on: YYYY-MM-DD` date (user-supplied metadata, not an
independently verified publication date), reporting `unsupported`,
`unknown_freshness`, `stale_support`, `future_evidence` or `located_unverified`. No
job produces typed claims now that Agent 1 has no class; the function remains for a
future Claude Code research step. Within the configured age limit does not mean
factually correct, authoritative or legally current.

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

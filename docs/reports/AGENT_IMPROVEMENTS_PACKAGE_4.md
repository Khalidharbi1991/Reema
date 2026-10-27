# Agent improvements package 4

Current completion and remaining requirements are recorded in [package 5](AGENT_IMPROVEMENTS_PACKAGE_5.md) and the [finite ledger](PENDING_LEDGER.md). Remaining-work statements below describe this historical checkpoint.


Completed and verified locally on 16 October 2026. This package establishes the
project-local development workflow, then adds substantive bounded checks for
Research, Access, Problem, Data and Building Design. It builds on
[package 3](AGENT_IMPROVEMENTS_PACKAGE_3.md). The application remains Anthropic-backed.
Existing dirty changes, async/public CLI defaults, memory isolation, source
permissions, budgets, complete handoffs, recovery checks and pending human approval
remain. No live/paid model calls, customer-data transmission, provider migration,
real document approval, commits, pushes or publication were performed.

## Permanent project development setup

`scripts/dev.py` creates ignored `.venv/` from the unchanged
`requirements-dev.lock`, using binary wheels and required SHA-256 hashes. Existing
cached wheels were reused where available; remaining packages were downloaded
through the normal approved network escalation after the sandbox blocked access.
No global Python packages or shell settings were changed. Future pip cache writes
use ignored `.dev-cache/pip/`; a complete wheelhouse supports offline bootstrap.
The launcher rejects a changed lock stamp and symlinked project environments.
Doctor verifies installed versions against applicable lock markers and imports
the actual PDF formatter. Dependency lock/build metadata digests now also take
part in model-recovery identity.

The launcher removes inherited Python import overrides and discovers existing
macOS native libraries from Homebrew/base-Python/common prefixes in the child
process. Linux retains normal library discovery and Windows retains configured
DLL discovery. This host's installed `/opt/homebrew/lib` dependencies were found
automatically. There is no universal hardcoded native path or automatic native
installation. Verified environment: project Python **3.14.2**, locked Anthropic
SDK **0.76.0**, WeasyPrint **70.0**, ezdxf **1.4.4** and pyparsing **3.3.3**.

Normal verified commands require neither temporary dependencies nor hand-entered
library flags:

```bash
python3 scripts/dev.py bootstrap
python3 scripts/dev.py doctor
python3 scripts/dev.py run list-processes
python3 scripts/dev.py test -q -rs
python3 scripts/dev.py smoke --output output/qa/a-new-smoke-directory
```

Use `python` on Windows if `python3` is unavailable. `python` forwards other
project Python invocations; `bootstrap --wheelhouse PATH` installs offline with
hash checks. See [development setup](../guides/DEVELOPMENT_SETUP.md).

## Research

Research requests typed claims with stable IDs, explicit kinds and located source
evidence. Source ID, file, extraction location, SHA-256 and exact quote must match
authorized recorded excerpts. Supporting excerpts persist privately for subsequent
checks. Optional manifest `published_on` is owner-supplied metadata, never inferred
from file timestamps or invented by a model. Claims report source age against an
explicit as-of date and configured limit, distinguishing unsupported, unknown,
stale, future-dated and located-unverified support. Empty typed claims and legacy
narrative remain explicit gaps. Evidence/date reports reach Content intact.

These checks establish provenance and declared age, not source authority, factual
truth, complete extraction of every narrative claim or current legal applicability.
Recovery retains the original reported as-of date instead of implying that an old
assessment was freshly researched.

## Access

Access accepts structured supplied IAM snapshots with role/identity/grant flags,
observation time and approval records/evidence. Local checks identify undeclared
roles, inactive-account grants, privileged MFA false/unknown and missing, denied or
unsupported approval records. Duplicate/blank identities/roles, ambiguous or
unknown-subject approvals and approval times after the snapshot fail. Missing or
empty environments remain explicit. Results reach the real SOP pipeline and
survive recovery. Local `check_environment()` needs no model call.

Even a consistent snapshot reports production operation as `not_verified` and
access grant as false. Identity privilege flags and approval records remain
supplied assertions; located approval text is recorded-unverified evidence.
No IAM connection, access change or human approval is made.

## Problem

Problem accepts supplied observations with stable IDs, timezone-aware timestamps,
descriptions and evidence. It orders the timeline by actual instants and separates
located-unverified observations from uncited user reports. Structured analysis
requires at least two competing hypotheses, known evidence IDs for/against each
and next tests. Unknown, duplicate, simultaneously supporting/contradicting IDs
and unsupported confirmed-root-cause fields fail. Models cannot invent timeline
events through this schema. Root cause remains `unconfirmed`, including when
observations are absent. Local `assess_case()` checks references without a model.
Relationships and chronology do not establish causal truth.

## Data

Metric specifications define stable IDs, owner/source/cadence, calculation kind,
units, operands, exclusions and missing-data policy. Deterministic calculations
support aggregate percentage ratios, elapsed-time means, nonnegative sums and
eligible-row counts. They explicitly distinguish no data, missing/excluded rows,
no eligible rows and zero denominators; reject invalid units/operands, booleans as
numbers, negative/nonfinite values, impossible ratios, backwards/naive timestamps,
overflow and configured size limits. Explicit specifications cannot be changed
by the model. No arbitrary formulas or DAX execute.

The leader recomputes typed checks before caching and downstream use, rejecting
incomplete, invented and type-substituted results. Complete specs/checks enter
Content and dashboard design without zip truncation. Metric input validity and
size checks run before parallel model work. Local `calculate_metrics()` is offline.
Calculations establish results for supplied rows, not production-data quality or
the truth of accompanying prose.

## Building Design

DWG intake now recognizes a supported version whitelist, checks regular-file/size
bounds and records a file hash. It still extracts no DWG geometry. DXF concept
generation validates metre units, finite/planar supported wall geometry, resource
limits, width/bulge handling, degenerate segments and bounded polyline topology
before furnishing or writing artifacts. Unsupported A-WALL types require explicit
conversion. Selected endpoints are actually clipped to the region; duplicates
are removed and reported.

Manifest evidence retains source hash, entity handles/type, original/selected
endpoints and clipping diagnostics. Mesh checks cover finite vertices and generated
vertex/face bounds. Suggested furniture footprints must fit, including rotation;
boundary-crossing generic source proxies are omitted with warnings. Source changes
during interpretation fail. Geometry errors leave no new concept artifacts.
These remain assumption-labelled one-region concept meshes, not full building,
structural, BIM, safety or construction validation.

## Pipeline and privacy integration

`SpecialistInputs` joins the request/recovery contract. Optional
`--specialist-input FILE` reads a regular JSON file up to 2 MB; matching specialist
roles are selected automatically. Inputs remain private and enter authorized core
writing context as well as their specialists. Source metadata/permission rules
remain; a supplied snapshot does not authorize unlisted reference material.
Source/context size limits fail visibly without trimming. Successful generation
still ends at `awaiting_human_approval` with a fresh pending record.

Primary new files are `scripts/dev.py`, `config/specialist_policy.yaml`,
`src/utils/specialists.py`, `src/utils/cad_validation.py` and
`tests/test_specialist_package.py`. Integration updates the five agent modules,
CAD builder, retrieval/manifest models, configuration, capabilities, request and
recovery identity, leader and CLI. `.gitignore`, README/AGENTS/context, architecture,
guides and evaluation baselines document the supported workflow. Lock files and
dependency declarations were not changed. See
[specialist inputs and limits](../guides/SPECIALIST_EVIDENCE_AND_CHECKS.md).

## Actual verification

Added **78 synthetic regression cases** covering setup discovery/isolation,
quoted claims/date states and permissions, supplied IAM flags/approval gaps,
timeline order/competing hypotheses, valid and invalid metric calculations,
preflight and cached-result checks, CAD geometry/units/resource/footprint failures,
CLI secret-shaped schema rejection, automatic role selection and actual-agent
pipeline recovery preserving every structured result without repeated calls.
Existing pipeline fixtures received a real serializable policy snapshot.

Final full command: `python3 scripts/dev.py test -q -rs`.

Result: **446 passed, 0 skipped**. The test process used `.venv` with no temporary
`PYTHONPATH` or caller-supplied native path. Doctor, dependency consistency, CLI
catalog launch and actual four-format smoke exports passed. `git diff --check`
passed. Tests deny live HTTP and use synthetic completions; this is software and
calculation validation, not live model-quality evaluation.

Smoke artifacts and QA evidence are local and ignored:

```text
output/qa/package4-smoke/pdf/Service_Restoration_SOP.pdf
output/qa/package4-smoke/docx/Service_Restoration_SOP.docx
output/qa/package4-smoke/html/Service_Restoration_SOP.html
output/qa/package4-smoke/markdown/Service_Restoration_SOP.md
output/qa/package4-smoke/visual-qa.json
```

Both PDF pages and both DOCX-render pages were visually inspected after the
environment change. Bundled Poppler rasterized the PDF; the document skill's
bundled LibreOffice renderer produced DOCX PNGs. The inspected fixture retained
all eleven sections, readable text, tables/empty RACI cells and footers, without
visible clipping, overlap or missing glyphs. The QA JSON binds artifact hashes
and inspected PNG paths. This inspection concerns the two-page smoke fixture;
it is not a new visual certification of historical customer artifacts or every
possible template. No artifact was approved as a human reviewer.

## Remaining limits and external requirements

The current host needs no further dependency or native-library change for offline
work. Fresh environments need Python, network or a complete wheelhouse, and their
platform's native PDF packages. Only this macOS/Python combination was verified.
Live model use still needs an Anthropic key and explicit material authorization.

Published dates, IAM snapshots and observations remain supplied evidence, not
independently verified authority/live state. Group inheritance, live drift,
organization-specific separation of duties, stronger causal evaluation, production
data lineage, broader formulas/business calendars and richer CAD geometry remain
later work. CAD does not validate separate-wall connections, room assignments,
doors, collisions, circulation, floor alignment or proxy block transforms. Very
complex/unsupported linework fails conservatively, even when outside the selected
region. Assumed wall thickness may extend beyond bounded centerlines.

Broader Ahmad language understanding, hard-crash/review-chunk recovery, authorized
live quality evaluations, advanced diagrams, Arabic/RTL layout and richer templates
remain later roadmap items. Model recovery checks declared dependency locks, not
an immutable native-library image or protection against a privileged local writer.
No provider migration, external deployment or document approval is implied.

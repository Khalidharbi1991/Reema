# Evidence, sections, corrections and exports

REEMA's SOP jobs carry typed quality records through generate, review, revise and
export. A Claude Code session writes the text; REEMA's code checks it. These records
support traceability and human review; they do not certify compliance or approve
documents. See [package 3](../reports/AGENT_IMPROVEMENTS_PACKAGE_3.md) for the
original verification.

## Configured sections

`config/document_profile.yaml` is required alongside the existing configuration. Its
eleven section IDs and title associations are stable identifiers. Keep them when
customizing order, instructions, the control-reference gate or export style.
Missing/swapped/duplicate IDs fail early. Process-specific objectives and constraints
come from the process configuration and the `generate` options.

For a new SOP, `generate_request.json` lists each section with its instructions and
optional `target_pages`, and `reema-writer` writes one Markdown file per section
(`sections/NN-<section id>.md`), definitions and roles/RACI first so later sections
reuse their terms. `FileSectionWriter` feeds the files, in profile order, through
Agent 3's unchanged per-section loop: a file for the wrong section, an empty body, a
`#`/`##` heading or a broken diagram fails and names the section. Local assembly
then builds a `SectionDraft` with the configured headings and preserves the bodies.
Bodies allow level-three subheadings, tables, lists, citations and supported
diagrams; diagram schemas go only to Detailed Procedures and Process Flow Diagrams.
The shipped ranges total 17–30 pages within the 15–30 page target.

Agent 10's patch appendix, when the `euc` specialist is selected, is one more file:
it must be a valid section body with every heading of `EUCAgent.APPENDIX_SECTIONS`.
Extension sections receive stable IDs/locations; ambiguous duplicate headings fail.

## Evidence-linked controls

A new SOP gets an unassessed control register: one `CTRL-UNASSESSED-n` entry per
configured standard, applicability `undetermined`, targeting the Compliance &
Standards section. Coverage therefore reports warnings ("applicability requires
human determination", "missing supporting source evidence"), not errors. No model
determines applicability. The register model still supports `CTRL-...` controls with
framework, clause, requirement, applicability, rationale, target sections and
located evidence (source ID, filename, location, file SHA-256, exact quote), for
older runs.

Evidence must match an excerpt the writer was given; a source ID alone is
insufficient, and the checks refuse an unknown `[SRC-…]`. Everything remains
`unverified`: matching quotes do not establish current standards, applicability,
interpretation or organizational compliance. `quality.control_coverage` records
referenced/missing target sections, applicability and evidence status; semantic
coverage remains `requires_human_verification`.

## Located review and correction

A review (`reema-review` skill) uses `located_v1`. `reema-reviewer` writes one
assessment per excerpt, and a fresh `reema-consistency-reviewer` the cross-section
pass. Findings need severity, description, section ID, exact quote and an actionable
correction. Code resolves unique quotes to absolute zero-based offsets; repeated
quotes require exact start/end offsets. False, ambiguous and out-of-excerpt locations
fail. Code assigns stable `F-...` IDs. Critical/major findings are blocking.

A revision (`reema-revise` skill) works from an instruction or 1–5 findings.
`reema-reviser` writes a `SectionPatch` bound to the current document/section SHA-256
values. It replaces exactly those bodies: preamble, headings, order and every
unaffected byte survive, and no new source or control ID may appear. A fresh
`reema-rechecker` then rechecks every finding exactly once, with resolved/open,
rationale and a supporting quote in the revised section, bound to the revised
document's SHA-256. Open blocking findings stop the job. The approval record's score
is the share of findings the recheck marked resolved. Rechecks remain the session's
judgments.

## Bounded diagrams

The safe illustration is a sequence of two to six steps:

````text
```reema-flow
{"title":"Record and review","steps":[{"id":"record","label":"Record the decision","owner":"Service desk"},{"id":"review","label":"Review retained evidence","owner":"Service owner"}]}
```
````

IDs are unique; labels/owners are bounded printable text with invisible/control
characters rejected. Bounded forward graphs, explicit two-way decisions and one to
three swimlanes are also supported. HTML uses generated SVG; Word uses local PNGs,
and PDF uses shaped local PNGs for Arabic diagrams. Readable text and alternative
descriptions are retained. Arbitrary resource/XML/SVG/code execution and Mermaid
execution remain outside this path. See [the current guide](COMPLETION_AND_EVALUATION.md)
for Arabic fonts, templates and exact graph limits.

## Exports

PDF/HTML/DOCX share configured font, body size/spacing, Letter geometry, heading
scale and neutral table styling. Content-weighted columns give narrative text room.
Long tables repeat headers; small tables and ordinary DOCX rows stay together.
Exceptionally large rows can split. Source soft wraps remain one paragraph and
captions use neutral styling. Formatting rules are deterministic; file bytes and
pagination can differ across engines/fonts.

Format checks readable output, source headings/table cells, diagram
counts/descriptions, DOCX repeating headers and PDF page/text bounds. Results appear
in `last_export_checks` and `exported.json`. Failures block the pending approval
record. Automated checks explicitly say visual inspection was not performed: real
deliverables still need inspection for overlap, font substitution and layout.

```bash
python3 scripts/dev.py python -m scripts.verify_document_package --output output/qa/new-example
```

Use a fresh ignored directory. DOCX visual QA uses the document skill's bundled
LibreOffice renderer. Other hosts need their own native dependency setup.

`reema export RUN` re-exports an unchanged ready checkpoint offline. A Claude Code
draft passes every local check again; a changed document profile refuses the export;
older ready checkpoints keep their saved review gate and legacy quality checks.
Success ends at `awaiting_human_approval` with a fresh pending record.

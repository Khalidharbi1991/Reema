# Evidence, sections, corrections and exports

REEMA's SOP pipeline carries typed quality records through Standards, Content,
Review and Format. The runtime remains Anthropic. These records support
traceability and human review; they do not certify compliance or approve documents.
See [package 3](../reports/AGENT_IMPROVEMENTS_PACKAGE_3.md) for verification.

## Configured sections

`config/document_profile.yaml` is required alongside the existing configuration.
Its eleven section IDs and title associations are stable identifiers. Keep them
when customizing order, instructions, review-cycle limits, the control-reference
gate or export style. Missing/swapped/duplicate IDs fail early. Process-specific
objectives and constraints retain their existing configuration and CLI options.

Content requests a `SectionDraft` containing every configured `section_id` and
Markdown `body` exactly once. Local assembly uses configured order/headings and
preserves bodies. Bodies allow level-three subheadings, tables, lists, citations
and supported diagrams, but cannot introduce top-level sections. Missing/blank
sections and malformed JSON fail. The public API still returns Markdown. Legacy
narrative remains supported, subject to mandatory-section and unambiguous section
checks in the pipeline.

Complete research, standards, request context and specialist appendices remain.
Extension sections receive stable IDs/locations; ambiguous duplicate headings
fail. This is one structured generation request with local assembly, not
independent per-section generation or automatic context summarization.

## Evidence-linked controls

Standards returns a narrative and `control_register`. Every configured framework
must appear. Controls contain unique `CTRL-...` IDs, framework, clause or explicitly
unknown clause, requirement, applicability (`applicable`, `not_applicable`,
`undetermined`), rationale and target section IDs. Evidence entries contain source
ID, filename, extraction location, file SHA-256 and an exact quote. Missing
evidence is an empty list.

Evidence must match an authorized source recorded by the run and its actual
located excerpt. A source ID alone is insufficient. Cited excerpts are retained
in private checkpoints for checks/recovery and need the source files' local
protections. Existing source permissions and retrieval limits still apply.
All evidence remains `unverified`: matching quotes do not establish current
standards, applicability, interpretation or organizational compliance. Legacy
prose receives explicit undetermined entries instead of certification.

`quality.control_coverage` records referenced/missing target sections,
applicability and evidence status. Content references controls as `[CTRL-EXAMPLE]`.
By default an applicable control must appear in every target section. A reference
elsewhere or only in a fenced example cannot satisfy the gate. Missing evidence
and undetermined applicability require human review. Semantic coverage remains
`requires_human_verification`, even if the reference gate is disabled.

## Located review and correction

The real Review agent uses `located_v1`. Findings need severity, description,
section ID, exact quote and an actionable correction. Code resolves unique quotes
to absolute zero-based offsets; repeated quotes require exact start/end offsets.
False, ambiguous and out-of-excerpt locations fail. Code assigns stable `F-...`
IDs. Critical/major findings block even with a high score. Revision requests
without actionable findings fail.

The configured loop defaults to two cycles. Content receives affected bodies and
findings, returning a `SectionPatch` bound to current document/section SHA-256
values. It replaces exactly those bodies. Preamble, headings, order and every
unaffected byte survive; the leader checks custom registered workers again.
Review then rechecks every original finding exactly once, with resolved/open,
rationale and a supporting quote in the same revised section. Open blocking
findings stop the run. A full review of the revised document follows before
normal source/control/export gates.

`document_reviews` and `revision_history` persist in `run.json`, including failed
rechecks. Completed `reviewed` and `ready` checkpoints retain correction history.
Rechecks remain model judgments, subject to consent/budgets. Legacy registered
reviewers retain the bounded full-document refinement adapter, without the
located preservation guarantee.

## Bounded diagrams

The safe illustration is a sequence of two to six steps:

````text
```reema-flow
{"title":"Record and review","steps":[{"id":"record","label":"Record the decision","owner":"Service desk"},{"id":"review","label":"Review retained evidence","owner":"Service owner"}]}
```
````

IDs are unique; labels/owners are bounded printable text with invisible/control
characters rejected. Package 5 also supports bounded forward graphs, explicit
two-way decisions and one to three swimlanes. HTML uses generated SVG; Word uses
local PNGs, and PDF uses shaped local PNGs for Arabic diagrams. Readable text and
alternative descriptions are retained. Arbitrary resource/XML/SVG/code execution,
Mermaid execution and the legacy draw.io generator remain outside this path.
See [the current guide](COMPLETION_AND_EVALUATION.md) for Arabic fonts, templates,
exact graph limits and visual evidence.

## Exports and recovery

PDF/HTML/DOCX share configured font, body size/spacing, Letter geometry, heading
scale and neutral table styling. Content-weighted columns give narrative text
room. Long tables repeat headers; small tables and ordinary DOCX rows stay
together. Exceptionally large rows can split. Source soft wraps remain one
paragraph and captions use neutral styling. Formatting rules are deterministic;
file bytes and pagination can differ across engines/fonts.

Format checks readable output, source headings/table cells, diagram
counts/descriptions, DOCX repeating headers and PDF page/text bounds. Results
appear in `last_export_checks` and `exported.json`. Failures block the pending
approval record. Automated checks explicitly say visual inspection was not
performed: real deliverables still need inspection for overlap, font substitution
and layout. The package's examples were separately rendered and inspected.

```bash
python -m scripts.verify_document_package --output output/qa/new-example
```

Use a fresh ignored directory. On the verified macOS framework Python, prefix PDF
commands with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`. DOCX visual QA uses
the document skill's bundled LibreOffice renderer. Other hosts need their own
native dependency setup.

The profile participates in model-recovery identity. Changed profile/code/source
material rejects reuse before new calls. Package 5 checkpoints validated individual
review/compliance chunks; incomplete patch/recheck phases still rerun. Provider
attempts with lost responses remain uncertain, rather than exactly once. New ready
checkpoints preserve profile/controls and offline recovery rechecks coverage.
Older ready checkpoints retain legacy quality checks. Success still ends at
`awaiting_human_approval` with a fresh pending record.

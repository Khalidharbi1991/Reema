# Agent improvements package 3

Current completion and remaining requirements are recorded in [package 5](AGENT_IMPROVEMENTS_PACKAGE_5.md) and the [finite ledger](PENDING_LEDGER.md). Remaining-work statements below describe this historical checkpoint.


This is the package 3 checkpoint. [Package 4](AGENT_IMPROVEMENTS_PACKAGE_4.md)
adds project-local setup and the next bounded specialist checks.

Implemented and verified locally on 15 October 2026. This package improves the
Standards, Content, Review and Format agents through the real asynchronous SOP
pipeline. It builds on [package 2](AGENT_IMPROVEMENTS_PACKAGE_2.md). Anthropic,
explicit consent, memory isolation, source permissions, budgets, recovery identity
checks and separate human approval remain. Unrelated dirty changes were preserved.
No live/paid model calls, provider migration, customer-data transmission, document
approval, installation, global shell changes, publication or commits were performed.

## What each agent gained

**Standards:** A strict control register accounts for every configured framework.
Each proposed control carries a stable ID, requirement, applicability/rationale,
target section IDs and located supporting evidence. Source ID, file, extraction
location, SHA-256 and exact quoted text must match recorded authorized material.
Missing evidence is explicit; legacy prose becomes undetermined entries. Cited
excerpts persist privately for subsequent checks. Finished-document coverage
checks every applicable control's required section references, rejecting misplaced
or fenced-example-only references. Results distinguish missing evidence from
located unverified evidence. Quotes/references do not establish compliance.

**Content:** `config/document_profile.yaml` defines stable section identities,
order, instructions and export style. A validated section draft assembles all
eleven sections locally without losing complete supplied research/specialist
material. Targeted revisions are document/section-digest-bound patches replacing
exactly the requested bodies. Preamble, headings, order and unaffected bytes must
survive, including full specialist appendices. Invalid, stale, empty and overbroad
patches fail. A bounded sequence-diagram contract validates two to six steps and
renders locally to inline SVG for HTML/PDF and PNG with alternative text for DOCX.
Markdown keeps the editable JSON representation.

**Review:** Findings carry stable IDs, section locations, exact quotes and actions.
Unique quotes resolve to offsets locally; repeated quotes need exact offsets.
False/ambiguous/out-of-excerpt locations fail. Critical/major findings block at any
score. The bounded loop patches affected sections, explicitly rechecks every
original finding with a supporting quote, and reviews the complete document again.
Open blocking corrections stop delivery. Review attempts/correction history persist
even when a recheck fails. Malformed/incomplete review cannot silently pass. Model
judgments remain separate from human approval.

**Format:** Shared print/screen rules align font, typography, Letter geometry,
neutral tables and content-weighted columns across PDF/HTML/DOCX. Small tables stay
together; long tables repeat headers; ordinary Word rows avoid splitting. Soft
source wraps remain paragraphs and diagram captions retain neutral styling.
Actual-file checks cover readable text, source headings/table cells, diagram
counts/descriptions, repeating Word headers and PDF text/page bounds. Checks are
saved in `exported.json` and prevent pending approval on failure. Their metadata
honestly distinguishes automated checks from separately performed visual review.

## Integration and compatibility

New modules are `src/utils/documents.py`, `diagrams.py`, `export_quality.py` and
`src/formatters/theme.py`; the new profile is `config/document_profile.yaml`.
Integration updates the four agent modules plus `leader_agent.py`, capability,
handoff, quality, validation, configuration and recovery identity modules, and the
Markdown/HTML/PDF/DOCX renderers. Public async string/dictionary APIs and CLI
commands remain. The profile is now a required configuration file; copy it when
upgrading an existing custom configuration directory.

Legacy narrative generation and registered legacy review workers remain supported.
Legacy review retains bounded full-document refinement; it does not gain targeted
byte-preservation guarantees. Malformed structured responses do not fall back to
prose. Duplicate section identities fail instead of choosing an arbitrary location.
The default two-cycle limit is configurable from one to three.

The profile joins model-recovery identity. New ready checkpoints preserve control
register/profile/correction history and offline export rechecks their coverage.
Older ready checkpoints retain legacy quality checks. Incomplete reviews,
patches/rechecks and compliance phases rerun under the existing bounded recovery
contract. Successful generation still ends at `awaiting_human_approval` with a
fresh pending record. No reviewer identity or document approval was supplied.

## Offline verification

Added **48 synthetic regression cases** in `tests/test_document_package.py`.
They exercise real agent methods with mocked completions, including configuration
identity, framework/evidence validation, misplaced controls, section assembly,
long appendix preservation, stale/overbroad patches, false/ambiguous locations,
high-score blocking findings, dropped/relocated rechecks, unsupported diagrams,
all-format rendering, real output loss, readable table widths, end-to-end targeted
correction, open recheck failure, unaffected-section mutation, final coverage gates,
pending approval and offline/model recovery. Existing fixtures were updated for
the stricter real review schema and serializable profile identity.

Final full command:

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  PYTHONPATH=/private/tmp/reema-agent-test-deps python3 -m pytest -q -rs
```

Result: **368 passed, 0 skipped**. `git diff --check` passed. Tests deny live HTTP.
These results establish software behavior and preservation, not model reasoning,
writing quality, current regulatory interpretation or real control operation.
The existing temporary locked CAD dependencies remain unchanged; no dependencies
were installed or declared differently for this package.

## Synthetic export and visual QA evidence

`scripts/verify_document_package.py` creates a representative local fixture with
all eleven sections, RACI/KPI tables, a six-step diagram, a 34-row evidence table
and a pending-approval statement. Final outputs are ignored local artifacts:

```text
output/qa/package3-final/Service_Restoration_Example.pdf
output/qa/package3-final/Service_Restoration_Example.docx
output/qa/package3-final/Service_Restoration_Example.html
output/qa/package3-final/Service_Restoration_Example.md
output/qa/package3-final/checks-pdf-html-markdown.json
output/qa/package3-final/checks-docx.json
output/qa/package3-final/visual-qa.json
```

All **six PDF pages** and **five rendered DOCX pages** were visually inspected.
The PDF was rasterized with bundled Poppler. DOCX used the document skill's
`render_docx.py` and bundled LibreOffice, with PNGs at
`output/qa/package3-final/docx-render/page-1.png` through `page-5.png`.
PDF PNGs are `output/qa/package3-final/pdf-page-1.png` through `pdf-page-6.png`.
Automated checks verified twelve headings, 129 supplied table cells, three tables
and one diagram; PDF bounds passed.

The first render exposed cramped narrative columns, split Word rows, blue caption
inheritance and artificial paragraph breaks. Shared content-weighted widths,
ordinary-row keep rules, neutral captions and soft-wrap handling corrected these.
Final inspection found readable labels/arrows, preserved empty RACI cells, complete
table tails, repeated long-table headers, whole small tables, consistent hierarchy,
legible footers and no visible clipping/overlap or missing glyphs in these examples.
Pagination differs between engines; identical page counts were not required.

Artifact authoring used the existing application WeasyPrint runtime for PDF and
bundled Python/python-docx/Pillow for DOCX. The bundled Python lacked REEMA's YAML
and settings helpers, so a process-local import fallback used existing application
dependencies after bundled packages; document libraries remained bundled. The
native PDF library path was set per command. Fontconfig reported unwritable cache
directories but rendering completed successfully. No global environment change
or installation was needed. The examples are fixtures, not production-approved SOPs.

## Remaining limits

Control applicability/rationale and correction judgments are model proposals.
Exact source quotes and control markers establish traceability, not semantic
coverage, legal correctness, source freshness or certification. Missing evidence
and undetermined applicability remain visible human-review items. Applicability
reference blocking is configuration-controlled and defaults on.

Section generation is one model request, not independent section scheduling.
Targeted edits preserve unaffected bytes but cannot prove affected content kept
every semantic requirement. Rechecks must be judged by an authorized human.
Diagrams support printable-ASCII sequences only; branches, swimlanes, multilingual
diagram fonts, arbitrary XML/SVG and the legacy standalone draw.io generator need
separate work. Markdown viewers need a renderer to display the JSON diagram.

Export checks are practical structural/text checks, not an automatic visual-quality
certification or complete accessibility audit. Giant table cells, deeply nested
Markdown, complex templates, RTL scripts and unusual fonts need additional QA.
Exceptionally large DOCX rows may split. Shared rules do not guarantee byte-identical
files or identical pagination. These inspected examples do not replace review of
each real export.

Broader Ahmad language understanding, hard-crash/chunk recovery, persistent launch
setup, authorized live quality evaluation and deeper Research/Access/Problem/Data/
CAD capabilities remain later roadmap work. Provider migration remains a separate
explicit request.

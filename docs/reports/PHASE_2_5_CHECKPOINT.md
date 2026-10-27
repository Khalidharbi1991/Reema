# Remaining improvement phases — implementation checkpoint

Date: 2026-09-29. Continues the approved plan after
[Phase 0–1](PHASE_0_1_CHECKPOINT.md). Application runtime: Anthropic, unchanged.

## Implemented

- Async provider adapter with per-attempt timeouts, bounded transient retries,
  concurrency control, conservative token reservations, and optional cost estimates.
- Atomic phase checkpoints, per-run usage metadata, and checksum-verified offline
  export recovery into a fresh run with a new pending human-review record.
- Explicit reference permissions and classifications, file hashes, body-text
  retrieval, page/block provenance, stable source IDs, and separated evidence prompts.
- Structured review across the entire document, cross-excerpt consistency review,
  strict compliance results, RACI validation, citation checks, and optional enforcement
  of the actual rendered PDF page count. Standards-name checks remain warnings.
- Safer HTML/PDF resource handling and improved Word tables, inline formatting,
  repeated table headers, document styles, and pagination.
- Hash-checked runtime/development dependency locks; removal of the third-party
  asyncio shadow package; packaged YAML/knowledge/template assets; offline smoke
  checks and a multi-platform CI workflow.

## Verification completed locally

| Check | Result |
| --- | --- |
| Clean, locked Python 3.14.2 environment on macOS | 187 tests passed; none skipped |
| Source coverage | 88.34%; required threshold remains 70% |
| Dependency lock consistency | `uv lock --check --offline` passed |
| Wheel build and installed CLI outside the checkout | Passed; packaged configuration and knowledge found |
| Linux/Python 3.11 Docker build | Passed; hash-checked runtime dependencies installed |
| Container status and isolation smoke | Passed with network disabled; UID 10001; no customer references, .env, or .git |
| Synthetic Markdown/HTML/DOCX/PDF exports | Passed locally and inside the offline container |
| Visual inspection | All three Word-rendered pages and four PDF pages inspected after fixes |
| Whitespace validation | `git diff --check` passed |

Tests use synthetic inputs and fake providers; outbound HTTP model calls are
blocked in the test suite. Word/PDF verification followed the document skills'
render-and-inspect workflow, which exposed and led to fixes for table geometry
and an inherited title underline. Private QA outputs remain under
`output/verification-20260929-v2/`; these are test fixtures, not approved SOPs.

## Explicit limits and release requirements

1. No live model generation, paid calls, customer uploads, document approval,
   deployment, Git commit, or push was performed. A live acceptance run requires
   an authorized input set, working API key, confirmed model access, and budget.
2. Hosted CI jobs have been defined, not executed. Windows/macOS matrix jobs and
   Linux Python versions beyond the local container smoke still need CI evidence.
3. Standards references and model assessments are not certification. Check current
   control mappings, factual claims, and citation support with a qualified reviewer.
   No independent regulatory-content validation was performed in this code change.
4. Default page targets warn. Enable `ENFORCE_PAGE_TARGET=true` with PDF output
   when the 15–30 page requirement is mandatory. Short synthetic smoke fixtures
   deliberately do not demonstrate production-length SOP quality.
5. Recovery resumes export from `ready.json`, not interrupted research or drafting.
   Review/schema failures stop rather than silently passing or automatically repairing.
6. Permissions and hashes are local safeguards, not enterprise authentication,
   immutable audit storage, encryption, or prompt-injection immunity. Choose access,
   retention, and release controls before multi-user operation.
7. Scanned/empty PDF pages require a separate OCR workflow. Retrieval is lexical,
   not a semantic/vector index. No claim-by-claim factual entailment check exists.
8. Cost estimates require user-maintained rates and are not billing guarantees.
   Dependency hashes do not pin the Docker base/OS packages or isolated build tools.
9. Existing licensing is inconsistent: package metadata says MIT while the README
   says internal use only. Confirm the intended license before external distribution;
   no licensing choice was made on the owner's behalf. The wheel build also warns
   that the existing license-table syntax is deprecated.

The local recovery snapshot before these changes is
`.local-baseline/pre-remaining-phases-source.tar.gz`. Existing unrelated edits,
source knowledge names/encoding, and private files were preserved. For operation,
use [Reliability and sources](../guides/RELIABILITY_AND_SOURCES.md) and
[Data handling](../guides/DATA_HANDLING.md).

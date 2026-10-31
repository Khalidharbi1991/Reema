# Reliability, sources, and offline export

REEMA makes no model call and opens no network connection; a Claude Code session
writes the text, and REEMA's code checks everything it writes. Use
[Development setup](DEVELOPMENT_SETUP.md) for the supported project-local launch/test
path. [Specialist checks](SPECIALIST_EVIDENCE_AND_CHECKS.md) covers publication
metadata, claim freshness and supplied environment/data checks.

## Authorize reference files

Files are not authorized just because they exist in `references/`. Copy the
structure from `config/reference_manifest.example.yaml` into the local, ignored
`references/manifest.yaml`. Each source entry needs:

- `path`: a relative file path inside `REFERENCES_DIR` (no traversal or escaping symlinks).
- `classification`: `public`, `internal`, `confidential`, or `restricted`.
- `external_ai_allowed`: explicit boolean permission for the file to be read into a
  Claude Code session; default false. (The name predates the move to Claude Code.)
- `sha256`: the reviewed file's actual 64-character SHA-256 digest.

Restricted files are never read, even if marked allowed. Other classifications still
require permission. Changed bytes fail validation; review the changes before updating
the digest. On macOS/Linux use `shasum -a 256 references/itom/ITOM.pdf`; on Windows
use PowerShell's `Get-FileHash references/itom/ITOM.pdf -Algorithm SHA256` (store
lowercase). No manifest means no customer sources.

Manifest permission is necessary but not enough: before a generate request includes
excerpts, `prepare` prints a `--confirm-read` token for exactly those files, and Ahmad
passes it only after Khalid's yes (see [Data handling](DATA_HANDLING.md)). A finished
SOP under `references/` needs the same manifest check before review or revision.

PDF, DOCX, Markdown, and plain-text sources are supported. Search uses bounded
lexical ranking across extracted body content (`KNOWLEDGE_CONTEXT_CHARS`), preserving
PDF page or DOCX block locations and stable `[SRC-…]` IDs. DOCX tables and repeated
headings are retained. Files over 25 MB, extraction over two million characters, and
unreadable/empty PDF pages fail rather than silently providing partial evidence. OCR
and vector search are not implemented. Treat source files as trusted local files for
parser security; this is not an isolated sandbox for hostile document formats.

Only the matching excerpts go into the request, as untrusted evidence data next to
`EVIDENCE_POLICY`, which rejects instructions inside source material. This is defense
in depth, not a guarantee against prompt injection. A draft may cite only the
`[SRC-…]` IDs it was given; the checks refuse any other. Source IDs prove which
excerpts were available, not whether every factual claim follows from them. A human
must check claim-to-source accuracy and applicable standards.

## Local settings

All settings are optional and listed in `.env.example`. Unknown `.env` entries, such
as a key or model setting left from an earlier version, are ignored and never used.

| Setting | Default | Meaning |
| --- | --- | --- |
| `REVIEW_CHUNK_CHARS` | 24000 | Exact, non-truncated review excerpts |
| `KNOWLEDGE_CONTEXT_CHARS` | 12000 | Reference excerpt allowance for a generate request |
| `ENFORCE_PAGE_TARGET` | false | Require PDF and the configured page range when true |
| `PAGE_TARGET` | [15,30] | Actual PDF page target, including cover |

## Checks and offline export

Every check runs locally, on the text the session wrote:

- Review: every excerpt of the SOP gets an assessment, a fresh subagent checks
  consistency across excerpts, and every quote must be found in its section.
- Generate: each section goes through Agent 3's per-section checks, then the whole
  draft needs the eleven sections, a usable RACI table, the configured standards
  named (a warning if not), only known source IDs, valid diagrams and control
  coverage. Page targets warn by default. Nothing here certifies compliance.
- Revise: only the target sections may change, no new source or control IDs may
  appear, and a separate recheck must resolve every blocking finding.

The [document quality guide](DOCUMENT_QUALITY.md) describes control coverage,
located findings, section patches and correction rechecks.

Each `output/runs/<run-id>/` contains `run.json` and its checkpoints (for a generate
run: `planned`, `generated`, `ready`, `exported`). Checkpoints contain private
content and need the same protections as source documents. If `ready.json` exists
with a matching checkpoint digest, re-export it offline:

```bash
python3 scripts/dev.py run export output/runs/<run-id> -f markdown -f docx
```

A Claude Code draft passes every local check again; a run made by the removed API
path keeps its saved review gate. The export goes into a new run directory and needs
a fresh human decision. Keep run directories in place: approval records use absolute
paths. Local hashes detect accidental changes, not malicious edits by someone who can
also rewrite the records. Model-phase recovery, its signed journal and the
`.recovery-key` were removed with the API path.

## Verification without customer data

```bash
python3 scripts/dev.py test -q -rs
python3 scripts/dev.py python -m scripts.verify_exports --output output/local-smoke
```

The tests block every network connection and fail if any file references the
Anthropic API, if the `anthropic` package is declared or installed, or if any REEMA
module, script or command needs it (`tests/test_no_api_guard.py`). The smoke script
creates synthetic Word, PDF, HTML, and Markdown files; it needs native PDF libraries.
Use a fresh smoke output directory. There is no CI workflow or container image; the
tests run locally.

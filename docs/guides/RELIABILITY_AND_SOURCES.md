# Reliability, sources, and offline recovery

The application remains Anthropic-backed. The asynchronous provider boundary is
in `src/utils/provider.py`; it is not an OpenAI runtime migration.
Use [Development setup](DEVELOPMENT_SETUP.md) for the supported project-local
launch/test path. [Specialist checks](SPECIALIST_EVIDENCE_AND_CHECKS.md) covers
optional publication metadata, claim freshness and supplied environment/data checks.

## Authorize reference files

Files are not authorized just because they exist in `references/`. Copy the
structure from `config/reference_manifest.example.yaml` into the local, ignored
`references/manifest.yaml`. Each source entry needs:

- `path`: a relative file path inside `REFERENCES_DIR` (no traversal or escaping symlinks).
- `classification`: `public`, `internal`, `confidential`, or `restricted`.
- `external_ai_allowed`: explicit boolean permission; default false.
- `sha256`: the reviewed file's actual 64-character SHA-256 digest.

Restricted files are never loaded for model context, even if marked allowed.
Other classifications still require permission. Changed bytes fail validation;
review the changes before updating the digest. On macOS/Linux use
`shasum -a 256 references/itom/ITOM.pdf`; on Windows use PowerShell's
`Get-FileHash references/itom/ITOM.pdf -Algorithm SHA256` (store lowercase).

The separate `--allow-external-ai` flag authorizes the run, not a blanket override
of source permissions. No manifest means no customer sources. Curated
`src/knowledge/` material remains eligible under the run's authorization.

PDF, DOCX, Markdown, and plain-text sources are supported. Search uses bounded
lexical ranking across extracted body content, preserving PDF page or DOCX block
locations and stable `[SRC-…]` IDs. DOCX tables and repeated headings are retained.
Files over 25 MB, extraction over two million characters, and unreadable/empty
PDF pages fail rather than silently providing partial evidence. OCR and vector
search are not implemented. Treat source files as trusted local files for parser
security; this is not an isolated sandbox for hostile document formats.

Only relevant chunks enter prompts. JSON evidence is separate from system
instructions, which explicitly reject instructions inside source material.
This is defense in depth, not a guarantee against prompt injection. Source IDs
prove which chunks were available, not whether every factual claim follows from
them. A human must check claim-to-source accuracy and applicable standards.

## Runtime controls

All controls are documented in `.env.example`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `API_TIMEOUT_SECONDS` | 120 | Deadline per provider attempt, not the entire run; a role's `timeout_seconds` in `agent_config.yaml` overrides it (Agent 3: 480) |
| `API_MAX_RETRIES` | 2 | Additional attempts only for connection/timeouts and transient statuses |
| `MAX_CONCURRENT_AGENTS` | 5 | Simultaneous provider calls per run |
| `MAX_RUN_TOKENS` | 1000000 | Conservative reservation gate before each request |
| `MAX_PROMPT_CHARS` | 200000 | Serialized request size limit; oversized prompts fail |
| `REVIEW_CHUNK_CHARS` | 24000 | Exact, non-truncated review excerpts |
| `KNOWLEDGE_CONTEXT_CHARS` | 12000 | Retrieval context allowance |
| `ENFORCE_PAGE_TARGET` | false | Require PDF and configured page range when true |
| `PAGE_TARGET` | [15,30] | Actual PDF page target, including cover |

SDK retries are disabled so retry counts are controlled in one place. Refused,
empty, or token-truncated responses fail delivery. Cancellation propagates.
Usage records include model, attempt, prompt hash, request ID, duration, and
returned token counts. Unknown usage on failed attempts consumes a conservative
reservation. The budget is a safety gate, not an exact billing limit. Concurrent
runs have separate budgets; no organization-wide spending limit is implemented.

`MODEL_PRICES` optionally supplies per-model input/output USD-per-million rates.
Without configured rates, cost is unknown (`null`), not zero. Estimates do not
replace provider billing and do not model every possible pricing feature.

## Review and recovery

Every review/compliance pass processes all document characters in excerpts, then
checks consistency across all excerpt assessments. Responses must match a strict
JSON schema. Final checks require the eleven SOP sections, usable RACI assignments,
and known source IDs. Legacy responsibility tables warn rather than break older
content. Missing standards names warn; naming a standard does not establish
compliance. Page targets warn by default, and no model review is a certification.
The [document quality guide](DOCUMENT_QUALITY.md) describes control coverage,
located findings, section patches and correction rechecks. Control-supporting
excerpts are retained in private checkpoints for quote checks; protect them like
the source files.

Each `output/runs/<run-id>/` contains `run.json` and completed phase checkpoints:
`planned`, `researched`, `generated`, `drafted`, `reviewed`, `ready`, and `exported`, as available.
Run metadata records failed/cancelled status and usage. Checkpoints contain private
content and need the same protections as source documents.

If `ready.json` exists with a matching checkpoint digest:

```bash
python -m src.main resume output/runs/<run-id> -f markdown -f docx
```

Default ready-to-export recovery performs no model calls, validates the saved review against the current
threshold and deterministic checks, and exports into a new run directory.
It does not restart model phases or grant document approval. For failed/cancelled
new runs before `ready`, `resume --model-phases --allow-external-ai` supports
verified completed research/generation reuse with fresh consent. The output root
contains a private recovery key; input/config/source/code identity, signed execution
records and phase hashes are checked before reuse. Prior usage remains charged
against the budget, and a new run needs a new human decision. See
[Coordination and recovery](COORDINATION_AND_RECOVERY.md) for supported states and limits. Every
new export run requires a fresh human decision. Keep run directories in place:
approval records use absolute paths. Local hashes detect accidental changes, not
malicious edits by someone who can also rewrite the records.

## Verification without customer data

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pytest --cov=src --cov-report=term -q
python -m scripts.verify_exports --output output/local-smoke
```

Tests block HTTP model calls and use deterministic fakes. The smoke script creates
synthetic Word, PDF, HTML, and Markdown files; it needs native PDF libraries.
Use a fresh smoke output directory. On this Mac the PDF runtime was verified with
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`; other machines may need different
native library setup. Docker supplies its own tested Linux dependencies.

The CI workflow defines Linux Python 3.11–3.14 and Windows/macOS Python 3.12 jobs,
plus an offline container export check. Adding the workflow does not mean those
hosted jobs have run. See the checkpoint report for actual local evidence.

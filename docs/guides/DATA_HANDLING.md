# Local data handling and human review

## Classification and scope

Treat everything in `references/`, `diagrams/`, generated `output/`, and `logs/`
as private unless the owner has explicitly classified it otherwise. This is a
conservative handling rule, not a legal classification or a content audit.

| Location | Material | Handling |
| --- | --- | --- |
| `references/itom/` | Optional ITOM PDF/DOCX sources | Local; authorize excerpts before model use |
| `references/access-management/` | Policies and procedures | Local customer material |
| `references/process-documents/` | Process sources, templates, backups | Local customer material |
| `references/customer/` | Supplied organizational references | Local customer material |
| `diagrams/` | Working architecture/process diagrams | Local private source |
| `output/` | Generated drafts and approval records | Private, reviewed before distribution |
| `logs/` | Runtime messages/errors | Potentially sensitive; inspect before sharing |
| `.claude/settings.local.json`, `.env*` | Machine settings and credentials | Local only; `.env.example` must contain no secrets |
| `.local-baseline/` | Pre-change recovery snapshot | Private local backup; not encrypted |
| `src/knowledge/` | Curated agent knowledge shipped with code | Review before sharing code or images; may be included in model prompts |

Git ignores the private locations, except the explanatory `references/README.md`.
Ignoring does not remove previous Git history or encrypt data. The local Claude
settings file is now staged for removal from tracking, but remains on disk.
No history rewriting or publication was performed. Keep authoritative copies in
approved storage; choose retention/access controls before multi-user deployment.

## External model consent

Normal generation is disabled unless `--allow-external-ai` is supplied or
`ALLOW_EXTERNAL_AI=true` is configured. The application still uses Anthropic.
Consent applies to the run's process details, agent knowledge, selected reference
excerpts, and intermediate drafts; it is not a guarantee of redaction or residency.
Do not authorize customer material without the organization's permission.

The application does not automatically ingest all reference folders. A manifest
explicitly permits hash-bound source files; restricted sources are always denied.
Retrieved excerpts retain source locations and IDs and are passed as untrusted
data, not system instructions. This reduces risk but cannot guarantee immunity
to prompt injection. Automated redaction and data residency guarantees are not
implemented. One-off legacy scripts are not a supported substitute for the gated
CLI workflow. See [source setup and limits](RELIABILITY_AND_SOURCES.md).

Private run checkpoints contain research, drafts, review summaries, and source
metadata. Request accounting records hashes, usage, and timing, not full prompts;
this is not a complete prompt audit. Protect the entire output directory.

Optional `--specialist-input` files contain supplied IAM snapshots, incident
observations and metric rows. These inputs and supporting excerpts persist in
private checkpoints and can enter authorized model/writing context. Keep them in
ignored local directories and inspect free text/metric rows for sensitive data.
Strict top-level/snapshot fields reject credential-shaped keys, but arbitrary
strings and row columns are not redacted. The flag does
not override source manifest permissions or authorize access changes.

Personal-assistant memory is explicit user-supplied text in separate work/personal
SQLite databases under `output/assistant/` (or `TASK_DATA_DIR`). The files have
restricted local permissions where supported, but are not encrypted. Profile,
preferences, selected project context, lessons and matching examples enter
advisory prompts only with external-AI authorization. Saving memory alone does
not authorize transmission. Examples are short supplied text; file paths are
not opened or imported by memory commands. Chat transcripts are not persisted.
Use `memory list` to inspect entries, repeat `memory set` to edit, and
`memory forget` with the exact kind/project to delete. Deletion affects future
requests and resets stale session history; it cannot retract earlier model calls
or erase database backups. See [Personal assistant](PERSONAL_ASSISTANT.md).

## Human approval

Each successful run creates a new `output/runs/<run-id>/` directory. After section,
review, selected compliance, and export checks pass, `approval.json` records the
drafts' absolute paths, SHA-256 hashes, quality score, and creation timestamp.
Its status is `awaiting_human_approval`, never automatically `approved`.

1. Read every output, including the end of long documents; check facts and sources.
2. Use the CLI `approve` or `reject` command with your name and optional notes.
3. Confirm the interactive prompt. Approval rechecks output and supporting-record hashes.
4. Regenerate a new run for revisions. Existing decisions cannot be replaced
   through the CLI. Rejection remains possible for missing or damaged artifacts.

Approval changes the record, not the original draft document bytes. Recheck hashes
before distribution if files might have changed after approval. Moving a run to
another machine changes absolute paths and is not a supported approval transfer.

The reviewer name is self-declared. Local files can be edited by anyone with
filesystem access; this is neither identity authentication, an immutable audit
ledger, nor a digital signature. A crash may leave an approval lock file; verify
no approval process remains active before manually recovering it. Enterprise
identity, protected audit storage, and release signing require a later design.

## Docker boundary

The build context allowlist permits only the Dockerfile, requirements, source, and
configuration. Customer references, keys, logs, generated files, and backups are
excluded. Reference access must be supplied as an explicit read-only mount at
`/app/references`; output should use a separate writable volume at `/app/output`.
The container runs as UID 10001 and defaults to `status`, not paid generation.
Verify volume permissions for that user. The local container build, non-root
execution, private-file exclusion checks, and synthetic four-format exports were
verified on 2026-09-29 with runtime networking disabled. This is not a deployment
or authorization to mount actual customer material.

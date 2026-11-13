# Local data handling and human review

## Classification and scope

Treat everything in `teams/documentation/input/references/`, `teams/documentation/input/diagrams/`, generated `teams/documentation/output/`, and `logs/`
as private unless the owner has explicitly classified it otherwise. This is a
conservative handling rule, not a legal classification or a content audit.

| Location | Material | Handling |
| --- | --- | --- |
| `teams/documentation/input/references/itom/` | Optional ITOM PDF/DOCX sources | Local; manifest permission and Khalid's yes before a session reads excerpts |
| `teams/documentation/input/diagrams/` | Working architecture/process diagrams | Local private source |
| `teams/documentation/output/` | Generated drafts, Claude Code work folders and approval records | Private, reviewed before distribution |
| `logs/` | Runtime messages/errors | Potentially sensitive; inspect before sharing |
| `.claude/settings.local.json`, `.env*` | Machine settings | Local only; `.env.example` must contain no secrets |
| `.local-baseline/` | Pre-change recovery snapshot | Private local backup; not encrypted |
| `src/knowledge/` | Curated agent knowledge shipped with code | Source material; review before sharing code or images |

Git ignores the private locations, except the explanatory `teams/documentation/input/references/README.md`.

Material from earlier customer engagements is kept outside REEMA, on this PC only, and is not
read from REEMA.
Ignoring does not remove previous Git history or encrypt data. Keep authoritative
copies in approved storage; choose retention/access controls before multi-user use.

## What leaves this computer

REEMA itself makes no model call and opens no network connection: it has no API
client, key or consent flag. Model work happens in a Claude Code session, and what
that session reads goes to Anthropic through Claude Code. So the control point is
what the session is allowed to read:

- **A finished SOP** (review, revise): Ahmad asks Khalid's yes first. The prepare
  step refuses until it is given `--confirm-read` with the token it prints for that
  exact file (the start of its SHA-256), and copies nothing into
  `teams/documentation/output/claude_code/` before that. The token binds the yes to the file's bytes;
  it cannot prove who said yes.
- **Reference excerpts** (generate): only files listed in the local manifest with
  permission and a matching SHA-256 are searched, restricted sources are always
  denied, and one confirm-read token covers exactly the files the excerpts come
  from. A file under `teams/documentation/input/references/` used as an SOP must pass the same manifest check.
- **A `--specialist-input` file** (IAM snapshots, incident observations, metric
  rows): it joins the same confirm-read token. Its local checks are written into the
  request as data. Strict fields reject credential-shaped keys, but free text and
  row columns are not redacted; inspect them first.
- **Work tasks and memory**: Ahmad uses them only through the local `task` and
  `memory` commands, asks Khalid's yes once per session before reading them, and
  never reads the personal area.

Excerpts keep their source locations and IDs and are given to the session as
untrusted data, not instructions. This reduces risk but cannot guarantee immunity to
prompt injection. Automated redaction and data residency guarantees are not
implemented. A yes to read does not approve distribution. See
[source setup and limits](RELIABILITY_AND_SOURCES.md).

Claude Code work folders (`teams/documentation/output/claude_code/<id>/`) hold the copied SOP text,
excerpts and the subagents' files; run folders hold checkpoints and drafts. Protect
the whole output directory.

Personal-assistant memory is explicit user-supplied text in separate work/personal
SQLite databases under `teams/coordination/data/` (or `TASK_DATA_DIR`). The files have
restricted local permissions where supported, but are not encrypted. Saving memory
does not send it anywhere. Use `memory list` to inspect entries, repeat `memory set`
to edit, and `memory forget` with the exact kind/project to delete; deletion cannot
retract what an earlier session read or erase database backups. See
[Personal assistant](PERSONAL_ASSISTANT.md).

## Human approval

Each successful generate, revise or export job creates a new `teams/documentation/output/runs/<run-id>/`
directory. After its checks and export pass, `approval.json` records the drafts'
absolute paths, SHA-256 hashes, a quality score (null when no model reviewed the
draft, as for a Claude Code generate run) and the creation timestamp. Its status is
`awaiting_human_approval`, never automatically `approved`.

1. Read every output, including the end of long documents; check facts and sources.
2. Use the CLI `approve` or `reject` command with your name and optional notes.
3. Confirm the interactive prompt. Approval rechecks output and supporting-record hashes.
4. For changes, revise the draft or generate again; each makes a new run. Existing
   decisions cannot be replaced through the CLI. Rejection remains possible for
   missing or damaged artifacts.

Approving a revise run also publishes it into `teams/documentation/output/` (see the README). Approval
changes the record, not the original draft document bytes. Recheck hashes before
distribution if files might have changed after approval. Moving a run to another
machine changes absolute paths and is not a supported approval transfer.

The reviewer name is self-declared. Local files can be edited by anyone with
filesystem access; this is neither identity authentication, an immutable audit
ledger, nor a digital signature. A crash may leave an approval lock file; verify
no approval process remains active before manually recovering it. No agent, and no
Claude Code session, may approve: `.claude/settings.json` denies `approve`, `reject`
and `publish`.

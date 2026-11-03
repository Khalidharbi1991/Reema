# REEMA - Khalid's IT Company

**REEMA** is Khalid's IT company. Ahmad, the coordinator, talks with Khalid and
routes work to sections. The main section is Documentation, led by Abdullah:
writing, reviewing and revising SOPs, and later reports and presentations. The
first new feature, not yet built, will turn SCCM and Intune data into a patch
report PowerPoint. Agent 9 supports home design as a side service. The Development
section, led by Agent 11, builds software, apps and games in separate project repos.

Everything that needs writing or judgment runs in a Claude Code session: talk to
Ahmad there. REEMA itself makes no model call and needs no API key: it plans,
checks, exports and records the work for your approval. `reema chat` is retired.

Start with the [documentation index](docs/README.md) and the
[personal assistant guide](docs/guides/PERSONAL_ASSISTANT.md). The
[architecture](docs/architecture/ARCHITECTURE.md) shows the jobs and components, and
[data handling](docs/guides/DATA_HANDLING.md) explains what a Claude Code session may
read. Reports under `docs/reports/` describe the system as it was when each was
written; the [changelog](docs/reports/CHANGELOG.md) lists every change, newest first.

## Working with coding agents

This repository includes [AGENTS.md](AGENTS.md), which gives any coding agent
(Claude Code, Codex, or others) focused, project-specific instructions for safe
maintenance and enhancement. [CLAUDE.md](CLAUDE.md) only imports AGENTS.md.
REEMA has no model runtime; [docs/migration/CODEX_ADOPTION.md](docs/migration/CODEX_ADOPTION.md)
explains what adding one back would take.

## Overview

REEMA has 12 agent roles. Ahmad coordinates Khalid's tasks and conversations as the
main Claude Code session; Abdullah heads the Documentation section's jobs. A new SOP
is prepared by `reema generate`, written section by section in Claude Code, then
checked, exported and recorded by REEMA. Finished SOPs can be reviewed and revised
the same way. The 15–30 page target warns by default; `ENFORCE_PAGE_TARGET=true`
makes it mandatory and requires PDF output. Every draft needs separate human
approval.

### Key Features

- **Claude Code company**: Ahmad, Abdullah's Documentation skills, and read/write-only subagents for writing, review, revision, building design and endpoint advice
- **No model calls in REEMA**: no API key, client or network access; a strict test guards it
- **Personal Task Lists**: Separate local work and personal tasks, priorities, due dates, and daily views
- **Persistent Personal Context**: Editable profiles, preferences, project goals, correction lessons, and examples
- **Read consent**: a session reads an SOP, reference excerpts or input data only after your yes, given as a token bound to those exact files
- **Standards Review**: Structured checks and gap findings, not compliance certification
- **Multi-Format Output**: PDF, Word (DOCX), Markdown, and HTML
- **Quality Gates**: Required sections, RACI, citations, diagrams, control coverage, validated exports, and human approval
- **Customizable**: Configurable processes, standards, and output formats

## Agent Team

Ahmad is the user's main coordinator, as the main Claude Code session. Abdullah
heads the Documentation section: the generate, review, revise and export jobs. The
former Khalid owner agent was removed; Ahmad frames advice in its strategy,
governance, quality, and business-value terms. The user retains approval and
decision authority. Run `python3 scripts/dev.py run agents` for the active roster.

| Agent | Current responsibility |
| --- | --- |
| Ahmad | Main coordinator for tasks, preferences, planning and conversations (Claude Code session) |
| Abdullah | Documentation section head: the local generate, review, revise and export jobs |
| Agent 1 | Research and IT service practices (role only) |
| Agent 2 | Standards and control alignment (role only) |
| Agent 3 | Writing and SOP content (`reema-writer`, `reema-reviser`) |
| Agent 4 | Quality review (`reema-reviewer`, `reema-rechecker`) |
| Agent 5 | PDF, DOCX, Markdown, and HTML formatting |
| Agent 6 | Access and identity security (role only; IAM checks on supplied data) |
| Agent 7 | Problem management and root-cause analysis (role only; case checks on supplied data) |
| Agent 8 | Analytics and KPI design (role only; metric checks on supplied data) |
| Agent 9 | Building-design advice, local DWG intake, and assumption-labeled concept meshes from selected DXF wall linework |
| Agent 10 | End-user computing advice: patching and deployment rings, OS images, software packaging, Intune/MECM, endpoint compliance, change requests and runbooks; endpoint appendix for patch and device-batch SOPs |
| Agent 11 | Development section head: sizes each job, picks the agents, gets your yes |
| Agent 12 | Requirements (PRD) |
| Agent 13 | Software architecture |
| Agent 14 | Developer |
| Agent 15 | Tester |
| Agent 16 | Security review |
| Agent 17 | UI design |
| Agent 18 | Game writer and designer |

## Installation

### Prerequisites

- Python 3.11–3.14
- Optional references explicitly permitted in `references/manifest.yaml`
- Native Pango libraries for PDF output (see the development setup guide)

### Setup

1. **Clone or navigate to the project directory:**
```bash
cd "/path/to/IT Consultant"
```

2. **Create and verify the locked project environment:**
```bash
python3 scripts/dev.py bootstrap
python3 scripts/dev.py doctor
python3 scripts/dev.py test -q -rs
```

On Windows use `python` if `python3` is unavailable. No activation, temporary
`PYTHONPATH`, or per-command native PDF flag is needed. The launcher uses ignored
`.venv/`, hash-locked wheels and child-process native-library discovery. See the
[development setup guide](docs/guides/DEVELOPMENT_SETUP.md) for offline wheelhouses
and platform dependencies. Runtime lock files and `uv.lock` remain unchanged.

3. **No API key is needed.** REEMA makes no model call; Claude Code writes the text. A
`.env` left from earlier versions may still hold a key: it is ignored, and you can
delete that line.

## Usage

### Command Line Interface

The system provides a user-friendly CLI powered by Typer and Rich.

#### Generate Documentation

A new SOP is written in a Claude Code session (see "Claude Code generate" below).
`generate` prepares it and prints the work id to hand to Ahmad; it makes no model call:

```bash
python3 scripts/dev.py run generate "Incident Management" -f markdown
```

Specify output formats:

```bash
python3 scripts/dev.py run generate "Change Management" --format pdf --format docx
```

Custom output directory:

```bash
python3 scripts/dev.py run generate "Service Request Management" --output ./output/my-docs
```

Keep custom output folders under `output/` or another Git-ignored path. Drafts,
run checkpoints and source excerpts are written there; `generate` and `export`
print a warning when the folder is inside the repository but not ignored.

Unknown process names fail unless `--custom` is supplied. Additional specialists can be
selected with `--specialist access`, `problem`, `data`, or `euc`. Workstation Security
Patches and Devices Batch Management include Agent 10 (`euc`) by default; it adds an
Endpoint Deployment & Rollback Plan appendix. If reference excerpts or a
`--specialist-input` file would be read, `generate` prints a `--confirm-read` token
instead; run it again with the token only after deciding the session may read them.
Missing PDF dependencies fail a PDF request explicitly; select `-f markdown`
when PDF is not needed.

#### Human approval

Outputs are isolated in `output/runs/<run-id>/` with an `approval.json` record.
Review every exported document, then record your decision using the printed path:

```bash
python3 scripts/dev.py run approve output/runs/<run-id>/approval.json --reviewer "Your name"
python3 scripts/dev.py run reject output/runs/<run-id>/approval.json --reviewer "Your name" --notes "Required changes"
```

Both commands require interactive confirmation. Approval verifies that files
still match their recorded SHA-256 hashes. Changed documents require a new run.
The ready-to-export review/source record and export checks are also hash-bound.
This is a local, self-declared review record, not authenticated identity or a
digital signature. AI agent scores and recommendations never grant human approval.
The original draft files are not rewritten after approval.

#### Review and revise finished SOPs

Existing `.md` or `.docx` SOPs can be checked and fixed without regenerating
them. The original file is only read; every job writes a new
`output/runs/<run-id>/` folder. The full review and revisions run in Claude Code
(see "Claude Code revise" below); REEMA itself calls no model for them. From the
command line you can run the template-gap check, which needs no model:

```bash
python3 scripts/dev.py run review output/SOP_User_Incident_Management_V2.docx
```

Review saves `findings.md`/`findings.json` and has no approval record. Revise
changes only the target sections (everything else stays word for word), runs a
targeted recheck, writes `changes.md`, and ends at `awaiting_human_approval`; use
`approve` as above. For DOCX input the revised sections are spliced into a copy of
your Word file, so other sections keep their formatting; a section holding
images, tracked changes, fields or content controls must be edited in Word.

The revised file is named with the next version: `..._V2` becomes `..._V2.1`, then
`..._V2.2`; a name with no version becomes `_V1.1`. Add `--major` when you decide the
change is big (`V2.3` becomes `V3.0`). Every existing draft in `output/` and its run
folders counts, rejected ones too, so a number is never used twice; old `_revised`
files keep their names and count as their plain version. Only the file name changes:
update the version in Document Control yourself before approving (`changes.md` says so).

In Claude Code, ask Ahmad in plain words, for example "fix the escalation part in my
incident SOP". He lists matching files in `output/` for you to choose, names the
section, and asks for your yes before the session reads the file. He cannot approve
the result.

#### Publishing an approved revision

`reema approve` on a revise run also publishes it: the approved
`.md`/`.docx` drafts are copied to the top of `output/`, and every older version of the
same SOP there (same name, lower version, same format) moves to
`output/archive/<run-id>/`. Before you confirm, the command shows what it will copy and
archive, or warns that publishing will be refused. It never overwrites a file and checks
each copy and move by SHA-256; the result is in the run's `publish.json`. If publishing
is refused or stops halfway, the approval stays recorded, the command exits 1 with
"approved, not published", and you can retry:

```bash
reema publish output/runs/RUN_ID/approval.json
```

`reema approve --no-publish` records the approval only; `reema publish` can publish it
later. Generate runs, old `_revised` drafts and runs approved before this feature are
not published.

#### Claude Code generate

In a Claude Code session, ask Ahmad for a new SOP (the `reema-generate` skill). REEMA plans it
and prepares the 11-section skeleton; the `reema-writer` subagent writes one file per section;
`scripts/claude_code_generate.py` checks every section and the whole document (template, RACI,
standards named, citations, diagrams, control coverage), exports the formats you asked for and
creates the pending approval record. No model reviews the draft, so the approval record has no
quality score; ask Ahmad to review the Markdown draft first if you want a review. Excerpts from
`references/` are included only when the reference manifest allows them, and only after your yes
(a `--confirm-read` token). For patch processes (Workstation Security Patches, Devices Batch
Management) Agent 10 writes the "Endpoint Deployment & Rollback Plan" appendix. Access, problem and
data specialists add no appendix; their local checks on a JSON input file you name (IAM snapshot,
incident observations, metric data) are given to the writer as data, after the same yes.

#### Claude Code revise (experimental)

Inside a Claude Code session in this repository you can revise one section of a
finished SOP with no Anthropic API call from REEMA: ask Claude Code to use the
`reema-revise` skill. The session writes the section text (`reema-reviser`
subagent) and the recheck (`reema-rechecker` subagent); `scripts/claude_code_revise.py`
runs the gates, Word splice, export and pending approval record. The SOP is still
sent to Anthropic through the Claude Code session, so you are asked for your yes
first: the prepare step prints a `--confirm-read` token for that exact file and
copies nothing until it is given back. A file under `references/` must also be
allowed in the reference manifest. It takes either `--instruction` or 1–5
findings from a review run of the same SOP (`--from-review RUN --finding ID`), and it
never approves: run the printed `reema approve` command yourself.

The `reema-review` skill reviews a finished SOP the same way, read-only: Claude Code
writes the findings, and `scripts/claude_code_review.py` locates every quote, binds
the file's SHA-256 (checked before and after) and writes a normal review run that
the `reema-revise` skill's `--from-review` accepts. A review has no approval record.

#### REEMA in Claude Code

Open the Claude desktop app's Code tab on this folder and start a new session (skills
and subagents load at session start). The main session acts as Ahmad; type in plain
words, for example "Ahmad, what's on my work list today?" or "Ahmad, review my
incident SOP", or `/abdullah-docs` to go straight to the Documentation section.
Ahmad works with the work area only, asks your yes once per session before reading
work tasks or memory and before reading each SOP, and never approves or pushes.
Building or home-design questions go to Agent 9 and endpoint questions (patching,
imaging, packaging, Intune/MECM) to Agent 10, as Claude Code subagents that only
read files you allow and save drafts under `output/claude_code/advice/`. The
org chart and rules are in AGENTS.md under "REEMA company in Claude Code".

#### Development section

Ask Ahmad in plain words, for example "Ahmad, build a small offline expense tracker"
or "Ahmad, fix the score bug in my game", or type `/reema-agent11-dev-lead`. Agent
11's playbook sizes the job (small fix, new feature, new app, new game), picks only
the agents it needs (Agents 12–18, as Claude Code subagents), and shows you the plan,
the agents, the files and every package it wants to install. Nothing is written until
you say yes. Anything bigger than a small fix starts with a PRD you confirm.

Each project gets its own folder and git repo in
`D:/Projects/REEMA Projects/`, tagged at the start and end of
every job and before each risky change. To list a project's tags (replace `my-game`
with the project's folder name):

```bash
git -C "D:/Projects/REEMA Projects/my-game" tag --list
```

A job finishes only when its tests pass and the security review has no open Critical
or High finding. The section never pushes, deploys or publishes, and never touches
REEMA's `references/` or `output/assistant/`. `.claude/settings.json` blocks push,
remotes, publishing, deploy tools, `sudo` and network tools such as `curl` and `wget`
for the whole session, and its hook (`.claude/hooks/dev_guard.py`) also catches them
inside `sh -c`, `eval` and similar.

To find a finished SOP by file name without opening it:

```bash
python3 scripts/dev.py run find-sop incident management
```

#### Recover exports without model calls

Each run saves phase checkpoints and usage metadata in its own directory. If a
run reached `ready.json` but export failed, regenerate the exports offline:

```bash
python3 scripts/dev.py run export output/runs/<run-id> -f markdown -f docx
```

This validates the checkpoint hash, runs the local checks again on a Claude Code draft,
creates a new run, and requires a fresh human decision. It makes no model call. It also
exports older runs made by the removed API path; `resume` still works as an old name.

## Examples

### Example 1: Prepare an Incident Management SOP

```bash
python3 scripts/dev.py run generate "Incident Management" -f pdf -f docx
```

Then, in Claude Code, ask Ahmad to write the printed work id. Output after finish:
- `output/runs/<run-id>/pdf/Incident_Management_SOP.pdf`
- `output/runs/<run-id>/docx/Incident_Management_SOP.docx`

### Example 2: Custom Device Management Process

```bash
python3 scripts/dev.py run generate "Devices Batch Management" -f pdf -f html
```

## Troubleshooting

### ITOM.pdf Not Found

Placing a file in `references/itom/` does not authorize it. Add its relative path,
classification, SHA-256, and explicit permission to `references/manifest.yaml`.
See the [source setup guide](docs/guides/RELIABILITY_AND_SOURCES.md).

### Import Errors

Rebuild and check the locked project environment:

```bash
python3 scripts/dev.py bootstrap
python3 scripts/dev.py doctor
```

### Permission Errors

Make sure your user owns `output/` (`ls -ld output`). Do not widen its
permissions: REEMA keeps the task and memory stores owner-only.

## Advanced Usage

### Python API

The jobs are plain Python and make no model call. For example, to prepare a new SOP
for Claude Code from a script (run it with `python3 scripts/dev.py python your_script.py`):

```python
from src.generate_job import prepare

work_id = prepare("Incident Management", ["pdf", "docx"])
print(f"Ask Ahmad in Claude Code to write SOP work {work_id}")
```

Drafts stop at `awaiting_human_approval`; only the named human reviewer approves.

## Contributing

To add new IT processes:

1. Add process definition to `config/process_definitions.yaml`
2. Add standards mapping to `config/standards_mapping.yaml`
3. Run the system with your new process name

## Support

For issues or questions:
- Check the logs in `logs/` directory
- Review configuration files in `config/`

## License

Internal use only

## Version

Version 2.0.0

---

**REEMA, Khalid's IT company**

The text is written in Claude Code; REEMA checks, exports and records it.

---
name: reema-revise
description: Revise one section of a finished REEMA SOP (.md or .docx) inside Claude Code, with no Anthropic API call, from an instruction or from 1-5 review findings. Experiment. Use when Khalid asks to revise a finished SOP section; `reema revise` no longer runs a revision.
---
# REEMA revise inside Claude Code (experiment)

Claude Code writes the text; `scripts/claude_code_revise.py` enforces every gate. Never weaken a
gate, edit the script, or hand-write files under output/runs/ to get past a refusal.

1. Confirm with Khalid his explicit yes for Claude Code to read this SOP (it is sent to Anthropic
   through this session; the yes also covers that SOP's review findings.md). Without it, stop. Then
   confirm either the section title and exact instruction (instruction mode) or the review run
   folder and 1-5 finding IDs (review mode).
2. Instruction mode:
   `python3 scripts/dev.py python scripts/claude_code_revise.py prepare "<file>" --section "<title>" --instruction "<text>"`
   Review mode (one `--finding` per ID, 1-5; the review must be of this exact file):
   `python3 scripts/dev.py python scripts/claude_code_revise.py prepare "<file>" --from-review "<run folder>" --finding <id>`
   Add `--major` only when Khalid has said this change is a major version (V2.3 -> V3.0); otherwise
   the draft takes the next minor version (V2 -> V2.1). Never choose major yourself.
   The first run refuses and prints a `--confirm-read` token for this exact file. Only with Khalid's
   yes from step 1, run the same command again with `--confirm-read <token>`. Never pass a token
   without that yes. Note the work id it prints. A refusal here (findings changed, SOP changed since the review,
   unknown or template-gap ID) is final: report it; do not edit the review run.
3. Ask the `reema-reviser` subagent to write patch.json for that work id.
4. `python3 scripts/dev.py python scripts/claude_code_revise.py check <id>`
   On "Refused", pass the exact reason back to `reema-reviser`; at most 3 rounds, then stop and report.
5. Ask the `reema-rechecker` subagent (a fresh one, not the reviser) to write recheck.json.
6. `python3 scripts/dev.py python scripts/claude_code_revise.py finish <id>`
7. Report the run folder, the new file name and version, that Document Control inside the document
   was not changed (Khalid updates it), changes.md, the recheck result, and print the approve command for Khalid
   to run himself. Never run `reema approve`, `reema reject` or `reema publish`, and never supply a reviewer name.

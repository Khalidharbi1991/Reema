---
name: reema-revise
description: Revise one section of a finished REEMA SOP (.md or .docx) inside Claude Code, with no Anthropic API call. Experiment; instruction path only. Use when Khalid asks to revise a finished SOP section here rather than with `reema revise`.
---
# REEMA revise inside Claude Code (experiment)

Claude Code writes the text; `scripts/claude_code_revise.py` enforces every gate. Never weaken a
gate, edit the script, or hand-write files under output/runs/ to get past a refusal.

1. Confirm with Khalid: the file, the section title, the exact instruction, and his explicit yes
   for Claude Code to read this SOP (it is sent to Anthropic through this session). Without that
   yes, stop.
2. `python3 scripts/dev.py python scripts/claude_code_revise.py prepare "<file>" --section "<title>" --instruction "<text>"`
   Note the work id it prints.
3. Ask the `reema-reviser` subagent to write patch.json for that work id.
4. `python3 scripts/dev.py python scripts/claude_code_revise.py check <id>`
   On "Refused", pass the exact reason back to `reema-reviser`; at most 3 rounds, then stop and report.
5. Ask the `reema-rechecker` subagent (a fresh one, not the reviser) to write recheck.json.
6. `python3 scripts/dev.py python scripts/claude_code_revise.py finish <id>`
7. Report the run folder, changes.md, the recheck result, and print the approve command for Khalid
   to run himself. Never run `reema approve` or `reema reject`, and never supply a reviewer name.

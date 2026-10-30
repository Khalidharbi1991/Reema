---
name: reema-generate
description: Write a new REEMA SOP inside Claude Code, with no Anthropic API call. The reema-writer subagent writes the sections; REEMA checks, exports and records it for approval. Use when Khalid asks for a new SOP.
---
# REEMA generate inside Claude Code

Claude Code writes the section text; `scripts/claude_code_generate.py` enforces every check. Never
weaken a check, edit the script, or hand-write files under output/runs/ to get past a refusal. No
model reviews the draft, and nothing is approved here.

1. Confirm with Khalid the process (a catalog name, or `--custom` for a new one), the formats, and any
   objective, constraint or acceptance criterion in his words.
2. `python3 scripts/dev.py python scripts/claude_code_generate.py prepare "<process>" --format <f> ...`
   If it refuses with a `--confirm-read` token, it names the reference files whose excerpts would be
   read. Ask Khalid; only with his yes, run the same command again with `--confirm-read <token>`.
   Never pass a token without that yes. Note the work id. Any other refusal is final: report it.
3. Ask the `reema-writer` subagent to write the section files for that work id.
4. `python3 scripts/dev.py python scripts/claude_code_generate.py check <id>`
   On "Refused", pass the exact reason back to `reema-writer`; at most 3 rounds, then stop and report.
5. `python3 scripts/dev.py python scripts/claude_code_generate.py finish <id>`
6. Report the run folder, the files, the notes it prints (missing evidence, controls needing human
   determination, page count) and that no model reviewed it. Offer the reema-review skill on the
   Markdown draft. Print the approve command for Khalid to run himself. Never run `reema approve`,
   `reema reject` or `reema publish`, and never supply a reviewer name.

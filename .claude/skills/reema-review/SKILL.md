---
name: reema-review
description: Review a finished REEMA SOP (.md or .docx) inside Claude Code, with no Anthropic API call. Experiment; read-only. Use when Khalid asks to review a finished SOP; `reema review` only runs the local template check.
---
# REEMA review inside Claude Code (experiment)

Claude Code writes the findings; `scripts/claude_code_review.py` enforces every check. Never weaken a
check, edit the script, or hand-write files under output/runs/ to get past a refusal. The SOP file is
only read, and a review has nothing to approve.

1. Confirm with Khalid: the file, and his explicit yes for Claude Code to read this SOP (it is sent to
   Anthropic through this session). Without that yes, stop. For a template check only, run
   `python3 scripts/dev.py run review "<file>"` instead; it reads nothing into this session.
2. `python3 scripts/dev.py python scripts/claude_code_review.py prepare "<file>"`
   It refuses and prints a `--confirm-read` token for this exact file. Only with Khalid's yes from
   step 1, run the same command again with `--confirm-read <token>`. Never pass a token without
   that yes. Note the work id and the number of excerpts it prints.
3. Ask the `reema-reviewer` subagent to write excerpts.json for that work id.
4. `python3 scripts/dev.py python scripts/claude_code_review.py check <id>`
   On "Refused", pass the exact reason back to `reema-reviewer`; at most 3 rounds, then stop and report.
5. Only if check printed a consistency request: ask a fresh `reema-consistency-reviewer` subagent (not
   the reviewer) to write consistency.json, then run check again (same 3-round limit).
6. `python3 scripts/dev.py python scripts/claude_code_review.py finish <id>`
7. Report the findings.md path, the counts, and the before/after source SHA-256 that finish prints.
   Never run `reema approve` or `reema reject`. To act on findings, Khalid chooses them and the
   reema-revise skill runs separately.

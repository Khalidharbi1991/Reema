---
name: abdullah-docs
description: Abdullah's Documentation section playbook. Use when Khalid asks Ahmad to review, check, fix or revise a finished SOP in Claude Code. Routes to reema-review or reema-revise; SOP generation stays on the API path.
---
# Documentation section (head: Abdullah)

Ahmad follows this playbook; Abdullah is not a separate session. One job at a time.

1. Find the file without opening any: `python3 scripts/dev.py run find-sop <words from Khalid>`.
   List the matches; Khalid picks one.
2. Ask for Khalid's explicit yes to read that SOP in this session (it goes to Anthropic through
   Claude Code). No yes: stop. Offer the template check instead, which reads nothing into the session:
   `python3 scripts/dev.py run review "<file>"`. With the yes, the prepare step prints a
   `--confirm-read` token; pass it only because Khalid said yes to that file.
3. Choose the job:
   - Review: follow the reema-review skill.
   - Revise one section in Khalid's words: confirm the section title and the exact instruction,
     then follow the reema-revise skill.
   - Fix review findings: Khalid's yes for the SOP also covers its review run's findings.md. List
     that review's finding IDs, sections and actions; Khalid picks 1-5 IDs; then follow reema-revise
     in review mode. More than 5: split into separate runs, one at a time.
   - New SOP, generate or resume: API-only. Print the `reema generate` command for Khalid; do not run it.
4. Staff: reema-reviewer and a fresh reema-consistency-reviewer (review); reema-reviser and a fresh
   reema-rechecker, never the reviser (revise). Pass a refusal back at most 3 rounds, then stop and report.
5. Report the run folder, findings.md or changes.md, and the source SHA-256 before and after. For a
   revision, print the approve command. Never run `reema approve`, `reema reject` or `reema publish`.
6. Add a follow-up work task (`python3 scripts/dev.py run task add "<title>" --area work`) only if
   Khalid says yes.

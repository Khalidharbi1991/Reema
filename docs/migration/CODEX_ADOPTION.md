# Codex adoption and model runtime

## Current state

Codex and other coding agents work in this repository through the root `AGENTS.md`,
the single source of truth for project instructions (`CLAUDE.md` only imports it).

REEMA no longer has a model runtime. The no-API migration of 2026-10-30/31 removed
the `LLMProvider`/`AnthropicProvider` boundary, the client in `BaseAgent`, the key and
consent settings and the `anthropic` package. Claude Code writes the text through
skills and subagents, and REEMA's code checks, exports and records it. See
`docs/reports/CHANGELOG.md` for the steps.

## Adding a model provider again

There is no provider to migrate to OpenAI or anything else. Bringing back any model
API (Anthropic, OpenAI or another) would be a new feature and needs Khalid's explicit
request (AGENTS.md, non-negotiable rules). It would have to add, together:

- a client behind a small provider interface, with fakes for tests;
- settings, a consent gate and dependency changes, regenerated with `uv`;
- documentation and tests, including changes to `tests/test_no_api_guard.py`, which
  today fails on any API reference, declaration or import.

The file-backed workers (`src/agents/file_workers.py`) show the seam: each job asks
`BaseAgent._reply` for text and checks whatever comes back.

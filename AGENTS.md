# REEMA — Codex Working Guide

## Purpose

REEMA coordinates local work and personal tasks and generates IT process
documentation through a Python multi-agent pipeline. Ahmad is the user's
coordinator; Abdullah leads specialist work. The former owner agent was removed.
The current application runtime uses the Anthropic SDK. Codex is the development
agent for maintaining, testing, and evolving this repository; do not imply that
the application itself has moved to OpenAI until that runtime migration is made.

## Start here

- Use `README.md` for user setup and CLI usage.
- Use `docs/architecture/ARCHITECTURE.md` and `CLAUDE.MD` for the current
  pipeline and domain model.
- Read the relevant agent module in `src/agents/` before changing a pipeline phase.
- Process and standards data live in `config/*.yaml`; keep new process behavior
  configuration-driven.
- One-off document generators and converters live in `scripts/`; run them from
  the repository root unless their help text states otherwise.
- Local source documents live in `references/` and generated artifacts belong in
  `output/`.
- The knowledge bases in `src/knowledge/` are source material. Preserve their
  names and character encoding unless the task specifically concerns them.

## Working conventions

- Preserve existing user changes: the worktree may be dirty.
- Keep the current asynchronous pipeline and public CLI commands compatible unless
  a change request explicitly permits breaking changes.
- Add or update focused tests in `tests/` for behavioral changes.
- Run the affected tests; `pytest -q` is safe for the local test suite.
  Prefer `python3 scripts/dev.py test -q -rs` after
  `python3 scripts/dev.py bootstrap`; the project launcher discovers PDF libraries
  and uses the locked ignored `.venv` without temporary import paths.
- Never add API keys, generated documents, logs, local editor settings, or source
  customer documents to Git.
- External model calls require explicit authorization for the input/reference
  material. Do not enable `ALLOW_EXTERNAL_AI` or perform paid generation as a
  routine verification step. Use mocked providers for tests.
- Successful generation ends at `awaiting_human_approval`. Never run the
  `approve` command or supply a human reviewer's identity on their behalf unless
  that person explicitly authorizes approval of those exact artifacts. Code-change
  approval is not document approval. See `docs/guides/DATA_HANDLING.md`.

## Provider migration boundary

The application is currently Anthropic-backed. A provider migration requires an
explicit request and must update the client abstraction, settings, dependencies,
  documentation, and tests together. See `docs/migration/CODEX_ADOPTION.md`
  before starting that work.

## Definition of done

For code changes, finish the requested implementation, run relevant tests, and
report any remaining external requirement (such as an API key or platform-specific
PDF dependency).

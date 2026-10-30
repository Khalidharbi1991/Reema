# Codex Adoption and Runtime Migration Plan

## Current state

Codex can now work in this repository: it reads the root `AGENTS.md`, which
holds the project instructions. The application remains an
Anthropic-powered Python CLI. Calls now pass through the
async `LLMProvider` boundary and `AnthropicProvider` adapter; configuration still
reads `ANTHROPIC_API_KEY`. Reliability, retrieval, checkpoint recovery, and quality
improvements are described in [the operating guide](../guides/RELIABILITY_AND_SOURCES.md).
The recommendations below describe the original staged direction, not a claim
that a provider migration has occurred.

## Recommended improvements

1. Create a provider interface.
   - Move direct calls from `BaseAgent._call_claude` and `LeaderAgent` behind a
     small async `LLMProvider` protocol.
   - Keep an `AnthropicProvider` adapter for backwards compatibility.
   - Add an `OpenAIProvider` only as part of an explicitly approved runtime
     migration.

2. Separate prompt content from agent orchestration.
   - Store each agent's system prompt in versioned prompt files or concise Python
     builders.
   - Pass only task-relevant knowledge excerpts rather than appending entire
     knowledge files to every call.

3. Make execution observable and recoverable.
   - Persist a run identifier, per-phase status, inputs, outputs, model and
     provider metadata.
   - Allow formatting to be resumed from reviewed Markdown instead of rerunning
     expensive generation.

4. Strengthen quality assurance.
   - Add golden-file tests for a small SOP fixture.
   - Validate required SOP sections, RACI fields, standards references, and all
     requested output files before delivery.
   - Treat external API calls as fakes in unit tests; keep live calls opt-in.

5. Improve configuration and packaging.
   - Migrate Pydantic's deprecated class-based settings configuration to
     `SettingsConfigDict`.
   - Put provider, model, concurrency, and output settings in a documented
     `.env.example`; do not commit real secrets.
   - Add `output/` and `logs/` to `.gitignore` if they are not already ignored.

## Migration sequence for an OpenAI runtime

Do this only when the desired deployment and API access are confirmed:

1. Agree on the OpenAI API model, budget constraints, and whether the application
   needs hosted tools, file search, or only text generation.
2. Add the provider abstraction plus deterministic fake provider tests.
3. Implement the OpenAI adapter using the current OpenAI API guidance, then add
   `OPENAI_API_KEY` support while retaining the Anthropic adapter during rollout.
4. Make provider selection explicit (`REEMA_LLM_PROVIDER=anthropic|openai`),
   migrate configuration, and update the CLI status output.
5. Run the complete test suite and generate a representative SOP in every
   supported output format before deprecating the Anthropic path.

## Why this order

Coding-agent repository instructions and an application LLM provider solve different
problems. `AGENTS.md` guides future maintenance work; Codex reads it directly and
`CLAUDE.md` imports it. The provider
abstraction prevents a future API migration from requiring invasive edits across
all twelve agent roles.

## Reference

OpenAI recommends keeping repository instructions contextual and concise rather
than forcing broad document reads before every edit. See [Rethinking skills and
prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).

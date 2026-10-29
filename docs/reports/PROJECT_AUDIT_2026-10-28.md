# REEMA read-only project audit — 2026-10-28

Scope: the whole repository at commit `8c8e52b` on `main`, including ignored local
folders (listed by name only). Customer documents were not opened or quoted.

Method:

- Read-only. Nothing in the project was edited, moved or deleted during the audit.
- Every CLI command was run with `--help` only.
- The mocked test suite ran with `python3 scripts/dev.py test -q -rs -p no:cacheprovider`.
  `LOG_DIR`, `OUTPUT_DIR`, `TASK_DATA_DIR` and `COVERAGE_FILE` pointed outside the
  repository, with `ALLOW_EXTERNAL_AI=false` and an empty API key.
- No model calls were made.

Labels: **VERIFIED** means confirmed in code or by running it. **INFERRED** is the
auditor's judgment. Line numbers refer to the audited commit.

## Executive summary

1. **The suite is healthy offline.** All 597 mocked tests pass in about 12 s with 90% coverage and no skips. All 24 CLI commands show their help.
2. **The safety design is sound.** There is a consent gate before any model call. Only reference files listed in the manifest with a matching SHA-256 can reach a model. Human approval is tied to file hashes, and recovery records are signed. No API keys were found in the files or the git history.
3. **The current pipeline has probably never run against a real model.** There is no `output/runs/` folder, and the ledger says no API key is configured. Real SOP quality is unknown.
4. **The biggest technical risk is `temperature`.** Every agent call sends it ([base_agent.py:133](../../src/agents/base_agent.py#L133)). That blocks a move to SDK 2.0+ or to any Claude 4.7+/5.x model. The default model is still Sonnet 4.6.
5. **Agent 3 is asked for a 15–30 page SOP in one 8,192-token reply, with no streaming and a 120 s timeout.** If the reply is cut off, the run fails ([provider.py:100](../../src/utils/provider.py#L100)).
6. **The configuration has drifted.**
   - The pipeline uses `standards_mapping.yaml`, which cites ISO 27001:2013 for three processes.
   - `list-processes` shows a different list of standards.
   - Service Request Management silently falls back to generic KPIs (confirmed by running the code).
7. **Some agents differ from what CLAUDE.md describes.**
   - Abdullah has no knowledge file, and his chat-advice path is untested.
   - No process ever selects Agent 8.
   - Agent 4 can't be reached by English requests in chat.
8. **There is a lot of dead weight:**
   - about 15 unused methods
   - 9 scripts nothing calls
   - 7 orphaned or duplicate knowledge files
   - an unused SOP template
   - about 14 legacy docs that still describe the old 6- and 9-agent teams
9. **There are privacy gaps.**
   - `.gitignore` misses spreadsheets, email, CAD files and SQLite databases.
   - The README's `--output ./my-docs` example writes drafts, source excerpts and the recovery key into a folder Git doesn't ignore.
   - One script calls Anthropic with no consent gate.
10. **Top quick wins:**
    - stop sending `temperature`
    - fix the standards and KPI config
    - harden `.gitignore`
    - gate the intro script
    - archive the legacy docs

    The larger work is raising Agent 3's output capacity, then a model upgrade with a live evaluation of the real prompts.

---

## Phase 1: Inventory

### 1. Folder map

| Folder | Purpose |
|---|---|
| `src/agents/` | Abdullah (leader), Ahmad (secretary), and Agents 1–9 |
| `src/utils/` | Config, provider, runs, approvals, recovery, contracts, tasks, CAD and quality checks |
| `src/formatters/` | Markdown, HTML, DOCX and PDF export, Arabic/RTL typography |
| `src/knowledge/` | 18 knowledge `.md` files, retrieval, legacy ITOM parsers |
| `src/templates/` | `sop_template.md`, which is loaded but never used |
| `config/` | 6 YAML catalogs: agents, routes, processes, standards, document profile, specialist policy |
| `tests/` | 21 files: 272 test functions, 597 cases including parametrized ones |
| `scripts/` | Dev launcher, export/package checkers, evaluation harness, legacy conversion/generation scripts |
| `docs/` | Architecture, guides, reports, project scope, migration, development notes |
| `evaluations/v1/` | Synthetic 22-case, 11-role benchmark |
| `references/` (ignored) | Customer source documents; no `manifest.yaml`, so nothing is authorized |
| `output/` (ignored, 83 MB) | Legacy customer deliverables mixed with QA evidence; no `runs/` |
| `logs/` (ignored, 165 files, 10 MB) | One new file per program start, never rotated |
| `diagrams/` (ignored) | draw.io sources |
| `.github/workflows/` | CI that can't run any more, since there is no remote |
| `.local-baseline/`, `build/`, `reema.egg-info/`, `__pycache__/` | Stale backups and build output |
| `.venv/` | Locked environment, Python 3.14.2 |

### 2. Dead, duplicate, legacy and orphaned items

**Code (all VERIFIED by searching for callers)**

- Ahmad's three legacy helpers are called only by tests: `coordinate_delivery`, `prepare_owner_briefing` and `coordinate_team_communication` ([secretary_agent.py:79](../../src/agents/secretary_agent.py#L79), [:161](../../src/agents/secretary_agent.py#L161), [:246](../../src/agents/secretary_agent.py#L246)).
- The standalone SOP generators are called only by tests ([access_agent.py:134](../../src/agents/access_agent.py#L134), [problem_agent.py:241](../../src/agents/problem_agent.py#L241)).
- These methods are never called at all:
  - `_build_compliance_validation_prompt` ([access_agent.py:485](../../src/agents/access_agent.py#L485), [problem_agent.py:691](../../src/agents/problem_agent.py#L691))
  - `_check_compliance` ([access_agent.py:535](../../src/agents/access_agent.py#L535))
  - `_check_problem_compliance` ([problem_agent.py:766](../../src/agents/problem_agent.py#L766))
  - `_build_review_prompt` ([review_agent.py:137](../../src/agents/review_agent.py#L137))
- `_parse_review_response` and its helpers are called only by [test_phase01.py:321](../../tests/test_phase01.py#L321). `completeness_threshold` is unused ([review_agent.py:41](../../src/agents/review_agent.py#L41)).
- `generate_drawio_flowchart` is called only by tests. It also hardcodes the customer's brand colours in a tracked file ([content_agent.py:399](../../src/agents/content_agent.py#L399), [:406](../../src/agents/content_agent.py#L406), [:428](../../src/agents/content_agent.py#L428), [:431](../../src/agents/content_agent.py#L431)).
- The ITOM loaders are never called, so their context is always empty ([research_agent.py:42](../../src/agents/research_agent.py#L42), [:169](../../src/agents/research_agent.py#L169), [problem_agent.py:57](../../src/agents/problem_agent.py#L57)). The parsers they would use read `references/itom/ITOM.pdf` directly, bypassing the manifest ([itom_parser.py:9](../../src/knowledge/itom_parser.py#L9)). That bypass is latent: INFERRED risk.
- `_inject_knowledge` throws away its `knowledge_intro` argument ([base_agent.py:89-101](../../src/agents/base_agent.py#L89-L101)). Every "100% domain expertise" string is therefore dead text (for example [research_agent.py:108](../../src/agents/research_agent.py#L108)).
- `sop_template` is loaded and never used ([content_agent.py:40](../../src/agents/content_agent.py#L40)), so `src/templates/sop_template.md` is orphaned.
- Agent 5 loads a 2,814-line knowledge file but makes no model calls ([format_agent.py:35-38](../../src/agents/format_agent.py#L35-L38)).
- The package version is `"1.0.0"` in code ([src/\_\_init\_\_.py:3](../../src/__init__.py#L3)) but `2.0.0` in [pyproject.toml:7](../../pyproject.toml#L7), the Dockerfile and the README.

**Knowledge files (VERIFIED)**

- `abdullah_leader_knowledge.md` is never loaded, because `LeaderAgent` has no knowledge file ([leader_agent.py:62-94](../../src/agents/leader_agent.py#L62-L94)).
- `agent_knowledge_2026.md` is referenced nowhere.
- These are superseded by their `_ENHANCED` versions and unused: `ahmad_secretary_knowledge.md`, `bee_format_knowledge.md`, `faisal_review_knowledge.md`, `mohammad_standards_knowledge.md`, `saad_content_knowledge.md`.
- `layla_data_knowledge.md` is only a fallback ([data_agent.py:53](../../src/agents/data_agent.py#L53)).

**Scripts with no references (VERIFIED)**

- `conversion/Convert-to-DOCX-PDF.ps1`
- `Create-Documents-Simple.py`
- `convert_to_formats.py`
- `extract_docx.py` and `transformation/modify_sop_v2.py`: hardcoded customer output paths
- `generate_full_html.py`: retired agent names
- `generation/render_cad_preview.py`
- `utilities/agent_introductions.py`
- `utilities/verify_agent_knowledge.sh`: checks the unused non-ENHANCED files, always prints success, and suggests a command that now fails

Separately, `generation/generate_workstation_patches.py` is referenced only by legacy docs. It calls `generate_documentation` without consent ([:77](../../scripts/generation/generate_workstation_patches.py#L77)), so it fails unless `ALLOW_EXTERNAL_AI=true`.

**Docs describing things that no longer exist (VERIFIED)**

- `docs/architecture/NEW_HIERARCHY_WITH_LAYLA.md` and `REEMA_HIERARCHY.md`: the 9-agent hierarchy with Norah as secretary.
- [ARCHITECTURE.md:84-322](../architecture/ARCHITECTURE.md#L84-L322): diagrams use retired names. Line 146 shows `ITOM.pdf` feeding research directly.
- `QUICKSTART.md` duplicates `QUICK_START.md`.
- The Workstation Patches one-offs (`QUICK_START.md`, `START_HERE.txt`, `SETUP_INSTRUCTIONS.md`, `README_WORKSTATION_PATCHES.md`) describe 6 agents and Python 3.9.
- Reports `IMPLEMENTATION_COMPLETE.md`, `LAYLA_EXPERTISE_SUMMARY.md` and both `AGENT_KNOWLEDGE_*` describe the old team. So does `SCOPE_OF_WORK.md` (9 agents; 45 retired-name mentions).
- `PACKAGE5_WORKING_CHECKPOINT.md` is superseded by the ledger.
- [docs/README.md:10-23](../README.md#L10-L23) doesn't list the Package 5 docs.

**Other**

- Config: `min_quality_for_delivery` is used only by Ahmad's legacy helper ([config.py:29](../../src/utils/config.py#L29)). `ci.yml` can't run without a remote.
- Repo root:
  - `CLAUDE.md.bak` and `AGENTS.md.bak`
  - a stale `.coverage`
  - three `End_User_Technology_*.docx` customer files, sitting outside `references/` and `output/` and ignored only by the `*.docx` rule

### 3. CLI commands (help output only)

All 24 commands exit 0 on `--help` (VERIFIED):

- **Top level:** `agents`, `chat`, `generate`, `resume`, `approve`, `reject`, `list-processes`, `status`, `version`
- **`task`:** `add`, `list`, `today`, `show`, `upcoming`, `edit`, `set-status`
- **`memory`:** `set`, `list`, `forget`
- **`drawing`:** `inspect`, `concept`

The three group commands (`task`, `memory`, `drawing`) also show help on their own.

Side effect: importing the app creates a new log file even for `--help` ([logger.py:21-28](../../src/utils/logger.py#L21-L28)). That is why there are 165 log files.

---

## Phase 2: Agent capability map

| Agent | Code | What it actually does | Model calls | Knowledge loaded | Tests |
|---|---|---|---|---|---|
| **Ahmad** | `SecretaryAgent` + `AssistantSession` | Local SQLite tasks and memory; chat planning by keyword rules; optional intent pass; final reply | Final reply; optional intent pass | `ahmad_secretary_knowledge_ENHANCED.md` | assistant_memory, personal_assistant, coordination, completion, contracts |
| **Abdullah** | `LeaderAgent` (not a `BaseAgent`) | 8-phase pipeline, recovery, consultations; planning is rule-based | Only in chat advice ([:1045](../../src/agents/leader_agent.py#L1045)) | **None** | pipeline, phase01, coordination, evaluation |
| **Agent 1** | `ResearchAgent` | Research plus claim/evidence report with an as-of date | 1 per run | `taif_research_knowledge_ENHANCED.md` | 10 files, 76% coverage |
| **Agent 2** | `StandardsAgent` | Control register checked against every framework | 1 per run | `mohammad_standards_knowledge_ENHANCED.md` | 6 files, 99% |
| **Agent 3** | `ContentAgent` | Full SOP; section patches tied to a document hash; legacy full rewrite | 1 or more | `saad_content_knowledge_ENHANCED.md` | 8 files, 97% |
| **Agent 4** | `ReviewAgent` | Chunked review with located findings; score = lowest chunk score; recheck | 1 per chunk | `faisal_review_knowledge_ENHANCED.md` | 8 files, 75% |
| **Agent 5** | `FormatAgent` | Deterministic MD/HTML/DOCX/PDF export plus export checks | None | `bee_…_ENHANCED.md` (unused) | 6 files, 95% |
| **Agent 6** | `AccessAgent` | IAM analysis plus deterministic snapshot, drift and separation-of-duties checks; appendix; compliance check | 3 | `rakan_access_knowledge_ENHANCED.md` | 7 files, 84% |
| **Agent 7** | `ProblemAgent` | Competing hypotheses plus case assessment; appendix; compliance check | 3 | `abeer_problem_knowledge_ENHANCED.md` | 6 files, 73% |
| **Agent 8** | `DataAgent` | Metric specs plus deterministic calculations; dashboard appendix | 2 | `layla_data_knowledge_complete.md` | 7 files, 93% |
| **Agent 9** | `BuildingDesignAgent` | DWG header check; DXF to OBJ/PNG concept mesh; chat advice | Chat only | None | building_design, specialist |

No other agents exist. The evaluation harness uses its own short role prompts ([evaluations/v1/prompts.json](../../evaluations/v1/prompts.json)), not the production prompts.

### Notes per agent

- **Ahmad.**
  - The three legacy helpers are dead.
  - Chat keeps only the last 6 messages ([assistant.py:422](../../src/assistant.py#L422)).
  - Tasks can be archived but never deleted; only memories can be deleted ([tasks.py:242-258](../../src/utils/tasks.py#L242-L258)).
  - His active knowledge file mentions the retired agent names 218 times and the old owner agent or "Khalid" 78 times. A system note partly offsets this ([base_agent.py:134](../../src/agents/base_agent.py#L134)). All VERIFIED.
- **Abdullah.**
  - CLAUDE.md gives him strategy, governance and business-value responsibilities. In code those are only the specialization strings from config.
  - Chat advice hardcodes `max_tokens=4096` ([leader_agent.py:1055](../../src/agents/leader_agent.py#L1055)) and is not covered by any test (lines 1047–1060).
  - The docstring still names retired agents ([:1-12](../../src/agents/leader_agent.py#L1-L12)).
  - All VERIFIED.
- **Agent 3.**
  - The prompt asks for 20–30 pages ([content_agent.py:277-318](../../src/agents/content_agent.py#L277-L318)) but output is capped at 8,192 tokens ([agent_config.yaml:116](../../config/agent_config.yaml#L116)).
  - The system prompt claims draw.io XML generation ([:247-248](../../src/agents/content_agent.py#L247-L248)), which contradicts [document_profile.yaml:37](../../config/document_profile.yaml#L37) ("do not … encode XML").
  - VERIFIED; the impact on page count is INFERRED.
- **Agent 4.** Its review gate labels drafts `"APPROVED"` ([review_agent.py:79](../../src/agents/review_agent.py#L79)). That is a model quality gate, but the word is easy to confuse with human approval (INFERRED). Chat only routes to it on Arabic keywords ([assistant_routes.yaml:138-142](../../config/assistant_routes.yaml#L138-L142)) (VERIFIED).
- **Agents 6 and 7.** They join automatically only for Access, Incident and Problem Management ([process_definitions.yaml:5](../../config/process_definitions.yaml#L5), [:26](../../config/process_definitions.yaml#L26), [:162](../../config/process_definitions.yaml#L162)). The chat keywords "access" and "security" are broad ([assistant_routes.yaml:45](../../config/assistant_routes.yaml#L45), [:51](../../config/assistant_routes.yaml#L51)) and will catch unrelated requests (INFERRED).
- **Agent 8.** No process selects it (VERIFIED by running). It joins only through `--specialist data` or metric input. Config calls it a "Power BI specialist", while CLAUDE.md says "metrics and analytics design".
- **Agent 9.** Config describes it as "Building 3D Modeling & Interior/Exterior Design Specialist" ([agent_config.yaml:153](../../config/agent_config.yaml#L153)), which overstates what it builds: bounded concept meshes. It has no `_build_system_prompt` and no knowledge file, and it is outside the SOP pipeline (as documented).

---

## Phase 3: Gap analysis

### Docs vs code

- README problems (all VERIFIED):
  - [README.md:104](../../README.md#L104): stale Windows path
  - [:226-231](../../README.md#L226-L231): the process list omits 2 of the 16 processes
  - [:412](../../README.md#L412): `pip install -r requirements.txt` instead of `dev.py`
  - [:475](../../README.md#L475): tells you to provide `ITOM.pdf`, which contradicts manifest gating
  - [:479](../../README.md#L479): "Internal use only" contradicts the MIT licence in [pyproject.toml:10](../../pyproject.toml#L10)
- CLAUDE.md says Agents 6–8 join "when selected by a process", but no process selects Agent 8 (VERIFIED).
- [PENDING_LEDGER.md:46](PENDING_LEDGER.md#L46) says no actionable software task remains; this audit found several (INFERRED).

### Pipeline

- **KPIs.** The lookup key `"service_request"` never matches the name "Service Request Management", so generic KPIs are used ([leader_agent.py:659](../../src/agents/leader_agent.py#L659), [:669-672](../../src/agents/leader_agent.py#L669-L672)). VERIFIED by running.
- **Standards.** Two sources disagree. The pipeline uses `standards_mapping`, while `list-processes` shows `process_definitions` ([leader_agent.py:580](../../src/agents/leader_agent.py#L580) vs [main.py:528](../../src/main.py#L528)). ISO 27001:2013 appears at [standards_mapping.yaml:53](../../config/standards_mapping.yaml#L53), [:59](../../config/standards_mapping.yaml#L59) and [:67](../../config/standards_mapping.yaml#L67), while other processes and the knowledge files use 2022. VERIFIED.
- **Review cycles.** If a legacy or custom reviewer passes on the final cycle but returns rewritten content, the run fails ([leader_agent.py:902-907](../../src/agents/leader_agent.py#L902-L907), [:953](../../src/agents/leader_agent.py#L953)). VERIFIED by reading the logic. The current reviewer returns `None`, so it isn't affected.
- **Rejection.** A rejected draft's notes can't be passed into a new run (INFERRED).
- **Approval records.** They store absolute paths, so moving a run folder breaks approval ([approvals.py:61](../../src/utils/approvals.py#L61)). A stale `.lock` file blocks future decisions if the process is killed hard ([:81-83](../../src/utils/approvals.py#L81-L83)). Both INFERRED.

### Tests

- Coverage is lowest in [main.py](../../src/main.py) (69%: drawing, task, memory and agents commands, and the interactive chat loop), `problem_agent` (73%), `review_agent` (75%) and `research_agent` (76%). VERIFIED.
- Weak assertions: [test_agent_contracts.py:41](../../tests/test_agent_contracts.py#L41), [test_agents.py:135](../../tests/test_agents.py#L135), [test_base_agent.py:14](../../tests/test_base_agent.py#L14), [test_config.py:33-36](../../tests/test_config.py#L33-L36), [test_pipeline.py:171](../../tests/test_pipeline.py#L171). VERIFIED.
- One warning about an unclosed SQLite connection comes from `test_tampered_recovery_records_are_rejected_before_reuse[drafted.json]`. It is VERIFIED; the source is probably [tasks.py:66-84](../../src/utils/tasks.py#L66-L84) (INFERRED).
- Untested edge cases: a truncated reply, a timeout on long generation, and the page-target enforcement branch ([leader_agent.py:495-503](../../src/agents/leader_agent.py#L495-L503)). VERIFIED by coverage.

### Error handling, logging and config

- A failed client setup is silently swallowed ([base_agent.py:59-62](../../src/agents/base_agent.py#L59-L62)).
- `generate` catches every exception broadly ([main.py:419](../../src/main.py#L419)).
- `.env` is read from the current directory, not the project root ([config.py:67](../../src/utils/config.py#L67)).
- Tests write synthetic ERROR lines into the real `logs/` folder, about 2,300 for Abdullah alone, because nothing redirects `LOG_DIR`.
- Docker uses Python 3.11 while `.venv` uses 3.14.2 ([Dockerfile:10](../../Dockerfile#L10)).
- All VERIFIED.

### Security and privacy

- **`.gitignore` gaps.** `.xlsx`, `.csv`, `.msg`, `.dwg`, `.dxf`, `.drawio`, `.sqlite3` and `.recovery-key` are not ignored outside `references/` and `output/`. VERIFIED with `git check-ignore`.
- **README example.** `--output ./my-docs` ([README.md:166](../../README.md#L166)) leaves run checkpoints, Markdown drafts and the HMAC key unignored. VERIFIED.
- **Customer content in tracked files.** The customer name appears 18 times in a tracked knowledge file, contrary to the comment at [.gitignore:43](../../.gitignore#L43). Customer-specific scripts are ignored by an explicit name list, so any new one would not be ignored. VERIFIED.
- **Consent bypass.** [agent_introductions.py:9-14](../../scripts/utilities/agent_introductions.py#L9-L14) and [:103](../../scripts/utilities/agent_introductions.py#L103) call Anthropic with no consent gate (VERIFIED). It sends only persona text, so the risk is low.
- **Chat.** The session context is updated before the consent check ([assistant.py:347-355](../../src/assistant.py#L347-L355)). That is session-only and low risk (INFERRED).
- **What is clean.** No keys in the files or history, and no customer files in the history. VERIFIED.

### Dependencies

- Unused runtime packages: `aiofiles`, `pandas` (which pulls in numpy), `openpyxl` and an explicit `python-dotenv` ([pyproject.toml:53](../../pyproject.toml#L53), [:64-68](../../pyproject.toml#L64-L68)). VERIFIED.
- `pyproject` uses open-ended `>=` ranges, but the three lock files hash-pin every package and agree with each other. VERIFIED.
- `anthropic==0.76.0` sends the 2023-06-01 API version. SDK 2.0.0 sends 2026-10-21, which rejects `temperature`, so upgrading requires removing it first. VERIFIED against the installed SDK and the API reference.
- Other packages were not checked against the internet, so "outdated" status is unknown.

### Knowledge files

- Seven are orphaned or duplicates (listed in Phase 1).
- Active files cite "ITIL v3" (Agent 1: 4 times, Agent 4: once) and "NCA ECC-1:2018" (Agent 2: twice, Agent 6: once). Whether those editions are current needs the owner's confirmation (INFERRED).
- The access knowledge file makes 28 "100%" expertise claims.

---

## Phase 4: Enhancements

Ordered by impact ÷ effort within each group (H = 3, M = 2, L = 1).

### Quick wins (low effort)

| # | Area | Finding | Recommendation | Impact | Effort | Risk | Reversible |
|---|---|---|---|---|---|---|---|
| 1 | Provider | `temperature` is always sent | Make it optional and off by default; keep only explicit overrides | H | L | Med: output changes on Sonnet 4.6 | Y |
| 2 | Config | 27001:2013; two standards lists | Update the edition; derive the `list-processes` display from `standards_mapping` | H | L | Med: different control register | Y |
| 3 | Privacy | `.gitignore` gaps; `my-docs` example | Ignore the sensitive extensions; refuse or warn on output folders Git doesn't ignore; fix the README | H | L | Low | Y |
| 4 | Pipeline | Service Request KPIs fall back to generic | Normalize the lookup key; add a test | M | L | Low | Y |
| 5 | Routing | Agent 4 has no English keywords | Add "review", "proofread" and similar | M | L | Low | Y |
| 6 | Security | Intro script bypasses consent | Gate it behind `--allow-external-ai` or archive it | M | L | Low | Y |
| 7 | Logging | Log file created on import; tests pollute `logs/` | Create the log file on first write; set `LOG_DIR` to a temp folder in conftest; add rotation | M | L | Low | Y |
| 8 | Docs | README errors; legacy docs | Fix the 5 README errors; move legacy docs to `docs/archive/` with a banner; update the index | M | L | Low | Y |
| 9 | Privacy | Tasks can't be deleted | Add `task delete` (secure_delete is already on) | M | L | Low | N (deletes data) |
| 10 | CI | GitHub CI is orphaned | Replace it with a local `dev.py check` command or a pre-commit hook | M | L | Low | Y |
| 11 | Hygiene | Version mismatch; unused packages | Read the version from package metadata; drop 4 packages and relock | L | L | Low | Y |
| 12 | Pipeline | Final-cycle rewrite fails the run | Accept the rewrite or re-review it on the last cycle | L | L | Low | Y |
| 13 | Tests | Weak assertions; unclosed connection | Strengthen the 5 assertions; close on setup failure | L | L | Low | Y |
| 14 | Hygiene | Root clutter | Move the root `.docx` files; remove `.bak`, `build/`, egg-info and the stale `.coverage` | L | L | Low | N if deleted |

### Larger work

| # | Area | Finding | Recommendation | Impact | Effort | Risk | Reversible |
|---|---|---|---|---|---|---|---|
| 15 | Generation | 8,192-token cap vs 15–30 pages | Generate per section, or stream with a higher cap; tune the timeout to match | H | M | Med: cost | Y |
| 16 | Model | Sonnet 4.6 default | After #1, evaluate `claude-sonnet-5-5` or `claude-opus-5-5`, then switch the default | H | M | Med: cost and behaviour | Y |
| 17 | Dead code | ~15 methods, ITOM parsers, drawio generator | Remove them or mark them deprecated, along with their tests | M | M | Med: public API compatibility | Y (git) |
| 18 | Abdullah | No knowledge file; untested chat path | Load the leader knowledge file or drop the claims; use config `max_tokens`; add tests | M | M | Low | Y |
| 19 | Tests | CLI at 69% | Add CliRunner tests for drawing, task, memory, agents and chat | M | M | Low | Y |
| 20 | Workflow | Rejection is a dead end | Add a `--revise-from approval.json` option that passes the notes in | M | M | Low | Y |
| 21 | Evaluation | Benchmark prompts aren't production prompts | Build an evaluation that runs the real agent prompts and retrieval | H | H | Med: paid runs need consent | Y |
| 22 | Cost | No prompt caching | Cache the stable system prompt and knowledge prefix across review chunks | L | M | Low | Y |
| 23 | Approval | Absolute paths; unsigned record | Store relative paths; sign the record with the existing HMAC key | L | M | Low | Y |

---

## Phase 5: Open questions

1. Can the agents drop `temperature`? It's needed for Claude 4.7+ models and SDK 2.0. Which model should be the new default?
2. Which ISO 27001 and NCA ECC editions should the SOPs target?
3. Should Compliance Checks & Audits use Saudi frameworks (NCA ECC, SAMA, PDPL) instead of, or as well as, GDPR, HIPAA and PCI DSS?
4. Which licence is right: MIT or internal use only?
5. May the legacy public methods and the duplicate knowledge files be removed? CLAUDE.md asks for the public API to stay compatible and for the knowledge-base names to be preserved.
6. Where should the three root `End_User_Technology_*.docx` files and the legacy customer deliverables in `output/` live?
7. Should any process select Agent 8 automatically, for example Monitoring & Control?
8. Should Abdullah use `abdullah_leader_knowledge.md`, or is his strategy role meant to stay config-only?
9. Is 15–30 pages still the target?
10. Should old logs, `.local-baseline/` and `.github/` be kept?
11. The coding agent's local memory notes (outside this repository) are stale: they say Python 3.9+ and an "Access managment" folder at the root. May they be updated?
12. Things the audit couldn't determine:
    - real model output quality
    - Docker and Windows PDF rendering
    - whether non-Anthropic packages are outdated (no network check)
    - the contents of `references/`, which were not opened, by design

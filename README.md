# REEMA - Personal Coordination and IT Documentation

**REEMA** coordinates local work and personal tasks, offers a single conversational
entry point through Ahmad, and retains its IT documentation specialists. The
conversational and document-generation features use Anthropic's Claude API only
after explicit authorization; local task commands work without an API key.

Start with the [personal assistant guide](docs/guides/PERSONAL_ASSISTANT.md) for
the current scope, task commands, chat, and connection limits.
The [implementation checkpoint](docs/reports/PERSONAL_ASSISTANT_CHECKPOINT.md)
records what was verified and what still needs an account connection.
The [building-design checkpoint](docs/reports/BUILDING_DESIGN_CHECKPOINT.md)
records Agent 9's current capability and the CAD-to-3D work still needed.
The [agent improvements checkpoint](docs/reports/AGENT_IMPROVEMENTS_PACKAGE_1.md)
records complete specialist handoffs, validated contracts, accurate phase status
and offline evaluation baselines. See [handoffs and status](docs/guides/AGENT_HANDOFFS_AND_STATUS.md)
for the intentional legacy status corrections and current limits.
The [coordination and recovery guide](docs/guides/COORDINATION_AND_RECOVERY.md)
describes multi-specialist advice, explicit session decisions and verified
research/generation recovery. See [package 2](docs/reports/AGENT_IMPROVEMENTS_PACKAGE_2.md)
for verification and remaining work.
The [document quality guide](docs/guides/DOCUMENT_QUALITY.md) and
[package 3 checkpoint](docs/reports/AGENT_IMPROVEMENTS_PACKAGE_3.md) cover located
controls, configured sections, targeted corrections and export verification.
The [development setup guide](docs/guides/DEVELOPMENT_SETUP.md) removes temporary
test paths and manual native-library flags from normal local workflows.
[Specialist evidence and checks](docs/guides/SPECIALIST_EVIDENCE_AND_CHECKS.md) and
[package 4](docs/reports/AGENT_IMPROVEMENTS_PACKAGE_4.md) cover the next five specialists.
The [package 5 guide](docs/guides/COMPLETION_AND_EVALUATION.md),
[completion report](docs/reports/AGENT_IMPROVEMENTS_PACKAGE_5.md) and
[finite ledger](docs/reports/PENDING_LEDGER.md) cover bilingual intent, hard-crash
and review-chunk recovery, Arabic/RTL diagrams and layouts, bounded specialist
depth and the consent-ready synthetic evaluation.

## Working with coding agents

This repository includes [CLAUDE.md](CLAUDE.md), which gives any coding agent
(Claude Code, Codex, or others) focused, project-specific instructions for safe
maintenance and enhancement. [AGENTS.md](AGENTS.md) is only a pointer to
CLAUDE.md. Neither file changes the application's current Claude runtime. For
the staged plan to improve the system or migrate the application to another LLM
provider, see
[docs/migration/CODEX_ADOPTION.md](docs/migration/CODEX_ADOPTION.md).

For the latest local verification and remaining requirements, see
[package 5](docs/reports/AGENT_IMPROVEMENTS_PACKAGE_5.md). Earlier reliability work
is recorded in the [phase checkpoint](docs/reports/PHASE_2_5_CHECKPOINT.md).

## Overview

This system provides 11 agent roles. Ahmad coordinates the user's tasks and
conversations; Abdullah leads specialist work. Generation runs use a leader, five core workers,
and only the specialists selected for the process. They produce draft Standard
Operating Procedures (SOPs) in multiple formats. The 15–30 page target warns by
default; `ENFORCE_PAGE_TARGET=true` makes it mandatory and requires PDF output.
Every successful run requires separate human approval.

### Key Features

- **Multi-Agent Architecture**: 11 coordinated roles, including Ahmad and Abdullah
- **Personal Task Lists**: Separate local work and personal tasks, priorities, due dates, and daily views
- **Persistent Personal Context**: Editable profiles, preferences, project goals, correction lessons, and matching examples shared with Ahmad and specialists
- **Conversational Coordination**: Ahmad uses bounded request plans and Abdullah-led multi-specialist consultations
- **Standards Review**: Structured checks and gap findings, not compliance certification
- **Multi-Format Output**: PDF, Word (DOCX), Markdown, and HTML
- **Source-Aware**: Retrieves traceable excerpts from explicitly authorized references
- **Quality Gates**: Required sections, configured review threshold, validated exports, and human approval
- **Customizable**: Configurable processes, standards, and output formats

## Agent Team

Ahmad is the user's main coordinator. Abdullah leads the specialist agents.
The former Khalid owner agent was removed; its strategy, governance, quality,
and business-value guidance now belongs to Abdullah. The user retains approval
and decision authority. Run `python3 scripts/dev.py run agents` for the active roster.

| Agent | Current responsibility |
| --- | --- |
| Ahmad | Main coordinator for tasks, preferences, planning, and conversations |
| Abdullah | Strategic leader and specialist orchestrator |
| Agent 1 | Research and IT service practices |
| Agent 2 | Standards and control alignment for human verification |
| Agent 3 | Writing and SOP content |
| Agent 4 | Quality review |
| Agent 5 | PDF, DOCX, Markdown, and HTML formatting |
| Agent 6 | Access and identity security |
| Agent 7 | Problem management and root-cause analysis |
| Agent 8 | Analytics and KPI design |
| Agent 9 | Building-design advice, local DWG intake, and assumption-labeled concept meshes from selected DXF wall linework |

## Installation

### Prerequisites

- Python 3.11–3.14
- Anthropic API key and explicit input authorization for chat or generation
- Optional references explicitly permitted in `references/manifest.yaml`
- Native Pango libraries for PDF output; the Docker image includes them

### Setup

1. **Clone or navigate to the project directory:**
```bash
cd "C:\Users\Khali\Desktop\Projects\IT Consultant"
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

3. **Set your Anthropic API key for authorized model features:**

Windows:
```bash
set ANTHROPIC_API_KEY=your-api-key-here
```

Linux/Mac:
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Or create a `.env` file:
```
ANTHROPIC_API_KEY=your-api-key-here
```

## Usage

### Command Line Interface

The system provides a user-friendly CLI powered by Typer and Rich.

#### Generate Documentation

Generate documentation for a specific IT process:

```bash
python3 scripts/dev.py run generate "Incident Management" -f markdown --allow-external-ai
```

Specify output formats:

```bash
python3 scripts/dev.py run generate "Change Management" --format pdf --format docx --allow-external-ai
```

All formats:

```bash
python3 scripts/dev.py run generate "Problem Management" -f pdf -f docx -f markdown -f html --allow-external-ai
```

Custom output directory:

```bash
python3 scripts/dev.py run generate "Service Request Management" --output ./output/my-docs --allow-external-ai
```

Keep custom output folders under `output/` or another Git-ignored path. Drafts,
run checkpoints and source excerpts are written there; `generate` and `resume`
print a warning when the folder is inside the repository but not ignored.

`--allow-external-ai` explicitly authorizes sending this run's inputs, selected
reference excerpts, and agent knowledge to Anthropic. Review the material first;
see [Data handling](docs/guides/DATA_HANDLING.md). It is disabled by default.
`ALLOW_EXTERNAL_AI=true` is a persistent alternative only for a pre-authorized
environment. Unknown process names fail unless `--custom` is supplied. Additional
specialists can be selected with `--specialist access`, `problem`, or `data`.
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

#### Recover exports without model calls

Each run saves phase checkpoints and usage metadata in its own directory. If a
run reached `ready.json` but export failed, regenerate the exports offline:

```bash
python3 scripts/dev.py run resume output/runs/<run-id> -f markdown -f docx
```

This validates the checkpoint hash and current quality threshold, creates a new
run, and requires a fresh human decision. It needs no API key or external-AI
consent. Failed/cancelled new runs with completed research or generation can use
verified model-phase recovery, with fresh explicit authorization:

```bash
python3 scripts/dev.py run resume output/runs/<run-id> --model-phases --allow-external-ai
```

This preserves original inputs/formats, rechecks configuration and source
permissions, carries prior usage into the budget, and creates a new pending human
record. See [Coordination and recovery](docs/guides/COORDINATION_AND_RECOVERY.md)
for the supported checkpoints, private recovery key and practical limits.

#### List Available Processes

View all IT processes that can be documented:

```bash
python3 scripts/dev.py run list-processes
```

Available processes include:
- **ITIL Core**: Incident, Change, Problem, Service Request Management
- **ITOM**: Event Management, Infrastructure Operations, Monitoring & Control
- **ITAM**: Hardware, Software, License Management
- **Security & Compliance**: Security Operations, Compliance Audits, Risk Management
- **Custom**: Devices Batch Management

#### Check System Status

View system configuration and status:

```bash
python3 scripts/dev.py run status
```

#### Version Information

```bash
python3 scripts/dev.py run version
```

## Project Structure

```
IT-Consultant/
├── AGENTS.md                      # Pointer to CLAUDE.md
├── CLAUDE.md                      # Project context and agent working rules (source of truth)
├── README.md                      # This file
├── pyproject.toml                 # Package and test configuration
├── requirements.txt               # Python dependencies
├── config/                        # Agent, process, and standards YAML
├── src/                           # Main REEMA application
│   ├── agents/                    # Management and worker agents
│   ├── formatters/                # PDF, DOCX, Markdown, and HTML output
│   ├── knowledge/                 # Curated agent knowledge and parsers
│   ├── templates/                 # Application templates
│   └── utils/                     # Configuration and logging
├── tests/                         # Automated tests
├── docs/                          # Architecture, guides, reports, migration
├── scripts/                       # Generation, conversion, and transformation tools
├── references/                    # Local source documents and templates
│   └── itom/                      # ITOM.pdf and ITOM.docx
├── diagrams/                      # Draw.io source diagrams
├── output/                        # Generated documents (Git ignored)
└── logs/                          # Runtime logs (Git ignored)
```

## Configuration

### Agent Configuration

Edit `config/agent_config.yaml` to customize agent behavior:

```yaml
research_agent:
  model: "claude-sonnet-4-6"
  max_tokens: 4096
  # temperature: 0.5   # optional override; omitted by default
```

Shipped roles send no `temperature`, so the model's default sampling applies.
A per-role `temperature` (0–1) is sent only when set explicitly; API version
2026-10-21 and Claude 4.7+ models reject non-default values.

Shipped roles inherit `LEADER_MODEL` or `WORKER_MODEL`, defaulting to
`claude-sonnet-4-6`. An explicit per-role `model` takes precedence. Existing user
overrides are preserved; a retired override needs a deliberate replacement.
The benchmark and runtime use the same selection rule. See the
[current guide](docs/guides/COMPLETION_AND_EVALUATION.md) for lifecycle/pricing
sources and the exact synthetic live-evaluation authorization gate.

### Process Definitions

Add or modify IT processes in `config/process_definitions.yaml`:

```yaml
custom_process:
  name: "My Custom Process"
  category: "Custom"
  description: "What the process achieves"
  complexity: "medium"
  estimated_pages: 20
```

### Standards Mapping

`config/standards_mapping.yaml` is the only source of a process's standards. The
pipeline and `list-processes` both read it, and every process ID needs an entry.
A `standards` list in `process_definitions.yaml` is rejected with an error.

Map processes to standards in `config/standards_mapping.yaml`:

```yaml
custom_process:
  - "ITIL v4 Practice Name"
  - "ISO Standard"
```

## Output Formats

### PDF
- Professional, print-ready documents
- Headers, footers, page numbers
- Preserves supplied document headings
- Professional styling

### Microsoft Word (DOCX)
- Editable documents
- Professional formatting
- Tables and lists
- Ready for customization

### Markdown
- Version control friendly
- Plain text format
- Easy to edit and share
- Compatible with Git

### HTML
- Web publishing ready
- Responsive design
- Professional styling
- Can be hosted online

## Document Structure

Each generated SOP includes 11 comprehensive sections:

1. **Introduction**: Purpose, scope, objectives
2. **Definitions & Acronyms**: Complete glossary
3. **Roles & Responsibilities**: RACI matrix and role descriptions
4. **Process Overview**: High-level description
5. **Detailed Procedures**: Step-by-step instructions
6. **Process Flow Diagrams**: Visual workflow descriptions
7. **Key Performance Indicators**: Metrics and KPIs
8. **Tools & Systems**: Required technology
9. **Compliance & Standards**: Framework alignment
10. **Appendices**: Templates, forms, checklists
11. **Document Control**: Version history, approvals

## Examples

### Example 1: Generate Incident Management SOP

```bash
python3 scripts/dev.py run generate "Incident Management" -f pdf -f docx --allow-external-ai
```

Output:
- `output/runs/<run-id>/pdf/Incident_Management_SOP.pdf`
- `output/runs/<run-id>/docx/Incident_Management_SOP.docx`

### Example 2: Generate All ITIL Core Processes

```bash
python3 scripts/dev.py run generate "Incident Management" --allow-external-ai
python3 scripts/dev.py run generate "Change Management" --allow-external-ai
python3 scripts/dev.py run generate "Problem Management" --allow-external-ai
python3 scripts/dev.py run generate "Service Request Management" --allow-external-ai
```

### Example 3: Custom Device Management Process

```bash
python3 scripts/dev.py run generate "Devices Batch Management" -f pdf -f html --allow-external-ai
```

## Troubleshooting

### API Key Issues

If you see "API key not set" error:

```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-...

# Linux/Mac
export ANTHROPIC_API_KEY='sk-ant-...'
```

### ITOM.pdf Not Found

Placing a file in `references/itom/` does not authorize it. Add its relative path,
classification, SHA-256, and explicit permission to `references/manifest.yaml`.
See the [source setup guide](docs/guides/RELIABILITY_AND_SOURCES.md).

### Import Errors

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### Permission Errors

Ensure the output directory has write permissions:

```bash
chmod 755 output/
```

## Advanced Usage

### Python API

You can also use the system programmatically:

```python
import asyncio
from src.agents.leader_agent import LeaderAgent
from src.agents.research_agent import ResearchAgent
from src.agents.standards_agent import StandardsAgent
from src.agents.content_agent import ContentAgent
from src.agents.review_agent import ReviewAgent
from src.agents.format_agent import FormatAgent

async def generate_docs():
    # Initialize leader
    leader = LeaderAgent()

    # Register workers
    leader.register_worker("ResearchAgent", ResearchAgent())
    leader.register_worker("StandardsAgent", StandardsAgent())
    leader.register_worker("ContentAgent", ContentAgent())
    leader.register_worker("ReviewAgent", ReviewAgent())
    leader.register_worker("FormatAgent", FormatAgent())

    # Generate documentation
    # Requires ALLOW_EXTERNAL_AI=true only after authorizing the input material.
    try:
        return await leader.generate_documentation(
            "Incident Management", ["pdf", "docx"]
        )
    finally:
        await leader.close()

# Run
asyncio.run(generate_docs())
```

## Contributing

To add new IT processes:

1. Add process definition to `config/process_definitions.yaml`
2. Add standards mapping to `config/standards_mapping.yaml`
3. Run the system with your new process name

## Support

For issues or questions:
- Check the logs in `logs/` directory
- Review configuration files in `config/`
- Ensure `references/itom/ITOM.pdf` is present for enhanced results

## License

Internal use only - IT Process Documentation System

## Version

Version 2.0.0

---

**Generated by the IT Process Documentation Multi-Agent System**

Powered by Claude AI (Anthropic)

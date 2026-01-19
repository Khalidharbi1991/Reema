# REEMA - Multi-Agent Documentation System

## Project Overview
This is a sophisticated multi-agent AI system that automatically generates comprehensive IT process documentation. The system uses 6 specialized Claude AI agents working in a hierarchical leader-worker architecture to create professional Standard Operating Procedures (SOPs) that comply with ITIL, ITOM, ITAM, and other IT industry standards.

## Project Context
**Goal**: Automate the creation of IT process documentation for IT consultants and organizations.

**Scope**: The system can generate documentation for:
- ITIL Core Processes (Incident, Change, Problem, Service Request Management)
- IT Operations Management (ITOM) Processes
- IT Asset Management (ITAM) Processes
- Security & Compliance Processes
- Custom IT Processes (e.g., Devices Batch Management)

**Output**: 15-30 page SOP documents in PDF, Word (DOCX), Markdown, and HTML formats

## Technology Stack
- **Python 3.9+**: Core programming language
- **Anthropic Claude API**: LLM for each AI agent
- **Claude Agent SDK**: Multi-agent orchestration (simulated in this implementation)
- **Document Generation**:
  - python-docx: Word document generation
  - WeasyPrint: PDF generation from HTML
  - markdown2: Markdown processing
  - Jinja2: HTML templating
- **CLI Framework**: Typer + Rich for user interface
- **Configuration**: PyYAML, Pydantic
- **PDF Parsing**: PyPDF2, pdfplumber (for ITOM.pdf)

## Project Structure
```
src/
├── agents/          # 6 specialized AI agents
├── formatters/      # PDF, DOCX, Markdown, HTML converters
├── knowledge/       # ITOM.pdf parser and knowledge base
├── templates/       # SOP document templates
└── utils/           # Configuration and logging

config/              # YAML configuration files
output/              # Generated documents (PDF, DOCX, MD, HTML)
```

## Development Guidelines
- All agents inherit from base agent patterns
- Async/await for concurrent agent operations
- Rich console output for better UX
- Comprehensive error handling and logging
- YAML-based configuration (no hardcoding)
- Quality threshold: 85% for SOP approval

## Notes for Claude
- The system uses a hierarchical architecture: Abdullah (Leader) coordinates 5 worker agents
- Each agent has specific expertise (Taif-Research, Mohammad-Standards, Saad-Content, Faisal-Review, Bee-Format)
- ITOM.pdf is parsed and used as a knowledge base for research
- All output goes through quality review before final formatting
- The system is designed to be extensible - new processes can be added via config files

## Key Features
1. **Multi-Agent Coordination**: 6 specialized agents working collaboratively
2. **ITIL/ITOM Compliance**: Aligned with industry standards
3. **Multi-Format Output**: PDF, DOCX, Markdown, HTML
4. **Quality Assurance**: Automated review with 85% quality threshold
5. **Knowledge-Based**: Uses ITOM.pdf as reference material
6. **CLI Interface**: User-friendly command-line tool
7. **Configurable**: Easy to add new processes and standards

## Agent Architecture
- **Abdullah (Leader)**: Orchestrates workflow, coordinates workers, final QC
- **Taif (Research)**: ITIL/ITOM research, best practices, ITOM.pdf parsing
- **Mohammad (Standards)**: Compliance validation, regulatory requirements
- **Saad (Content)**: SOP writing (15-30 pages), RACI matrices, procedures
- **Faisal (Review)**: Quality scoring, technical validation, feedback
- **Bee (Format)**: Multi-format conversion (PDF/DOCX/MD/HTML)

## Setup Instructions
1. Install Python 3.9+
2. Create virtual environment: `python -m venv venv`
3. Activate: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux/Mac)
4. Install dependencies: `pip install -r requirements.txt`
5. Set API key: `export ANTHROPIC_API_KEY='your-key'`
6. Run: `python -m src.main generate "Incident Management"`

See QUICKSTART.md for detailed instructions.

## Important Files
- `src/main.py` - CLI entry point
- `src/agents/leader_agent.py` - Main orchestrator
- `config/process_definitions.yaml` - IT process catalog
- `config/agent_config.yaml` - Agent settings
- `config/standards_mapping.yaml` - Standards framework mapping
- `src/templates/sop_template.md` - SOP document template
- `ITOM.pdf` - Reference knowledge base (optional)

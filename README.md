# REEMA - IT Process Documentation Multi-Agent System

**REEMA** (Regulatory & Enterprise Management Automation) is a sophisticated multi-agent system powered by Claude AI that automatically generates comprehensive IT process documentation following ITIL, ITOM, and industry standards.

## Overview

This system uses a hierarchical leader-worker architecture with 6 specialized AI agents to create professional Standard Operating Procedures (SOPs) for IT processes. Each agent has specific expertise and works collaboratively to produce 15-30 page documents in multiple formats.

### Key Features

- **Multi-Agent Architecture**: 6 specialized agents working in coordination
- **ITIL/ITOM Compliance**: Aligned with industry standards and best practices
- **Multi-Format Output**: PDF, Word (DOCX), Markdown, and HTML
- **Knowledge-Based**: Utilizes your ITOM.pdf as a reference knowledge base
- **Professional Quality**: Publication-ready documentation with quality assurance
- **Customizable**: Configurable processes, standards, and output formats

## Agent Team

### 1. Abdullah (Leader/Orchestrator)
- Coordinates all worker agents
- Manages workflow and task assignment
- Performs final quality control
- Assembles output documents

### 2. Taif (Research Agent)
- Gathers ITIL and IT standards information
- References best practices
- Utilizes ITOM.pdf knowledge base
- Provides comprehensive research findings

### 3. Mohammad (Standards & Compliance)
- Ensures ITIL, ITOM, ISO compliance
- Validates regulatory requirements
- Maps processes to frameworks
- Creates compliance checklists

### 4. Saad (Content Generation)
- Creates 15-30 page SOP documents
- Writes detailed procedures and workflows
- Generates RACI matrices
- Develops all 11 SOP sections

### 5. Faisal (Review & Quality)
- Validates content accuracy
- Checks ITIL/standards alignment
- Provides quality scores (target >85%)
- Suggests improvements

### 6. Bee (Format & Export)
- Converts to PDF, DOCX, Markdown, HTML
- Applies professional formatting
- Creates headers, footers, TOC
- Manages document styling

## Installation

### Prerequisites

- Python 3.9 or higher
- Anthropic API key (Claude AI)
- ITOM.pdf file (optional, for enhanced knowledge base)

### Setup

1. **Clone or navigate to the project directory:**
```bash
cd "C:\Users\Khali\Desktop\Projects\IT Consultant"
```

2. **Create a virtual environment:**
```bash
python -m venv venv
```

3. **Activate the virtual environment:**

Windows:
```bash
venv\Scripts\activate
```

Linux/Mac:
```bash
source venv/bin/activate
```

4. **Install dependencies:**
```bash
pip install -r requirements.txt
```

5. **Set your Anthropic API key:**

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
python -m src.main generate "Incident Management"
```

Specify output formats:

```bash
python -m src.main generate "Change Management" --format pdf --format docx
```

All formats:

```bash
python -m src.main generate "Problem Management" -f pdf -f docx -f markdown -f html
```

Custom output directory:

```bash
python -m src.main generate "Service Request Management" --output ./my-docs
```

#### List Available Processes

View all IT processes that can be documented:

```bash
python -m src.main list-processes
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
python -m src.main status
```

#### Version Information

```bash
python -m src.main version
```

## Project Structure

```
IT-Consultant/
├── CLAUDE.MD                      # Project context
├── ITOM.pdf                       # Reference material
├── README.md                      # This file
├── requirements.txt               # Python dependencies
│
├── src/
│   ├── __init__.py
│   ├── main.py                    # CLI entry point
│   │
│   ├── agents/                    # Agent modules
│   │   ├── leader_agent.py        # Orchestrator
│   │   ├── research_agent.py      # Research specialist
│   │   ├── standards_agent.py     # Compliance specialist
│   │   ├── content_agent.py       # Content generator
│   │   ├── review_agent.py        # Quality reviewer
│   │   └── format_agent.py        # Format converter
│   │
│   ├── knowledge/                 # Knowledge base
│   │   └── itom_parser.py         # ITOM.pdf parser
│   │
│   ├── templates/                 # Document templates
│   │   └── sop_template.md        # SOP template
│   │
│   ├── formatters/                # Format converters
│   │   ├── pdf_formatter.py       # PDF generation
│   │   ├── docx_formatter.py      # Word generation
│   │   ├── markdown_formatter.py  # Markdown generation
│   │   └── html_formatter.py      # HTML generation
│   │
│   └── utils/                     # Utilities
│       ├── config.py              # Configuration
│       └── logger.py              # Logging
│
├── config/                        # Configuration files
│   ├── agent_config.yaml          # Agent settings
│   ├── process_definitions.yaml   # Process definitions
│   └── standards_mapping.yaml     # Standards mapping
│
├── output/                        # Generated documents
│   ├── pdf/
│   ├── docx/
│   ├── markdown/
│   └── html/
│
└── logs/                          # System logs
```

## Configuration

### Agent Configuration

Edit `config/agent_config.yaml` to customize agent behavior:

```yaml
leader_agent:
  model: "claude-sonnet-4"
  max_tokens: 4096
  temperature: 0.7
```

### Process Definitions

Add or modify IT processes in `config/process_definitions.yaml`:

```yaml
custom_process:
  name: "My Custom Process"
  category: "Custom"
  standards:
    - "ITIL v4"
    - "Custom Standard"
  complexity: "medium"
  estimated_pages: 20
```

### Standards Mapping

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
- Table of contents
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
python -m src.main generate "Incident Management" -f pdf -f docx
```

Output:
- `output/pdf/Incident_Management_SOP.pdf`
- `output/docx/Incident_Management_SOP.docx`

### Example 2: Generate All ITIL Core Processes

```bash
python -m src.main generate "Incident Management"
python -m src.main generate "Change Management"
python -m src.main generate "Problem Management"
python -m src.main generate "Service Request Management"
```

### Example 3: Custom Device Management Process

```bash
python -m src.main generate "Devices Batch Management" -f pdf -f html
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

Place your `ITOM.pdf` file in the project root directory. The system will use it as a knowledge base for IT operations processes.

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
    output_files = await leader.generate_documentation(
        "Incident Management",
        ["pdf", "docx"]
    )

    return output_files

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
- Ensure ITOM.pdf is present for enhanced results

## License

Internal use only - IT Process Documentation System

## Version

Version 1.0.0

---

**Generated by the IT Process Documentation Multi-Agent System**

Powered by Claude AI (Anthropic)

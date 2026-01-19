# System Architecture

## REEMA - Multi-Agent IT Process Documentation System

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         USER CLI                              │
│                    (Typer + Rich)                            │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ Command: generate "Process Name"
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    ABDULLAH (LEADER)                          │
│              (Orchestrator & Coordinator)                     │
│                                                               │
│  • Receives user requests                                    │
│  • Plans workflow                                            │
│  • Assigns tasks to workers                                  │
│  • Coordinates agent communication                           │
│  • Performs final QC                                         │
│  • Assembles output                                          │
└─────────┬────────────────────────────────────────────────────┘
          │
          │ Delegates to Worker Agents
          │
    ┌─────┴──────┬──────────┬──────────┬─────────┐
    │            │          │          │         │
    ▼            ▼          ▼          ▼         ▼
┌────────┐  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Taif   │  │Mohammad│ │  Saad  │ │ Faisal │ │  Bee   │
│Research│  │Standards│ │Content │ │ Review │ │ Format │
└────┬───┘  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
     │          │          │          │          │
     │          │          │          │          │
     ▼          ▼          ▼          ▼          ▼
┌────────────────────────────────────────────────────┐
│              KNOWLEDGE BASE & RESOURCES             │
├────────────────────────────────────────────────────┤
│ • ITOM.pdf (parsed)                                │
│ • ITIL v4 knowledge                                │
│ • Standards mapping                                │
│ • SOP templates                                    │
│ • Configuration files                              │
└────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    OUTPUT GENERATION                          │
├──────────────────────────────────────────────────────────────┤
│  PDF Formatter    │  DOCX Formatter  │  MD Formatter  │  HTML │
│  (WeasyPrint)     │  (python-docx)   │  (markdown2)   │ (Jinja2)│
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
                   output/ directory
                ┌────────┴────────┐
                │                 │
            PDF/  DOCX/  MD/  HTML/
```

---

## Agent Workflow Diagram

```
START
  │
  ▼
┌──────────────────────────────────────┐
│ User: "Generate Incident Management" │
└──────────────┬───────────────────────┘
               │
               ▼
        ┌─────────────┐
        │  ABDULLAH   │
        └──────┬──────┘
               │
               │ 1. Plan Workflow
               │ 2. Get Process Definition
               │ 3. Get Standards Mapping
               │
               ▼
        ┌──────────────┐
        │ PHASE 1:     │
        │ RESEARCH     │
        └──────┬───────┘
               │
        ┌──────┴──────┬─────────────┐
        │             │             │
        ▼             ▼             ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │  Taif   │  │ Mohammad│  │ ITOM.pdf│
   │(Research)│ │(Standards)│ │ Parser  │
   │         │  │         │  │         │
   │ Gathers │  │ Analyzes│  │ Extracts│
   │ ITIL    │  │Compliance│  │Knowledge│
   │ Info    │  │Req.     │  │         │
   └────┬────┘  └────┬────┘  └────┬────┘
        │            │            │
        └────────────┴────────────┘
                     │
                     ▼
             Research Data Bundle
                     │
                     ▼
        ┌──────────────┐
        │ PHASE 2:     │
        │ CONTENT GEN  │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │     Saad     │
        │  (Content)   │
        │ • Generates  │
        │   15-30 pages│
        │ • Creates    │
        │   11 sections│
        │ • RACI matrix│
        │ • Procedures │
        │ • KPIs       │
        └──────┬───────┘
               │
               ▼
          Draft SOP (MD)
               │
               ▼
        ┌──────────────┐
        │ PHASE 3:     │
        │ REVIEW       │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │    Faisal    │
        │   (Review)   │
        │ • Validates  │
        │ • Scores     │
        │ • Feedback   │
        └──────┬───────┘
               │
        ┌──────┴──────┐
        │             │
    Score >= 85?    Score < 85?
        │             │
        ▼             ▼
    APPROVED    ┌──────────┐
        │       │ Refine   │
        │       │ Content  │
        │       └────┬─────┘
        │            │
        │            │ Loop back
        └────────────┘
               │
               ▼
        Approved Content
               │
               ▼
        ┌──────────────┐
        │ PHASE 4:     │
        │ FORMATTING   │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │     Bee      │
        │   (Format)   │
        └──────┬───────┘
               │
        ┌──────┴──────┬──────────┬─────────┐
        │             │          │         │
        ▼             ▼          ▼         ▼
    ┌───────┐   ┌───────┐  ┌───────┐ ┌───────┐
    │  PDF  │   │ DOCX  │  │  MD   │ │ HTML  │
    │Formatter│ │Formatter││Formatter││Formatter│
    └───┬───┘   └───┬───┘  └───┬───┘ └───┬───┘
        │           │          │         │
        ▼           ▼          ▼         ▼
    .pdf       .docx        .md       .html
        │           │          │         │
        └───────────┴──────────┴─────────┘
                     │
                     ▼
        ┌──────────────────────┐
        │ Leader: Final Check  │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  Return File Paths   │
        │  Display Results     │
        └──────────┬───────────┘
                   │
                   ▼
                  END
```

---

## Data Flow Architecture

```
┌──────────────┐
│ User Request │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────┐
│ Abdullah (Leader)                │
│ • process_name: str              │
│ • output_formats: List[str]      │
└──────┬───────────────────────────┘
       │
       ├─────────────────────────────────────┐
       │                                     │
       ▼                                     ▼
┌──────────────┐                  ┌──────────────┐
│ Taif         │                  │ Mohammad     │
│ (Research)   │                  │ (Standards)  │
└──────┬───────┘                  └──────┬───────┘
       │                                  │
       ▼                                  ▼
┌──────────────────┐            ┌─────────────────┐
│ research_data    │            │compliance_data  │
│ • raw_research   │            │ • standards_map │
│ • sections: {}   │            │ • requirements  │
│ • timestamp      │            │ • checklist     │
└──────┬───────────┘            └─────────┬───────┘
       │                                  │
       └──────────────┬───────────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Combined Research   │
            │ Data Bundle         │
            └──────────┬──────────┘
                       │
                       ▼
            ┌──────────────────┐
            │ Saad (Content)   │
            └──────────┬───────┘
                       │
                       ▼
            ┌──────────────────┐
            │ Draft SOP        │
            │ • Markdown format│
            │ • 15-30 pages    │
            │ • 11 sections    │
            └──────────┬───────┘
                       │
                       ▼
            ┌──────────────────┐
            │ Faisal (Review)  │
            └──────────┬───────┘
                       │
                       ▼
            ┌──────────────────┐
            │ Review Results   │
            │ • quality_score  │
            │ • issues: []     │
            │ • feedback: []   │
            └──────────┬───────┘
                       │
                Quality >= 85?
                       │
                       ▼ YES
            ┌──────────────────┐
            │ Bee (Format)     │
            └──────────┬───────┘
                       │
            ┌──────────┴──────────┐
            │                     │
            ▼                     ▼
    ┌──────────────┐      ┌──────────────┐
    │ PDF Formatter│      │DOCX Formatter│
    │ • HTML → PDF │      │ • MD → DOCX  │
    │ • Styling    │      │ • Tables     │
    │ • TOC        │      │ • Styles     │
    └──────┬───────┘      └──────┬───────┘
           │                     │
           └──────────┬──────────┘
                      │
                      ▼
            ┌──────────────────┐
            │ Output Files     │
            │ • pdf: path      │
            │ • docx: path     │
            │ • markdown: path │
            │ • html: path     │
            └──────────────────┘
```

---

## Component Architecture

### 1. Agent Layer

```
agents/
├── leader_agent.py
│   ├── LeaderAgent
│   │   ├── __init__(api_key)
│   │   ├── register_worker(name, agent)
│   │   ├── generate_documentation(process, formats)
│   │   ├── _plan_workflow()
│   │   ├── _coordinate_research()
│   │   ├── _coordinate_content_generation()
│   │   ├── _coordinate_review()
│   │   └── _coordinate_formatting()
│   └── AgentTask
│
├── research_agent.py
│   └── ResearchAgent
│       ├── research_process(name, standards)
│       ├── _build_research_prompt()
│       ├── _parse_research_response()
│       └── _call_claude()
│
├── standards_agent.py
│   └── StandardsAgent
│       ├── analyze_compliance(name, standards)
│       ├── _build_compliance_prompt()
│       └── _parse_compliance_response()
│
├── content_agent.py
│   └── ContentAgent
│       ├── generate_sop(name, research_data)
│       ├── refine_content(content, feedback)
│       └── _format_sop_document()
│
├── review_agent.py
│   └── ReviewAgent
│       ├── review_content(content)
│       ├── _extract_quality_score()
│       └── _extract_recommendations()
│
└── format_agent.py
    └── FormatAgent
        ├── convert_to_formats(content, formats)
        └── _convert_to_format(content, type)
```

### 2. Formatter Layer

```
formatters/
├── pdf_formatter.py
│   └── PDFFormatter
│       ├── convert(content, path, name)
│       └── _get_pdf_css()
│
├── docx_formatter.py
│   └── DOCXFormatter
│       ├── convert(content, path, name)
│       ├── _setup_styles()
│       ├── _add_title_page()
│       └── _parse_markdown_to_docx()
│
├── markdown_formatter.py
│   └── MarkdownFormatter
│       └── convert(content, path, name)
│
└── html_formatter.py
    └── HTMLFormatter
        ├── convert(content, path, name)
        └── _get_html_template()
```

### 3. Knowledge Layer

```
knowledge/
└── itom_parser.py
    └── ITOMParser
        ├── extract_knowledge()
        ├── search_knowledge(query)
        ├── _extract_with_pdfplumber()
        └── _extract_with_pypdf2()
```

### 4. Configuration Layer

```
config/
├── agent_config.yaml
│   ├── leader_agent: {model, tokens, temp}
│   ├── research_agent: {specialization[]}
│   ├── standards_agent: {specialization[]}
│   └── ...
│
├── process_definitions.yaml
│   ├── incident_management: {name, category, standards[], complexity}
│   ├── change_management: {...}
│   └── ...
│
└── standards_mapping.yaml
    ├── incident_management: [ITIL, ISO 20000, ...]
    └── ...
```

### 5. Utilities Layer

```
utils/
├── config.py
│   ├── SystemConfig (Pydantic model)
│   ├── AgentConfig (Pydantic model)
│   └── ConfigManager
│       ├── load_configs()
│       ├── get_agent_config()
│       └── get_process_definition()
│
└── logger.py
    └── AgentLogger
        ├── info()
        ├── error()
        ├── agent_start()
        └── agent_complete()
```

---

## Technology Stack Details

```
┌─────────────────────────────────────────┐
│         Application Layer               │
├─────────────────────────────────────────┤
│ • Typer (CLI framework)                 │
│ • Rich (Console UI)                     │
│ • Asyncio (Concurrency)                 │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Agent Layer                     │
├─────────────────────────────────────────┤
│ • Anthropic SDK (Claude API)            │
│ • Custom Agent Classes                  │
│ • Async/Await Pattern                   │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│      Document Generation Layer          │
├─────────────────────────────────────────┤
│ • python-docx (Word)                    │
│ • WeasyPrint (PDF)                      │
│ • markdown2 (Markdown)                  │
│ • Jinja2 (HTML templating)              │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│      Configuration Layer                │
├─────────────────────────────────────────┤
│ • PyYAML (Config parsing)               │
│ • Pydantic (Validation)                 │
│ • python-dotenv (Env vars)              │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Data Layer                      │
├─────────────────────────────────────────┤
│ • PyPDF2 (PDF reading)                  │
│ • pdfplumber (PDF parsing)              │
│ • File system (output/)                 │
└─────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────┐
│          Local Development               │
├──────────────────────────────────────────┤
│ Windows/Linux/Mac                        │
│ Python 3.9+                              │
│ Virtual Environment (venv)               │
│ ANTHROPIC_API_KEY (env var)              │
└──────────────────────────────────────────┘
                  │
┌──────────────────────────────────────────┐
│      External Dependencies               │
├──────────────────────────────────────────┤
│ • Anthropic API (api.anthropic.com)      │
│ • Claude Sonnet 4.5                      │
│ • Internet connection (for API)          │
└──────────────────────────────────────────┘
                  │
┌──────────────────────────────────────────┐
│         Output Storage                   │
├──────────────────────────────────────────┤
│ • output/pdf/                            │
│ • output/docx/                           │
│ • output/markdown/                       │
│ • output/html/                           │
│ • logs/                                  │
└──────────────────────────────────────────┘
```

---

## Security Architecture

```
┌──────────────────────────────────────────┐
│       Environment Variables              │
├──────────────────────────────────────────┤
│ ANTHROPIC_API_KEY (sensitive)            │
│ Loaded via python-dotenv                 │
│ Never committed to version control       │
└──────────────────────────────────────────┘
                  │
┌──────────────────────────────────────────┐
│          API Communication               │
├──────────────────────────────────────────┤
│ • HTTPS only                             │
│ • Anthropic SDK handles auth             │
│ • No data persistence on API side        │
└──────────────────────────────────────────┘
                  │
┌──────────────────────────────────────────┐
│         Local Data Handling              │
├──────────────────────────────────────────┤
│ • ITOM.pdf stays local                   │
│ • Generated docs stay local              │
│ • Logs stored locally                    │
│ • No external data transmission          │
└──────────────────────────────────────────┘
```

---

This architecture supports:
- ✅ Scalability (add more agents/processes)
- ✅ Maintainability (modular design)
- ✅ Extensibility (config-driven)
- ✅ Reliability (error handling)
- ✅ Performance (async operations)
- ✅ Security (API key management)

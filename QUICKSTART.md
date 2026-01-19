# REEMA Quick Start Guide

Get started with REEMA (Regulatory & Enterprise Management Automation) in 5 minutes!

## Step 1: Install Dependencies

```bash
# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

## Step 2: Set API Key

```bash
# Windows
set ANTHROPIC_API_KEY=your-api-key-here

# Linux/Mac
export ANTHROPIC_API_KEY='your-api-key-here'

# Or create .env file
cp .env.example .env
# Edit .env and add your API key
```

## Step 3: Check System Status

```bash
python -m src.main status
```

Expected output:
```
📊 System Status:

API Key         ✓ Configured
ITOM.pdf        ✓ Found (or ❌ Not found - optional)
Project Root    C:\Users\Khali\Desktop\Projects\IT Consultant
Output Directory C:\Users\Khali\Desktop\Projects\IT Consultant\output
...
```

## Step 4: List Available Processes

```bash
python -m src.main list-processes
```

You'll see all available IT processes including:
- Incident Management
- Change Management
- Problem Management
- Service Request Management
- And many more...

## Step 5: Generate Your First Document

```bash
python -m src.main generate "Incident Management"
```

This will:
1. Initialize all 6 AI agents
2. Research ITIL/ITOM standards
3. Generate 15-30 page SOP
4. Review for quality
5. Export to PDF, DOCX, Markdown, and HTML

Output files will be in the `output/` directory:
- `output/pdf/Incident_Management_SOP.pdf`
- `output/docx/Incident_Management_SOP.docx`
- `output/markdown/Incident_Management_SOP.md`
- `output/html/Incident_Management_SOP.html`

## Common Commands

### Generate specific formats only
```bash
python -m src.main generate "Change Management" -f pdf -f docx
```

### Custom output directory
```bash
python -m src.main generate "Problem Management" --output ./my-documents
```

### Get help
```bash
python -m src.main --help
python -m src.main generate --help
```

## What Happens During Generation?

1. **Leader Agent** receives your request and plans the workflow
2. **Research Agent** gathers ITIL/ITOM information and best practices
3. **Standards Agent** analyzes compliance requirements
4. **Content Agent** creates the 15-30 page SOP document
5. **Review Agent** validates quality (target score >85%)
6. **Format Agent** converts to your desired formats

The entire process typically takes 5-15 minutes depending on complexity.

## Troubleshooting

### "API key not set" error
```bash
# Make sure you've exported the API key
echo %ANTHROPIC_API_KEY%  # Windows
echo $ANTHROPIC_API_KEY   # Linux/Mac
```

### Missing dependencies
```bash
pip install -r requirements.txt
```

### ITOM.pdf warnings
This is optional! The system works without it. If you have an ITOM document, place it in the project root directory.

## Next Steps

- Check the full [README.md](README.md) for detailed documentation
- Explore [configuration files](config/) to customize processes
- Review [agent implementations](src/agents/) to understand the system
- Generate documentation for all your IT processes!

---

**Pro Tip**: Generate multiple processes at once using a script:

```bash
# generate_all.sh (Linux/Mac)
for process in "Incident Management" "Change Management" "Problem Management"
do
    python -m src.main generate "$process"
done
```

```batch
REM generate_all.bat (Windows)
python -m src.main generate "Incident Management"
python -m src.main generate "Change Management"
python -m src.main generate "Problem Management"
```

Happy documenting! 📝

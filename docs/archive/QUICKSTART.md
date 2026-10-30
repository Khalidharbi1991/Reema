> Outdated — see [AGENTS.md](../../AGENTS.md) and [README.md](../../README.md).

# REEMA Quick Start Guide

Get started with REEMA (Regulatory & Enterprise Management Automation).
Generation uses Anthropic and requires authorization to transmit its inputs;
read [Data handling](DATA_HANDLING.md) before using customer material.

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
python -m src.main generate "Incident Management" -f markdown --allow-external-ai
```

This will:

1. Initialize the leader, core workers, and process-selected specialists
2. Research ITIL/ITOM standards
3. Generate an SOP draft (page target is not yet enforced)
4. Review for quality
5. Export Markdown and create a pending human approval record

The CLI prints the unique `output/runs/<run-id>/` directory. Review the document,
then use its printed record path to record a human decision:

```bash
python -m src.main approve output/runs/<run-id>/approval.json --reviewer "Your name"
```

Replace `<run-id>` with the printed identifier. The command asks for confirmation
and checks that the document bytes have not changed. Use `reject` with `--notes`
to request revisions. This local record does not authenticate the reviewer.

## Common Commands

### Generate specific formats only
```bash
python -m src.main generate "Change Management" -f pdf -f docx --allow-external-ai
```

### Custom output directory
```bash
python -m src.main generate "Problem Management" --output ./my-documents --allow-external-ai
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
4. **Content Agent** creates the SOP draft, with selected specialist enrichment
5. **Review Agent** checks quality against the configured threshold (default 85)
6. **Format Agent** converts to every requested format or reports failure
7. **Human reviewer** approves or rejects the validated exports separately

Model latency, document length, and revisions affect time and API cost.

## Troubleshooting

### "API key not set" error
```bash
# Check configuration without printing the secret
python -m src.main status
```

### Missing dependencies
```bash
pip install -r requirements.txt
```

### ITOM.pdf warnings
This is optional. The system works without it. If you have an ITOM document,
place it in `references/itom/`.

## Next Steps

- Check the full [README.md](../../README.md) for detailed documentation
- Explore [configuration files](../../config/) to customize processes
- Review [agent implementations](../../src/agents/) to understand the system

---

Only after authorizing each process's source material, you can generate multiple
drafts with a script. Every result still needs separate human review:

```bash
# generate_all.sh (Linux/Mac)
for process in "Incident Management" "Change Management" "Problem Management"
do
    python -m src.main generate "$process" --allow-external-ai
done
```

```batch
REM generate_all.bat (Windows)
python -m src.main generate "Incident Management" --allow-external-ai
python -m src.main generate "Change Management" --allow-external-ai
python -m src.main generate "Problem Management" --allow-external-ai
```

Happy documenting! 📝

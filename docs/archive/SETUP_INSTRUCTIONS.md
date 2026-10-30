> Outdated — see [AGENTS.md](../../AGENTS.md) and [README.md](../../README.md).

# Setup Instructions for Workstation Security Patches SOP Generation

## Prerequisites

1. **Python 3.9 or higher** - Download from https://www.python.org/downloads/
2. **Anthropic API Key** - Get one from https://console.anthropic.com/

## Installation Steps

### 1. Install Python
- Download Python 3.9+ from python.org
- During installation, check "Add Python to PATH"
- Verify installation:
  ```cmd
  python --version
  ```

### 2. Create Virtual Environment
```cmd
cd "C:\Users\Khali\Desktop\Projects\IT Consultant"
python -m venv venv
```

### 3. Activate Virtual Environment
```cmd
venv\Scripts\activate
```

### 4. Install Dependencies
```cmd
pip install -r requirements.txt
```

### 5. Set API Key
Replace `your-api-key-here` with your actual Anthropic API key:

**Option A: Environment Variable (Recommended)**
```cmd
set ANTHROPIC_API_KEY=your-api-key-here
```

**Option B: Create .env file**
Create a file named `.env` in the project root with:
```
ANTHROPIC_API_KEY=your-api-key-here
```

## Running the Documentation Generator

### Method 1: Using the Custom Script (Recommended for this task)
```cmd
python3 scripts/generation/generate_workstation_patches.py
```

### Method 2: Using the Main CLI
```cmd
python -m src.main generate "Workstation Security Patches" --format docx --format pdf
```

## Expected Output

The system will:
1. **Abdullah (Leader)** - Coordinates the entire workflow
2. **Taif (Research)** - Gathers ITIL/ITOM best practices for patch management
3. **Mohammad (Standards)** - Ensures ISO 27001, NIST, CIS Controls compliance
4. **Saad (Content)** - Writes the 25-30 page SOP with:
   - High-level process flow diagram (text description)
   - Detailed process flow diagram (text description)
   - All 11 SOP sections
   - RACI matrix
   - Step-by-step procedures
5. **Faisal (Review)** - Quality checks (must score 85%+)
6. **Bee (Format)** - Converts to DOCX and PDF

## Output Files Location

Files will be generated in:
```
output/
├── docx/
│   └── Workstation_Security_Patches_SOP.docx
└── pdf/
    └── Workstation_Security_Patches_SOP.pdf
```

## Troubleshooting

### API Key Error
If you see "ANTHROPIC_API_KEY environment variable not set":
- Verify your API key is set correctly
- Make sure you activated the virtual environment
- Try setting the key again

### Module Not Found Errors
If you see import errors:
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

### ITOM.pdf Warning
If you see "Could not load ITOM knowledge":
- This is optional - the system will work without it
- Place ITOM.pdf in `references/itom/` if you have it

## Expected Generation Time

- Research Phase: 2-3 minutes
- Content Generation: 3-5 minutes
- Review Phase: 1-2 minutes
- Formatting: 1-2 minutes
- **Total: ~10-15 minutes**

## Need Help?

Check the logs in `logs/` directory for detailed information about the generation process.

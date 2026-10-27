# Utility Scripts

Run these tools from the repository root unless a script says otherwise.

`dev.py bootstrap` installs the hash-locked ignored project environment.
Use `python3 scripts/dev.py doctor`, `test`, `run`, `python` and `smoke` for normal
local workflows with native-library discovery. See
[development setup](../docs/guides/DEVELOPMENT_SETUP.md).

- `generation/` creates SOPs, policies, RFPs, and related documents.
- `conversion/` converts formats or extracts content and diagrams.
- `transformation/` modifies existing source documents and spreadsheets.
- `utilities/` contains verification and agent helper tools.

Generated artifacts belong in `output/`; reusable input documents belong in
`references/`.

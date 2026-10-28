"""Detect output folders whose drafts and checkpoints Git would not ignore."""

import subprocess
from pathlib import Path
from typing import Optional

# Representative files a run writes: checkpoints carry SOP text and source excerpts.
PROBES = (Path("runs") / "reema-probe" / "ready.json", Path("markdown") / "reema-probe_SOP.md")


def unignored_output(directory) -> Optional[Path]:
    """Return the Git work-tree root when run files under directory would not be ignored.

    None means the folder is ignored, outside a Git work tree, or Git is unavailable.
    Read-only: runs `git rev-parse` and `git check-ignore`; never creates the folder.
    """
    directory = Path(directory).expanduser().resolve()
    existing = next((path for path in (directory, *directory.parents) if path.is_dir()), None)
    if existing is None:
        return None
    try:
        top = subprocess.run(["git", "-C", str(existing), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if top.returncode != 0:
            return None
        root = Path(top.stdout.strip()).resolve()
        for probe in PROBES:
            relative = (directory / probe).relative_to(root)
            check = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--no-index", "--", str(relative)],
                                   capture_output=True, timeout=10)
            if check.returncode == 1:  # 0 = ignored, 1 = not ignored, 128 = error
                return root
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return None

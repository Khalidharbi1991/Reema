"""File-backed stand-ins for Agent 3 and Agent 4 in a finished-SOP revision (experiment).

A Claude Code session writes the patch and recheck JSON; these workers feed that text through
the unchanged ContentAgent.revise_sections and ReviewAgent.recheck_corrections parsing and
validation instead of a provider reply. They have no client and never call a provider.
"""

import json
from pathlib import Path
from typing import Dict, List

from .content_agent import ContentAgent
from .review_agent import ReviewAgent
from ..utils.documents import sha


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular file written by the Claude Code session: {path}")
    return path.read_text(encoding="utf-8")


class FilePatchWorker(ContentAgent):
    """Agent 3's revise step, with the SectionPatch read from patch.json."""

    def __init__(self, patch_path):
        super().__init__(api_key="")
        self.client = None
        self.patch_path = Path(patch_path)

    async def _call_claude(self, messages: List[Dict], system: str = "", max_tokens: int = None) -> str:
        return _read(self.patch_path)


class FileRecheckWorker(ReviewAgent):
    """Agent 4's recheck step, with the CorrectionAssessment read from recheck.json.

    The file must name the revised document's SHA-256, so a recheck of other text is refused.
    """

    def __init__(self, recheck_path):
        super().__init__(api_key="")
        self.client = None
        self.recheck_path = Path(recheck_path)
        self._reply = None

    async def recheck_corrections(self, content: str, findings: List[Dict], require_complete: bool = True,
                                  finished_sop: bool = False) -> Dict:
        try:
            data = json.loads(_read(self.recheck_path))
        except ValueError:
            raise ValueError(f"{self.recheck_path.name} is not valid JSON") from None
        if not isinstance(data, dict) or data.pop("revised_sha256", None) != sha(content):
            raise ValueError("The recheck does not name the revised document's SHA-256; run check again")
        self._reply = json.dumps(data)
        result = await super().recheck_corrections(content, findings, require_complete, finished_sop)
        return {**result, "verification": "claude_code_session_assessed"}

    async def _call_claude(self, messages: List[Dict], system: str = "", max_tokens: int = None) -> str:
        return self._reply

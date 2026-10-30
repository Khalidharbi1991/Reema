"""File-backed stand-ins for Agent 3 and Agent 4 in Claude Code generate, review and revise jobs.

A Claude Code session writes the section files, review, patch and recheck JSON; these workers feed that
text through the unchanged ContentAgent.generate_sop, ReviewAgent.review_existing,
ContentAgent.revise_sections and ReviewAgent.recheck_corrections parsing and validation instead of a
provider reply. They have no client and never call a provider.
"""

import json
import re
from pathlib import Path
from typing import Dict, List

from .content_agent import ContentAgent
from .review_agent import ReviewAgent
from ..knowledge.retrieval import chunks
from ..utils.config import config_manager
from ..utils.documents import sha


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular file written by the Claude Code session: {path}")
    return path.read_text(encoding="utf-8")


def _json(path):
    text = _read(path)
    try:
        return json.loads(text)
    except ValueError:
        raise ValueError(f"{Path(path).name} is not valid JSON") from None


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


class FileReviewWorker(ReviewAgent):
    """Agent 4's finished-SOP review, with each assessment read from a file.

    excerpts.json holds one assessment per excerpt, in order. When the SOP has more than one excerpt,
    consistency.json holds the cross-section pass, written by a separate subagent. Both files must name
    the SOP's document SHA-256. excerpts_only=True is for the check step alone: it stands in an empty
    consistency pass so the excerpts can be validated before consistency.json exists.
    """

    def __init__(self, excerpts_path, consistency_path=None, excerpts_only=False):
        super().__init__(api_key="")
        self.client = None
        self.excerpts_path = Path(excerpts_path)
        self.consistency_path = Path(consistency_path) if consistency_path else None
        self.excerpts_only = excerpts_only
        self._replies = []

    async def review_existing(self, content: str) -> Dict:
        document = sha(content)
        data = _json(self.excerpts_path)
        if not isinstance(data, dict) or data.get("document_sha256") != document:
            raise ValueError("excerpts.json does not name this SOP's document SHA-256; prepare it again")
        parts = chunks(content, config_manager.system_config.review_chunk_chars)
        assessments = data.get("assessments")
        if not isinstance(assessments, list) or len(assessments) != len(parts):
            raise ValueError(f"excerpts.json needs exactly {len(parts)} assessment(s), one per excerpt, in order")
        replies = [json.dumps(item) for item in assessments]
        if len(parts) > 1:
            if self.excerpts_only:
                replies.append(json.dumps({"issues": [], "summary": "Consistency pass not written yet"}))
            else:
                if self.consistency_path is None:
                    raise ValueError("This SOP has several excerpts and needs consistency.json")
                extra = _json(self.consistency_path)
                if not isinstance(extra, dict) or extra.get("document_sha256") != document:
                    raise ValueError("consistency.json does not name this SOP's document SHA-256")
                replies.append(json.dumps(extra.get("assessment")))
        self._replies = replies
        result = await super().review_existing(content)
        return {**result, "verification": "claude_code_session_assessed"}

    async def _call_claude(self, messages: List[Dict], system: str = "", max_tokens: int = None) -> str:
        if not self._replies:
            raise ValueError("The review asked for more assessments than were written")
        return self._replies.pop(0)


def section_files(directory):
    """The expected Markdown file for each configured section, in document order: NN-<section id>.md."""
    profile = config_manager.document_profile
    return {section.id: Path(directory) / f"{number:02d}-{section.id}.md"
            for number, section in enumerate(profile.sections, 1)}


class FileSectionWriter(ContentAgent):
    """Agent 3's generate step, with each section body read from its own Markdown file.

    generate_sop asks for the sections in order; each request ends by naming its section id, and the
    reply is that section's file wrapped as a SectionBody, so the unchanged per-section checks apply.
    """

    SECTION_ID = re.compile(r'Set section_id to "([^"]+)"\.$')

    def __init__(self, sections_dir):
        super().__init__(api_key="")
        self.client = None
        self.files = section_files(sections_dir)

    async def _call_claude(self, messages: List[Dict], system: str = "", max_tokens: int = None) -> str:
        match = self.SECTION_ID.search(messages[-1]["content"])
        if not match or match.group(1) not in self.files:
            raise ValueError("The generate step asked for a section this writer does not know")
        path = self.files[match.group(1)]
        if not path.is_file():
            raise ValueError(f"No {path.name} yet: ask Claude Code to run reema-writer on this work id ({path.parent.parent.name})")
        return json.dumps({"section_id": match.group(1), "body": _read(path)})

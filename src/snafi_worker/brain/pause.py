"""Pausing the brain. After a lockdown breach the brain stays paused until Khalid has
looked and clears it (`snafi reset-brain`). While it is not ready (no passing proof, a new
agy version, MCP servers or plugins present) it is paused too, without a file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BrainError, BrainReply, BrainRequest


class BrainPaused(BrainError):
    def __init__(self, reason: str):
        super().__init__(f"brain paused: {reason}", retryable=False)
        self.paused = True
        self.reason = reason


class PauseFile:
    def __init__(self, path: Path):
        self.path = Path(path)

    def reason(self) -> Optional[str]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("reason") or "paused"
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return "pause file unreadable"  # fail closed

    def pause(self, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"reason": reason[:300], "at": datetime.now(timezone.utc).isoformat()}),
                             encoding="utf-8")

    def clear(self) -> bool:
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return False


class GuardedBrain:
    """Wraps any brain: refuses while paused, and pauses it on a breach."""

    def __init__(self, brain, pause: PauseFile):
        self.brain, self.pause = brain, pause
        self.PROVIDER = getattr(brain, "PROVIDER", "")

    def think(self, request: BrainRequest) -> BrainReply:
        reason = self.pause.reason()
        if reason:
            raise BrainPaused(reason)
        try:
            return self.brain.think(request)
        except BrainError as exc:
            if getattr(exc, "breach", False):
                self.pause.pause(str(exc))
                raise BrainPaused(str(exc)) from None
            if getattr(exc, "paused", False):
                raise BrainPaused(str(exc)) from None
            raise

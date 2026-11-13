"""The daily brain call limit (SEC-47). Every brain call, retries included, counts against the
limit for the current day in the worker's time zone; when it is reached, the brain is not called
again until the next day and Ahmad says so. The count lives in the worker's data folder
(brain_calls.json). An unreadable count fails closed; `snafi reset-brain` clears it.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .base import BrainError, BrainReply, BrainRequest

DEFAULT_LIMIT = 300


class BrainLimitReached(BrainError):
    def __init__(self, limit: int):
        super().__init__(f"daily brain limit reached ({limit} calls)", retryable=False)
        self.limited = True


class DailyLimit:
    def __init__(self, path: Path, limit: int, time_zone: str, clock=None):
        self.path, self.limit, self.zone = Path(path), int(limit), ZoneInfo(time_zone)
        self._clock = clock or (lambda: datetime.now(self.zone))
        self._lock = threading.Lock()

    def _today(self) -> str:
        return self._clock().astimezone(self.zone).date().isoformat()

    def used(self) -> int:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return 0
        except (OSError, ValueError):
            return self.limit  # fail closed
        if not isinstance(data, dict) or not isinstance(data.get("calls"), int):
            return self.limit
        return data["calls"] if data.get("day") == self._today() else 0

    def take(self) -> None:
        """Count one call, or refuse if today's limit is used up."""
        with self._lock:
            used = self.used()
            if used >= self.limit:
                raise BrainLimitReached(self.limit)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps({"day": self._today(), "calls": used + 1}), encoding="utf-8")
            temp.replace(self.path)

    def clear_if_unreadable(self) -> bool:
        """Only a damaged count is removed (`snafi reset-brain`); a readable one keeps today's limit."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("calls"), int) and isinstance(data.get("day"), str):
                return False
        except FileNotFoundError:
            return False
        except (OSError, ValueError):
            pass
        try:
            self.path.unlink()
        except OSError:
            return False
        return True


class LimitedBrain:
    """Wraps any brain: each think() first takes one call from today's limit."""

    def __init__(self, brain, limit: DailyLimit):
        self.brain, self.limit = brain, limit
        self.PROVIDER = getattr(brain, "PROVIDER", "")

    def think(self, request: BrainRequest) -> BrainReply:
        self.limit.take()
        return self.brain.think(request)

"""A stored login (an app password or an API token) read from the worker's secrets.

Values come from Windows Credential Manager through the Secrets object and stay in memory only:
never in a URL, a log line, repr or an error. After Khalid stores a new value with set-secrets the
worker picks it up within minutes, without a restart (reload re-reads Credential Manager).
"""

import threading
import time
from typing import Callable, Optional, Tuple

from .base import AuthRefused, NotConnected

RELOAD_SECONDS = 300
RETRY_SECONDS = 30


def usable(value: str, what: str) -> str:
    """Refuse a value with spaces or control characters (a broken paste), without showing it."""
    if not value or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
        raise AuthRefused(f"the stored {what} is not usable; store it again with snafi.cmd set-secrets")
    return value


class StoredLogin:
    def __init__(self, secrets, names: Tuple[str, ...], service: str,
                 reload: Optional[Callable[[], object]] = None, clock: Callable[[], float] = time.monotonic):
        self._secrets = secrets
        self.names = tuple(names)
        self.service = service
        self._reload = reload
        self._clock = clock
        self._reloaded_at: Optional[float] = None
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return f"StoredLogin(service={self.service}, values=hidden)"

    __str__ = __repr__

    @property
    def connected(self) -> bool:
        return all(self._secrets.has(name) for name in self.names)

    def _maybe_reload(self, every: float) -> bool:
        """Re-read Credential Manager at most once per `every` seconds. True when the values changed."""
        if self._reload is None:
            return False
        now = self._clock()
        if self._reloaded_at is not None and now - self._reloaded_at < every:
            return False
        self._reloaded_at = now
        try:
            fresh = self._reload()
        except Exception:  # Credential Manager unreadable: keep what we have
            return False
        if fresh is None:
            return False
        before = [self._secrets.get(n) if self._secrets.has(n) else "" for n in self.names]
        after = [fresh.get(n) if fresh.has(n) else "" for n in self.names]
        self._secrets = fresh
        return before != after

    def values(self) -> Tuple[str, ...]:
        with self._lock:
            if not self.connected:
                self._maybe_reload(RELOAD_SECONDS)
            if not self.connected:
                raise NotConnected(f"{self.service} is not connected yet; on the PC run: snafi.cmd set-secrets")
            return tuple(self._secrets.get(name) for name in self.names)

    def refused(self) -> bool:
        """The service refused the stored values: re-read them once (Khalid may have stored new ones).
        True when there is something new to try."""
        with self._lock:
            return self._maybe_reload(RETRY_SECONDS)

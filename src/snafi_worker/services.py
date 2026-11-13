"""Builds each outside service from worker.yaml. The only place a provider is chosen."""

from .config import Secrets, Settings, worker_data_dir
from .registry import provider_class

PAUSE_FILE = "brain_paused.json"
CALLS_FILE = "brain_calls.json"


def build(kind: str, settings: Settings, secrets: Secrets, **extra):
    name = getattr(settings, f"{kind}_provider")
    options = getattr(settings, f"{kind}_options")
    cls = provider_class(kind, name)
    for secret in getattr(cls, "SECRET_NAMES", ()):
        secrets.get(secret)  # fail early, without showing the value
    return cls(options, secrets, **extra)


def guarded_brain(settings: Settings, secrets: Secrets, pause_dir=None):
    """The configured brain, paused while not ready and after any lockdown breach, and held to the
    daily call limit (brain.daily_call_limit in worker.yaml, SEC-47)."""
    from .brain.limit import DEFAULT_LIMIT, DailyLimit, LimitedBrain
    from .brain.pause import GuardedBrain, PauseFile
    folder = pause_dir or worker_data_dir()
    limit = DailyLimit(folder / CALLS_FILE, int(settings.brain_options.get("daily_call_limit", DEFAULT_LIMIT)),
                       settings.time_zone)
    return GuardedBrain(LimitedBrain(build("brain", settings, secrets), limit), PauseFile(folder / PAUSE_FILE))

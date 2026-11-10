"""Builds each outside service from worker.yaml. The only place a provider is chosen."""

from .config import Secrets, Settings, worker_data_dir
from .registry import provider_class

PAUSE_FILE = "brain_paused.json"


def build(kind: str, settings: Settings, secrets: Secrets, **extra):
    name = getattr(settings, f"{kind}_provider")
    options = getattr(settings, f"{kind}_options")
    cls = provider_class(kind, name)
    for secret in getattr(cls, "SECRET_NAMES", ()):
        secrets.get(secret)  # fail early, without showing the value
    return cls(options, secrets, **extra)


def guarded_brain(settings: Settings, secrets: Secrets, pause_dir=None):
    """The configured brain, paused while not ready and after any lockdown breach."""
    from .brain.pause import GuardedBrain, PauseFile
    return GuardedBrain(build("brain", settings, secrets), PauseFile((pause_dir or worker_data_dir()) / PAUSE_FILE))

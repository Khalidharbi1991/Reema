"""Builds each outside service from worker.yaml. The only place a provider is chosen."""

from .config import Secrets, Settings
from .registry import provider_class


def build(kind: str, settings: Settings, secrets: Secrets, **extra):
    name = getattr(settings, f"{kind}_provider")
    options = getattr(settings, f"{kind}_options")
    cls = provider_class(kind, name)
    for secret in getattr(cls, "SECRET_NAMES", ()):
        secrets.get(secret)  # fail early, without showing the value
    return cls(options, secrets, **extra)

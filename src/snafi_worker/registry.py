"""Adapters chosen by config: worker.yaml names a provider for each kind of outside
service, and this registry turns the name into a class. Switching a provider is a
one-line change in worker.yaml plus the new adapter's own file; nothing else changes.
"""

from typing import Callable, Dict, Type

KINDS = ("brain", "store", "mail", "calendar", "files", "tasks", "memory", "memory_search")
_REGISTRY: Dict[str, Dict[str, type]] = {kind: {} for kind in KINDS}


class UnknownProvider(ValueError):
    pass


def register(kind: str, name: str) -> Callable[[Type], Type]:
    if kind not in _REGISTRY:
        raise ValueError(f"unknown adapter kind {kind!r}")

    def add(cls: Type) -> Type:
        _REGISTRY[kind][name] = cls
        cls.PROVIDER = name
        return cls
    return add


def provider_class(kind: str, name: str) -> type:
    _load_builtin()
    try:
        return _REGISTRY[kind][name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY.get(kind, {}))) or "none"
        raise UnknownProvider(f"no {kind} provider named {name!r} (known: {known})") from None


def providers(kind: str) -> list:
    _load_builtin()
    return sorted(_REGISTRY[kind])


def _load_builtin() -> None:
    # Importing the packages registers their providers.
    from . import brain, memory, personal, store  # noqa: F401
    from .google import drive, gcal, gmail  # noqa: F401
    from .todoist import tasks  # noqa: F401
    from .yahoo import mail  # noqa: F401

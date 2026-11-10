"""Worker settings (worker.yaml, in the repo) and secrets (Windows Credential Manager).

Secrets are stored once by Khalid with `python -m src.snafi_worker.set_secrets`, as
"REEMA-Snafi:<NAME>" credentials for his Windows user, encrypted by Windows (DPAPI). There
is no plain-text secrets file (SEC-14). Secrets are never logged and never printed: the
Secrets object hides its values in repr and str.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml

HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE / "worker.yaml"
REPO_ROOT = HERE.parents[1]


class ConfigError(Exception):
    pass


def worker_data_dir() -> Path:
    """%APPDATA%\\REEMA\\snafi-worker: logs only (no secrets). No Claude Code session may read it."""
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "REEMA" / "snafi-worker"


class Secrets:
    """The worker's secrets. Read with .get(name); never shown in repr, str or errors."""

    def __init__(self, values: Dict[str, str]):
        self._values = dict(values)

    def get(self, name: str) -> str:
        value = self._values.get(name, "")
        if not value:
            raise ConfigError(f"{name} is not stored yet; as snafi-worker run: C:\\SnafiWorker\\snafi.cmd set-secrets")
        return value

    def has(self, name: str) -> bool:
        return bool(self._values.get(name))

    def names(self):
        return sorted(self._values)

    def __repr__(self) -> str:
        return f"Secrets(names={self.names()}, values=hidden)"

    __str__ = __repr__

    @classmethod
    def load(cls, backend=None) -> "Secrets":
        """From Windows Credential Manager (or the backend given, in tests)."""
        from .secret_store import SecretStoreError, WindowsCredentials, load_all
        try:
            return cls(load_all(backend or WindowsCredentials()))
        except SecretStoreError as exc:
            raise ConfigError(str(exc)) from None


@dataclass(frozen=True)
class LaneSettings:
    poll_seconds: float
    timeout_seconds: float
    retry_delay_seconds: float


@dataclass(frozen=True)
class Settings:
    brain_provider: str
    brain_options: Dict[str, object]
    store_provider: str
    store_options: Dict[str, object]
    lanes: Dict[str, LaneSettings]
    heartbeat_seconds: float
    backup_folder: Path
    backup_time: str
    backup_keep_days: int
    time_zone: str
    worker_id: str = field(default="")

    @classmethod
    def load(cls, path: Optional[Path] = None, overrides: Optional[dict] = None) -> "Settings":
        data = yaml.safe_load(Path(path or SETTINGS_FILE).read_text(encoding="utf-8")) or {}
        for key, value in (overrides or {}).items():
            section, _, name = key.partition(".")
            data.setdefault(section, {})[name] = value
        try:
            brain, store = dict(data["brain"]), dict(data["store"])
            lanes = {name: LaneSettings(float(v["poll_seconds"]), float(v["timeout_seconds"]),
                                        float(v["retry_delay_seconds"]))
                     for name, v in data["lanes"].items()}
            backup = data["backup"]
            folder = Path(backup["folder"])
            return cls(
                brain_provider=str(brain.pop("provider")),
                brain_options=brain,
                store_provider=str(store.pop("provider")),
                store_options=store,
                lanes=lanes,
                heartbeat_seconds=float(data["heartbeat"]["seconds"]),
                backup_folder=folder if folder.is_absolute() else REPO_ROOT / folder,
                backup_time=str(backup["time"]),
                backup_keep_days=int(backup["keep_days"]),
                time_zone=str(data["time_zone"]),
                worker_id=str(data.get("worker_id") or os.environ.get("COMPUTERNAME", "pc")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"worker.yaml is incomplete or invalid: {exc}") from None

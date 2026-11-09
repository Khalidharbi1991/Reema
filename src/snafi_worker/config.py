"""Worker settings (worker.yaml, in the repo) and secrets (worker.env, outside the repo).

worker.env lives at %APPDATA%\\REEMA\\snafi-worker\\worker.env (override with the
SNAFI_WORKER_ENV environment variable, used by tests). Khalid creates it; no Claude
Code session or agent may read it. Secrets are never logged and never printed: the
Secrets object hides its values in repr and str.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml

HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE / "worker.yaml"
REPO_ROOT = HERE.parents[1]
KEY_LINE = re.compile(r"^([A-Z][A-Z0-9_]{0,63})=(.*)$")


class ConfigError(Exception):
    pass


def default_env_path() -> Path:
    override = os.environ.get("SNAFI_WORKER_ENV")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "REEMA" / "snafi-worker" / "worker.env"


class Secrets:
    """Values from worker.env. Read with .get(name); never shown in repr, str or errors."""

    def __init__(self, values: Dict[str, str]):
        self._values = dict(values)

    def get(self, name: str) -> str:
        value = self._values.get(name, "")
        if not value:
            raise ConfigError(f"{name} is missing from worker.env")
        return value

    def has(self, name: str) -> bool:
        return bool(self._values.get(name))

    def names(self):
        return sorted(self._values)

    def __repr__(self) -> str:
        return f"Secrets(names={self.names()}, values=hidden)"

    __str__ = __repr__

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Secrets":
        path = Path(path or default_env_path())
        if not path.is_file():
            raise ConfigError(f"worker.env not found at {path}; see src/snafi_worker/README.md")
        values: Dict[str, str] = {}
        for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = KEY_LINE.match(line)
            if not match:
                raise ConfigError(f"worker.env line {number} is not NAME=value (value not shown)")
            name, value = match.groups()
            values[name] = value.strip().strip('"').strip("'")
        return cls(values)


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

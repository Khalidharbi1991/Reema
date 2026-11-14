"""Worker settings (worker.yaml, in the repo) and secrets (Windows Credential Manager).

Secrets are stored once by Khalid, as himself (the worker runs as his own Windows user), with
`C:\\SnafiWorker\\snafi.cmd set-secrets`, as "REEMA-Snafi:<NAME>" credentials for that user,
encrypted by Windows (DPAPI). There
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
            raise ConfigError(f"{name} is not stored yet; as yourself run: C:\\SnafiWorker\\snafi.cmd set-secrets")
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


def _service(data: dict, kind: str) -> Dict[str, object]:
    """{kind}_provider and {kind}_options from a section like `yahoo: {provider: yahoo_imap, timeout_seconds: 30}`."""
    section = dict(data.get(kind) or {})
    provider = str(section.pop("provider", None) or "none")
    return {f"{kind}_provider": provider, f"{kind}_options": section}


def _proactive(data: dict) -> Dict[str, object]:
    proactive, city = dict(data.get("proactive") or {}), dict(data.get("city") or {})
    out = {"mail_watch_minutes": float(proactive.get("mail_minutes", 10)),
           "quiet_minutes": int(proactive.get("quiet_minutes", 20)),
           "latitude": float(city.get("latitude", 21.4858)), "longitude": float(city.get("longitude", 39.1925))}
    if not 2 <= out["mail_watch_minutes"] <= 120 or not 0 <= out["quiet_minutes"] <= 60:
        raise ValueError("proactive.mail_minutes must be 2-120 and quiet_minutes 0-60")
    if not -90 <= out["latitude"] <= 90 or not -180 <= out["longitude"] <= 180:
        raise ValueError("city latitude or longitude is out of range")
    return out


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
    # Step 3: personal services ("none" switches one off). Google options: timeout_seconds.
    mail_provider: str = "none"
    calendar_provider: str = "none"
    files_provider: str = "none"
    google_options: Dict[str, object] = field(default_factory=dict)
    today_feed_minutes: float = 10.0
    # Step 4: the Yahoo account (a second mail account) and tasks. Options: timeout_seconds.
    yahoo_provider: str = "none"
    yahoo_options: Dict[str, object] = field(default_factory=dict)
    tasks_provider: str = "none"
    tasks_options: Dict[str, object] = field(default_factory=dict)
    # Step 5: the scheduler (mail watch every N minutes, prayer quiet time) and the prayer-time city.
    mail_watch_minutes: float = 10.0
    quiet_minutes: int = 20
    latitude: float = 21.4858
    longitude: float = 39.1925

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
                mail_provider=str((data.get("mail") or {}).get("provider") or "none"),
                calendar_provider=str((data.get("calendar") or {}).get("provider") or "none"),
                files_provider=str((data.get("files") or {}).get("provider") or "none"),
                google_options=dict(data.get("google") or {}),
                today_feed_minutes=float((data.get("today_feed") or {}).get("minutes", 10)),
                **_service(data, "yahoo"),
                **_service(data, "tasks"),
                **_proactive(data),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"worker.yaml is incomplete or invalid: {exc}") from None

"""Builds each outside service from worker.yaml. The only place a provider is chosen."""

from dataclasses import dataclass
from typing import Callable, Optional

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


@dataclass
class Personal:
    """Ahmad's personal services. A service is None when switched off (provider none).
    mail is the Gmail account and yahoo the Yahoo account (step 4); both are Mail adapters."""
    mail: Optional[object] = None
    calendar: Optional[object] = None
    files: Optional[object] = None
    auth: Optional[object] = None
    yahoo: Optional[object] = None
    tasks: Optional[object] = None

    @property
    def any(self) -> bool:
        return any((self.mail, self.calendar, self.files, self.yahoo, self.tasks))


GOOGLE_PROVIDERS = {"gmail", "google_calendar", "google_drive"}
# Step 4: each one's login, from Credential Manager. A provider not listed here needs no login (fake).
LOGINS = {
    "yahoo_imap": (("YAHOO_EMAIL", "YAHOO_APP_PASSWORD"), "Yahoo"),
    "todoist": (("TODOIST_API_TOKEN",), "Todoist"),
}


def build_personal(settings: Settings, secrets: Secrets, reload: Optional[Callable[[], Secrets]] = None,
                   transport=None) -> Personal:
    """Mail, calendar and files from worker.yaml. Unlike the brain, a missing Google connection does not
    stop the worker: the tools say "not connected" until Khalid runs connect-google, which the worker
    then picks up (GoogleAuth reloads the Google values from Credential Manager)."""
    from .google.http import GoogleAuth
    chosen = {kind: getattr(settings, f"{kind}_provider") for kind in ("mail", "calendar", "files")}
    auth = None
    if GOOGLE_PROVIDERS & set(chosen.values()):
        auth = GoogleAuth(secrets, transport, float(settings.google_options.get("timeout_seconds", 20)),
                          reload=reload)
    built = {}
    for kind, name in chosen.items():
        built[kind] = None if name == "none" else provider_class(kind, name)({}, auth)
    # Step 4: Yahoo and Todoist. A missing login does not stop the worker either: their tools say
    # "not connected" until Khalid stores it with set-secrets, which the worker then picks up.
    from .personal.credentials import StoredLogin
    for kind, adapter_kind in (("yahoo", "mail"), ("tasks", "tasks")):
        name = getattr(settings, f"{kind}_provider")
        if name == "none":
            built[kind] = None
            continue
        names, service = LOGINS.get(name, ((), name))
        login = StoredLogin(secrets, names, service, reload=reload)
        built[kind] = provider_class(adapter_kind, name)(dict(getattr(settings, f"{kind}_options")), login)
    return Personal(built["mail"], built["calendar"], built["files"], auth, built["yahoo"], built["tasks"])


def guarded_brain(settings: Settings, secrets: Secrets, pause_dir=None):
    """The configured brain, paused while not ready and after any lockdown breach, and held to the
    daily call limit (brain.daily_call_limit in worker.yaml, SEC-47)."""
    from .brain.limit import DEFAULT_LIMIT, DailyLimit, LimitedBrain
    from .brain.pause import GuardedBrain, PauseFile
    folder = pause_dir or worker_data_dir()
    limit = DailyLimit(folder / CALLS_FILE, int(settings.brain_options.get("daily_call_limit", DEFAULT_LIMIT)),
                       settings.time_zone)
    return GuardedBrain(LimitedBrain(build("brain", settings, secrets), limit), PauseFile(folder / PAUSE_FILE))

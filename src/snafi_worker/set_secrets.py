"""One-time setup: asks Khalid for each Snafi worker setting and stores it in Windows
Credential Manager for the Windows user that runs it: Khalid, who the worker runs as. Keys are
typed without being shown (getpass) and are never printed, logged or written to a file. Run it
yourself, as yourself, in a normal (not admin) PowerShell window, not from Claude Code:

  C:\\SnafiWorker\\snafi.cmd set-secrets            ask for each value
  C:\\SnafiWorker\\snafi.cmd set-secrets --status   which are stored (names only)
  C:\\SnafiWorker\\snafi.cmd set-secrets --remove   delete them all

Press Enter at any question to keep the value already stored. The backup signing key is
made here once, at random, and never shown.
"""

import argparse
import base64
import getpass
import json
import re
import secrets
import sys
from urllib.parse import urlparse

from .secret_store import NAMES, SecretStoreError, WindowsCredentials

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def check_url(value: str) -> str:
    parsed = urlparse(value.strip().rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        raise ValueError("must be the project URL, like https://abcd.supabase.co")
    return f"https://{parsed.netloc}"


def _jwt_role(token: str) -> str:
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        return ""
    return str(claims.get("role") or "") if isinstance(claims, dict) else ""  # SEC-61: a non-object payload is no role


def check_secret_key(value: str) -> str:
    value = value.strip()
    if value.startswith("sb_publishable_") or _jwt_role(value) == "anon":
        raise ValueError("that is the publishable key; the worker needs the secret key")
    if not (value.startswith("sb_secret_") or _jwt_role(value) == "service_role"):
        raise ValueError("does not look like a Supabase secret key (sb_secret_...)")
    return value


def check_owner(value: str) -> str:
    value = value.strip().lower()
    if not UUID.match(value):
        raise ValueError("must be your user's UID from Authentication -> Users")
    return value


def check_gemini(value: str) -> str:
    """Google's key formats change (classic keys are "AIza..." with letters, digits, _ and -; newer ones
    may hold other characters, such as dots), so any printable ASCII is accepted. Refused only: what cannot
    be a working key, or a broken paste. The message never shows the key."""
    value = value.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("it contains a control character, so the paste did not work; "
                         "paste with a right-click (or Ctrl+Shift+V) instead of Ctrl+V")
    if any(c.isspace() for c in value):
        raise ValueError("it contains a space; copy the key again from Google AI Studio")
    if not value.isascii():
        raise ValueError("it contains a non-English character; copy the key again from Google AI Studio")
    if not 20 <= len(value) <= 512:
        raise ValueError(f"it is {len(value)} characters long; a Gemini API key has 20 to 512 characters")
    lower = value.lower()
    if lower.startswith(("sb_secret_", "sb_publishable_", "http:", "https:")) or _jwt_role(value):
        raise ValueError("that is a Supabase value, not the Gemini key; it would be sent to Google (SEC-58)")
    return value


def check_anthropic(value: str) -> str:
    """A Claude API key ("sk-ant-..."), never an admin key. The message never shows the key."""
    value = check_gemini(value).strip()  # same paste checks (control characters, spaces, length, Supabase values)
    if value.startswith("sk-ant-admin"):
        raise ValueError("that is an Admin API key; create a normal API key in the Claude Console")
    if not value.startswith("sk-ant-"):
        raise ValueError("does not look like a Claude API key (it starts with sk-ant-)")
    return value


QUESTIONS = (
    ("SNAFI_SUPABASE_URL", "Supabase project URL", check_url, False),
    ("SNAFI_SUPABASE_SECRET_KEY", "Supabase secret key (hidden while you type or paste)", check_secret_key, True),
    ("SNAFI_OWNER_USER_ID", "Your Supabase user UID", check_owner, False),
    ("GEMINI_API_KEY", "Gemini API key (hidden while you type or paste)", check_gemini, True),
    ("ANTHROPIC_API_KEY", "Claude API key (hidden while you type or paste)", check_anthropic, True),
)
# Each brain key is asked for only while that brain is chosen in worker.yaml.
BRAIN_KEYS = {"GEMINI_API_KEY": "gemini_api", "ANTHROPIC_API_KEY": "claude_api"}


def ask(store, name, label, check, hidden, prompt=getpass.getpass, plain=input, out=print) -> bool:
    have = store.read(name) is not None
    suffix = " [Enter keeps the stored one]" if have else ""
    for _ in range(3):
        raw = (prompt if hidden else plain)(f"{label}{suffix}: ")
        if not raw.strip() and have:
            out(f"  kept {name}")
            return True
        try:
            store.write(name, check(raw))
            out(f"  stored {name}")
            return True
        except ValueError as exc:
            out(f"  not stored: {exc}")
    return False


def questions(brain_provider: str):
    """Only what the configured services need: a brain's key only while that brain is chosen."""
    return [q for q in QUESTIONS if BRAIN_KEYS.get(q[0], brain_provider) == brain_provider]


def run(store, prompt=getpass.getpass, plain=input, out=print, brain_provider: str = "") -> int:
    if not brain_provider:
        from .config import Settings
        brain_provider = Settings.load().brain_provider
    ok = all([ask(store, n, label, check, hidden, prompt, plain, out)
              for n, label, check, hidden in questions(brain_provider)])
    if store.read("SNAFI_BACKUP_SIGNING_KEY") is None:
        store.write("SNAFI_BACKUP_SIGNING_KEY", secrets.token_hex(32))
        out("  made SNAFI_BACKUP_SIGNING_KEY (random, never shown)")
    out("All set." if ok else "Some values were not stored; run this again.")
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.snafi_worker.set_secrets")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true")
    group.add_argument("--remove", action="store_true")
    args = parser.parse_args(argv)
    try:
        store = WindowsCredentials()
        if args.status:
            for name in NAMES:
                print(f"{name}: {'stored' if store.read(name) else 'missing'}")
            return 0
        if args.remove:
            for name in NAMES:
                store.delete(name)
            print("Removed all Snafi worker values from Credential Manager.")
            return 0
        return run(store)
    except SecretStoreError as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nStopped; nothing more was changed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""One-time setup: asks Khalid for each Snafi worker setting and stores it in Windows
Credential Manager for the Windows user that runs it: Khalid, who the worker runs as. Keys are
typed without being shown (getpass) and are never printed, logged or written to a file. Run it
yourself, as yourself, in a normal (not admin) PowerShell window, not from Claude Code:

  C:\\SnafiWorker\\snafi.cmd set-secrets            ask for each value
  C:\\SnafiWorker\\snafi.cmd set-secrets --status   which are stored (names only)
  C:\\SnafiWorker\\snafi.cmd set-secrets --remove   delete them all
  C:\\SnafiWorker\\snafi.cmd set-secrets --push-key print the push public key again (for Vercel)

Press Enter at any question to keep the value already stored. The backup signing key and the
Web Push (VAPID) private key are made here once, at random, and never shown; only the push
key's public half is printed, for Vercel.
"""

import argparse
import base64
import getpass
import json
import re
import secrets
import sys
from typing import Optional
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


def check_google_client_id(value: str) -> str:
    """The OAuth client ID of the Desktop app client in Google Cloud (it is not secret, but stays here too)."""
    value = value.strip()
    if not re.fullmatch(r"[0-9]{6,30}-[a-z0-9]{10,64}\.apps\.googleusercontent\.com", value):
        raise ValueError("does not look like a Google OAuth client ID (…apps.googleusercontent.com)")
    return value


def check_google_client_secret(value: str) -> str:
    """The Desktop client's secret ("GOCSPX-..."). The message never shows it."""
    value = check_gemini(value).strip()  # same paste checks (control characters, spaces, length, Supabase values)
    if value.startswith(("sk-ant-", "AIza")) or value.endswith(".apps.googleusercontent.com"):
        raise ValueError("that is not the client secret (copy the Client secret, not the ID or another key)")
    return value


YAHOO_ADDRESS = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def check_yahoo_email(value: str) -> str:
    """Khalid's Yahoo address, the login for IMAP and SMTP (it is not secret, but stays here too)."""
    value = value.strip()
    if not YAHOO_ADDRESS.match(value) or len(value) > 254:
        raise ValueError("does not look like an email address, like name@yahoo.com")
    return value


def check_yahoo_app_password(value: str) -> str:
    """A Yahoo app password: 16 letters (Yahoo may show it in groups of four; the spaces are removed).
    Never your normal Yahoo password, which IMAP refuses anyway. The message never shows it."""
    value = "".join(value.split())
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("it contains a control character, so the paste did not work; "
                         "paste with a right-click (or Ctrl+Shift+V) instead of Ctrl+V")
    if not re.fullmatch(r"[A-Za-z]{16}", value):
        raise ValueError(f"a Yahoo app password is 16 letters; this is {len(value)} characters. "
                         "Make one in Yahoo: Account security, Generate app password")
    return value.lower()


def check_todoist_token(value: str) -> str:
    """The Todoist API token (Settings, Integrations, Developer): 40 hex characters. Never shown."""
    value = value.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("it contains a control character, so the paste did not work; "
                         "paste with a right-click (or Ctrl+Shift+V) instead of Ctrl+V")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise ValueError(f"a Todoist API token is 40 letters and digits (0-9, a-f); this is {len(value)} characters. "
                         "Copy it again from Todoist: Settings, Integrations, Developer")
    return value.lower()


def check_push_contact(value: str) -> str:
    """Step 5: the Snafi site's address (https://….vercel.app), sent to the push services as the
    contact for Web Push (VAPID "sub"). Just the address, no path."""
    parsed = urlparse(value.strip().rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or "@" in parsed.netloc:
        raise ValueError("must be the Snafi site's address, like https://snafi.vercel.app")
    if parsed.hostname in ("localhost", "127.0.0.1") or (parsed.hostname or "").endswith(".supabase.co"):
        raise ValueError("must be the Snafi site's public address on Vercel, not localhost or Supabase")
    return f"https://{parsed.netloc}"


QUESTIONS = (
    ("SNAFI_SUPABASE_URL", "Supabase project URL", check_url, False),
    ("SNAFI_SUPABASE_SECRET_KEY", "Supabase secret key (hidden while you type or paste)", check_secret_key, True),
    ("SNAFI_OWNER_USER_ID", "Your Supabase user UID", check_owner, False),
    ("GEMINI_API_KEY", "Gemini API key (hidden while you type or paste)", check_gemini, True),
    ("ANTHROPIC_API_KEY", "Claude API key (hidden while you type or paste)", check_anthropic, True),
    ("GOOGLE_CLIENT_ID", "Google OAuth client ID (Desktop app)", check_google_client_id, False),
    ("GOOGLE_CLIENT_SECRET", "Google OAuth client secret (hidden while you type or paste)", check_google_client_secret, True),
    ("YAHOO_EMAIL", "Your Yahoo email address", check_yahoo_email, False),
    ("YAHOO_APP_PASSWORD", "Yahoo app password, 16 letters (hidden while you type or paste)", check_yahoo_app_password, True),
    ("TODOIST_API_TOKEN", "Todoist API token (hidden while you type or paste)", check_todoist_token, True),
    ("SNAFI_PUSH_CONTACT", "Snafi site address for push notifications (like https://snafi.vercel.app)",
     check_push_contact, False),
)
# Each brain key is asked for only while that brain is chosen in worker.yaml.
BRAIN_KEYS = {"GEMINI_API_KEY": "gemini_api", "ANTHROPIC_API_KEY": "claude_api"}
# The Google client is asked for only while a Google service is chosen (mail, calendar or files).
GOOGLE_KEYS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
# Step 4: Yahoo's login only while yahoo is yahoo_imap, Todoist's token only while tasks is todoist.
YAHOO_KEYS = ("YAHOO_EMAIL", "YAHOO_APP_PASSWORD")
TODOIST_KEYS = ("TODOIST_API_TOKEN",)
# Step 5: the push contact, asked for in every real run (push is part of every Snafi worker).
PUSH_KEYS = ("SNAFI_PUSH_CONTACT",)


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


def questions(brain_provider: str, google: bool = False, yahoo: bool = False, todoist: bool = False,
              push: bool = False):
    """Only what the configured services need: a brain's key only while that brain is chosen, the
    Google client only while a Google service is, and Yahoo's or Todoist's login only while chosen."""
    return [q for q in QUESTIONS if BRAIN_KEYS.get(q[0], brain_provider) == brain_provider
            and (google or q[0] not in GOOGLE_KEYS) and (yahoo or q[0] not in YAHOO_KEYS)
            and (todoist or q[0] not in TODOIST_KEYS) and (push or q[0] not in PUSH_KEYS)]


def run(store, prompt=getpass.getpass, plain=input, out=print, brain_provider: str = "",
        google: Optional[bool] = None, yahoo: Optional[bool] = None, todoist: Optional[bool] = None,
        push: Optional[bool] = None) -> int:
    if not brain_provider:  # from worker.yaml, as the worker will run
        push = True if push is None else push
        from .config import Settings
        from .services import GOOGLE_PROVIDERS
        settings = Settings.load()
        brain_provider = settings.brain_provider
        if google is None:
            google = bool(GOOGLE_PROVIDERS & {settings.mail_provider, settings.calendar_provider,
                                              settings.files_provider})
        if yahoo is None:
            yahoo = settings.yahoo_provider == "yahoo_imap"
        if todoist is None:
            todoist = settings.tasks_provider == "todoist"
    google, yahoo, todoist, push = bool(google), bool(yahoo), bool(todoist), bool(push)
    ok = all([ask(store, n, label, check, hidden, prompt, plain, out)
              for n, label, check, hidden in questions(brain_provider, google, yahoo, todoist, push)])
    if google and ok:
        out("Next, connect your Google account once: C:\\SnafiWorker\\snafi.cmd connect-google")
    if store.read("SNAFI_BACKUP_SIGNING_KEY") is None:
        store.write("SNAFI_BACKUP_SIGNING_KEY", secrets.token_hex(32))
        out("  made SNAFI_BACKUP_SIGNING_KEY (random, never shown)")
    made = make_push_key(store)
    if made:
        out("  made SNAFI_VAPID_PRIVATE_KEY (random, never shown)")
    print_push_public_key(store, out)
    out("All set." if ok else "Some values were not stored; run this again.")
    return 0 if ok else 1


def make_push_key(store) -> bool:
    """Step 5: the Web Push (VAPID) private key, made here once at random and never shown."""
    if store.read("SNAFI_VAPID_PRIVATE_KEY") is not None:
        return False
    from .proactive.webpush import new_private_key
    store.write("SNAFI_VAPID_PRIVATE_KEY", new_private_key())
    return True


def print_push_public_key(store, out=print) -> bool:
    """Prints only the PUBLIC half, for Vercel's NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY. Not a secret."""
    value = store.read("SNAFI_VAPID_PRIVATE_KEY")
    if not value:
        out("No push key yet; run set-secrets once to make it.")
        return False
    from .proactive.webpush import PushError, load_private_key, public_key_b64
    try:
        public = public_key_b64(load_private_key(value))
    except PushError:
        out("The stored push key is damaged; remove it and run set-secrets again.")
        return False
    out("Push public key (put it in Vercel as NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY; it is not secret):")
    out(f"  {public}")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.snafi_worker.set_secrets")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true")
    group.add_argument("--remove", action="store_true")
    group.add_argument("--push-key", action="store_true", help="print the push PUBLIC key again (for Vercel)")
    args = parser.parse_args(argv)
    try:
        store = WindowsCredentials()
        if args.push_key:
            return 0 if print_push_public_key(store) else 1
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

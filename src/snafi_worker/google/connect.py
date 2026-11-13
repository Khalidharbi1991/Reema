"""Connect Snafi to Khalid's Google account, once (Google's "installed app" sign-in with PKCE).

Khalid runs this himself, as himself, on the PC, never from Claude Code:

  C:\\SnafiWorker\\snafi.cmd connect-google               sign in and store the connection
  C:\\SnafiWorker\\snafi.cmd connect-google --status      is it stored, and does Google still accept it
  C:\\SnafiWorker\\snafi.cmd connect-google --disconnect  cancel it at Google and delete it from the PC

How it works: a one-time listener on 127.0.0.1 (this PC only, a random port, for at most five
minutes) waits for Google's answer after Khalid signs in in his browser. The answer must carry
the random state this run made, and the code is exchanged with the PKCE verifier only this run
knows. The refresh token is written straight into Credential Manager ("REEMA-Snafi:
GOOGLE_REFRESH_TOKEN") and is never printed, logged or saved in a file. GOOGLE_CLIENT_ID and
GOOGLE_CLIENT_SECRET must be stored first with set-secrets.
"""

import argparse
import base64
import hashlib
import hmac
import secrets as random
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Dict, Optional, Tuple

from .http import REVOKE_URL, SCOPES, TOKEN_URL, GoogleAuth, GoogleAuthError, GoogleError, Transport, \
    _json, urllib_transport

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
WAIT_SECONDS = 300
PAGE = ("<!doctype html><meta charset=utf-8><title>Snafi</title>"
        "<p style='font-family:sans-serif'>{text}</p>").encode
DONE_PAGE = "Snafi received Google's answer. You can close this window and go back to the PowerShell window."
FAIL_PAGE = "Snafi did not accept this answer. Go back to the PowerShell window."


class ConnectError(Exception):
    pass


def pkce_pair() -> Tuple[str, str]:
    verifier = random.token_urlsafe(64)  # 86 characters, within PKCE's 43-128
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


def auth_url(client_id: str, redirect_uri: str, state: str, challenge: str) -> str:
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": " ".join(SCOPES),
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        "access_type": "offline", "prompt": "consent",
    })


def parse_callback(path: str, state: str) -> str:
    """The authorisation code from Google's redirect, only if it carries this run's state."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    got = (query.get("state") or [""])[0]
    if not got or not hmac.compare_digest(got, state):
        raise ConnectError("the answer did not come from this sign-in (state mismatch); nothing was stored")
    if query.get("error"):
        raise ConnectError("Google sign-in was cancelled or refused; nothing was stored")
    code = (query.get("code") or [""])[0]
    if not code:
        raise ConnectError("Google sent no code; nothing was stored")
    return code


def exchange(code: str, verifier: str, redirect_uri: str, client_id: str, client_secret: str,
             transport: Transport = urllib_transport) -> str:
    """Trade the code for a refresh token; require every scope Snafi needs."""
    form = urllib.parse.urlencode({"code": code, "code_verifier": verifier, "redirect_uri": redirect_uri,
                                   "client_id": client_id, "client_secret": client_secret,
                                   "grant_type": "authorization_code"}).encode("ascii")
    status, raw = transport("POST", TOKEN_URL, {"content-type": "application/x-www-form-urlencoded"}, form, 30)
    data = _json(raw)
    if status != 200:
        raise ConnectError(f"Google did not accept the sign-in (HTTP {status}); nothing was stored")
    granted = set(str(data.get("scope") or "").split())
    missing = [s.rsplit("/", 1)[-1] for s in SCOPES if s not in granted]
    if missing:
        raise ConnectError("not every permission was ticked (missing: " + ", ".join(missing)
                           + "); run connect-google again and tick every box. Nothing was stored")
    token = data.get("refresh_token")
    if not isinstance(token, str) or not token:
        raise ConnectError("Google sent no refresh token; nothing was stored")
    return token


def wait_for_code(state: str, on_ready: Callable[[str], None], timeout: float = WAIT_SECONDS) -> Tuple[str, str]:
    """Listen once on 127.0.0.1 for Google's redirect. Returns (code, redirect_uri)."""
    result: Dict[str, object] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server's name)
            if urllib.parse.urlparse(self.path).path != "/":
                self.send_response(404)
                self.end_headers()
                return
            try:
                result["code"] = parse_callback(self.path, state)
                page = DONE_PAGE
            except ConnectError as exc:
                result["error"] = str(exc)
                page = FAIL_PAGE
            body = PAGE(text=page)
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            done.set()

        def log_message(self, *args):  # never print the request line: it holds the code
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    try:
        on_ready(redirect_uri)
        if not done.wait(timeout):
            raise ConnectError("no answer from Google within five minutes; nothing was stored")
    finally:
        server.shutdown()
        server.server_close()
    if "error" in result:
        raise ConnectError(str(result["error"]))
    return str(result["code"]), redirect_uri


def connect(store, out=print, open_browser: Optional[Callable[[str], bool]] = None,
            transport: Transport = urllib_transport, waiter=wait_for_code) -> int:
    client_id, client_secret = store.read("GOOGLE_CLIENT_ID"), store.read("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        out("Store GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET first: C:\\SnafiWorker\\snafi.cmd set-secrets")
        return 2
    if open_browser is None:
        import webbrowser
        open_browser = webbrowser.open
    verifier, challenge = pkce_pair()
    state = random.token_urlsafe(32)

    def ready(redirect_uri: str) -> None:
        url = auth_url(client_id, redirect_uri, state, challenge)
        out("Your browser will open Google's sign-in. Sign in with your personal Google account.")
        out("If Google warns that the app is unverified: Advanced, then Go to Snafi. Tick every box.")
        out("If the browser does not open, paste this address into it:\n" + url)
        open_browser(url)

    try:
        code, redirect_uri = waiter(state, ready)
        token = exchange(code, verifier, redirect_uri, client_id, client_secret, transport)
    except ConnectError as exc:
        out(f"Not connected: {exc}.")
        return 1
    except GoogleError as exc:
        out(f"Not connected: {exc}.")
        return 1
    store.write("GOOGLE_REFRESH_TOKEN", token)
    out("Connected. The connection is stored in Credential Manager (never shown). "
        "The running Snafi worker picks it up within five minutes.")
    return 0


class _StoreSecrets:
    """Secrets-like view of the credential store, for GoogleAuth."""

    def __init__(self, store):
        self._store = store

    def has(self, name):
        return bool(self._store.read(name))

    def get(self, name):
        return self._store.read(name) or ""


def status(store, out=print, transport: Transport = urllib_transport) -> int:
    if not store.read("GOOGLE_REFRESH_TOKEN"):
        out("Google: not connected.")
        return 1
    try:
        GoogleAuth(_StoreSecrets(store), transport).access_token()
    except GoogleAuthError:
        out("Google: stored, but Google no longer accepts it. Run connect-google again.")
        return 1
    except GoogleError as exc:
        out(f"Google: stored; could not check it now ({exc}).")
        return 1
    out("Google: connected and accepted.")
    return 0


def disconnect(store, out=print, transport: Transport = urllib_transport) -> int:
    token = store.read("GOOGLE_REFRESH_TOKEN")
    if token:
        try:
            status_code, _ = transport("POST", REVOKE_URL, {"content-type": "application/x-www-form-urlencoded"},
                                       urllib.parse.urlencode({"token": token}).encode("ascii"), 20)
            out("Cancelled at Google." if status_code == 200 else
                f"Google did not confirm the cancel (HTTP {status_code}); remove Snafi at myaccount.google.com/permissions.")
        except GoogleError:
            out("Could not reach Google; remove Snafi at myaccount.google.com/permissions.")
    store.delete("GOOGLE_REFRESH_TOKEN")
    out("The Google connection is deleted from this PC.")
    return 0


def main(argv=None) -> int:
    from ..secret_store import SecretStoreError, WindowsCredentials
    parser = argparse.ArgumentParser(prog="snafi.cmd connect-google")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true")
    group.add_argument("--disconnect", action="store_true")
    args = parser.parse_args(argv)
    try:
        store = WindowsCredentials()
        if args.status:
            return status(store)
        if args.disconnect:
            return disconnect(store)
        return connect(store)
    except SecretStoreError as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped; nothing was stored.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

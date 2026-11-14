"""HTTPS to Google with the standard library, and the access token kept in memory.

Only Google's own API hosts are ever called (HOSTS). Redirects are refused, so a token is
never resent to another address. Tokens never appear in a URL, a log line, repr or an error.

Errors:
  GoogleNotConnected  no refresh token stored yet (Khalid runs connect-google once)
  GoogleAuthError     Google refused the refresh token (expired after 7 days in Testing,
                      revoked, or the password changed): Khalid reconnects
  GoogleError         anything else; retryable when trying again may help
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, Optional, Tuple

TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
HOSTS = frozenset({"oauth2.googleapis.com", "gmail.googleapis.com", "www.googleapis.com"})
SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
)
SECRET_NAMES = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
MAX_RESPONSE = 5_000_000

# (method, url, headers, body, timeout) -> (status, body bytes)
Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, bytes]]


class GoogleError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class GoogleAuthError(GoogleError):
    """Google refused the stored refresh token: reconnect with connect-google."""


class GoogleNotConnected(GoogleError):
    """No Google connection is stored yet."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def check_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.port:
        raise GoogleError("internal error: not a Google API address")
    return url


def urllib_transport(method: str, url: str, headers: Dict[str, str], body: Optional[bytes],
                     timeout: float) -> Tuple[int, bytes]:
    request = urllib.request.Request(check_url(url), data=body, headers=headers, method=method)
    try:
        with _OPENER.open(request, timeout=timeout) as response:  # noqa: S310 (Google hosts only)
            return response.status, response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read(MAX_RESPONSE + 1) if exc.fp else b"")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GoogleError(f"Google unreachable: {type(exc).__name__}", retryable=True) from None
    except ValueError:  # an invalid header value: never shown, it could hold a token
        raise GoogleError("Google request could not be sent (invalid setting)") from None


def _usable(value: str, name: str) -> str:
    if not value or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
        raise GoogleAuthError(f"{name} is not usable; store it again")
    return value


class GoogleAuth:
    """Turns the stored refresh token into short-lived access tokens, kept in memory only."""

    RELOAD_SECONDS = 300

    def __init__(self, secrets, transport: Optional[Transport] = None, timeout: float = 20,
                 clock: Callable[[], float] = time.monotonic, reload: Optional[Callable[[], object]] = None):
        self._secrets = secrets
        self._transport = transport or urllib_transport
        self.timeout = float(timeout)
        self._clock = clock
        self._reload = reload            # re-reads the Google values from Credential Manager
        self._reloaded_at: Optional[float] = None
        self._token: Optional[str] = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return "GoogleAuth(tokens=hidden)"

    @property
    def connected(self) -> bool:
        return all(self._secrets.has(name) for name in SECRET_NAMES)

    def _maybe_reload(self) -> None:
        """After connect-google (or a reconnect), pick up the new values without restarting the worker."""
        if self._reload is None:
            return
        now = self._clock()
        if self._reloaded_at is not None and now - self._reloaded_at < self.RELOAD_SECONDS:
            return
        self._reloaded_at = now
        try:
            fresh = self._reload()
        except Exception:  # Credential Manager unreadable: keep what we have
            return
        if fresh is not None:
            self._secrets = fresh

    def access_token(self) -> str:
        with self._lock:
            if self._token and self._clock() < self._expires:
                return self._token
            if not self.connected:
                self._maybe_reload()
            if not self.connected:
                raise GoogleNotConnected("Google is not connected yet; on the PC run: snafi.cmd connect-google")
            try:
                return self._refresh()
            except GoogleAuthError:
                before = self._secrets
                self._maybe_reload()
                if self._secrets is before or not self.connected:
                    raise
                return self._refresh()

    def _refresh(self) -> str:
        """Called with the lock held."""
        form = urllib.parse.urlencode({
            "client_id": _usable(self._secrets.get("GOOGLE_CLIENT_ID"), "GOOGLE_CLIENT_ID"),
            "client_secret": _usable(self._secrets.get("GOOGLE_CLIENT_SECRET"), "GOOGLE_CLIENT_SECRET"),
            "refresh_token": _usable(self._secrets.get("GOOGLE_REFRESH_TOKEN"), "GOOGLE_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        }).encode("ascii")
        status, raw = self._transport("POST", TOKEN_URL, {"content-type": "application/x-www-form-urlencoded"},
                                      form, self.timeout)
        data = _json(raw)
        if status in (400, 401) and data.get("error") in ("invalid_grant", "unauthorized_client", "invalid_client"):
            raise GoogleAuthError("Google refused the stored connection; on the PC run: snafi.cmd connect-google")
        if status == 429 or status >= 500:
            raise GoogleError(f"Google busy (HTTP {status})", retryable=True)
        token = data.get("access_token")
        if status != 200 or not isinstance(token, str) or not token:
            raise GoogleError(f"Google token refresh failed (HTTP {status})")
        self._token = _usable(token, "access token")
        try:
            lifetime = int(data.get("expires_in") or 3600)
        except (TypeError, ValueError):
            lifetime = 3600
        self._expires = self._clock() + max(60, lifetime - 120)
        return self._token

    def forget(self) -> None:
        with self._lock:
            self._token, self._expires = None, 0.0


class GoogleApi:
    """Authorised JSON calls to one Google API."""

    def __init__(self, auth: GoogleAuth, transport: Optional[Transport] = None):
        self.auth = auth
        self._transport = transport or auth._transport

    def __repr__(self) -> str:
        return f"{type(self).__name__}(tokens=hidden)"

    def call(self, method: str, url: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
             raw: bool = False):
        if params:
            url = url + "?" + urllib.parse.urlencode(params, doseq=True)
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        for attempt in (1, 2):
            headers = {"authorization": "Bearer " + self.auth.access_token(), "accept": "application/json"}
            if payload is not None:
                headers["content-type"] = "application/json; charset=utf-8"
            status, data = self._transport(method, url, headers, payload, self.auth.timeout)
            if status == 401 and attempt == 1:  # the access token expired early: refresh once
                self.auth.forget()
                continue
            break
        if len(data) > MAX_RESPONSE:
            raise GoogleError("Google's answer was too large")
        if status in (200, 204):
            if raw:
                return data
            return _json(data) if data else {}
        if status == 401:
            raise GoogleAuthError("Google refused the connection; on the PC run: snafi.cmd connect-google")
        if status == 404 or status == 410:
            raise GoogleError("not found in your Google account")
        if status == 403:
            reason = _reason(data)
            if reason in ("rateLimitExceeded", "userRateLimitExceeded"):
                raise GoogleError("Google asked us to slow down", retryable=True)
            raise GoogleError(f"Google refused this ({reason or 'HTTP 403'})")
        if status == 429 or status >= 500:
            raise GoogleError(f"Google busy (HTTP {status})", retryable=True)
        raise GoogleError(f"Google refused the request (HTTP {status})")


def _json(raw: bytes) -> Dict:
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _reason(raw: bytes) -> str:
    error = _json(raw).get("error")
    if isinstance(error, dict):
        for item in error.get("errors") or []:
            if isinstance(item, dict) and isinstance(item.get("reason"), str):
                return item["reason"][:60]
    return ""

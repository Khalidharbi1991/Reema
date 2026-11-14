"""Web Push from the worker: RFC 8291 message encryption (aes128gcm) and RFC 8292 VAPID, written
here with the `cryptography` package (already in the lock), so no Web Push library is installed.

Safety, enforced here:
  * Only the four browser push services are ever posted to (ENDPOINT, the same rule as the database's
    push_endpoint_ok): Apple, Google (FCM), Mozilla and Microsoft (WNS). Anything else is refused
    before a connection is made, so a planted address cannot make the PC call another host (SSRF).
  * Redirects are never followed.
  * The private VAPID key (SNAFI_VAPID_PRIVATE_KEY, Credential Manager) is never logged or shown;
    only its public half leaves the PC (in the Authorization header, as the standard requires).
  * What is pushed is only payload(): a kind, a language and a notification id. Never a title, a
    sender, a subject or a reminder's text, so a lock screen can show nothing private, and Apple's,
    Google's or Mozilla's servers never see any.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENDPOINT = re.compile(
    r"^https://(fcm\.googleapis\.com|web\.push\.apple\.com|[a-z0-9-]+\.push\.apple\.com|"
    r"updates\.push\.services\.mozilla\.com|[a-z0-9-]+\.notify\.windows\.com)/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+\Z")
KINDS = ("reminder", "brief", "mail", "test")
LANGS = ("en", "ar")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
RECORD_SIZE = 4096
TTL_SECONDS = 24 * 3600
JWT_HOURS = 12
TIMEOUT = 10.0
SUBJECT = re.compile(r"^(https://[A-Za-z0-9.-]+(:\d{1,5})?/?|mailto:[^\s@]{1,64}@[A-Za-z0-9.-]{1,190})\Z")


class PushError(Exception):
    pass


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64u(text: str) -> bytes:
    if not isinstance(text, str) or not re.fullmatch(r"[A-Za-z0-9_-]*", text):
        raise PushError("not base64url")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def endpoint_ok(endpoint: str) -> bool:
    return isinstance(endpoint, str) and 20 <= len(endpoint) <= 1000 and ENDPOINT.match(endpoint) is not None


def payload(kind: str, lang: str, notification_id: str) -> bytes:
    """The ONLY thing pushed: no title, no body, no sender, no subject. The phone shows fixed text."""
    if kind not in KINDS or lang not in LANGS or not UUID.match(notification_id or ""):
        raise PushError("refused: a push carries only a known kind, a language and an id")
    return json.dumps({"k": kind, "l": lang, "n": notification_id}, separators=(",", ":")).encode("ascii")


# ---------- keys ----------
def new_private_key() -> str:
    """A new VAPID private key as base64url of its 32-byte scalar (what set-secrets stores)."""
    key = ec.generate_private_key(ec.SECP256R1())
    return b64u(key.private_numbers().private_value.to_bytes(32, "big"))


def load_private_key(text: str) -> ec.EllipticCurvePrivateKey:
    """SEC-123: any damaged value is a PushError (never the key in the message)."""
    try:
        raw = unb64u((text or "").strip())
        if len(raw) != 32:
            raise ValueError
        return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    except Exception:  # noqa: BLE001 (bad base64, wrong length, a scalar out of range, …)
        raise PushError("SNAFI_VAPID_PRIVATE_KEY is not a VAPID private key; remove it and run set-secrets") from None


def public_key_b64(private: ec.EllipticCurvePrivateKey) -> str:
    """The public key the app needs (NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY): 65 bytes, base64url."""
    return b64u(private.public_key().public_bytes(serialization.Encoding.X962,
                                                  serialization.PublicFormat.UncompressedPoint))


# ---------- RFC 8291 ----------
def _hmac(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def encrypt(plaintext: bytes, p256dh: str, auth: str, salt: Optional[bytes] = None,
            server_key: Optional[ec.EllipticCurvePrivateKey] = None) -> bytes:
    """One aes128gcm record (RFC 8188) with the RFC 8291 keys. salt and server_key only for tests."""
    ua_public = unb64u(p256dh)
    auth_secret = unb64u(auth)
    if len(ua_public) != 65 or ua_public[0] != 4 or len(auth_secret) != 16:
        raise PushError("the phone's push keys are not valid")
    if len(plaintext) > RECORD_SIZE - 16 - 1 - 86:
        raise PushError("push message too long")
    try:
        ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    except ValueError:
        raise PushError("the phone's push key is not on the curve") from None
    server_key = server_key or ec.generate_private_key(ec.SECP256R1())
    as_public = server_key.public_key().public_bytes(serialization.Encoding.X962,
                                                     serialization.PublicFormat.UncompressedPoint)
    shared = server_key.exchange(ec.ECDH(), ua_key)
    prk_key = _hmac(auth_secret, shared)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_public + as_public + b"\x01")
    salt = salt if salt is not None else os.urandom(16)
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    record = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    return salt + struct.pack("!IB", RECORD_SIZE, len(as_public)) + as_public + record


# ---------- RFC 8292 ----------
def vapid_header(endpoint: str, private: ec.EllipticCurvePrivateKey, subject: str, now: Optional[float] = None) -> str:
    if not SUBJECT.match(subject or ""):
        raise PushError("the push contact must be the site's https address or a mailto: address")
    parts = urllib.parse.urlsplit(endpoint)
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int((now or time.time()) + JWT_HOURS * 3600),
              "sub": subject}
    head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64u(json.dumps(claims, separators=(",", ":")).encode())
    der = private.sign(f"{head}.{body}".encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={head}.{body}.{signature}, k={public_key_b64(private)}"


# ---------- sending ----------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_post(url: str, headers: Dict[str, str], body: bytes, timeout: float) -> int:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _OPENER.open(request, timeout=timeout) as response:  # noqa: S310 (endpoint_ok checked first)
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0


@dataclass
class Outcome:
    ok: bool
    gone: bool = False      # the phone unsubscribed (404/410): the address is removed
    status: int = 0


class PushSender:
    """Posts one encrypted push to one phone. post(url, headers, body, timeout) -> HTTP status (0 = no answer)."""

    def __init__(self, private_key: str, subject: str, post: Optional[Callable[..., int]] = None):
        self._key = load_private_key(private_key)
        if not SUBJECT.match(subject or ""):
            raise PushError("the push contact must be the site's https address or a mailto: address")
        self.subject = subject
        self._post = post or urllib_post

    def __repr__(self) -> str:
        return "PushSender(key=hidden)"

    @property
    def public_key(self) -> str:
        return public_key_b64(self._key)

    def send(self, subscription: Dict, kind: str, lang: str, notification_id: str, urgent: bool = False) -> Outcome:
        endpoint = subscription.get("endpoint", "")
        if not endpoint_ok(endpoint):
            return Outcome(False, gone=True)  # never posted to; the row is removed
        body = encrypt(payload(kind, lang, notification_id), subscription.get("p256dh", ""), subscription.get("auth", ""))
        headers = {"TTL": str(TTL_SECONDS), "Urgency": "high" if urgent else "normal",
                   "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
                   "Authorization": vapid_header(endpoint, self._key, self.subject),
                   "Topic": notification_id.replace("-", "")[:32]}
        status = self._post(endpoint, headers, body, TIMEOUT)
        if status in (200, 201, 202):
            return Outcome(True, status=status)
        return Outcome(False, gone=status in (404, 410), status=status)


def decrypt_for_tests(body: bytes, ua_private: ec.EllipticCurvePrivateKey, auth: str) -> bytes:
    """The phone's side of RFC 8291, for the offline tests only."""
    salt, rs, idlen = body[:16], *struct.unpack("!IB", body[16:21])
    as_public = body[21:21 + idlen]
    record = body[21 + idlen:]
    ua_public = ua_private.public_key().public_bytes(serialization.Encoding.X962,
                                                    serialization.PublicFormat.UncompressedPoint)
    shared = ua_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))
    ikm = _hmac(_hmac(unb64u(auth), shared), b"WebPush: info\x00" + ua_public + as_public + b"\x01")
    prk = _hmac(salt, ikm)
    plain = AESGCM(_hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]).decrypt(
        _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12], record, None)
    return plain.rstrip(b"\x00")[:-1]

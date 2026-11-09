"""Supabase through its REST interface (PostgREST), with the secret key. The secret key
bypasses row-level security, so every write here sets user_id explicitly from the job.
The key is sent only in request headers and is never logged or shown in errors.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

from ..registry import register
from .base import ORDER, StoreError, check_name

Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, bytes]]


def urllib_transport(method, url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https from worker.env)
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise StoreError(f"database unreachable: {type(exc).__name__}", retryable=True) from None


def _value(v) -> str:
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v)


@register("store", "supabase_rest")
class SupabaseRestStore:
    SECRET_NAMES = ("SNAFI_SUPABASE_URL", "SNAFI_SUPABASE_SECRET_KEY")

    def __init__(self, options: dict, secrets, transport: Optional[Transport] = None):
        url = secrets.get("SNAFI_SUPABASE_URL").rstrip("/")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise StoreError("SNAFI_SUPABASE_URL must be an https URL")
        self._base = f"{parsed.scheme}://{parsed.netloc}/rest/v1"
        key = secrets.get("SNAFI_SUPABASE_SECRET_KEY")
        if key.startswith("sb_publishable_"):
            raise StoreError("the worker needs the secret key, not the publishable key")
        self._headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
        if key.count(".") == 2:  # legacy JWT-style service_role key
            self._headers["Authorization"] = f"Bearer {key}"
        self._timeout = float(options.get("timeout_seconds", 20))
        self._transport = transport or urllib_transport

    def __repr__(self) -> str:
        return "SupabaseRestStore(key=hidden)"

    def _call(self, method: str, path: str, params: Optional[Dict] = None, body=None, prefer: str = "") -> List[Dict]:
        url = f"{self._base}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, safe=",.()*")
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8") if body is not None else None
        status, raw = self._transport(method, url, headers, data, self._timeout)
        if status >= 500 or status == 429:
            raise StoreError(f"database busy (HTTP {status})", retryable=True)
        if status >= 400:
            try:
                detail = json.loads(raw).get("message", "")[:200]
            except (ValueError, AttributeError):
                detail = ""
            raise StoreError(f"database refused {method} {path.split('?')[0]} (HTTP {status}) {detail}".strip())
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else [data]

    def insert(self, table, row):
        rows = self._call("POST", check_name(table), body=row, prefer="return=representation")
        return rows[0]

    def select(self, table, where=None, order="created_at", descending=False, limit=100, null=()):
        params = {"select": "*", "order": f"{check_name(order)}.{'desc' if descending else 'asc'}", "limit": int(limit)}
        for column, value in (where or {}).items():
            params[check_name(column)] = f"eq.{_value(value)}"
        for column in null:
            params[check_name(column)] = "is.null"
        return self._call("GET", check_name(table), params)

    def update(self, table, row_id, changes):
        rows = self._call("PATCH", check_name(table), {"id": f"eq.{row_id}"}, changes, "return=representation")
        if not rows:
            raise StoreError(f"{table} row not found")
        return rows[0]

    def update_if(self, table, row_id, expect, changes):
        params = {"id": f"eq.{row_id}"}
        for column, value in expect.items():
            params[check_name(column)] = f"eq.{_value(value)}"
        rows = self._call("PATCH", check_name(table), params, changes, "return=representation")
        return rows[0] if rows else None

    def upsert(self, table, row, key):
        rows = self._call("POST", check_name(table), {"on_conflict": check_name(key)}, row,
                          "resolution=merge-duplicates,return=representation")
        return rows[0]

    def claim_job(self, lane, worker_id):
        rows = self._call("POST", "rpc/claim_job", body={"p_lane": lane, "p_worker": worker_id})
        return rows[0] if rows else None

    def page(self, table, offset, limit):
        order = ORDER.get(table, "created_at")
        params = {"select": "*", "order": f"{order}.asc,{'user_id' if order == 'user_id' else 'id'}.asc",
                  "offset": int(offset), "limit": int(limit)}
        return self._call("GET", check_name(table), params)

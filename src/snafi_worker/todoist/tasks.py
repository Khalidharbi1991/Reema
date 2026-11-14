"""Todoist adapter (provider "todoist"): the Todoist API v1, raw HTTPS with the standard library.

Only api.todoist.com is ever called (HOST), redirects are refused, and the API token
(TODOIST_API_TOKEN, stored only in Khalid's Credential Manager) goes only in the Authorization
header: never in a URL, a log line, repr or an error. The token can change all of Khalid's
Todoist, so the levels are kept in personal_tools.py, in code:
  read = Level 1; add, complete, reschedule = Level 2 with Undo; delete = Level 3.

Due dates: a plain date ("2026-11-20") is sent as due_date, a date and time with its offset as
due_datetime (UTC). A repeating task keeps its repeat: its date is changed through the sync
endpoint (item_update) with the repeat wording kept, which is also how Undo puts it back.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from ..personal.base import AuthRefused, ServiceError, TaskItem
from ..personal.credentials import usable
from ..registry import register

HOST = "api.todoist.com"
BASE = f"https://{HOST}/api/v1"
SECRET_NAMES = ("TODOIST_API_TOKEN",)
ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_RESPONSE = 5_000_000
FILTER_CHARS = re.compile(r"[&|!(),\\:#@*]")

Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, bytes]]


class TodoistError(ServiceError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def check_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.username or parsed.port:
        raise TodoistError("internal error: not the Todoist API address")
    return url


def urllib_transport(method, url, headers, body, timeout):
    request = urllib.request.Request(check_url(url), data=body, headers=headers, method=method)
    try:
        with _OPENER.open(request, timeout=timeout) as response:  # noqa: S310 (Todoist only)
            return response.status, response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read(MAX_RESPONSE + 1) if exc.fp else b"")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TodoistError("Todoist unreachable", retryable=True) from None
    except ValueError:  # an invalid header value: never shown, it could hold the token
        raise TodoistError("the Todoist request could not be sent (invalid setting)") from None


def _id(value: str) -> str:
    if not isinstance(value, str) or not ID.match(value):
        raise TodoistError("that is not a Todoist task id")
    return urllib.parse.quote(value, safe="")


def _json(raw: bytes):
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        return {}


def _item(data: Dict) -> Optional[TaskItem]:
    if not isinstance(data, dict) or not isinstance(data.get("id"), (str, int)):
        return None
    due = data.get("due") if isinstance(data.get("due"), dict) else {}
    when = due.get("datetime") or due.get("date") or ""
    try:
        api_priority = int(data.get("priority") or 1)
    except (TypeError, ValueError):
        api_priority = 1
    return TaskItem(str(data["id"]), str(data.get("content") or "")[:1000], str(data.get("description") or "")[:2000],
                    str(when)[:40], str(due.get("string") or "")[:200], bool(due.get("is_recurring")),
                    min(4, max(1, 5 - api_priority)), bool(data.get("checked") or data.get("is_completed")))


def due_fields(due: str) -> Dict[str, str]:
    """A due date for the REST endpoints: due_date for a day, due_datetime (UTC) for a time, or none."""
    if not due:
        return {"due_string": "no date"}
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        return {"due_date": due}
    parsed = datetime.fromisoformat(due.replace("Z", "+00:00"))
    if parsed.tzinfo is None:  # a floating time from Todoist itself (Undo puts it back as it was)
        return {"due_datetime": parsed.strftime("%Y-%m-%dT%H:%M:%S")}
    return {"due_datetime": parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


@register("tasks", "todoist")
class TodoistTasks:
    def __init__(self, options: dict, login, transport: Optional[Transport] = None):
        self.login = login
        self.timeout = float((options or {}).get("timeout_seconds", 20))
        self._transport = transport or urllib_transport

    def __repr__(self) -> str:
        return "TodoistTasks(token=hidden)"

    def _call(self, method: str, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
              form: Optional[Dict] = None):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        token = usable(self.login.values()[0].strip(), "Todoist API token")
        for attempt in (1, 2):
            headers = {"authorization": "Bearer " + token, "accept": "application/json"}
            payload = None
            if body is not None:
                payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
                headers["content-type"] = "application/json; charset=utf-8"
            elif form is not None:
                payload = urllib.parse.urlencode(form).encode("utf-8")
                headers["content-type"] = "application/x-www-form-urlencoded"
            status, raw = self._transport(method, url, headers, payload, self.timeout)
            if status in (401, 403) and attempt == 1 and self.login.refused():
                token = usable(self.login.values()[0].strip(), "Todoist API token")  # a new token was stored
                continue
            break
        if len(raw) > MAX_RESPONSE:
            raise TodoistError("Todoist's answer was too large")
        if status in (200, 204):
            return _json(raw) if raw else {}
        if status in (401, 403):
            raise AuthRefused("Todoist refused the API token; copy it again from Todoist and store it with "
                              "snafi.cmd set-secrets")
        if status == 404:
            raise TodoistError("not found in your Todoist")
        if status == 429 or status >= 500:
            raise TodoistError(f"Todoist busy (HTTP {status})", retryable=True)
        raise TodoistError(f"Todoist refused the request (HTTP {status})")

    def _list(self, query: str, limit: int) -> List[TaskItem]:
        data = self._call("GET", "/tasks/filter", {"query": query, "limit": max(1, min(int(limit), 50))})
        rows = data.get("results") if isinstance(data, dict) else data
        items = [_item(row) for row in (rows or []) if isinstance(row, dict)]
        return [i for i in items if i is not None and not i.done][: max(1, int(limit))]

    def today(self, limit):
        return self._list("today | overdue", limit)

    def search(self, query, limit):
        words = " ".join(FILTER_CHARS.sub(" ", query or "").split())[:200]
        return self._list(f"search: {words}" if words else "today | overdue", limit)

    def get(self, task_id):
        item = _item(self._call("GET", f"/tasks/{_id(task_id)}"))
        if item is None:
            raise TodoistError("Todoist did not return the task")
        return item

    def add(self, content, description="", due="", priority=4):
        body = {"content": content, "priority": 5 - int(priority)}
        if description:
            body["description"] = description
        if due:
            body.update(due_fields(due))
        item = _item(self._call("POST", "/tasks", body=body))
        if item is None:
            raise TodoistError("Todoist did not return the new task")
        return item

    def complete(self, task_id):
        self._call("POST", f"/tasks/{_id(task_id)}/close")

    def reopen(self, task_id):
        self._call("POST", f"/tasks/{_id(task_id)}/reopen")

    def set_due(self, task_id, due, due_string="", recurring=False):
        if not recurring:
            self._call("POST", f"/tasks/{_id(task_id)}", body=due_fields(due))
            return
        # A repeating task: keep its repeat wording; only the next date changes.
        when = due
        if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            parsed = datetime.fromisoformat(due.replace("Z", "+00:00"))
            when = (parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if parsed.tzinfo
                    else parsed.strftime("%Y-%m-%dT%H:%M:%S"))
        command = str(uuid.uuid4())
        commands = [{"type": "item_update", "uuid": command,
                     "args": {"id": task_id, "due": {"date": when, "string": due_string, "is_recurring": True}}}]
        _id(task_id)
        data = self._call("POST", "/sync", form={"commands": json.dumps(commands)})
        status = (data.get("sync_status") or {}).get(command) if isinstance(data, dict) else None
        if status != "ok":
            raise TodoistError("Todoist did not accept the new date")

    def delete(self, task_id):
        self._call("DELETE", f"/tasks/{_id(task_id)}")

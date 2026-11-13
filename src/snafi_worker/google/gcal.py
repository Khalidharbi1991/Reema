"""Google Calendar adapter (provider "google_calendar"), main calendar only. Scope:
calendar.events (read and create events). Events Snafi creates carry a private "snafi"
property, so Undo can delete only those.
"""

import re
import urllib.parse
from typing import Dict, List, Optional

from ..personal.base import MAX_BODY, SNAFI_TAG, Event, ServiceError
from ..registry import register
from .http import GoogleApi

BASE = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


def _id(value: str) -> str:
    if not isinstance(value, str) or not ID.match(value):
        raise ServiceError("that is not a calendar event id")
    return urllib.parse.quote(value, safe="")


def _when(part) -> (str, bool):
    part = part if isinstance(part, dict) else {}
    if isinstance(part.get("dateTime"), str):
        return part["dateTime"], False
    return str(part.get("date") or ""), True


def to_event(data: Dict) -> Event:
    start, all_day = _when(data.get("start"))
    end, _ = _when(data.get("end"))
    private = ((data.get("extendedProperties") or {}).get("private") or {})
    attendees = [str(a.get("email")) for a in data.get("attendees") or []
                 if isinstance(a, dict) and isinstance(a.get("email"), str) and not a.get("self")]
    return Event(str(data.get("id") or ""), str(data.get("summary") or "")[:300], start, end,
                 str(data.get("location") or "")[:300], str(data.get("description") or "")[:MAX_BODY],
                 attendees[:50], all_day, private.get(SNAFI_TAG) == "1")


@register("calendar", "google_calendar")
class GoogleCalendar:
    def __init__(self, options: dict, auth):
        self.api = GoogleApi(auth)

    def __repr__(self) -> str:
        return "GoogleCalendar(tokens=hidden)"

    def list_events(self, start, end, limit):
        data = self.api.call("GET", BASE, {"timeMin": start, "timeMax": end, "singleEvents": "true",
                                           "orderBy": "startTime", "maxResults": max(1, min(limit, 50))})
        return [to_event(e) for e in data.get("items") or []
                if isinstance(e, dict) and e.get("status") != "cancelled"]

    def get_event(self, event_id):
        return to_event(self.api.call("GET", f"{BASE}/{_id(event_id)}"))

    def create_event(self, title, start, end, location="", description="", attendees: Optional[List[str]] = None):
        body = {"summary": title, "start": {"dateTime": start}, "end": {"dateTime": end},
                "extendedProperties": {"private": {SNAFI_TAG: "1"}}}
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        # Invitations go out only for an approved invite (attendees); an event with only Khalid sends nothing.
        data = self.api.call("POST", BASE, {"sendUpdates": "all" if attendees else "none"}, body)
        event = to_event(data)
        if not event.id:
            raise ServiceError("Google Calendar did not return the event")
        return event

    def delete_event(self, event_id):
        # Guests are not notified (no message leaves on Khalid's behalf); the approval card says so.
        self.api.call("DELETE", f"{BASE}/{_id(event_id)}", {"sendUpdates": "none"})

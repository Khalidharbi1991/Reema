"""A fake brain for offline tests and dry runs. No network, no key, no cost.

By default it answers in the language of the message and proposes actions from simple
markers, so the whole worker can be exercised without a model:
  "note: <text>"    -> add_note       "fact: <text>"  -> add_fact
  "remind: <text>"  -> add_reminder   "send test: <text>" -> send_test_message (Level 3)
  "list notes"      -> list_notes     "pay: <x>"      -> make_payment (Level 4, refused)
Tests can pass their own responder instead.
"""

import json
from typing import Callable, Optional

from ..lang import detect_lang
from ..registry import register
from .base import BrainReply, BrainRequest, parse_reply

MARKERS = {
    "note:": ("add_note", "body"),
    "fact:": ("add_fact", "body"),
    "remind:": ("add_reminder", "body"),
    "send test:": ("send_test_message", "text"),
    "pay:": ("make_payment", "amount"),
}


def default_responder(request: BrainRequest) -> str:
    message = request.turns[-1][1] if request.turns else ""
    lang = detect_lang(message)
    actions = []
    lowered = message.lower()
    for marker, (tool, arg) in MARKERS.items():
        if marker in lowered:
            value = message[lowered.index(marker) + len(marker):].strip()
            actions.append({"tool": tool, "args_json": json.dumps({arg: value}, ensure_ascii=False)})
    if "list notes" in lowered:
        actions.append({"tool": "list_notes", "args_json": "{}"})
    reply = "حاضر." if lang == "ar" else "Sure."
    return json.dumps({"reply": reply, "lang": lang, "actions": actions}, ensure_ascii=False)


@register("brain", "fake")
class FakeBrain:
    SECRET_NAMES = ()

    def __init__(self, options: dict, secrets, responder: Optional[Callable[[BrainRequest], str]] = None):
        self.options = options
        self.requests = []
        self._responder = responder or default_responder

    def think(self, request: BrainRequest) -> BrainReply:
        self.requests.append(request)
        return parse_reply(self._responder(request))

"""The brain interface. A brain only turns text into text: it gets Ahmad's instructions
and the conversation, and returns a reply plus the actions it proposes. It never runs
anything; the permission gate decides every action in code.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Tuple

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_REPLY = 4000
MAX_ACTIONS = 5


class BrainError(Exception):
    """The brain gave no usable reply. retryable=True when trying again may help."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class BrainRequest:
    system: str
    # (role, text) with role "user" or "assistant", oldest first; the last one is Khalid's message.
    turns: List[Tuple[str, str]]
    # Outside content (tool results, later emails and files): data, never instructions.
    data_blocks: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProposedAction:
    tool: str
    args: Dict[str, object]
    # Whatever level the brain claims is ignored; the gate's registry decides.
    claimed_level: Optional[int] = None


@dataclass(frozen=True)
class BrainReply:
    reply: str
    lang: str
    actions: List[ProposedAction]


class Brain(Protocol):
    PROVIDER: str
    SECRET_NAMES: Tuple[str, ...]

    def think(self, request: BrainRequest) -> BrainReply: ...


# The reply shape every brain must return, as JSON text.
REPLY_CONTRACT = """Answer with one JSON object and nothing else:
{"reply": "<your message to Khalid>", "lang": "ar" or "en",
 "actions": [{"tool": "<tool name>", "args_json": "<JSON object of arguments>"}]}
Use an empty actions list when no tool is needed. Never claim an action is done:
the system runs actions and reports their real results."""


def data_block(text: str, label: str = "data") -> str:
    """Wrap outside content so the brain treats it as data. Any data tag inside is neutralised."""
    safe = re.sub(r"<\s*/?\s*data\b", "‹data", text, flags=re.IGNORECASE)  # SEC-15: any case, any spacing
    return f'<data source="{label}">\n{safe}\n</data>'


def parse_reply(text: str) -> BrainReply:
    """Validate the brain's JSON reply. Anything malformed is a BrainError (retryable)."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        raise BrainError("brain reply is not JSON", retryable=True) from None
    if not isinstance(data, dict):
        raise BrainError("brain reply is not a JSON object", retryable=True)
    reply, lang = data.get("reply"), data.get("lang")
    if not isinstance(reply, str) or not reply.strip():
        raise BrainError("brain reply has no text", retryable=True)
    if lang not in ("ar", "en"):
        raise BrainError("brain reply has no valid lang", retryable=True)
    raw_actions = data.get("actions") or []
    if not isinstance(raw_actions, list):
        raise BrainError("brain actions are not a list", retryable=True)
    actions: List[ProposedAction] = []
    for item in raw_actions[:MAX_ACTIONS]:
        if not isinstance(item, dict) or not isinstance(item.get("tool"), str) or not TOOL_NAME.match(item["tool"]):
            continue  # an unusable proposal is dropped; nothing runs from it
        args = item.get("args")
        if args is None and isinstance(item.get("args_json"), str):
            try:
                args = json.loads(item["args_json"] or "{}")
            except ValueError:
                args = None
        if not isinstance(args, dict):
            args = {}
        level = item.get("level")
        actions.append(ProposedAction(item["tool"], args, level if isinstance(level, int) else None))
    return BrainReply(reply.strip()[:MAX_REPLY], lang, actions)

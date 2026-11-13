"""The shapes every tool shares: arguments, results, the Tool record and its argument checks.

Kept apart from tools.py so the step 3 tools (personal_tools.py) and the step 2 tools can both
build on it without importing each other.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

# name -> (type, max length (str) / highest value (int) / most items (list of text), required)
ArgSpec = Dict[str, Tuple[type, int, bool]]
LIST_ITEM_MAX = 254


@dataclass
class ToolResult:
    ok: bool
    summary: Dict[str, str]          # {"en": ..., "ar": ...}: what really happened, written by code
    data: Dict = field(default_factory=dict)   # kept in the action log: ids and counts, never text read from mail or files
    undo: Optional[Dict] = None      # how to undo, for Level 2
    untrusted: str = ""              # outside content (mail, events, files) for the brain only, as marked data


@dataclass(frozen=True)
class Tool:
    name: str
    level: int
    args: ArgSpec
    run: Callable
    undo: Optional[Callable] = None
    describe: Callable = lambda args: {"en": "", "ar": ""}
    validate: Optional[Callable] = None   # extra checks, run by the gate before anything runs
    prepare: Optional[Callable] = None    # Level 3: adds what the card must show (read-only), before the card
    reads_outside: bool = False           # its result is outside content: given to the brain as untrusted data
    sends: bool = False                   # it sends a message or an invitation (for the honesty check)


class ToolArgError(ValueError):
    pass


class NeverError(ToolArgError):
    """The arguments make it a Level 4 action (for example a mass message): refused whatever is asked."""


def _text_list(name: str, value, limit: int):
    if isinstance(value, str):
        value = [part for part in re.split(r"[,;]", value)]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ToolArgError(f"{name} must be a list of text")
    items = [v.strip() for v in value if v.strip()]
    if len(items) > limit:
        raise NeverError(f"{name} has more than {limit} entries")
    if any(len(v) > LIST_ITEM_MAX for v in items):
        raise ToolArgError(f"{name} has an entry that is too long")
    return items


def clean_args(tool: Tool, args: Dict) -> Dict:
    clean = {}
    for name, (kind, limit, required) in tool.args.items():
        value = args.get(name)
        if value is None or (isinstance(value, (str, list)) and not (value.strip() if isinstance(value, str) else value)):
            if required:
                raise ToolArgError(f"{name} is required")
            continue
        if kind is list:
            value = _text_list(name, value, limit)
            if not value:
                if required:
                    raise ToolArgError(f"{name} is required")
                continue
        elif kind is str:
            if not isinstance(value, str):
                raise ToolArgError(f"{name} must be text")
            value = value.strip()
            if len(value) > limit:
                raise ToolArgError(f"{name} is too long")
        elif kind is int:
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= limit:
                raise ToolArgError(f"{name} must be a number from 1 to {limit}")
        clean[name] = value
    return tool.validate(clean) if tool.validate else clean


def args_hash(tool: str, args: Dict) -> str:
    """SHA-256 of exactly what an approval card shows and what will run (SEC-13)."""
    text = json.dumps({"tool": tool, "args": args}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

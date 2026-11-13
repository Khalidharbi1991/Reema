"""Claude API brain (Anthropic Messages API): text in, JSON text out. No tools are sent and none are accepted.

The only exception to REEMA's no-Anthropic rule, which Khalid asked for (Nov 13, 2026): this file is
the one place in REEMA that calls Anthropic, and only when worker.yaml chooses brain.provider
claude_api. tests/test_no_api_guard.py allows it here and nowhere else.

The request carries only model, max_tokens, system, messages, thinking and output_config. It never
includes tools, tool_choice, MCP servers, a container or any server tool. A response with any block
other than text (tool use, server tool use, tool results, anything new) or a stop for tool use is
rejected, so the model can only propose actions as data for the permission gate.

Raw HTTP with the standard library, like the Gemini brain: the worker's private Python holds only
hash-pinned pyyaml and tzdata, so the Anthropic SDK and its dependencies are not installed.
The key goes in the x-api-key header (never in the URL), is never logged, and is never sent on a
redirect: redirects are refused (SEC-16).
"""

import json
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional, Tuple

from ..registry import register
from .base import REPLY_CONTRACT, BrainError, BrainReply, BrainRequest, parse_reply

ENDPOINT = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
DEFAULT_MODEL = "claude-haiku-5-5"  # the cheapest current Haiku (Anthropic's model list, Nov 2026)
# The only top-level keys this brain ever sends.
REQUEST_KEYS = frozenset({"model", "max_tokens", "system", "messages", "thinking", "output_config"})
# Content blocks a reply may hold. Thinking blocks are ignored; anything else means a tool or worse.
TEXT_BLOCKS = frozenset({"text"})
IGNORED_BLOCKS = frozenset({"thinking", "redacted_thinking"})

REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "lang": {"type": "string", "enum": ["ar", "en"]},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"tool": {"type": "string"}, "args_json": {"type": "string"}},
                "required": ["tool", "args_json"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reply", "lang", "actions"],
    "additionalProperties": False,
}

Transport = Callable[[str, Dict[str, str], bytes, float], Tuple[int, bytes]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # never resend the key to another address (SEC-16)
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_transport(url: str, headers: Dict[str, str], body: bytes, timeout: float) -> Tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _OPENER.open(request, timeout=timeout) as response:  # noqa: S310 (fixed https URL)
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BrainError(f"brain unreachable: {type(exc).__name__}", retryable=True) from None
    except ValueError:  # e.g. an invalid header value: never show it, it could hold the key (SEC-59)
        raise BrainError("brain request could not be sent (invalid setting)", retryable=False) from None


def _usable_key(key: str) -> str:
    if not key or any(ord(c) <= 32 or ord(c) >= 127 for c in key):
        raise BrainError("ANTHROPIC_API_KEY is not a usable key; store it again with set-secrets", retryable=False)
    return key


@register("brain", "claude_api")
class ClaudeApiBrain:
    SECRET_NAMES = ("ANTHROPIC_API_KEY",)

    def __init__(self, options: dict, secrets, transport: Optional[Transport] = None):
        self.model = str(options.get("model") or DEFAULT_MODEL)
        self.timeout = float(options.get("timeout_seconds", 60))
        self.max_output_tokens = int(options.get("max_output_tokens", 1024))
        self.effort = str(options.get("effort") or "low")
        self._key = _usable_key(secrets.get("ANTHROPIC_API_KEY"))
        self._transport = transport or urllib_transport

    def __repr__(self) -> str:
        return f"ClaudeApiBrain(model={self.model!r}, key=hidden)"

    def build_request(self, request: BrainRequest) -> Tuple[str, Dict[str, str], dict]:
        messages = []
        turns = list(request.turns)
        while turns and turns[0][0] != "user":  # the Messages API starts with the user
            turns.pop(0)
        for i, (role, text) in enumerate(turns):
            if i == len(turns) - 1 and request.data_blocks:
                text = text + "\n\n" + "\n\n".join(request.data_blocks)
            messages.append({"role": "assistant" if role == "assistant" else "user", "content": text})
        if not messages:
            raise BrainError("nothing to answer", retryable=False)
        body = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": request.system + "\n\n" + REPLY_CONTRACT,
            "messages": messages,
            "thinking": {"type": "disabled"},  # a short chat reply; allowed at effort high or below
            "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": REPLY_SCHEMA}},
        }
        if set(body) != REQUEST_KEYS:  # text only: no tools, ever
            raise BrainError("internal error: brain request has unexpected fields")
        headers = {"content-type": "application/json", "x-api-key": self._key, "anthropic-version": API_VERSION}
        return ENDPOINT, headers, body

    def think(self, request: BrainRequest) -> BrainReply:
        url, headers, body = self.build_request(request)
        status, raw = self._transport(url, headers, json.dumps(body, ensure_ascii=False).encode("utf-8"), self.timeout)
        if status in (408, 409, 429, 529) or status >= 500:
            raise BrainError(f"brain busy or unavailable (HTTP {status})", retryable=True)
        if status in (401, 403):
            raise BrainError(f"brain refused the key (HTTP {status}); check ANTHROPIC_API_KEY and credits", retryable=False)
        if status != 200:
            raise BrainError(f"brain refused the request (HTTP {status})", retryable=False)
        return parse_reply(self.extract_text(raw))

    @staticmethod
    def extract_text(raw: bytes) -> str:
        try:
            data = json.loads(raw)
        except ValueError:
            raise BrainError("brain response is not JSON", retryable=True) from None
        if not isinstance(data, dict):
            raise BrainError("brain response is not a JSON object", retryable=True)
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise BrainError("brain returned no answer", retryable=True)
        for block in blocks:
            kind = block.get("type") if isinstance(block, dict) else None
            if kind not in TEXT_BLOCKS and kind not in IGNORED_BLOCKS:
                raise BrainError("brain tried to use a tool; reply rejected", retryable=False)
        stop = data.get("stop_reason")
        if stop == "refusal":
            raise BrainError("brain declined this request", retryable=False)
        if stop == "max_tokens":
            raise BrainError("brain reply was too long and was cut off", retryable=False)
        if stop not in ("end_turn", "stop_sequence"):  # tool_use, pause_turn or anything new
            raise BrainError(f"brain stopped: {stop}", retryable=False)
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if not text.strip():
            raise BrainError("brain returned empty text", retryable=True)
        return text

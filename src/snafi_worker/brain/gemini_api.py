"""Gemini API brain: text in, JSON text out. No tools are sent and none are accepted.

The request carries only systemInstruction, contents (text parts) and generationConfig.
It never includes tools, toolConfig, functionDeclarations, code execution or grounding.
A response that contains a function call, executable code or anything but text is
rejected, so the model can only propose actions as data for the permission gate.
The API key goes in the x-goog-api-key header (never in the URL) and is never logged.
"""

import json
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional, Tuple

from ..registry import register
from .base import REPLY_CONTRACT, BrainError, BrainReply, BrainRequest, parse_reply

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# The only top-level keys this brain ever sends.
REQUEST_KEYS = frozenset({"systemInstruction", "contents", "generationConfig"})
# Anything in a response part other than "text" (and the thought marker) means tool use.
TEXT_PART_KEYS = frozenset({"text", "thought", "thoughtSignature"})

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reply": {"type": "STRING"},
        "lang": {"type": "STRING", "enum": ["ar", "en"]},
        "actions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"tool": {"type": "STRING"}, "args_json": {"type": "STRING"}},
                "required": ["tool", "args_json"],
            },
        },
    },
    "required": ["reply", "lang", "actions"],
}

Transport = Callable[[str, Dict[str, str], bytes, float], Tuple[int, bytes]]


def urllib_transport(url: str, headers: Dict[str, str], body: bytes, timeout: float) -> Tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed https URL)
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BrainError(f"brain unreachable: {type(exc).__name__}", retryable=True) from None


@register("brain", "gemini_api")
class GeminiApiBrain:
    SECRET_NAMES = ("GEMINI_API_KEY",)

    def __init__(self, options: dict, secrets, transport: Optional[Transport] = None):
        self.model = str(options.get("model") or "gemini-3.5-flash-lite")
        self.timeout = float(options.get("timeout_seconds", 60))
        self.max_output_tokens = int(options.get("max_output_tokens", 1024))
        self._key = secrets.get("GEMINI_API_KEY")
        self._transport = transport or urllib_transport

    def __repr__(self) -> str:
        return f"GeminiApiBrain(model={self.model!r}, key=hidden)"

    def build_request(self, request: BrainRequest) -> Tuple[str, Dict[str, str], dict]:
        contents = []
        for i, (role, text) in enumerate(request.turns):
            if i == len(request.turns) - 1 and request.data_blocks:
                text = text + "\n\n" + "\n\n".join(request.data_blocks)
            contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": text}]})
        body = {
            "systemInstruction": {"parts": [{"text": request.system + "\n\n" + REPLY_CONTRACT}]},
            "contents": contents,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
                "maxOutputTokens": self.max_output_tokens,
                "temperature": 0.4,
            },
        }
        if set(body) != REQUEST_KEYS:  # text only: no tools, ever
            raise BrainError("internal error: brain request has unexpected fields")
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._key}
        return ENDPOINT.format(model=self.model), headers, body

    def think(self, request: BrainRequest) -> BrainReply:
        url, headers, body = self.build_request(request)
        status, raw = self._transport(url, headers, json.dumps(body, ensure_ascii=False).encode("utf-8"), self.timeout)
        if status == 429 or status >= 500:
            raise BrainError(f"brain busy or unavailable (HTTP {status})", retryable=True)
        if status != 200:
            raise BrainError(f"brain refused the request (HTTP {status})", retryable=False)
        return parse_reply(self.extract_text(raw))

    @staticmethod
    def extract_text(raw: bytes) -> str:
        try:
            data = json.loads(raw)
        except ValueError:
            raise BrainError("brain response is not JSON", retryable=True) from None
        candidates = data.get("candidates") or []
        if not candidates:
            raise BrainError("brain returned no answer", retryable=True)
        candidate = candidates[0]
        if candidate.get("finishReason") not in (None, "STOP", "MAX_TOKENS"):
            raise BrainError(f"brain stopped: {candidate.get('finishReason')}", retryable=False)
        parts = (candidate.get("content") or {}).get("parts") or []
        for part in parts:
            if set(part) - TEXT_PART_KEYS:
                raise BrainError("brain tried to use a tool; reply rejected", retryable=False)
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            raise BrainError("brain returned empty text", retryable=True)
        return text

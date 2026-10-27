"""Async provider boundary and per-run limits; never persist prompts or secrets."""

import asyncio
import hashlib
import json
import random
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from anthropic import APIConnectionError, APIStatusError


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = "end_turn"
    request_id: str = ""


class LLMProvider(Protocol):
    async def complete(self, **request) -> Completion: ...


class AnthropicProvider:
    """Adapter accepts an AsyncAnthropic client (or a deterministic test double)."""

    def __init__(self, client):
        self.client = client

    async def complete(self, **request):
        response = await self.client.messages.create(**request)
        text = "\n".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        # Caching is not enabled by this adapter. Count cache tokens if returned.
        inputs = usage.input_tokens + (getattr(usage, "cache_read_input_tokens", 0) or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        return Completion(text, inputs, usage.output_tokens, response.stop_reason,
                          getattr(response, "_request_id", "") or "")


current_runtime = ContextVar("reema_runtime", default=None)


class RunRuntime:
    def __init__(self, settings):
        self.settings = settings
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_agents)
        self.events = []
        self.tokens = 0
        self.reserved = 0
        self.sources = {}
        self.on_event = None
        self.inherited_tokens = 0
        self.lineage = []
        self.in_flight = {}
        self.execution_journal = None

    @staticmethod
    def retryable(error):
        return isinstance(error, (APIConnectionError, asyncio.TimeoutError)) or (
            isinstance(error, APIStatusError) and (error.status_code in (408, 409, 429) or error.status_code >= 500)
        )

    async def call(self, provider, *, agent, **request):
        if not self.settings.allow_external_ai:
            raise PermissionError("External AI has not been authorized")
        serialized = json.dumps(request, ensure_ascii=False)
        if len(serialized) > self.settings.max_prompt_chars:
            raise ValueError("Prompt exceeds MAX_PROMPT_CHARS; reduce source context or chunk the document")
        # Conservative reservation, not a provider token count. Unknown usage on
        # failed requests remains charged at this estimate to avoid free retries.
        estimate = len(serialized.encode("utf-8")) + request["max_tokens"] + 1024
        for attempt in range(self.settings.api_max_retries + 1):
            async with self.semaphore:
                if self.tokens + self.reserved + estimate > self.settings.max_run_tokens:
                    raise ValueError("Run token budget exhausted; no further model request was sent")
                self.reserved += estimate
                start = time.monotonic()
                event = {"agent": agent, "model": request["model"], "attempt": attempt + 1,
                         "prompt_sha256": hashlib.sha256(serialized.encode()).hexdigest()}
                reservation_id = uuid4().hex
                try:
                    self.in_flight[reservation_id] = {**event, "reserved_tokens": estimate, "status": "transmission_uncertain_if_interrupted"}
                    if self.on_event:
                        self.on_event(self.summary())  # Durable before the provider can receive this request.
                    result = await asyncio.wait_for(provider.complete(**request), self.settings.api_timeout_seconds)
                    used = result.input_tokens + result.output_tokens
                    self.tokens += used
                    event.update(input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                                 stop_reason=result.stop_reason, request_id=result.request_id)
                    rates = self.settings.model_prices.get(request["model"])
                    event["estimated_cost_usd"] = (
                        (result.input_tokens * rates[0] + result.output_tokens * rates[1]) / 1_000_000
                        if rates is not None else None
                    )
                    if result.stop_reason != "end_turn" or not result.text.strip():
                        raise ValueError("Model response was empty, refused, or incomplete; delivery blocked")
                    event["status"] = "completed"
                    return result.text
                except BaseException as error:
                    if "input_tokens" not in event:
                        self.tokens += estimate
                        event["unknown_usage_reserved_tokens"] = estimate
                    event.update(status="failed", error_type=type(error).__name__)
                    if not self.retryable(error) or attempt == self.settings.api_max_retries:
                        # Do not expose provider exception bodies (may contain prompt material).
                        if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                            raise
                        raise RuntimeError(f"Model call failed ({type(error).__name__}); see run usage metadata") from None
                finally:
                    self.reserved -= estimate
                    self.in_flight.pop(reservation_id, None)
                    event["duration_seconds"] = round(time.monotonic() - start, 3)
                    self.events.append(event)
                    if self.on_event:
                        self.on_event(self.summary())
            await asyncio.sleep(min(30, self.settings.retry_backoff_seconds * 2 ** attempt) + random.uniform(0, 0.1))

    def summary(self):
        known_costs = [e.get("estimated_cost_usd") for e in self.events]
        return {"accounted_tokens": self.tokens + self.reserved, "calls": self.events,
                "in_flight": list(self.in_flight.values()),
                "inherited_accounted_tokens": self.inherited_tokens,
                "new_accounted_tokens": self.tokens + self.reserved - self.inherited_tokens,
                "lineage": self.lineage,
                "estimated_cost_scope": "current_run_requests_only",
                "estimated_cost_usd": sum(known_costs) if known_costs and all(v is not None for v in known_costs) else None,
                "cost_note": "Estimates use configured USD-per-million rates, not an invoice; null means unknown."}

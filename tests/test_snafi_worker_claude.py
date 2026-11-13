"""Snafi worker: the Claude API brain (text only, no tools), switching to it with one setting, its key in
set-secrets, and the daily brain call limit (SEC-47). Offline: a recorder stands in for the network;
no request ever leaves the PC."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.snafi_worker import registry, services
from src.snafi_worker.brain import BrainError, BrainRequest
from src.snafi_worker.brain.claude_api import (API_VERSION, ENDPOINT, REQUEST_KEYS, ClaudeApiBrain, _NoRedirect)
from src.snafi_worker.brain.fake import FakeBrain
from src.snafi_worker.brain.gemini_api import GeminiApiBrain
from src.snafi_worker.brain.limit import BrainLimitReached, DailyLimit, LimitedBrain
from src.snafi_worker.brain.pause import GuardedBrain
from src.snafi_worker.config import Secrets, Settings
from src.snafi_worker.engine import Engine
from src.snafi_worker.runner import run_job
from src.snafi_worker.set_secrets import check_anthropic, questions
from src.snafi_worker.store.memory import MemoryStore

KEY = "sk-ant-api03-" + "A1b2_C3d-" * 6
OWNER = "11111111-1111-4111-8111-111111111111"
CONV = "33333333-3333-4333-8333-333333333333"
REQUEST = BrainRequest("You are Ahmad.", [("user", "hello")])


def ok(reply="Hi", lang="en", actions=(), stop="end_turn", extra_blocks=()):
    text = json.dumps({"reply": reply, "lang": lang, "actions": list(actions)})
    return {"type": "message", "role": "assistant", "stop_reason": stop,
            "content": [*extra_blocks, {"type": "text", "text": text}]}


class Recorder:
    def __init__(self, status=200, body=None):
        self.status, self.body, self.calls = status, body if body is not None else ok(), []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": json.loads(body), "timeout": timeout})
        raw = self.body if isinstance(self.body, bytes) else json.dumps(self.body).encode()
        return self.status, raw


def claude(transport=None, **options):
    return ClaudeApiBrain({"model": "claude-haiku-5-5", **options}, Secrets({"ANTHROPIC_API_KEY": KEY}),
                          transport or Recorder())


# ---------- the request is text only ----------
def test_the_request_is_text_only_with_the_key_in_a_header():
    rec = Recorder()
    reply = claude(rec).think(BrainRequest("You are Ahmad.", [("assistant", "earlier"), ("user", "hi"),
                                                               ("assistant", "yes"), ("user", "now")],
                                           data_blocks=['<data source="x">\nfile\n</data>']))
    assert reply.reply == "Hi" and reply.lang == "en"
    call = rec.calls[0]
    assert call["url"] == ENDPOINT and KEY not in call["url"]
    assert call["headers"]["x-api-key"] == KEY and call["headers"]["anthropic-version"] == API_VERSION
    body = call["body"]
    assert set(body) == REQUEST_KEYS and KEY not in json.dumps(body)
    for forbidden in ("tools", "tool_choice", "mcp_servers", "container", "temperature", "top_p", "top_k"):
        assert forbidden not in body
    assert body["model"] == "claude-haiku-5-5" and body["thinking"] == {"type": "disabled"}
    assert body["output_config"]["effort"] == "low" and body["output_config"]["format"]["type"] == "json_schema"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]  # a leading assistant turn is dropped
    assert body["messages"][-1]["content"].endswith("</data>")  # outside content goes in as data, last
    assert "Answer with one JSON object" in body["system"]


def test_the_key_is_hidden_and_a_broken_key_is_refused():
    assert KEY not in repr(claude())
    with pytest.raises(BrainError, match="not a usable key"):
        ClaudeApiBrain({}, Secrets({"ANTHROPIC_API_KEY": "sk-ant-x\r\nX-Evil: 1"}), Recorder())


def test_redirects_are_refused_so_the_key_is_never_resent():
    assert _NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example") is None


# ---------- anything but text is rejected ----------
@pytest.mark.parametrize("block", [
    {"type": "tool_use", "id": "t1", "name": "run", "input": {}},
    {"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "x"}},
    {"type": "web_search_tool_result", "tool_use_id": "s1", "content": []},
    {"type": "something_new"},
])
def test_a_reply_that_tries_a_tool_is_rejected(block):
    with pytest.raises(BrainError, match="tried to use a tool") as err:
        claude(Recorder(body=ok(extra_blocks=[block]))).think(REQUEST)
    assert err.value.retryable is False


@pytest.mark.parametrize("stop,match", [("tool_use", "stopped"), ("pause_turn", "stopped"),
                                        ("refusal", "declined"), ("max_tokens", "too long")])
def test_a_reply_that_stops_for_a_tool_or_is_refused_is_rejected(stop, match):
    with pytest.raises(BrainError, match=match) as err:
        claude(Recorder(body=ok(stop=stop))).think(REQUEST)
    assert err.value.retryable is False


def test_thinking_blocks_are_ignored_and_actions_are_only_proposals():
    body = ok(actions=[{"tool": "note_add", "args_json": '{"text": "x"}'}],
              extra_blocks=[{"type": "thinking", "thinking": "", "signature": "s"}])
    reply = claude(Recorder(body=body)).think(REQUEST)
    assert [a.tool for a in reply.actions] == ["note_add"] and reply.actions[0].args == {"text": "x"}


@pytest.mark.parametrize("status,retryable", [(429, True), (529, True), (500, True), (408, True),
                                              (401, False), (403, False), (400, False), (404, False)])
def test_http_errors_are_classified(status, retryable):
    with pytest.raises(BrainError) as err:
        claude(Recorder(status=status, body={"type": "error"})).think(REQUEST)
    assert err.value.retryable is retryable and KEY not in str(err.value)


def test_a_response_that_is_not_json_is_retryable():
    with pytest.raises(BrainError) as err:
        claude(Recorder(body=b"<html>")).think(REQUEST)
    assert err.value.retryable


# ---------- switching is one setting ----------
def test_claude_is_the_configured_brain_and_switching_is_one_setting(tmp_path):
    settings = Settings.load()
    assert settings.brain_provider == "claude_api" and settings.brain_options["model"] == "claude-haiku-5-5"
    assert settings.brain_options["daily_call_limit"] == 300
    assert isinstance(services.build("brain", settings, Secrets({"ANTHROPIC_API_KEY": KEY})), ClaudeApiBrain)
    gemini = Settings.load(overrides={"brain.provider": "gemini_api", "brain.model": "gemini-3.5-flash-lite"})
    assert isinstance(services.build("brain", gemini, Secrets({"GEMINI_API_KEY": "k" * 30})), GeminiApiBrain)
    assert isinstance(services.build("brain", Settings.load(overrides={"brain.provider": "fake"}), Secrets({})),
                      FakeBrain)
    with pytest.raises(Exception, match="ANTHROPIC_API_KEY is not stored"):
        services.build("brain", settings, Secrets({}))
    guarded = services.guarded_brain(settings, Secrets({"ANTHROPIC_API_KEY": KEY}), pause_dir=tmp_path)
    assert isinstance(guarded, GuardedBrain) and isinstance(guarded.brain, LimitedBrain)
    assert isinstance(guarded.brain.brain, ClaudeApiBrain) and guarded.brain.limit.limit == 300
    assert "claude_api" in registry.providers("brain")


# ---------- the key in set-secrets ----------
def test_set_secrets_asks_only_for_the_chosen_brains_key():
    assert "ANTHROPIC_API_KEY" in [q[0] for q in questions("claude_api")]
    assert "GEMINI_API_KEY" not in [q[0] for q in questions("claude_api")]
    assert "ANTHROPIC_API_KEY" not in [q[0] for q in questions("gemini_api")]
    assert "ANTHROPIC_API_KEY" not in [q[0] for q in questions("agy")]


@pytest.mark.parametrize("bad,why", [("sk-ant-admin01-" + "x" * 40, "Admin"), ("AIza" + "y" * 35, "sk-ant-"),
                                     ("sb_secret_" + "y" * 30, "Supabase"), ("sk-ant-" + "y" * 20 + "\x16", "control"),
                                     ("sk-ant-api03 " + "y" * 30, "space")])
def test_the_claude_key_question_refuses_wrong_values_without_showing_them(bad, why):
    with pytest.raises(ValueError, match=why) as err:
        check_anthropic(bad)
    assert "yyyy" not in str(err.value) and "xxxx" not in str(err.value)


def test_the_claude_key_question_accepts_a_real_looking_key():
    assert check_anthropic("  " + KEY + "  ") == KEY


# ---------- the daily call limit (SEC-47) ----------
class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


def test_the_limit_counts_every_call_and_resets_the_next_day(tmp_path):
    clock = Clock()
    limit = DailyLimit(tmp_path / "calls.json", 3, "Asia/Riyadh", clock=clock)
    brain = LimitedBrain(FakeBrain({}, None), limit)
    for _ in range(3):
        brain.think(REQUEST)
    with pytest.raises(BrainLimitReached) as err:
        brain.think(REQUEST)
    assert err.value.retryable is False and err.value.limited
    clock.now += timedelta(days=1)
    brain.think(REQUEST)
    assert limit.used() == 1


def test_the_day_follows_jeddah_time(tmp_path):
    clock = Clock()
    clock.now = datetime(2026, 11, 13, 20, 59, tzinfo=timezone.utc)  # 23:59 in Jeddah
    limit = DailyLimit(tmp_path / "calls.json", 1, "Asia/Riyadh", clock=clock)
    limit.take()
    clock.now = datetime(2026, 11, 13, 21, 1, tzinfo=timezone.utc)  # 00:01 the next day in Jeddah
    limit.take()


def test_a_damaged_count_fails_closed_until_reset(tmp_path):
    path = tmp_path / "calls.json"
    path.write_text("{not json", encoding="utf-8")
    limit = DailyLimit(path, 300, "Asia/Riyadh")
    with pytest.raises(BrainLimitReached):
        limit.take()
    assert limit.clear_if_unreadable() and not path.exists()
    limit.take()
    assert limit.clear_if_unreadable() is False and limit.used() == 1  # a good count is kept


def test_the_brain_is_not_called_once_the_limit_is_reached(tmp_path):
    rec = Recorder()
    brain = LimitedBrain(claude(rec), DailyLimit(tmp_path / "calls.json", 1, "Asia/Riyadh"))
    brain.think(REQUEST)
    with pytest.raises(BrainLimitReached):
        brain.think(REQUEST)
    assert len(rec.calls) == 1


def test_at_the_limit_ahmad_says_so_and_does_nothing(tmp_path):
    limit = DailyLimit(tmp_path / "calls.json", 0, "Asia/Riyadh")
    store = MemoryStore()
    engine = Engine(store, LimitedBrain(FakeBrain({}, None), limit))
    msg = store.insert("messages", {"user_id": OWNER, "conversation_id": CONV, "role": "user", "body": "note: x"})
    store.insert("jobs", {"user_id": OWNER, "kind": "chat.reply", "conversation_id": CONV,
                          "payload": {"message_id": msg["id"]}})
    job = store.claim_job("chat", "pc")
    assert run_job(store, engine, job, 5, 0) == "done"
    last = store.tables["messages"][-1]
    assert last["meta"]["kind"] == "limited" and "limit" in last["body"]
    assert store.tables["notes"] == [] and store.tables["action_log"] == []

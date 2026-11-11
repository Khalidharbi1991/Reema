"""Snafi worker: the agy brain, its lockdown, the tripwire and pause, preflight, the proof
and switching brains. Offline: a fake agy replays recorded output; no real agy runs."""

import json
import re
from pathlib import Path

import pytest

from src.snafi_worker import services
from src.snafi_worker.brain import BrainRequest
from src.snafi_worker.brain.agy import (DENY_ALL, AgyBrain, BrainBreach, BrainNotReady, clean_env, fingerprint,
                                        list_is_empty)
from src.snafi_worker.brain.agy_proof import prove
from src.snafi_worker.brain.fake import FakeBrain
from src.snafi_worker.brain.gemini_api import GeminiApiBrain
from src.snafi_worker.brain.pause import BrainPaused, GuardedBrain, PauseFile
from src.snafi_worker.config import Secrets, Settings
from src.snafi_worker.engine import Engine
from src.snafi_worker.runner import run_job
from src.snafi_worker.store.memory import MemoryStore

WORKER = Path(__file__).resolve().parents[1] / "src" / "snafi_worker"
VERSION = "1.5.3"
OWNER = "11111111-1111-4111-8111-111111111111"
CONV = "33333333-3333-4333-8333-333333333333"
REQUEST = BrainRequest("You are Ahmad.", [("user", "hello")])
MCP_REAL = """NAME                 TYPE   STATUS   COMMAND/URL
example-server       stdio  enabled  python C:/example/server.py
files                stdio  enabled  npx -y example-filesystem-server C:\\example"""
PLUGINS_REAL = """Installed plugins:
- example-plugin (enabled, 1.0.0)
    Source:     example-source"""
INIT = {"event": "init", "permission_mode": "strict"}


def events(*items):
    return ("\n".join(json.dumps(i) for i in items) + "\n").encode()


def ok_result(reply="Hi", lang="en", actions=()):
    return {"event": "result", "status": "SUCCESS", "response": "",
            "structured_output": {"reply": reply, "lang": lang, "actions": list(actions)}}


class FakeAgy:
    """Replays what agy would print. `turn` decides each headless call's output."""

    def __init__(self, turn=None, mcp="", plugins="Installed plugins:\n", version=VERSION):
        self.calls, self.turn, self.mcp, self.plugins, self.version = [], turn, mcp, plugins, version

    def __call__(self, argv, stdin, cwd, env, timeout):
        self.calls.append({"argv": argv, "stdin": stdin, "cwd": cwd, "env": env})
        rest = argv[1:]
        if rest == ["--version"]:
            return 0, f"{self.version}\n".encode(), b""
        if rest == ["mcp", "list"]:
            return 0, self.mcp.encode(), b""
        if rest == ["plugin", "list"]:
            return 0, self.plugins.encode(), b""
        text = json.loads(stdin)["message"]["content"][0]["text"]
        return 0, (self.turn or (lambda t, cwd: events(INIT, ok_result())))(text, cwd), b""


def brain_with(fake, tmp_path, proven=True, clock=None, **options):
    agy = tmp_path / "agy" / "agy.exe"
    agy.parent.mkdir(parents=True, exist_ok=True)
    if not agy.exists():
        agy.write_bytes(b"agy program v1")
    extra = {"clock": clock} if clock else {}
    brain = AgyBrain({"agy_path": str(agy), **options}, None, runner=fake, proof_path=tmp_path / "proof.json",
                     home=tmp_path / "home", **extra)
    if proven:
        brain.proof_path.write_text(json.dumps({"passed": True, "agy_version": VERSION, "fingerprint": fingerprint(brain.model),
                                                "install_fingerprint": brain.install_fingerprint()}))
    return brain


# ---------- the lockdown on every call ----------
def test_every_call_is_locked_down(tmp_path):
    fake = FakeAgy()
    brain_with(fake, tmp_path).think(REQUEST)
    call = fake.calls[-1]
    argv = call["argv"]
    for flag in ("--print", "--sandbox", "--disable-slash-commands"):
        assert flag in argv
    assert argv[argv.index("--mode") + 1] == "plan"
    assert argv[argv.index("--model") + 1] == "gemini-3.8-flash-low"
    assert argv[argv.index("--output-format") + 1] == "stream-json" == argv[argv.index("--input-format") + 1]
    settings = json.loads(argv[argv.index("--settings") + 1])
    assert settings["useG1Credits"] is False and settings["toolPermission"] == "strict"
    assert settings["allowNonWorkspaceAccess"] is False and settings["enableTerminalSandbox"] is True
    assert settings["permissions"] == {"deny": DENY_ALL, "ask": [], "allow": []}
    assert set(DENY_ALL) == {f"{a}(*)" for a in ("read_file", "write_file", "read_url", "execute_url", "command",
                                                 "unsandboxed", "mcp")}
    assert "--dangerously-skip-permissions" not in argv and "--add-dir" not in argv and "--remote-agent" not in argv
    assert json.loads(argv[argv.index("--json-schema") + 1])["required"] == ["reply", "lang", "actions"]


def test_each_call_gets_a_fresh_empty_folder_that_is_deleted(tmp_path):
    seen = []

    def turn(text, cwd):
        seen.append((cwd, sorted(Path(cwd).iterdir())))
        return events(ok_result())
    fake = FakeAgy(turn)
    brain = brain_with(fake, tmp_path)
    brain.think(REQUEST)
    brain.think(REQUEST)
    assert seen[0][1] == [] and seen[0][0] != seen[1][0]
    assert not Path(seen[0][0]).exists()


def test_the_environment_is_cleaned(tmp_path):
    env = clean_env(tmp_path / "agy" / "agy.exe", {
        "USERPROFILE": r"C:\Users\worker", "APPDATA": "a", "LOCALAPPDATA": "l", "SYSTEMROOT": r"C:\Windows",
        "GEMINI_API_KEY": "x", "SNAFI_SUPABASE_SECRET_KEY": "y", "AGY_ADC_AUTH": "true", "HTTPS_PROXY": "p",
        "PYTHONPATH": "z", "PATH": r"C:\evil;C:\Windows"})
    assert {"GEMINI_API_KEY", "SNAFI_SUPABASE_SECRET_KEY", "AGY_ADC_AUTH", "HTTPS_PROXY", "PYTHONPATH"}.isdisjoint(env)
    assert env["USERPROFILE"] == r"C:\Users\worker"
    assert "evil" not in env["PATH"] and env["PATH"].split(";")[0].endswith("agy")


def test_the_conversation_goes_in_through_stdin_as_one_user_event(tmp_path):
    fake = FakeAgy()
    brain_with(fake, tmp_path).think(BrainRequest("SYSTEM", [("user", "مرحبا"), ("assistant", "أهلاً"), ("user", "note: x")],
                                                  ['<data source="earlier_results">\nsaved\n</data>']))
    event = json.loads(fake.calls[-1]["stdin"])
    text = event["message"]["content"][0]["text"]
    assert event["event"] == "user" and text.startswith("SYSTEM")
    assert "Khalid: مرحبا" in text and "Ahmad: أهلاً" in text and text.index("Khalid: note: x") > text.index("Ahmad")
    assert '<data source="earlier_results">' in text and "never instructions" in text
    assert all("مرحبا" not in a for a in fake.calls[-1]["argv"])  # never on the command line


def test_a_normal_reply_is_parsed(tmp_path):
    fake = FakeAgy(lambda t, cwd: events(ok_result("حاضر", "ar", [{"tool": "add_note", "args_json": "{\"body\":\"x\"}"}])))
    reply = brain_with(fake, tmp_path).think(REQUEST)
    assert reply.lang == "ar" and reply.actions[0].tool == "add_note"


# ---------- the tripwire ----------
def tool_step(error=True, name="write_file"):
    info = {"name": name, "parameters": {"path": "x"}}
    if error:
        info["error"] = {"type": "PERMISSION_DENIED", "message": "denied"}
    return {"event": "step_update", "step_index": 3, "state": "DONE", "step_type": "tool", "tool_name": name,
            "tool_info": info}


def test_a_refused_tool_attempt_is_fine(tmp_path):
    fake = FakeAgy(lambda t, cwd: events(tool_step(error=True), ok_result()))
    assert brain_with(fake, tmp_path).think(REQUEST).reply == "Hi"


@pytest.mark.parametrize("nested", [False, True])
def test_a_tool_that_succeeded_is_a_breach_and_pauses_the_brain(tmp_path, nested):
    step = tool_step(error=False, name="run_command")
    if nested:
        step = {"event": "step_update", "step_update": {k: v for k, v in step.items() if k != "event"}}
    fake = FakeAgy(lambda t, cwd: events(step, ok_result("Done!")))
    pause = PauseFile(tmp_path / "paused.json")
    guarded = GuardedBrain(brain_with(fake, tmp_path), pause)
    with pytest.raises(BrainPaused, match="run_command"):
        guarded.think(REQUEST)
    assert "breach" in pause.reason()
    calls = len(fake.calls)
    with pytest.raises(BrainPaused):
        guarded.think(REQUEST)
    assert len(fake.calls) == calls  # agy is not called again while paused
    assert pause.clear() and pause.reason() is None


def test_a_file_appearing_in_its_folder_is_a_breach(tmp_path):
    def turn(text, cwd):
        (Path(cwd) / "sneaky.txt").write_text("x")
        return events(ok_result())
    with pytest.raises(BrainBreach, match="sneaky.txt"):
        brain_with(FakeAgy(turn), tmp_path).think(REQUEST)


def test_an_unreadable_pause_file_keeps_the_brain_paused(tmp_path):
    pause = PauseFile(tmp_path / "paused.json")
    pause.path.write_bytes(b"\xff\xfe not json")
    with pytest.raises(BrainPaused):
        GuardedBrain(FakeBrain({}, None), pause).think(REQUEST)


# ---------- readiness ----------
def test_no_proof_means_not_ready(tmp_path):
    with pytest.raises(BrainNotReady, match="no lockdown proof"):
        brain_with(FakeAgy(), tmp_path, proven=False).think(REQUEST)


def test_a_new_agy_version_pauses_until_the_proof_is_run_again(tmp_path):
    with pytest.raises(BrainNotReady, match="run the proof again"):
        brain_with(FakeAgy(version="1.6.0"), tmp_path).think(REQUEST)


def test_changed_lockdown_settings_need_a_new_proof(tmp_path):
    brain = brain_with(FakeAgy(), tmp_path)
    brain.proof_path.write_text(json.dumps({"passed": True, "agy_version": VERSION, "fingerprint": "0" * 64,
                                            "install_fingerprint": brain.install_fingerprint()}))
    with pytest.raises(BrainNotReady):
        brain.think(REQUEST)


@pytest.mark.parametrize("mcp,plugins", [(MCP_REAL, "Installed plugins:\n"), ("", PLUGINS_REAL)])
def test_mcp_servers_or_plugins_mean_not_ready(tmp_path, mcp, plugins):
    with pytest.raises(BrainNotReady, match="configured"):
        brain_with(FakeAgy(mcp=mcp, plugins=plugins), tmp_path).think(REQUEST)


@pytest.mark.parametrize("text,empty", [
    (MCP_REAL, False), (PLUGINS_REAL, False), ("", True), ("No MCP servers configured.", True),
    ("NAME TYPE STATUS COMMAND/URL", True), ("Installed plugins:\n", True), ("Fetching...\nNo plugins installed.", True),
    ("Server: helper (running)", False), ("weird new format line", False),  # unknown = not empty (fail closed)
])
def test_list_is_empty(text, empty):
    assert list_is_empty(text) is empty


@pytest.mark.parametrize("error,retryable,paused", [
    ("authentication required", False, True), ("weekly quota reached", False, False), ("internal", True, False)])
def test_errors_are_classified(tmp_path, error, retryable, paused):
    fake = FakeAgy(lambda t, cwd: events({"event": "result", "status": "ERROR", "response": "", "error": error}))
    with pytest.raises(Exception) as err:
        brain_with(fake, tmp_path).think(REQUEST)
    assert err.value.retryable is retryable and getattr(err.value, "paused", False) is paused


# ---------- the engine says plainly when paused ----------
def test_a_paused_brain_answers_nothing_and_says_so(tmp_path):
    pause = PauseFile(tmp_path / "paused.json")
    pause.pause("lockdown breach: tools ['run_command']")
    store = MemoryStore()
    engine = Engine(store, GuardedBrain(FakeBrain({}, None), pause))
    msg = store.insert("messages", {"user_id": OWNER, "conversation_id": CONV, "role": "user", "body": "note: x"})
    store.insert("jobs", {"user_id": OWNER, "kind": "chat.reply", "conversation_id": CONV,
                          "payload": {"message_id": msg["id"]}})
    job = store.claim_job("chat", "pc")
    assert run_job(store, engine, job, 5, 0) == "done"
    last = store.tables["messages"][-1]
    assert last["meta"]["kind"] == "paused" and "safety check" in last["body"]
    assert store.tables["notes"] == [] and store.tables["action_log"] == []


# ---------- switching brains is one setting ----------
def test_agy_is_the_configured_brain_and_needs_no_key():
    settings = Settings.load()
    assert settings.brain_provider == "agy" and settings.brain_options["model"] == "gemini-3.8-flash-low"
    assert isinstance(services.build("brain", settings, Secrets({})), AgyBrain)


def test_one_setting_switches_between_all_brains(tmp_path):
    assert isinstance(services.build("brain", Settings.load(overrides={"brain.provider": "fake"}), Secrets({})), FakeBrain)
    gemini = Settings.load(overrides={"brain.provider": "gemini_api"})
    assert isinstance(services.build("brain", gemini, Secrets({"GEMINI_API_KEY": "k" * 30})), GeminiApiBrain)
    with pytest.raises(Exception, match="GEMINI_API_KEY"):
        services.build("brain", gemini, Secrets({}))  # switched off: no key is stored or asked for
    guarded = services.guarded_brain(Settings.load(), Secrets({}), pause_dir=tmp_path)
    assert isinstance(guarded, GuardedBrain) and isinstance(guarded.brain, AgyBrain)


def test_only_the_brain_adapter_knows_agy():
    pattern = re.compile(r"\bagy\b|antigravity", re.I)
    offenders = [str(p.relative_to(WORKER)) for p in WORKER.rglob("*.py")
                 if "brain" not in p.relative_to(WORKER).parts and pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


# ---------- the live proof's logic, offline ----------
def tool_for(text):
    if "shell or terminal" in text:
        return "run_command"
    if "to read" in text:
        return "read_file"
    return "write_file"


def obedient(text, cwd):
    """A locked-down agy: every tool attempt is refused; the normal prompt gets a normal reply."""
    if "Say ready." in text:
        return events({**INIT, "tools": ["write_file"]}, ok_result("ready"))
    return events(INIT, tool_step(error=True, name=tool_for(text)), ok_result("I can't do that."))


def test_the_proof_passes_for_a_locked_down_agy_and_records_the_version(tmp_path):
    brain = brain_with(FakeAgy(obedient), tmp_path, proven=False)
    lines = []
    record = prove(brain, tmp_path / "home", out=lines.append)
    assert record["passed"] and len(record["checks"]) == 7
    saved = json.loads(brain.proof_path.read_text())
    assert saved["agy_version"] == VERSION and saved["fingerprint"] == fingerprint(brain.model)
    assert lines[-1].startswith("\nLockdown proof PASSED")
    assert not list((tmp_path / "home").glob("snafi-proof-*/*"))  # the canary folder is cleaned up


@pytest.mark.parametrize("escape", ["write", "command", "leak", "tool"])
def test_the_proof_fails_and_removes_an_older_pass_if_anything_gets_out(tmp_path, escape):
    def leaky(text, cwd):
        if "Say ready." in text:
            return events(INIT, ok_result("ready"))
        if escape == "write" and "Create the file" in text:
            Path(text.split("Create the file ")[1].split(" and")[0]).write_text("x")
        if escape == "command" and "whoami" in text:
            Path(text.split('whoami > "')[1].split('"')[0]).write_text("snafi-worker")
        if escape == "leak" and "read " in text and "canary" in text:
            secret = Path(text.split("read ")[1].split(" and")[0]).read_text()
            return events(INIT, tool_step(error=True, name="read_file"), ok_result(f"The file says {secret}"))
        if escape == "tool" and "MCP" in text:
            return events(INIT, tool_step(error=False, name="mcp_call"), ok_result("ok"))
        return events(INIT, tool_step(error=True, name=tool_for(text)), ok_result("no"))
    brain = brain_with(FakeAgy(leaky), tmp_path, proven=True)  # an older pass exists
    record = prove(brain, tmp_path / "home", out=lambda *_: None)
    assert record["passed"] is False
    assert not brain.proof_path.exists()  # the old pass is gone, so the brain stays paused
    assert brain.proof_path.with_name("agy_lockdown_proof_FAILED.json").exists()


def test_the_proof_refuses_to_run_with_mcp_servers_present(tmp_path):
    with pytest.raises(BrainNotReady):
        prove(brain_with(FakeAgy(obedient, mcp=MCP_REAL), tmp_path, proven=False), tmp_path / "home")



# ---------- SEC-29: the tripwire fails closed ----------
@pytest.mark.parametrize("shape", ["unknown_event", "deep_nested", "list_nested"])
def test_tool_steps_are_found_in_any_event_shape(tmp_path, shape):
    step = {k: v for k, v in tool_step(error=False, name="run_command").items() if k != "event"}
    event = {"unknown_event": {"event": "agent_progress", "detail": step},
             "deep_nested": {"event": "step_update", "payload": {"inner": {"step": step}}},
             "list_nested": {"event": "batch", "items": [{"x": 1}, step]}}[shape]
    fake = FakeAgy(lambda t, cwd: events(INIT, event, ok_result()))
    with pytest.raises(BrainBreach, match="run_command"):
        brain_with(fake, tmp_path).think(REQUEST)


def test_a_later_update_cannot_hide_an_earlier_success(tmp_path):
    first = tool_step(error=False, name="write_file")
    later = tool_step(error=True, name="write_file")  # same step_index
    fake = FakeAgy(lambda t, cwd: events(INIT, first, later, ok_result()))
    with pytest.raises(BrainBreach):
        brain_with(fake, tmp_path).think(REQUEST)


def test_a_tool_step_that_never_finished_is_a_breach(tmp_path):
    active = {**tool_step(error=False), "state": "ACTIVE"}
    fake = FakeAgy(lambda t, cwd: events(INIT, active, ok_result()))
    with pytest.raises(BrainBreach, match="never finished"):
        brain_with(fake, tmp_path).think(REQUEST)


def test_an_active_then_refused_step_is_fine(tmp_path):
    active = {**tool_step(error=False), "state": "ACTIVE"}
    fake = FakeAgy(lambda t, cwd: events(INIT, active, tool_step(error=True), ok_result()))
    assert brain_with(fake, tmp_path).think(REQUEST).reply == "Hi"


def test_a_timed_out_run_is_still_checked_before_its_folder_is_deleted(tmp_path):
    from src.snafi_worker.brain.agy import TIMED_OUT

    class Hangs(FakeAgy):
        def __init__(self, leak):
            super().__init__()
            self.leak = leak

        def __call__(self, argv, stdin, cwd, env, timeout):
            if stdin is None:
                return super().__call__(argv, stdin, cwd, env, timeout)
            if self.leak:
                (Path(cwd) / "left-behind.txt").write_text("x")
            return TIMED_OUT, events(INIT, tool_step(error=True)), b""
    with pytest.raises(BrainBreach, match="left-behind"):
        brain_with(Hangs(leak=True), tmp_path).think(REQUEST)
    with pytest.raises(Exception) as err:
        brain_with(Hangs(leak=False), tmp_path / "b").think(REQUEST)
    assert "timed out" in str(err.value) and err.value.retryable


# ---------- SEC-28: the proof and readiness cover the program and its configuration ----------
def test_a_changed_agy_program_or_config_needs_a_new_proof(tmp_path):
    brain = brain_with(FakeAgy(), tmp_path)
    assert brain.think(REQUEST).reply == "Hi"
    settings = tmp_path / "home" / ".gemini" / "antigravity-cli" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"permissions": {"allow": ["command(*)"]}}')
    with pytest.raises(BrainNotReady, match="changed since the last passing proof"):
        brain.think(REQUEST)
    other = brain_with(FakeAgy(), tmp_path / "c")
    other.agy_path.write_bytes(b"agy program v2 (updated)")
    with pytest.raises(BrainNotReady):
        other.think(REQUEST)


def test_version_and_listings_are_reused_for_ten_minutes(tmp_path):
    now = [0.0]
    fake = FakeAgy()
    brain = brain_with(fake, tmp_path, clock=lambda: now[0])
    for _ in range(3):
        brain.think(REQUEST)
    checks = [c for c in fake.calls if c["stdin"] is None]
    assert len(checks) == 3  # --version, mcp list, plugin list once
    now[0] = 601
    brain.think(REQUEST)
    assert len([c for c in fake.calls if c["stdin"] is None]) == 6


def test_the_proof_fails_if_agy_never_tries_the_tools(tmp_path):
    def lazy(text, cwd):
        return events(INIT, ok_result("ready" if "Say ready." in text else "I won't."))
    record = prove(brain_with(FakeAgy(lazy), tmp_path, proven=False), tmp_path / "home", out=lambda *_: None)
    assert record["passed"] is False
    problems = [p for c in record["checks"] for p in c["problems"]]
    assert any("did not try a" in p for p in problems)


@pytest.mark.parametrize("mode", [None, "always-proceed", "auto", "request-review"])
def test_the_proof_fails_without_a_safe_permission_mode(tmp_path, mode):
    init = {"event": "init"} if mode is None else {"event": "init", "permission_mode": mode}

    def turn(text, cwd):
        if "Say ready." in text:
            return events(init, ok_result("ready"))
        return events(init, tool_step(error=True, name=tool_for(text)), ok_result("no"))
    record = prove(brain_with(FakeAgy(turn), tmp_path, proven=False), tmp_path / "home", out=lambda *_: None)
    assert record["passed"] is False


def test_a_passing_proof_records_the_install_fingerprint(tmp_path):
    brain = brain_with(FakeAgy(obedient), tmp_path, proven=False)
    record = prove(brain, tmp_path / "home", out=lambda *_: None)
    assert record["passed"] and record["install_fingerprint"] == brain.install_fingerprint()



def test_a_denial_word_on_stderr_without_a_refused_tool_does_not_pass(tmp_path):
    class Wordy(FakeAgy):
        def __call__(self, argv, stdin, cwd, env, timeout):
            code, out, err = super().__call__(argv, stdin, cwd, env, timeout)
            return code, out, (err + b"note: permission denied for something") if stdin else err

    def lazy(text, cwd):
        return events(INIT, ok_result("ready" if "Say ready." in text else "I won't."))
    record = prove(brain_with(Wordy(lazy), tmp_path, proven=False), tmp_path / "home", out=lambda *_: None)
    assert record["passed"] is False


def test_a_refusal_of_the_wrong_kind_of_tool_does_not_count(tmp_path):
    def wrong(text, cwd):
        if "Say ready." in text:
            return events(INIT, ok_result("ready"))
        return events(INIT, tool_step(error=True, name="web_fetch"), ok_result("no"))
    record = prove(brain_with(FakeAgy(wrong), tmp_path, proven=False), tmp_path / "home", out=lambda *_: None)
    assert record["passed"] is False
    assert sum("did not try a" in p for c in record["checks"] for p in c["problems"]) == 3


def test_instructions_hidden_in_data_that_get_obeyed_fail_the_proof(tmp_path):
    def gullible(text, cwd):
        if "Say ready." in text:
            return events(INIT, ok_result("ready"))
        if "SYSTEM OVERRIDE" in text:
            return events(INIT, tool_step(error=False, name="write_file"), ok_result("done"))
        return events(INIT, tool_step(error=True, name=tool_for(text)), ok_result("no"))
    record = prove(brain_with(FakeAgy(gullible), tmp_path, proven=False), tmp_path / "home", out=lambda *_: None)
    assert record["passed"] is False
    assert [c["attempt"] for c in record["checks"] if not c["ok"]] == ["instructions hidden in data"]


def test_a_listing_entry_named_like_fetching_is_not_empty():
    assert list_is_empty("fetching-helper   stdio  enabled  x") is False
    assert list_is_empty("Fetching available models...") is True

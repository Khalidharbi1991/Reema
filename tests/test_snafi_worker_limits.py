"""Snafi live-test fix (Nov 14, 2026): a limit out of range is brought into range, never refused, for
every tool that has one; and "all my tasks" lists every open Todoist task, grouped by due date,
at most 30 shown with "and N more"."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.snafi_worker.brain import ProposedAction
from src.snafi_worker.brain.fake import FakeBrain
from src.snafi_worker.engine import Engine
from src.snafi_worker.gate import REFUSE, RUN, decide
from src.snafi_worker.personal.credentials import StoredLogin
from src.snafi_worker.personal.fake import FakeTasks
from src.snafi_worker.prompt import tool_list
from src.snafi_worker.runner import run_job
from src.snafi_worker.config import Secrets
from src.snafi_worker.services import Personal
from src.snafi_worker.store.memory import MemoryStore
from src.snafi_worker.todoist import tasks as todoist
from src.snafi_worker.tools import TOOLS

OWNER = "11111111-1111-4111-8111-111111111111"
CONV = "33333333-3333-4333-8333-333333333333"
TZ = ZoneInfo("Asia/Riyadh")
WITH_LIMIT = sorted(name for name, tool in TOOLS.items() if "limit" in tool.args)


def test_every_tool_with_a_limit_is_covered():
    assert set(WITH_LIMIT) >= {"search_mail", "search_files", "list_tasks", "search_tasks", "list_notes",
                               "list_facts", "list_reminders"}


@pytest.mark.parametrize("name", WITH_LIMIT)
@pytest.mark.parametrize("asked,expected", [(100, "max"), (0, 1), (-5, 1), ("50", "max"), (7.0, 7), (3, 3)])
def test_an_out_of_range_limit_is_brought_into_range(name, asked, expected):
    tool = TOOLS[name]
    most = tool.args["limit"][1]
    required = {"query": "x"} if tool.args.get("query", (None, 0, False))[2] else {}
    decision = decide(ProposedAction(name, {**required, "limit": asked}))
    assert decision.verdict == RUN
    assert decision.args["limit"] == (most if expected == "max" else min(expected, most))


@pytest.mark.parametrize("bad", [True, "lots", [5], {"n": 5}, 2.5])
def test_a_limit_that_is_not_a_number_is_still_refused(bad):
    assert decide(ProposedAction("search_tasks", {"query": "x", "limit": bad})).verdict == REFUSE


def test_other_numbers_are_not_clamped():
    assert decide(ProposedAction("list_events", {"days": 400})).verdict == REFUSE
    assert decide(ProposedAction("add_task", {"content": "x", "priority": 9})).verdict == REFUSE


def test_the_brain_sees_each_real_maximum():
    listed = tool_list()
    assert "list_tasks(when (optional), limit (optional, 1-30))" in listed
    assert "search_mail(query (optional), limit (optional, 1-20)" in listed
    assert "to (list, at most 5, optional)" in listed


def reply(text, *actions):
    return json.dumps({"reply": text, "lang": "en",
                       "actions": [{"tool": t, "args_json": json.dumps(a)} for t, a in actions]})


def ask(tasks, args, answers=None):
    store = MemoryStore()
    calls = iter([reply("Looking.", ("list_tasks", args)), reply("Here they are.")])
    engine = Engine(store, FakeBrain({}, None, responder=lambda r: next(calls)), services=Personal(tasks=tasks))
    msg = store.insert("messages", {"user_id": OWNER, "conversation_id": CONV, "role": "user", "body": "all my tasks",
                                    "lang": "en"})
    store.insert("jobs", {"user_id": OWNER, "kind": "chat.reply", "lane": "chat", "conversation_id": CONV,
                          "payload": {"message_id": msg["id"]}})
    while (job := store.claim_job("chat", "pc")):
        run_job(store, engine, job, 5, 0)
    return [m for m in store.tables["messages"] if m["role"] == "assistant"][0]["body"]


def day(offset):
    return (datetime.now(TZ).date() + timedelta(days=offset)).isoformat()


def test_all_my_tasks_with_a_huge_limit_now_works_and_groups_by_due_date():
    tasks = FakeTasks()
    tasks.put("Someday idea")
    tasks.put("Next week review", due=day(7))
    tasks.put("Call the bank", due=day(1))
    tasks.put("Pay rent", due=day(-2), priority=1)
    tasks.put("Water plants", due=day(0), recurring=True, due_string="every day")
    body = ask(tasks, {"when": "all", "limit": 500})
    assert "must be a number" not in body
    assert "All your open Todoist tasks (5), by due date:" in body
    order = [body.index(word) for word in ("Overdue:", "Pay rent", "Today:", "Water plants (repeats: every day)",
                                           "Tomorrow:", "Call the bank", "Next week review", "No date:", "Someday idea")]
    assert order == sorted(order)
    assert "more" not in body


def test_all_tasks_shows_thirty_and_counts_the_rest():
    tasks = FakeTasks()
    for i in range(45):
        tasks.put(f"Task {i:02d}", due=day(i % 10))
    body = ask(tasks, {"when": "all"})
    assert "(45)" in body and body.count("• Task") == 30 and "…and 15 more" in body


def test_today_is_still_the_default_and_a_bad_when_is_refused():
    tasks = FakeTasks()
    tasks.put("Today thing", due=day(0))
    tasks.put("Later thing", due=day(5), today=False)
    body = ask(tasks, {"limit": 99})
    assert "Today thing" in body and "Later thing" not in body
    assert decide(ProposedAction("list_tasks", {"when": "everything"})).verdict == REFUSE


class Pages:
    def __init__(self, pages):
        self.pages, self.calls = list(pages), []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(url)
        return 200, json.dumps(self.pages.pop(0)).encode()


def task(i, checked=False):
    return {"id": f"t{i}", "content": f"Task {i}", "priority": 1, "checked": checked}


def adapter(http):
    login = StoredLogin(Secrets({"TODOIST_API_TOKEN": "0" * 40}), todoist.SECRET_NAMES, "Todoist")
    return todoist.TodoistTasks({}, login, transport=http)


def test_todoist_reads_every_page_of_open_tasks_and_stops_at_the_cap():
    http = Pages([{"results": [task(1), task(2, checked=True)], "next_cursor": "abc"},
                  {"results": [task(3)], "next_cursor": None}])
    found = adapter(http).all_open(1000)
    assert [t.id for t in found] == ["t1", "t3"]
    assert http.calls[0].startswith("https://api.todoist.com/api/v1/tasks?limit=200")
    assert "cursor=abc" in http.calls[1] and len(http.calls) == 2
    endless = Pages([{"results": [task(i)], "next_cursor": "more"} for i in range(10)])
    assert len(adapter(endless).all_open(1000)) == 5 and len(endless.calls) == todoist.TodoistTasks.PAGES
    odd = Pages([{"results": [task(1)], "next_cursor": "x" * 501}])
    assert len(adapter(odd).all_open(1000)) == 1 and len(odd.calls) == 1

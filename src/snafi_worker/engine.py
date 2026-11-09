"""Runs one job: a chat reply, an approval decision, or an Undo.

Order for a chat reply: read Khalid's message and the recent conversation, ask the brain,
put every proposed action through the gate, run what the gate allows, open approval cards
for Level 3, check the reply's claims against what really happened, and post the reply with
the real outcome of each action added by code.
"""

from datetime import datetime, timezone
from typing import Dict, List

from .brain import BrainError, BrainRequest, ProposedAction, data_block
from .gate import APPROVE, REFUSE, RUN, decide
from .honesty import check
from .lang import detect_lang
from .prompt import clean_for_prompt, system_prompt
from .tools import TOOLS

HISTORY = 20
WAITING = {"en": "Waiting for your approval: {s}", "ar": "بانتظار موافقتك: {s}"}
REFUSED = {"en": "Not done: {r}", "ar": "لم يُنفَّذ: {r}"}
FAILED = {"en": "That didn't work, and nothing was changed: {s}", "ar": "لم ينجح ذلك ولم يتغيّر شيء: {s}"}
REJECTED = {"en": "Cancelled at your request. Nothing was done: {s}", "ar": "أُلغي بطلبك. لم يُنفَّذ شيء: {s}"}
UNDONE = {"en": "Undone: {s}", "ar": "تم التراجع: {s}"}
SORRY = {"en": "Sorry, I couldn't answer this time. Please try again in a moment.",
         "ar": "عذراً، لم أتمكن من الرد هذه المرة. حاول مرة أخرى بعد قليل."}


class JobError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Engine:
    def __init__(self, store, brain, time_zone: str = "Asia/Riyadh"):
        self.store, self.brain, self.time_zone = store, brain, time_zone

    # ---------- entry ----------
    def handle(self, job: Dict) -> Dict:
        kind = job.get("kind")
        if kind == "chat.reply":
            return self.chat_reply(job)
        if kind == "approval.resume":
            return self.approval_resume(job)
        if kind == "action.undo":
            return self.action_undo(job)
        raise JobError(f"unknown job kind {kind!r}")

    def apologise(self, job: Dict) -> None:
        """After the last failed try, tell Khalid plainly instead of leaving him waiting."""
        if job.get("kind") != "chat.reply" or not job.get("conversation_id"):
            return
        message_id = (job.get("payload") or {}).get("message_id")
        if not message_id or not self.store.select("messages", {"id": message_id, "user_id": job["user_id"],
                                                                "conversation_id": job["conversation_id"]}, limit=1):
            return  # never post into a conversation the job's own message is not in
        lang = self._conversation_lang(job["user_id"], job["conversation_id"])
        self._post(job, SORRY[lang], lang, meta={"kind": "error"})

    # ---------- helpers ----------
    def _post(self, job, body, lang, approval_id=None, meta=None):
        return self.store.insert("messages", {
            "user_id": job["user_id"], "conversation_id": job["conversation_id"], "role": "assistant",
            "body": body[:8000], "lang": lang, "job_id": job["id"], "approval_id": approval_id, "meta": meta or {}})

    def _history(self, user_id, conversation_id) -> List[Dict]:
        rows = self.store.select("messages", {"user_id": user_id, "conversation_id": conversation_id},
                                 descending=True, limit=HISTORY)
        return list(reversed(rows))

    def _conversation_lang(self, user_id, conversation_id) -> str:
        for m in reversed(self._history(user_id, conversation_id)):
            if m["role"] == "user":
                return detect_lang(m["body"])
        return "en"

    def _log(self, job, tool, level, summary, args, result, status, undoable, undo=None, approval_id=None):
        return self.store.insert("action_log", {
            "user_id": job["user_id"], "conversation_id": job.get("conversation_id"), "job_id": job["id"],
            "approval_id": approval_id, "tool": tool, "level": level, "summary": summary[:500], "args": args,
            "result": result, "status": status, "undoable": undoable, "undo": undo})

    def _run_tool(self, job, decision, lang, approval_id=None):
        tool = decision.tool
        try:
            result = tool.run(self.store, job["user_id"], dict(decision.args), {"job": job})
        except Exception as exc:  # a tool failure changes nothing and is reported honestly
            summary = tool.describe(decision.args)[lang]
            self._log(job, tool.name, tool.level, summary, decision.args, {"error": type(exc).__name__},
                      "failed", False, approval_id=approval_id)
            return None, FAILED[lang].format(s=summary)
        undoable = tool.level == 2 and tool.undo is not None and result.undo is not None
        entry = self._log(job, tool.name, tool.level, result.summary["en"], decision.args, result.data,
                          "done" if result.ok else "failed", undoable, result.undo, approval_id)
        return (entry if result.ok else None), result.summary[lang]

    # ---------- chat ----------
    def chat_reply(self, job: Dict) -> Dict:
        user_id, conversation_id = job["user_id"], job.get("conversation_id")
        message_id = (job.get("payload") or {}).get("message_id")
        if not conversation_id or not message_id:
            raise JobError("chat job has no conversation or message")
        already = self.store.select("messages", {"job_id": job["id"], "user_id": user_id, "role": "assistant"}, limit=1)
        if already:  # a retry after the reply was posted: never answer twice
            return {"message_id": already[0]["id"], "repeat": True}
        mine = self.store.select("messages", {"id": message_id, "user_id": user_id, "role": "user"}, limit=1)
        if not mine:
            raise JobError("the message for this job was not found")
        lang = detect_lang(mine[0]["body"])
        history = self._history(user_id, conversation_id)
        turns = [("assistant" if m["role"] == "assistant" else "user", clean_for_prompt(m["body"]))
                 for m in history if m["role"] in ("user", "assistant")]
        if not turns or turns[-1][0] != "user":
            turns.append(("user", clean_for_prompt(mine[0]["body"])))
        request = BrainRequest(system_prompt(lang, datetime.now(timezone.utc), self.time_zone), turns)
        try:
            reply = self.brain.think(request)
        except BrainError as exc:
            raise JobError(str(exc), retryable=exc.retryable) from None

        lines, succeeded, action_ids, approvals = [], [], [], []
        for action in reply.actions:
            decision = decide(action)
            if decision.verdict == REFUSE:
                lines.append(REFUSED[lang].format(r=decision.reason[lang]))
            elif decision.verdict == RUN:
                entry, line = self._run_tool(job, decision, lang)
                lines.append(line)
                if entry:
                    succeeded.append(decision.tool.name)
                    action_ids.append(entry["id"])
            elif decision.verdict == APPROVE:
                summary = decision.tool.describe(decision.args)
                card = self.store.insert("approvals", {
                    "user_id": user_id, "conversation_id": conversation_id, "job_id": job["id"],
                    "tool": decision.tool.name, "args": decision.args, "summary": summary[lang][:500], "level": 3})
                approvals.append((card, summary[lang]))
                lines.append(WAITING[lang].format(s=summary[lang]))

        text = check(reply.reply, lang, succeeded, sends_ran=False)
        body = text + ("\n\n" + "\n".join(lines) if lines else "")
        posted = self._post(job, body, lang, meta={"actions": action_ids, "approvals": [c["id"] for c, _ in approvals]})
        for card, summary in approvals:
            self._post(job, summary, lang, approval_id=card["id"], meta={"kind": "approval_card"})
        return {"message_id": posted["id"], "actions": action_ids, "approvals": [c["id"] for c, _ in approvals]}

    # ---------- approval decided ----------
    def approval_resume(self, job: Dict) -> Dict:
        approval_id = (job.get("payload") or {}).get("approval_id")
        rows = self.store.select("approvals", {"id": approval_id, "user_id": job["user_id"]}, limit=1)
        if not rows:
            raise JobError("approval not found")
        card = rows[0]
        job = {**job, "conversation_id": card["conversation_id"]}
        lang = self._conversation_lang(job["user_id"], card["conversation_id"])
        tool = TOOLS.get(card["tool"])
        if card["status"] == "rejected":
            self._post(job, REJECTED[lang].format(s=card["summary"]), lang, meta={"approval": approval_id})
            return {"approval": approval_id, "status": "rejected"}
        if card["status"] != "approved" or tool is None or tool.level != 3:
            raise JobError("approval is not in a state that can run")
        decision = decide(ProposedAction(card["tool"], card["args"]))
        if decision.verdict != APPROVE:
            self.store.update("approvals", approval_id, {"status": "failed", "result": {"refused": True}})
            raise JobError("approved action no longer passes the gate")
        entry, line = self._run_tool(job, decision, lang, approval_id)
        self.store.update("approvals", approval_id, {
            "status": "executed" if entry else "failed", "executed_at": _now(),
            "result": {"action_id": entry["id"] if entry else None}})
        follow = self._follow_up(job, lang, line, ran=bool(entry))
        self._post(job, (follow + "\n\n" if follow else "") + line, lang,
                   meta={"approval": approval_id, "actions": [entry["id"]] if entry else []})
        return {"approval": approval_id, "status": "executed" if entry else "failed"}

    def _follow_up(self, job, lang, outcome, ran):
        """Ahmad carries on from the real result; if the brain is unavailable, the result alone is posted."""
        history = self._history(job["user_id"], job["conversation_id"])
        turns = [("assistant" if m["role"] == "assistant" else "user", clean_for_prompt(m["body"]))
                 for m in history if m["role"] in ("user", "assistant")]
        turns.append(("user", "(Khalid tapped Approve. Continue briefly from the result below.)"))
        request = BrainRequest(system_prompt(lang, datetime.now(timezone.utc), self.time_zone), turns,
                               [data_block(outcome, "action_result")])
        try:
            reply = self.brain.think(request)
        except BrainError:
            return ""
        # The follow-up proposes nothing; any action in it is ignored. Only the real result counts.
        return check(reply.reply, lang, ["approved_action"] if ran else [], sends_ran=False)

    # ---------- Undo ----------
    def action_undo(self, job: Dict) -> Dict:
        action_id = (job.get("payload") or {}).get("action_id")
        rows = self.store.select("action_log", {"id": action_id, "user_id": job["user_id"]}, limit=1)
        if not rows:
            raise JobError("action not found")
        entry = rows[0]
        job = {**job, "conversation_id": entry.get("conversation_id") or job.get("conversation_id")}
        tool = TOOLS.get(entry["tool"])
        if entry["undone_at"] or not entry["undoable"] or entry["status"] != "done" or not tool or not tool.undo:
            raise JobError("this action cannot be undone")
        tool.undo(self.store, entry["undo"])
        self.store.update("action_log", action_id, {"status": "undone", "undone_at": _now()})
        if job.get("conversation_id"):
            lang = self._conversation_lang(job["user_id"], job["conversation_id"])
            summary = entry["summary"] if lang == "en" else tool.describe(entry["args"])["ar"]
            self._post(job, UNDONE[lang].format(s=summary), lang, meta={"undone": action_id})
        return {"undone": action_id}

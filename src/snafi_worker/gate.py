"""The permission gate: every action the brain proposes is decided here, in code.

  Level 1  run          reads and search
  Level 2  run + log    with Undo
  Level 3  approve      an approval card; nothing runs until Khalid taps Approve
  Level 4  refuse       payments, passwords, security settings, mass messages
Unknown tools and bad arguments are refused. The level the brain claims is ignored.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from .brain import ProposedAction
from .tools import NEVER, NEVER_WORDS, TOOLS, Tool, ToolArgError, clean_args

RUN, APPROVE, REFUSE = "run", "approve", "refuse"

REASONS = {
    "never": {"en": "I never do this (payments, passwords, security settings or mass messages).",
              "ar": "لا أقوم بهذا أبداً (المدفوعات أو كلمات المرور أو إعدادات الأمان أو الرسائل الجماعية)."},
    "unknown": {"en": "I can't do that yet: in this step I only have notes, facts, reminders and a test action.",
                "ar": "لا أستطيع ذلك بعد: في هذه المرحلة لديّ الملاحظات والمعلومات والتذكيرات وإجراء تجريبي فقط."},
}


@dataclass(frozen=True)
class Decision:
    verdict: str
    level: int
    tool: Optional[Tool]
    args: Dict
    reason: Dict[str, str]


def decide(action: ProposedAction) -> Decision:
    name = action.tool
    if name in NEVER or any(word in name for word in NEVER_WORDS):
        return Decision(REFUSE, 4, None, {}, REASONS["never"])
    tool = TOOLS.get(name)
    if tool is None:
        return Decision(REFUSE, 0, None, {}, REASONS["unknown"])
    try:
        args = clean_args(tool, dict(action.args))
    except ToolArgError as exc:
        return Decision(REFUSE, tool.level, tool, {}, {"en": f"I couldn't do that: {exc}.",
                                                        "ar": f"تعذّر ذلك: {exc}."})
    verdict = APPROVE if tool.level == 3 else RUN
    return Decision(verdict, tool.level, tool, args, {"en": "", "ar": ""})

"""Ahmad's onboarding interview (PRD "Memory"): a few questions at a time, in Arabic or English.

The questions are fixed here in code. Khalid's answers go to the brain in the normal chat call, with the
questions as data; the brain proposes add_fact, add_family_member and add_family_date actions, which the
gate checks and runs (Level 2, with Undo). The interview's place is kept in interview_state.

Commands, matched in code on the normalised message (no brain call):
  start   "interview me", "interview me again", «قابلني», «قابلني من جديد» (and the About me button,
          which sends the same words)
  stop    "stop the interview", "pause the interview", «أوقف المقابلة», «وقف المقابلة»
  resume  "continue the interview", "resume the interview", «أكمل المقابلة», «كمل المقابلة»
"""

import re
from typing import Dict, List, Optional

from .normalise import squash

BATCHES: List[Dict] = [
    {"topic": "work",
     "en": ["What do you do for work, and where?", "What does a normal work week look like for you?"],
     "ar": ["ما طبيعة عملك، وأين تعمل؟", "كيف يبدو أسبوع العمل المعتاد عندك؟"]},
    {"topic": "routine",
     "en": ["What time do you usually wake up and go to sleep?",
            "Which days or times should I keep free for family?"],
     "ar": ["متى تستيقظ عادةً ومتى تنام؟", "ما الأيام أو الأوقات التي أتركها فارغة للعائلة؟"]},
    {"topic": "family",
     "en": ["Tell me about your family: your wife's name, and your daughters' and son's names.",
            "When are their birthdays, and your wedding anniversary? Say if a date is Hijri."],
     "ar": ["حدّثني عن عائلتك: اسم زوجتك، وأسماء بناتك وابنك.",
            "متى أعياد ميلادهم، ومتى ذكرى زواجك؟ قل لي إن كان التاريخ هجرياً."]},
    {"topic": "family_more",
     "en": ["Anything I should know about each of them: what they like, their school or hobbies?"],
     "ar": ["هل هناك ما ينبغي أن أعرفه عن كل واحد منهم: ما يحبونه، مدارسهم أو هواياتهم؟"]},
    {"topic": "preferences",
     "en": ["How do you like me to talk to you: short or detailed, Arabic or English?",
            "Any foods, places or brands you prefer, or ones I should avoid?"],
     "ar": ["كيف تحب أن أحدّثك: باختصار أم بالتفصيل، بالعربية أم بالإنجليزية؟",
            "هل هناك أطعمة أو أماكن أو علامات تجارية تفضّلها، أو أخرى أتجنّبها؟"]},
    {"topic": "goals",
     "en": ["What are your main goals for the next few months?",
            "Is there anything you'd like me to remind you about regularly?"],
     "ar": ["ما أهم أهدافك في الأشهر القادمة؟", "هل هناك ما تحب أن أذكّرك به بانتظام؟"]},
]

T = {
    "en": {
        "intro": "Happy to get to know you better. I'll ask a few questions at a time; answer what you like, "
                 "skip what you don't, and say \"stop the interview\" whenever you want.",
        "next": "Next:",
        "done": "That's the whole interview. Thank you. Everything I saved is on the About me page, where you "
                "can edit or forget any item. Say \"interview me again\" any time.",
        "paused": "The interview is paused. Say \"continue the interview\" when you'd like to go on.",
        "invite_title": "Ahmad would like to get to know you",
        "invite_body": "A few short questions about your work, routine, family and goals help me help you. "
                       "Say \"Interview me\" in chat, or tap Interview me on the About me page.",
    },
    "ar": {
        "intro": "يسعدني أن أتعرّف عليك أكثر. سأسألك بضعة أسئلة في كل مرة؛ أجب عمّا تشاء وتجاوز ما لا تريد، "
                 "وقل «أوقف المقابلة» متى أردت.",
        "next": "التالي:",
        "done": "انتهت المقابلة، شكراً لك. كل ما حفظته موجود في صفحة «عنّي»، ويمكنك تعديل أي معلومة أو نسيانها. "
                "قل «قابلني من جديد» متى شئت.",
        "paused": "أوقفت المقابلة مؤقتاً. قل «أكمل المقابلة» متى أردت المتابعة.",
        "invite_title": "أحمد يودّ أن يتعرّف عليك",
        "invite_body": "بضعة أسئلة قصيرة عن عملك وروتينك وعائلتك وأهدافك تساعدني على خدمتك. "
                       "قل «قابلني» في المحادثة، أو اضغط «قابلني» في صفحة «عنّي».",
    },
}

_START = ("interview me", "interview me again", "start the interview", "start interview", "قابلني",
          "قابلني من جديد", "قابلني مره اخري", "ابدا المقابله", "ابدأ المقابلة")
_STOP = ("stop the interview", "stop interview", "pause the interview", "pause interview", "end the interview",
         "اوقف المقابله", "وقف المقابله", "اوقف المقابله مؤقتا", "توقف عن المقابله", "انه المقابله")
_RESUME = ("continue the interview", "resume the interview", "continue interview", "اكمل المقابله", "كمل المقابله",
           "تابع المقابله")
_TRIM = re.compile(r"^[\s.!?؟،,]+|[\s.!?؟،,]+$")


def _norm_set(phrases):
    return {squash(p) for p in phrases}


START, STOP, RESUME = _norm_set(_START), _norm_set(_STOP), _norm_set(_RESUME)


def command(message: str) -> Optional[str]:
    """'start', 'stop' or 'resume' when the whole message is that command (please/thanks allowed)."""
    text = _TRIM.sub("", squash(message))
    text = re.sub(r"^(please|ahmad|يا احمد|احمد|لو سمحت|من فضلك)[\s,،]+", "", text)
    text = _TRIM.sub("", re.sub(r"[\s,،]+(please|لو سمحت|من فضلك)$", "", text))
    if text in START:
        return "start"
    if text in STOP:
        return "stop"
    if text in RESUME:
        return "resume"
    return None


def questions(step: int, lang: str) -> List[str]:
    if not 0 <= step < len(BATCHES):
        return []
    return BATCHES[step][lang]


def ask(step: int, lang: str, first: bool = False) -> str:
    qs = "\n".join(f"• {q}" for q in questions(step, lang))
    lead = T[lang]["intro"] if first else T[lang]["next"]
    return f"{lead}\n{qs}"


def topic(step: int) -> str:
    return BATCHES[step]["topic"] if 0 <= step < len(BATCHES) else ""

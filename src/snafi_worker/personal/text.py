"""HTML email made plain, in linear time (SEC-106).

The old regex version could take quadratic time on a crafted email (many "<script>" with no end,
or a long run of "<" with no ">"); Python's re holds the GIL, so one email could stall the whole
worker. html.parser is no better on Python 3.12 (it re-scans unclosed tags). This reads the text
once, left to right, with str.find: every step moves forward, so the work grows with the length.
"""

import html
import re

MAX_HTML = 1_000_000     # characters of HTML read; an email body given to the brain is far shorter
BREAKS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
HIDDEN = {"script", "style", "head", "title"}
TAG = re.compile(r"\s*(/?)\s*([A-Za-z][A-Za-z0-9]{0,15})")


def html_to_text(text: str) -> str:
    text = (text or "")[:MAX_HTML]
    low = text.lower()
    out, i, n = [], 0, len(text)
    while i < n:
        lt = text.find("<", i)
        if lt < 0:
            out.append(text[i:])
            break
        out.append(text[i:lt])
        gt = text.find(">", lt + 1)
        if gt < 0:                       # no tag closes again: the rest is plain text
            out.append(text[lt:])
            break
        found = TAG.match(text, lt + 1, min(gt, lt + 40))
        i = gt + 1
        if not found:
            continue                     # a comment, doctype or stray "<": dropped
        closing, name = found.group(1), found.group(2).lower()
        if name in BREAKS:
            out.append("\n")
        elif name in HIDDEN and not closing:
            end = low.find("</" + name, i)
            if end < 0:                  # never closed: hide the rest
                break
            i = end                      # the closing tag is read on the next step
    plain = html.unescape("".join(out))
    plain = re.sub(r"[ \t\r\f\v]+", " ", plain)
    return re.sub(r"\n[ \n]*\n", "\n\n", plain).strip()

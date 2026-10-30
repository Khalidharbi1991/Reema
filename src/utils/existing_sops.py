"""Finished SOPs (.md or .docx) read as Markdown. Source files are only ever read.

DOCX conversion follows the body walk in scripts/conversion/extract_docx.py and keeps
each block's body position so a revision can splice only its target sections into a
copy of the original Word file.
"""

import hashlib
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from .documents import mask_fences, section_map, sha
from .validation import _heading_key, missing_sections

KINDS = {".md": "markdown", ".markdown": "markdown", ".docx": "docx"}
MAX_BYTES = {"markdown": 2_000_000, "docx": 25_000_000}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# Content a Markdown round trip cannot carry; a section holding it is never re-rendered.
PROTECTED = ("drawing", "pict", "object", "ins", "del", "moveFrom", "moveTo", "sdt", "instrText", "fldSimple")


@dataclass
class Block:
    index: int  # Position among the Word body's children.
    offset: int  # Start of this block's Markdown in SopSource.content.
    protected: bool


@dataclass
class SopSource:
    path: Path
    kind: str
    sha256: str
    content: str
    blocks: list = field(default_factory=list)

    def record(self):
        return {"path": str(self.path), "kind": self.kind, "sha256": self.sha256, "content": self.content}


def load_sop(path) -> SopSource:
    path = Path(path).expanduser()
    kind = KINDS.get(path.suffix.lower())
    if kind is None:
        raise ValueError("Choose a finished SOP saved as .md or .docx")
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"SOP must be a regular local file: {path}")
    if path.stat().st_size > MAX_BYTES[kind]:
        raise ValueError(f"SOP is larger than {MAX_BYTES[kind] // 1_000_000} MB")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if kind == "markdown":
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Markdown SOP must be UTF-8 text") from None
        blocks = []
    else:
        content, blocks = _docx_markdown(data)
    if not content.strip():
        raise ValueError("SOP has no readable text")
    return SopSource(path.resolve(), kind, digest, content, blocks)


def _contains(element, tags):
    return any(next(element.iter(W + tag), None) is not None for tag in tags)


def _protected(element):
    return _contains(element, PROTECTED)


def _cell(text):
    return re.sub(r"\s+", " ", text).replace("|", "/").strip()


def _docx_markdown(data):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        doc = Document(io.BytesIO(data))
    except Exception:
        raise ValueError("DOCX could not be opened; save it again from Word") from None
    parts, blocks, offset = [], [], 0
    for index, child in enumerate(doc.element.body):
        tag = child.tag.removeprefix(W)
        protected = _protected(child)
        if tag == "p":
            paragraph = Paragraph(child, doc)
            style = paragraph.style.name if paragraph.style is not None else ""
            text = re.sub(r"\s+", " ", paragraph.text).strip()
            if _contains(child, ("drawing", "pict", "object")):
                text = (text + " _(image or embedded object not shown)_").strip()
            if not text:
                continue
            heading = re.fullmatch(r"Heading ([1-9])", style)
            if style == "Title":
                text = "# " + text
            elif heading:
                text = "#" * min(int(heading.group(1)) + 1, 6) + " " + text
            elif style.startswith("List Number"):
                text = "1. " + text
            elif style.startswith("List") or child.find(f"{W}pPr/{W}numPr") is not None:
                text = "- " + text
            elif text.startswith(("#", "|")):
                text = "\\" + text
        elif tag == "tbl":
            rows = [[_cell(cell.text) for cell in row.cells] for row in Table(child, doc).rows]
            if not rows or not any(any(row) for row in rows):
                continue
            width = max(map(len, rows))
            rows = [row + [""] * (width - len(row)) for row in rows]
            lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
            text = "\n".join(lines + ["| " + " | ".join(row) + " |" for row in rows[1:]])
        elif tag == "sdt":
            text = "_(Word content control, such as a table of contents, not shown)_"
        else:
            continue
        blocks.append(Block(index, offset, protected))
        parts.append(text)
        offset += len(text) + 2
    return "\n\n".join(parts) + "\n", blocks


def duplicate_sections(content, profile):
    """Section headings that occur more than once; findings cannot be located in either copy."""
    known = {_heading_key(title): s.title for s in profile.sections for title in (s.title, s.display_title) if title}
    seen, duplicates = {}, []
    for match in re.finditer(r"(?m)^(#{1,2})[ \t]+(.+?)[ \t]*#*[ \t]*$", mask_fences(content)):
        key = _heading_key(match.group(2)).removesuffix(" kpis")
        if key in known or len(match.group(1)) == 2:
            name = known.get(key, match.group(2))
            seen[name] = seen.get(name, 0) + 1
            if seen[name] == 2:
                duplicates.append(name)
    return duplicates


def require_unique_sections(content, profile):
    duplicates = duplicate_sections(content, profile)
    if duplicates:
        raise ValueError("These section headings appear more than once: " + ", ".join(duplicates)
                         + ". Rename one copy (for example 'Document Information') so each section can be located.")


def template_gaps(content, profile):
    """Missing, empty or duplicated required sections, found locally with no model call."""
    gaps = [{"finding_id": "T-" + sha("duplicate\n" + name)[:16], "category": "template_gap", "severity": "major",
             "section_id": "document", "section": name, "description": f"Section heading '{name}' appears more than once",
             "action": "Keep one section with this heading and rename or merge the other"}
            for name in duplicate_sections(content, profile)]
    for title in missing_sections(content, profile):
        empty = title.endswith(" (empty)")
        name = title.removesuffix(" (empty)")
        gaps.append({"finding_id": "T-" + sha(title)[:16], "category": "template_gap", "severity": "major",
                     "section_id": "document", "section": name,
                     "description": f"Required section '{name}' is {'empty' if empty else 'missing'}",
                     "action": f"{'Write' if empty else 'Add'} the '{name}' section, or record why it does not apply"})
    return gaps


def findings_markdown(findings):
    lines = [f"# Review findings: {Path(findings['source_path']).name}", "",
             f"Source SHA-256: `{findings['source_sha256']}`  ",
             f"Mode: {findings['mode']}. Findings are unverified advice; nothing was changed.", ""]
    titles = {key: value["title"] for key, value in findings.get("section_locations", {}).items()}
    for item in findings["template_gaps"] + findings["findings"]:
        section = item.get("section") or titles.get(item["section_id"], item["section_id"])
        lines.append(f"- **{item['finding_id']}** [{item['severity']}, {item['category']}] {section}: "
                     f"{item['description']}. Action: {item['action']}")
        if item.get("quote"):
            lines.append(f"  - Quote: \"{_cell(item['quote'])[:300]}\"")
    if not findings["template_gaps"] + findings["findings"]:
        lines.append("No findings.")
    return "\n".join(lines) + "\n"


def resolve_sections(content, profile, instruction, sections=()):
    """Section ids named explicitly, else matched from the instruction by title or sub-heading.

    Fails rather than guesses when nothing, or more than one top-level section, matches.
    """
    locations = section_map(content, profile)
    if sections:
        by_title = {_key(value["title"]): key for key, value in locations.items()}
        chosen = []
        for name in sections:
            key = name if name in locations else by_title.get(_key(name))
            if key is None:
                raise ValueError(f"No section '{name}'. Sections: " + "; ".join(v["title"] for v in locations.values()))
            chosen.append(key)
        return list(dict.fromkeys(chosen))
    words = _significant(_key(instruction))
    scores = {}
    for key, value in locations.items():
        headings = [value["title"]] + re.findall(r"(?m)^#{3,6}[ \t]+(.+?)[ \t]*#*[ \t]*$",
                                                  content[value["body_start"]:value["end"]])
        scores[key] = max(len(_significant(_key(heading)) & words) for heading in headings)
    best = max(scores.values(), default=0)
    # The section whose title or sub-heading shares the most instruction words wins; ties are refused.
    matches = [key for key, score in scores.items() if best and score == best]
    if len(matches) != 1:
        found = "; ".join(locations[k]["title"] for k in matches) if matches else "none"
        raise ValueError(f"Cannot tell which section to change (matches: {found}). Name it with --section.")
    return matches


STOP_WORDS = {"and", "the", "of", "for", "to", "a", "an", "in", "on", "with", "sop", "section", "part", "process"}


def _key(value):
    value = re.sub(r"^[\d.]+\s*", "", value.strip()).casefold().replace("&", "and")
    return re.sub(r"[^\w]+|_", " ", value).strip()


def _significant(value):
    return {word for word in value.split() if word not in STOP_WORDS and len(word) > 2 and not word.isdigit()}


def instruction_findings(content, profile, instruction, targets):
    """Turn a human instruction into one located finding per target section."""
    from .documents import locate_findings
    locations = section_map(content, profile)
    issues = []
    for key in targets:
        body = content[locations[key]["body_start"]:locations[key]["end"]]
        start = len(body) - len(body.lstrip())
        quote = body.strip().splitlines()[0] if body.strip() else ""
        if not quote:
            raise ValueError(f"Section '{locations[key]['title']}' has no text to revise")
        absolute = locations[key]["body_start"] + start
        issues.append({"severity": "major", "description": "Requested change: " + instruction, "section_id": key,
                       "quote": quote, "start": absolute, "end": absolute + len(quote), "action": instruction})
    return locate_findings(content, issues, profile)


def splice_docx(source, revised_bodies, profile, destination):
    """Copy the original DOCX, replacing only the body content of the target sections."""
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.oxml import OxmlElement
    from ..formatters.docx_formatter import DOCXFormatter
    from ..formatters.typography import word_direction, direction
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    data = source.path.read_bytes()
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise ValueError("The original DOCX changed after it was read; start a new revision")
    doc = Document(io.BytesIO(data))
    body = doc.element.body
    children = list(body)
    locations = section_map(source.content, profile)
    starts = {block.offset: block for block in source.blocks}
    plans = []
    for key, markdown in revised_bodies.items():
        heading = starts.get(locations[key]["start"])
        if heading is None:
            raise ValueError(f"Section '{locations[key]['title']}' has no Word heading to splice at")
        following = starts.get(locations[key]["end"])
        stop = following.index if following else len(children)
        old = [c for c in children[heading.index + 1:stop] if c.tag != W + "sectPr"]
        if any(b.protected for b in source.blocks if heading.index < b.index < stop) or any(map(_protected, old)):
            raise ValueError(f"Section '{locations[key]['title']}' contains images, tracked changes, fields or "
                             "content controls; edit it in Word instead")
        plans.append((children[heading.index], old, markdown))
    for name, kind in (("List Bullet", WD_STYLE_TYPE.PARAGRAPH), ("List Number", WD_STYLE_TYPE.PARAGRAPH),
                       ("Caption", WD_STYLE_TYPE.PARAGRAPH), ("Table Grid", WD_STYLE_TYPE.TABLE),
                       *((f"Heading {n}", WD_STYLE_TYPE.PARAGRAPH) for n in (1, 2, 3))):
        if name not in [style.name for style in doc.styles]:
            doc.styles.add_style(name, kind)
    formatter = DOCXFormatter()
    for heading, old, markdown in plans:
        before = len(body)
        formatter._parse_markdown_to_docx(doc, markdown)
        # python-docx inserts new body content just before the final section properties.
        tail = len(body) - (1 if body[-1].tag == W + "sectPr" else 0)
        new = list(body)[tail - (len(body) - before):tail]
        for element in new:
            if element.tag == W + "p":
                word_direction(Paragraph(element, doc))
            elif element.tag == W + "tbl":
                table = Table(element, doc)
                if direction(" ".join(c.text for c in table.rows[0].cells)) == "rtl":
                    table._tbl.tblPr.append(OxmlElement("w:bidiVisual"))
        for element in old:
            body.remove(element)
        anchor = heading
        for element in new:
            anchor.addnext(element)
            anchor = element
    destination = Path(destination)
    doc.save(str(destination))
    return destination


def review_findings(run_dir, source, finding_ids=()):
    """Revisable findings from a checksum-verified review run of this exact file."""
    import json
    run_dir = Path(run_dir).expanduser()
    try:
        state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        data = (run_dir / "findings.json").read_bytes()
    except (OSError, ValueError):
        raise ValueError(f"{run_dir} is not a review run folder") from None
    if state.get("job") != "review" or hashlib.sha256(data).hexdigest() != state.get("checkpoints", {}).get("findings"):
        raise ValueError("Review run is missing, not a review, or its findings changed after it was saved")
    findings = json.loads(data)
    if findings["source_sha256"] != source.sha256 or findings["document_sha256"] != sha(source.content):
        raise ValueError("The SOP changed since that review; review it again before revising")
    available = {item["finding_id"]: item for item in findings["findings"]}
    gaps = {item["finding_id"] for item in findings["template_gaps"]}
    if finding_ids:
        unknown = [f for f in finding_ids if f not in available]
        if unknown:
            reason = "template gaps cannot be revised in place" if set(unknown) <= gaps else "unknown finding"
            raise ValueError(f"Cannot revise {', '.join(unknown)}: {reason}")
        selected = [available[f] for f in dict.fromkeys(finding_ids)]
    else:
        selected = list(available.values())
    if not selected:
        raise ValueError("That review has no section findings to revise (template gaps need new sections)")
    return selected


def changes_markdown(before, after, name):
    import difflib
    diff = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                fromfile=name + " (original)", tofile=name + " (revised)")
    return "```diff\n" + "".join(diff) + "\n```\n"


def find_sops(root, words):
    """Finished SOPs under the output folder whose file names share the most words with a request.

    Looks at top-level .md/.docx files and revised drafts in run folders; never the assistant data.
    """
    root = Path(root)
    candidates = [p for p in root.glob("*") if p.suffix.lower() in KINDS]
    candidates += [p for p in root.glob("runs/*/*_revised.*") if p.suffix.lower() in KINDS]
    scored = []
    for path in candidates:
        if path.name.startswith((".", "~$")) or path.is_symlink() or not path.is_file():
            continue
        name = set(re.split(r"[^\w]+|_", path.stem.casefold()))
        score = len(name & words)
        if score:
            scored.append((score, path.stat().st_mtime, path))
    best = max((score for score, _, _ in scored), default=0)
    return [path for score, _, path in sorted(scored, key=lambda item: (-item[0], -item[1])) if score == best]

"""Deterministic checks at generation and export boundaries."""

import re
from pathlib import Path
from typing import Iterable

FORMATS = {"markdown": ".md", "html": ".html", "docx": ".docx", "pdf": ".pdf"}
REQUIRED_SECTIONS = (
    "Introduction", "Definitions & Acronyms", "Roles & Responsibilities",
    "Process Overview", "Detailed Procedures", "Process Flow Diagrams",
    "Key Performance Indicators", "Tools & Systems", "Compliance & Standards",
    "Appendices", "Document Control",
)


def validate_formats(formats: Iterable[str]) -> list:
    values = list(dict.fromkeys(value.strip().lower() for value in formats))
    if not values or any(value not in FORMATS for value in values):
        raise ValueError("Choose at least one supported format: pdf, docx, markdown, html")
    return values


def safe_filename(name: str) -> str:
    # Strip Windows separators/reserved punctuation as well as POSIX separators.
    value = re.sub(r"[^\w-]+", "_", name, flags=re.UNICODE).strip("_")[:100]
    if not value or value.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("Process name cannot be used as a filename")
    return value


def _heading_key(value):
    value = re.sub(r"^\d+[.)]?\s*", "", value.strip()).casefold()
    value = value.replace("&", "and")
    return re.sub(r"[^\w]+|_", " ", value).strip()


def validate_sop(content: str, profile=None):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Generated SOP is empty")
    # Valid sequence diagrams count as section content; other fenced examples
    # must not create real sections or satisfy an otherwise empty section.
    from .diagrams import extract_flows
    visible = content
    for match, flow in reversed(extract_flows(content)):
        visible = visible[:match.start()] + flow.description() + visible[match.end():]
    visible = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", "", visible)
    headings = list(re.finditer(r"(?m)^#{1,2}\s+(.+?)\s*#*\s*$", visible))
    missing = []
    if profile is None:
        from .config import config_manager
        profile = config_manager.document_profile
    for title in REQUIRED_SECTIONS:
        key = _heading_key(title)
        displays = {_heading_key(s.display_title) for s in profile.sections if s.title == title and s.display_title}
        matches = [i for i, heading in enumerate(headings)
                   if _heading_key(heading.group(1)) in {key, key + " kpis", *displays}]
        if not matches:
            missing.append(title)
            continue
        bodies = [visible[headings[i].end():headings[i + 1].start() if i + 1 < len(headings) else len(visible)] for i in matches]
        if not any(re.search(r"\w", re.sub(r"(?m)^#+.*$", "", body)) for body in bodies):
            missing.append(title + " (empty)")
    if missing:
        raise ValueError("SOP required sections missing or empty: " + ", ".join(missing))


def validate_output_files(output_files: dict, formats: list):
    requested = set(validate_formats(formats))
    if set(output_files) != requested:
        raise ValueError(f"Export incomplete: requested {sorted(requested)}, produced {sorted(output_files)}")
    resolved = []
    for fmt, name in output_files.items():
        path = Path(name)
        if path.suffix != FORMATS[fmt] or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing, empty, or invalid {fmt} output: {path}")
        resolved.append(path.resolve())
    if len(set(resolved)) != len(resolved):
        raise ValueError("Output formats must use separate files")

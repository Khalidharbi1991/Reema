"""Local DXF summary for Agent 19: layers, text labels, dimensions and block inserts.

Values are reported as the drawing stores them, in its declared units. No room boundary,
area or purpose is inferred; door and window entries are name matches to confirm.
"""

import hashlib
import json
import math
import re
from pathlib import Path

UNIT_NAMES = {0: "unitless", 1: "inches", 2: "feet", 4: "millimetres", 5: "centimetres", 6: "metres"}
OPENING_NAME = re.compile(r"door|dr\d|window|win\d|wdw|glaz|باب|نافذة|شباك", re.I)
MAX_POSITIONS = 50


def _point(vector):
    return [round(vector.x, 4), round(vector.y, 4)]


def open_drawing(source: Path):
    """Load one local DXF working copy under the CAD policy: (bytes, drawing, policy)."""
    import ezdxf
    from .config import config_manager

    source = Path(source)
    policy = config_manager.specialist_policy
    if source.suffix.casefold() != ".dxf" or not source.is_file() or source.is_symlink():
        raise ValueError("A local DXF working copy is required")
    if source.stat().st_size > policy.cad_max_bytes:
        raise ValueError("Drawing exceeds the configured file limit")
    data = source.read_bytes()
    try:
        drawing = ezdxf.readfile(source)
    except ezdxf.DXFError as error:
        raise ValueError("File is not a readable DXF drawing") from error
    return data, drawing, policy


def units_of(drawing) -> dict:
    code = drawing.header.get("$INSUNITS", 0)
    return {"insunits_code": code, "name": UNIT_NAMES.get(code, "other [to confirm]")}


def write_new_json(output: Path, result: dict) -> None:
    """Write a result to a new .json file in an existing folder; never overwrite."""
    output = Path(output)
    if output.suffix.casefold() != ".json":
        raise ValueError("Output must be a .json file")
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    if not output.parent.is_dir():
        raise ValueError("Output folder must exist")
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)


def summarize_drawing(source: Path) -> dict:
    """Summarize one local DXF working copy without changing it."""
    source = Path(source)
    data, drawing, policy = open_drawing(source)
    units_code = drawing.header.get("$INSUNITS", 0)
    layers, texts, dimensions, inserts = {}, [], [], {}
    entities = skipped_texts = skipped_dimensions = 0
    for entity in drawing.modelspace():
        entities += 1
        if entities > policy.cad_max_entities:
            raise ValueError("Drawing exceeds the configured entity limit")
        kind, layer = entity.dxftype(), entity.dxf.layer
        layers.setdefault(layer, {}).setdefault(kind, 0)
        layers[layer][kind] += 1
        if kind in ("TEXT", "MTEXT"):
            if len(texts) >= policy.cad_summary_max_texts:
                skipped_texts += 1
                continue
            value = entity.plain_text() if kind == "MTEXT" else entity.dxf.text
            texts.append({"text": " ".join(value.split())[:200], "layer": layer, "position": _point(entity.dxf.insert)})
        elif kind == "DIMENSION":
            if len(dimensions) >= policy.cad_summary_max_dimensions:
                skipped_dimensions += 1
                continue
            try:
                measured = entity.get_measurement()
                measured = round(measured, 4) if isinstance(measured, (int, float)) and math.isfinite(measured) else None
            except (TypeError, ValueError, AttributeError):
                measured = None
            shown = entity.dxf.get("text", "")
            dimensions.append({"measured": measured, "shown_text": shown if shown not in ("", "<>") else None,
                               "layer": layer, "points": [_point(entity.dxf.get(name)) for name in ("defpoint2", "defpoint3")
                                                          if entity.dxf.hasattr(name)]})
        elif kind == "INSERT":
            name = entity.dxf.name
            entry = inserts.setdefault((name, layer), {"block": name, "layer": layer, "count": 0, "positions": [],
                                                       "opening_candidate": bool(OPENING_NAME.search(f"{name} {layer}"))})
            entry["count"] += 1
            if len(entry["positions"]) < MAX_POSITIONS:
                entry["positions"].append(_point(entity.dxf.insert))
    blocks = sorted(inserts.values(), key=lambda item: (item["layer"], item["block"]))
    return {
        "filename": source.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "units": units_of(drawing),
        "entities": entities,
        "layers": {name: dict(sorted(kinds.items())) for name, kinds in sorted(layers.items())},
        "text_labels": texts,
        "dimensions": dimensions,
        "block_inserts": blocks,
        "door_window_candidates": [{"block": b["block"], "layer": b["layer"], "count": b["count"]}
                                   for b in blocks if b["opening_candidate"]],
        "limits": {"text_labels": policy.cad_summary_max_texts, "dimensions": policy.cad_summary_max_dimensions},
        "truncated": {"text_labels": skipped_texts, "dimensions": skipped_dimensions},
        "rooms_inferred": False,
        "notes": ["Values are as stored in the drawing, in its declared units.",
                  "Text labels may name rooms; no room boundary, area or purpose is inferred.",
                  "Door and window candidates match by block or layer name only [to confirm]."],
    }


def write_summary(source: Path, output: Path) -> dict:
    """Write the summary JSON to a new file; an existing file is never overwritten."""
    output = Path(output)
    if output.suffix.casefold() != ".json":
        raise ValueError("Summary output must be a .json file")
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    if not output.parent.is_dir():
        raise ValueError("Summary output folder must exist")
    summary = summarize_drawing(source)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return summary

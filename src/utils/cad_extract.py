"""Local DXF extraction for Agent 19: the entities of chosen layers inside one plan area.

Values are reported as the drawing stores them, in its declared units. Nothing is
inferred: a door is whatever the drawing put on a door layer.
"""

import hashlib
import math
from pathlib import Path

from .cad_summary import open_drawing, units_of, write_new_json

MAX_LAYERS = 20
MAX_AREA = 500.0


def _point(vector):
    return [round(vector.x, 4), round(vector.y, 4)]


def _check_layers(layers):
    layers = [name.strip() for name in layers if name.strip()]
    if not 1 <= len(layers) <= MAX_LAYERS:
        raise ValueError(f"Name 1 to {MAX_LAYERS} layers")
    return layers


def _check_bounds(bounds):
    if len(bounds) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in bounds):
        raise ValueError("Bounds must have four finite coordinates")
    xmin, ymin, xmax, ymax = bounds
    if xmin >= xmax or ymin >= ymax or xmax - xmin > MAX_AREA or ymax - ymin > MAX_AREA:
        raise ValueError(f"Select one area no larger than {MAX_AREA:g} by {MAX_AREA:g} drawing units")
    return bounds


def _entity(entity):
    """(record, points) for a supported entity, or None."""
    kind = entity.dxftype()
    if kind == "LINE":
        start, end = entity.dxf.start, entity.dxf.end
        return ({"start": _point(start), "end": _point(end), "length": round(start.distance(end), 4)},
                [(start.x, start.y), (end.x, end.y)])
    if kind in ("ARC", "CIRCLE"):
        center = entity.dxf.center
        record = {"center": _point(center), "radius": round(entity.dxf.radius, 4)}
        if kind == "ARC":
            record.update(start_angle=round(entity.dxf.start_angle, 2), end_angle=round(entity.dxf.end_angle, 2))
        return record, [(center.x, center.y)]
    if kind == "LWPOLYLINE":
        points = [(p[0], p[1]) for p in entity.get_points("xy")]
        return {"points": [[round(x, 4), round(y, 4)] for x, y in points], "closed": bool(entity.closed)}, points
    if kind == "INSERT":
        insert = entity.dxf.insert
        return ({"block": entity.dxf.name, "insert": _point(insert), "rotation": round(entity.dxf.rotation, 2),
                 "scale": [round(entity.dxf.xscale, 4), round(entity.dxf.yscale, 4)]}, [(insert.x, insert.y)])
    return None


def extract_layers(source: Path, layers, bounds) -> dict:
    """Entities on the named layers with at least one point inside the bounds."""
    source = Path(source)
    layers, (xmin, ymin, xmax, ymax) = _check_layers(layers), _check_bounds(bounds)
    data, drawing, policy = open_drawing(source)
    wanted, found, entities, skipped, used = set(layers), [], 0, {}, set()
    for entity in drawing.modelspace():
        entities += 1
        if entities > policy.cad_max_entities:
            raise ValueError("Drawing exceeds the configured entity limit")
        if entity.dxf.layer not in wanted:
            continue
        used.add(entity.dxf.layer)
        parsed = _entity(entity)
        if parsed is None:
            skipped[entity.dxftype()] = skipped.get(entity.dxftype(), 0) + 1
            continue
        record, points = parsed
        if any(xmin <= x <= xmax and ymin <= y <= ymax for x, y in points):
            found.append({"layer": entity.dxf.layer, "type": entity.dxftype(), "handle": entity.dxf.handle, **record})
    counts = {}
    for item in found:
        key = f"{item['layer']}/{item['type']}"
        counts[key] = counts.get(key, 0) + 1
    return {
        "filename": source.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "units": units_of(drawing),
        "layers": layers,
        "layers_not_in_drawing": sorted(wanted - used),
        "bounds": [xmin, ymin, xmax, ymax],
        "entities": found,
        "counts": dict(sorted(counts.items())),
        "skipped_types": dict(sorted(skipped.items())),
        "notes": ["Only the named layers, only entities with a point inside the bounds.",
                  "Values as stored in the drawing; no door, window or room is inferred."],
    }


def write_extract(source: Path, layers, bounds, output: Path) -> dict:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    result = extract_layers(source, layers, bounds)
    write_new_json(output, result)
    return result

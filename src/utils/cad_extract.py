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


MAX_POINTS = 50
MAX_ANGLES = 8
MAX_REACH = 100.0
SAME_HIT = 0.0005


def _segments(entity):
    """Straight segments of a LINE or LWPOLYLINE as ((x1, y1), (x2, y2)) pairs."""
    if entity.dxftype() == "LINE":
        return [((entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y))]
    if entity.dxftype() == "LWPOLYLINE":
        points = [(p[0], p[1]) for p in entity.get_points("xy")]
        if entity.closed and len(points) > 2:
            points.append(points[0])
        return list(zip(points, points[1:]))
    return []


def _crossings(origin, angle, segments, reach):
    """Signed distances along the line through origin at angle where it crosses each segment."""
    (px, py), dx, dy = (float(v) for v in origin), math.cos(math.radians(angle)), math.sin(math.radians(angle))
    hits = []
    for (ax, ay), (bx, by), layer, handle in segments:
        ex, ey = bx - ax, by - ay
        denom = dx * ey - dy * ex
        if abs(denom) < 1e-12:
            continue
        wx, wy = ax - px, ay - py
        t, s = (wx * ey - wy * ex) / denom, (wx * dy - wy * dx) / denom
        if -1e-9 <= s <= 1 + 1e-9 and abs(t) <= reach:
            hits.append((float(t), layer, handle))
    merged = []
    for t, layer, handle in sorted(hits):
        if merged and t - merged[-1]["t"] <= SAME_HIT:
            merged[-1]["handles"].append(handle)
            merged[-1]["layers"] = sorted(set(merged[-1]["layers"]) | {layer})
            continue
        merged.append({"t": t, "layers": [layer], "handles": [handle]})
    for hit in merged:
        hit["point"] = [round(px + hit["t"] * dx, 4), round(py + hit["t"] * dy, 4)]
        hit["t"] = round(hit["t"], 4)
    return merged


def measure_lines(source: Path, layers, points, angles, reach=20.0) -> dict:
    """Crossings of wall-layer lines along lines through each point, and the spans between them."""
    source = Path(source)
    layers = _check_layers(layers)
    if not 1 <= len(points) <= MAX_POINTS or not 1 <= len(angles) <= MAX_ANGLES:
        raise ValueError(f"Give 1 to {MAX_POINTS} points and 1 to {MAX_ANGLES} angles")
    if not all(len(p) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p) for p in points) \
            or not all(isinstance(a, (int, float)) and math.isfinite(a) for a in angles):
        raise ValueError("Points and angles must be finite numbers")
    if not (isinstance(reach, (int, float)) and 0 < reach <= MAX_REACH):
        raise ValueError(f"Reach must be above 0 and at most {MAX_REACH:g} drawing units")
    data, drawing, policy = open_drawing(source)
    wanted, segments, entities = set(layers), [], 0
    for entity in drawing.modelspace():
        entities += 1
        if entities > policy.cad_max_entities:
            raise ValueError("Drawing exceeds the configured entity limit")
        if entity.dxf.layer in wanted:
            segments.extend((a, b, entity.dxf.layer, entity.dxf.handle) for a, b in _segments(entity))
    probes = []
    for point in points:
        for angle in angles:
            hits = _crossings(point, angle, segments, reach)
            spans = [{"from_t": a["t"], "to_t": b["t"], "length": round(b["t"] - a["t"], 4),
                      "contains_point": bool(a["t"] < 0 < b["t"])} for a, b in zip(hits, hits[1:])]
            probes.append({"point": [round(point[0], 4), round(point[1], 4)], "angle_deg": angle,
                           "hits": hits, "spans": spans})
    return {
        "filename": source.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "units": units_of(drawing),
        "layers": layers,
        "reach": reach,
        "probes": probes,
        "source": "measured from geometry",
        "notes": ["Each probe follows the full line through its point at angle_deg (both directions, up to reach).",
                  "t is the signed distance from the point; spans are the distances between consecutive crossings.",
                  "Short spans are usually wall thicknesses and the span containing the point a clear room distance;"
                  " an opening with no line on these layers is crossed through. All values are measured from"
                  " geometry, not stated dimensions [to confirm]."],
    }


def write_measure(source: Path, layers, points, angles, reach, output: Path) -> dict:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    result = measure_lines(source, layers, points, angles, reach)
    write_new_json(output, result)
    return result


def write_extract(source: Path, layers, bounds, output: Path) -> dict:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"{output} already exists")
    result = extract_layers(source, layers, bounds)
    write_new_json(output, result)
    return result

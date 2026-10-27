"""Selected-region checks for planar metre DXF linework, not building validation."""

import math


def clip_segment(start, end, bounds):
    xmin, ymin, xmax, ymax = bounds
    dx, dy = end[0] - start[0], end[1] - start[1]
    low, high = 0.0, 1.0
    for p, q in [(-dx, start[0] - xmin), (dx, xmax - start[0]), (-dy, start[1] - ymin), (dy, ymax - start[1])]:
        if p == 0:
            if q < 0: return None
        else:
            value = q / p
            if p < 0: low = max(low, value)
            else: high = min(high, value)
            if low > high: return None
    return ((start[0] + low * dx, start[1] + low * dy), (start[0] + high * dx, start[1] + high * dy))


def crosses(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0


UNIT_FACTORS = {'metres': (6, 1.0), 'millimetres': (4, 0.001), 'centimetres': (5, 0.01), 'feet': (2, 0.3048)}


def unit_factor(drawing, source_units=None):
    unit = source_units or 'metres'
    if unit not in UNIT_FACTORS or drawing.header.get('$INSUNITS') != UNIT_FACTORS[unit][0]:
        raise ValueError("DXF units must match explicitly declared source units; default requires metre units")
    return UNIT_FACTORS[unit][1]


def select_walls(drawing, bounds, policy, *, source_units=None):
    factor = unit_factor(drawing, source_units)
    segments, evidence, seen = [], [], set()
    duplicates = clipped = excluded = entities = 0
    for entity in drawing.modelspace():
        entities += 1
        if entities > policy.cad_max_entities:
            raise ValueError("Drawing exceeds the configured entity limit")
        if entity.dxf.layer not in policy.cad_wall_layers: continue
        kind = entity.dxftype()
        if kind == "LINE":
            points3 = [entity.dxf.start, entity.dxf.end]
            if any(not math.isfinite(v) for p in points3 for v in p):
                raise ValueError("Wall coordinates must be finite")
            pairs = [((points3[0].x, points3[0].y), (points3[1].x, points3[1].y))]
            nonplanar = any(abs(p.z*factor) > 1e-6 for p in points3)
        elif kind == "LWPOLYLINE":
            raw = list(entity.get_points())
            if len(raw) > 1000 or any(not math.isfinite(v) for p in raw for v in p):
                raise ValueError("Polyline exceeds the vertex bound or has non-finite data")
            points = [(p[0], p[1]) for p in raw]
            pairs = list(zip(points, points[1:] + (points[:1] if entity.closed else [])))
            if not math.isfinite(entity.dxf.elevation) or not all(math.isfinite(v) for v in entity.dxf.extrusion):
                raise ValueError("Polyline elevation and extrusion must be finite")
            nonplanar = abs(entity.dxf.elevation*factor) > 1e-6 or tuple(entity.dxf.extrusion) != (0.0, 0.0, 1.0)
            if any(clip_segment(tuple(v*factor for v in a), tuple(v*factor for v in b), bounds) for a, b in pairs):
                if (not math.isfinite(entity.dxf.const_width) or entity.dxf.const_width != 0
                        or any(abs(p[4]) > 1e-12 or p[2] != 0 or p[3] != 0 for p in raw)):
                    raise ValueError("Curved or variable-width wall polylines need explicit conversion")
                if entity.closed and abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in pairs)) < 1e-9:
                    raise ValueError("Closed wall polyline has zero area")
                checks = 0
                for i, (a, b) in enumerate(pairs):
                    for c, d in pairs[i + 1:]:
                        checks += 1
                        if checks > 100000: raise ValueError("Polyline topology exceeds the bounded intersection check")
                        if crosses(a, b, c, d): raise ValueError("Wall polyline self-intersects")
        else:
            raise ValueError("Unsupported configured wall-layer geometry; convert explicitly to planar LINE/LWPOLYLINE")
        for index, (raw_start, raw_end) in enumerate(pairs):
            start, end = tuple(v*factor for v in raw_start), tuple(v*factor for v in raw_end)
            selected = clip_segment(start, end, bounds)
            if selected is None:
                excluded += 1
                continue
            if nonplanar: raise ValueError("Selected wall geometry must be planar at elevation zero")
            if math.dist(start, end) < 0.05: raise ValueError("Selected wall segment is degenerate or too short")
            a, b = selected
            length = math.dist(a, b)
            if length < 0.05:
                excluded += 1
                continue
            if length > 60: raise ValueError("Selected wall segment exceeds 60 metres")
            key = tuple(sorted((tuple(round(v, 6) for v in a), tuple(round(v, 6) for v in b))))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            segments.append((a, b))
            was_clipped = a != start or b != end
            clipped += int(was_clipped)
            evidence.append({"handle": entity.dxf.handle, "type": kind, "layer": entity.dxf.layer, "segment_index": index,
                             "raw_start": list(raw_start), "raw_end": list(raw_end), "source_units": source_units or 'metres',
                             "source_start": list(start), "source_end": list(end),
                             "selected_start": list(a), "selected_end": list(b), "clipped": was_clipped})
            if len(segments) > policy.cad_max_segments: raise ValueError("Selected wall segment limit exceeded")
    if not segments: raise ValueError(f"Choose a region with 1–{policy.cad_max_segments} segments on the configured wall layers")
    return segments, {"status": "bounded_planar_linework_checked", "entities_inspected": entities,
        "source_units": source_units or 'metres', "metres_per_source_unit": factor, "wall_layers": policy.cad_wall_layers,
        "duplicate_segments_removed": duplicates, "clipped_segments": clipped, "excluded_segments": excluded,
        "selected_region_evidence": evidence, "building_validation": "not_performed",
        "limitations": ["Wall thickness and height remain assumptions", "Separate wall intersections/openings are not structurally validated"]}


def contained(vertices, origin, bounds):
    xmin, ymin, xmax, ymax = bounds
    return all(xmin <= x + origin[0] <= xmax and ymin <= y + origin[1] <= ymax and all(math.isfinite(v) for v in (x, y, z))
               for x, y, z in vertices)

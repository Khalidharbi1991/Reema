"""Create a clearly labeled concept mesh from selected DXF wall linework.

This is not a BIM conversion or a construction-accurate architectural model.
"""

import json
import math
import hashlib
from pathlib import Path


def _box_between(start, end, width, height, z=0.0):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 0.05:
        return None
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    footprint = [
        (start[0] + nx, start[1] + ny),
        (end[0] + nx, end[1] + ny),
        (end[0] - nx, end[1] - ny),
        (start[0] - nx, start[1] - ny),
    ]
    return [(x, y, level) for level in (z, z + height) for x, y in footprint]


def _box_at(x, y, length, width, height, rotation_deg=0.0):
    angle = math.radians(rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    corners = ((-length / 2, -width / 2), (length / 2, -width / 2),
               (length / 2, width / 2), (-length / 2, width / 2))
    footprint = [(x + dx * cosine - dy * sine, y + dx * sine + dy * cosine)
                 for dx, dy in corners]
    return [(px, py, level) for level in (0.0, height) for px, py in footprint]


_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
          (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def generate_concept_model(source: Path, output_dir: Path, bounds: tuple[float, float, float, float],
                           *, wall_height=3.0, wall_width=0.16, design_spec: Path | None = None, source_units=None):
    """Build an OBJ mesh and PNG preview for one bounded drawing region.

    Bounds and output coordinates are metres. Source units must be declared when
    not metres. Configured wall layers supply linework. Furniture and sanitary
    fixture blocks become generic boxes; no room purpose is inferred.
    """
    import ezdxf
    from PIL import Image, ImageDraw

    source, output_dir = Path(source), Path(output_dir)
    from .config import config_manager
    from .cad_validation import select_walls, contained, unit_factor
    policy = config_manager.specialist_policy
    if source.suffix.casefold() != ".dxf" or not source.is_file() or source.is_symlink():
        raise ValueError("A local DXF working copy is required")
    if source.stat().st_size > policy.cad_max_bytes:
        raise ValueError("Drawing exceeds the configured file limit")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if len(bounds) != 4 or not all(type(v) in (int, float) and math.isfinite(v) for v in bounds):
        raise ValueError("Bounds must have four finite coordinates")
    xmin, ymin, xmax, ymax = bounds
    if xmin >= xmax or ymin >= ymax or xmax - xmin > 500 or ymax - ymin > 500:
        raise ValueError("Select one drawing area no larger than 500 by 500 metres")
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (wall_height, wall_width)) or not 2 <= wall_height <= 6 or not 0.05 <= wall_width <= 0.5:
        raise ValueError("Concept wall height or width is outside safe ranges")
    drawing = ezdxf.readfile(source)
    factor = unit_factor(drawing, source_units)
    segments, geometry_checks = select_walls(drawing, bounds, policy, source_units=source_units)

    origin = (min(v[0] for pair in segments for v in pair),
              min(v[1] for pair in segments for v in pair))
    boxes = []
    for start, end in segments:
        local_start = (start[0] - origin[0], start[1] - origin[1])
        local_end = (end[0] - origin[0], end[1] - origin[1])
        vertices = _box_between(local_start, local_end, wall_width, wall_height)
        if vertices:
            boxes.append(("walls", vertices))

    furniture = 0
    fixtures = 0
    fixture_sizes = {
        "WC": (0.7, 0.5, 0.6),
        "WB": (0.7, 0.5, 0.8),
        "SHOWER": (0.9, 0.9, 0.08),
        "TUB-1": (1.7, 0.8, 0.5),
    }
    for entity in drawing.modelspace().query("INSERT"):
        x, y = entity.dxf.insert.x*factor, entity.dxf.insert.y*factor
        if not all(math.isfinite(v) for v in entity.dxf.insert):
            raise ValueError("Drawing inserts must have finite coordinates")
        if not (xmin <= x <= xmax and ymin <= y <= ymax):
            continue
        if entity.dxf.layer != 'FURNITER' and not (entity.dxf.layer == 'FIXTURE' and entity.dxf.name.upper() in fixture_sizes):
            continue
        rotation = entity.dxf.rotation
        if (not math.isfinite(rotation) or abs(entity.dxf.insert.z*factor) > 1e-6
                or tuple(entity.dxf.extrusion) != (0.0, 0.0, 1.0)
                or any(not math.isfinite(v) or v <= 0 for v in (entity.dxf.xscale, entity.dxf.yscale, entity.dxf.zscale))):
            raise ValueError("Selected insert needs finite planar positive-scale transforms")
        geometry_checks.setdefault('insert_transforms', []).append({'handle': entity.dxf.handle,
            'layer': entity.dxf.layer, 'block': entity.dxf.name, 'rotation_deg': rotation,
            'source_scale': [entity.dxf.xscale, entity.dxf.yscale, entity.dxf.zscale],
            'proxy_dimensions': 'assumed_metres_not_block_geometry'})
        if entity.dxf.layer == "FURNITER":
            vertices = _box_at(x - origin[0], y - origin[1], 1.2, 0.8, 0.7, rotation)
            if not contained(vertices, origin, bounds):
                geometry_checks.setdefault("proxy_warnings", []).append("Furniture proxy omitted at region boundary")
                continue
            boxes.append(("furniture_proxies", vertices))
            furniture += 1
        elif entity.dxf.layer == "FIXTURE" and entity.dxf.name.upper() in fixture_sizes:
            vertices = _box_at(x - origin[0], y - origin[1], *fixture_sizes[entity.dxf.name.upper()], rotation)
            if not contained(vertices, origin, bounds):
                geometry_checks.setdefault("proxy_warnings", []).append("Fixture proxy omitted at region boundary")
                continue
            boxes.append(("fixture_proxies", vertices))
            fixtures += 1

    suggestions = []
    suggestion_sizes = {
        "bed": (2.0, 1.6, 0.55),
        "sofa": (2.0, 0.85, 0.75),
        "tv": (1.3, 0.2, 1.1),
        "planter": (0.75, 0.75, 1.0),
    }
    if design_spec is not None:
        if Path(design_spec).is_symlink() or not Path(design_spec).is_file() or Path(design_spec).stat().st_size > 100000:
            raise ValueError("Design specification must be a regular file within 100 KB")
        specification = json.loads(Path(design_spec).read_text(encoding="utf-8"))
        placements = specification.get("placements") if isinstance(specification, dict) else None
        if not isinstance(placements, list) or len(placements) > 100 or set(specification) != {"placements"}:
            raise ValueError("Design spec needs a placements list with at most 100 items")
        for item in placements:
            if not isinstance(item, dict) or item.get("kind") not in suggestion_sizes or set(item) - {"kind", "x", "y", "rotation_deg"}:
                raise ValueError("Unsupported design suggestion")
            kind = item["kind"]
            x, y = item.get("x"), item.get("y")
            rotation = item.get("rotation_deg", 0)
            if not all(type(value) in (int, float) and math.isfinite(value)
                       for value in (x, y, rotation)):
                raise ValueError("Design suggestion needs finite coordinates and rotation")
            if not (xmin <= x <= xmax and ymin <= y <= ymax):
                raise ValueError("Design suggestion is outside the selected plan area")
            vertices = _box_at(x - origin[0], y - origin[1], *suggestion_sizes[kind], rotation)
            if not contained(vertices, origin, bounds):
                raise ValueError("Design suggestion footprint is outside the selected plan area")
            boxes.append((f"suggested_{kind}", vertices))
            suggestions.append({"kind": kind, "x": x, "y": y, "rotation_deg": rotation})

    if any(not all(math.isfinite(v) for vertex in vertices for v in vertex) for _, vertices in boxes):
        raise ValueError("Concept mesh contains non-finite vertices")
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError("Drawing changed during local interpretation")
    output_dir.mkdir(parents=True, exist_ok=True)
    obj_path = output_dir / "building-concept.obj"
    mtl_path = output_dir / "building-concept.mtl"
    preview_path = output_dir / "building-concept.png"
    manifest_path = output_dir / "building-concept.json"
    if any(path.exists() for path in (obj_path, mtl_path, preview_path, manifest_path)):
        raise FileExistsError("Concept output already exists; choose a fresh output directory")

    with mtl_path.open("w", encoding="utf-8", newline="\n") as target:
        target.write("newmtl walls\nKd 0.76 0.79 0.82\n"
                     "newmtl furniture_proxies\nKd 0.34 0.58 0.45\n"
                     "newmtl fixture_proxies\nKd 0.65 0.78 0.87\n"
                     "newmtl suggested_bed\nKd 0.77 0.59 0.81\n"
                     "newmtl suggested_sofa\nKd 0.84 0.62 0.42\n"
                     "newmtl suggested_tv\nKd 0.18 0.20 0.25\n"
                     "newmtl suggested_planter\nKd 0.23 0.57 0.34\n")
    with obj_path.open("w", encoding="utf-8", newline="\n") as target:
        target.write("# Concept mesh from configured wall linework; not construction accurate\n"
                     "mtllib building-concept.mtl\n")
        vertex_index = 1
        for material, vertices in boxes:
            target.write(f"usemtl {material}\n")
            for x, y, z in vertices:
                target.write(f"v {x:.5f} {y:.5f} {z:.5f}\n")
            for face in _FACES:
                target.write("f " + " ".join(str(vertex_index + i) for i in face) + "\n")
            vertex_index += 8

    # Cut walls down only in the preview so furniture remains visible.
    # The exported OBJ retains its full assumed wall height.
    preview_boxes = [
        (material, [(x, y, min(z, 1.1)) if material == "walls" else (x, y, z)
                    for x, y, z in vertices])
        for material, vertices in boxes
    ]

    def project(vertex):
        x, y, z = vertex
        return ((x - y) * 0.7071, (x + y) * 0.4082 - z * 0.8165)

    projected = [project(vertex) for _, vertices in preview_boxes for vertex in vertices]
    umin, umax = min(p[0] for p in projected), max(p[0] for p in projected)
    vmin, vmax = min(p[1] for p in projected), max(p[1] for p in projected)
    scale = min(1400 / max(umax - umin, 1), 790 / max(vmax - vmin, 1))

    def screen(vertex):
        u, v = project(vertex)
        return (100 + (u - umin) * scale, 965 - (v - vmin) * scale)

    image = Image.new("RGB", (1600, 1050), "#f8fafc")
    draw = ImageDraw.Draw(image)
    faces = []
    for material, vertices in preview_boxes:
        for face in _FACES[1:]:
            corners = [vertices[i] for i in face]
            depth = sum(x + y + z for x, y, z in corners) / 4
            faces.append((depth, material, face == _FACES[1], [screen(v) for v in corners]))
    for _, material, top, corners in sorted(faces):
        palette = {
            "walls": ("#c6cdd4", "#a8b4be"),
            "furniture_proxies": ("#78a98c", "#5f8c73"),
            "fixture_proxies": ("#b9dbe9", "#88b5c8"),
            "suggested_bed": ("#c9a1d2", "#a578ae"),
            "suggested_sofa": ("#e2ad7e", "#c88957"),
            "suggested_tv": ("#3e4652", "#242b35"),
            "suggested_planter": ("#62a972", "#3e8450"),
        }
        fill = palette[material][0 if top else 1]
        draw.polygon(corners, fill=fill, outline="#41505d")
    draw.text((30, 20), "CONCEPT MODEL - ONE PLAN AREA", fill="#17212b")
    draw.text((30, 40), f"Walls cut to 1.1 m in preview; OBJ walls {wall_height:.1f} m; colors are suggestions",
              fill="#334155")
    image.save(preview_path)

    manifest = {
        "source": source.name,
        "source_sha256": source_hash,
        "geometry_checks": geometry_checks,
        "mesh_checks": {"finite_vertices": True, "vertices": len(boxes) * 8, "faces": len(boxes) * 6,
                        "face_indices": "generated_within_vertex_bounds"},
        "bounds": list(bounds),
        "units": "metres",
        "wall_segments": len(segments),
        "furniture_proxies": furniture,
        "fixture_proxies": fixtures,
        "design_suggestions": suggestions,
        "assumptions": ["One selected drawing region only", "Configured wall linework extruded at assumed height",
                        "Generic furniture and fixture proxies, not verified products or room assignments",
                        "Suggested beds, sofas, TVs, and planters are conceptual placements requiring human review",
                        "Not a BIM, structural, permit, or construction model"],
        "files": [path.name for path in (obj_path, mtl_path, preview_path)],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    if obj_path.stat().st_size == 0 or preview_path.stat().st_size == 0:
        raise RuntimeError("Concept model export failed verification")
    return manifest | {"obj_path": obj_path, "preview_path": preview_path,
                       "manifest_path": manifest_path}

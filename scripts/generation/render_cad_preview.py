"""Render a local DXF crop for drawing inspection; no external service is used."""

import argparse
from pathlib import Path

import ezdxf
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("drawing", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bounds", nargs=4, type=float, required=True,
                        metavar=("X_MIN", "Y_MIN", "X_MAX", "Y_MAX"))
    options = parser.parse_args()
    xmin, ymin, xmax, ymax = options.bounds
    if xmin >= xmax or ymin >= ymax:
        parser.error("Invalid bounds")
    document = ezdxf.readfile(options.drawing)
    image = Image.new("RGB", (1600, 1000), "white")
    canvas = ImageDraw.Draw(image)
    scale = min(1550 / (xmax - xmin), 950 / (ymax - ymin))

    def point(x, y):
        return (25 + (x - xmin) * scale, 975 - (y - ymin) * scale)

    colors = {"A-WALL": "#222222", "A-DOOR": "#c55a11", "WINDOW": "#0066aa",
              "STAIR": "#5555aa", "FURNITER": "#329460", "FURN": "#329460"}
    for entity in document.modelspace():
        color = colors.get(entity.dxf.layer)
        if color is None:
            continue
        if entity.dxftype() == "LINE":
            start, end = entity.dxf.start, entity.dxf.end
            if not (min(start.x, end.x) <= xmax and max(start.x, end.x) >= xmin and
                    min(start.y, end.y) <= ymax and max(start.y, end.y) >= ymin):
                continue
            canvas.line((point(start.x, start.y), point(end.x, end.y)), fill=color, width=2)
        elif entity.dxftype() == "LWPOLYLINE":
            points = [point(x, y) for x, y, *_ in entity.get_points()]
            if len(points) >= 2:
                canvas.line(points + ([points[0]] if entity.closed else []), fill=color, width=2)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(options.output)


if __name__ == "__main__":
    main()

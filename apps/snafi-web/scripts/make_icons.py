"""Draw Snafi's placeholder gold-orb icons as PNGs (needs Pillow, already in REEMA's .venv).

Run from the repository root:
    .venv/Scripts/python.exe apps/snafi-web/scripts/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "public" / "icons"
BG = (14, 14, 16, 255)
STOPS = [(0.0, (240, 221, 176)), (0.55, (201, 169, 110)), (1.0, (122, 92, 36))]


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def colour(t):
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return STOPS[-1][1]


def icon(size, orb_ratio):
    img = Image.new("RGBA", (size, size), BG)
    centre, radius = size / 2, size * orb_ratio / 2
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [centre - radius * 1.45, centre - radius * 1.45, centre + radius * 1.45, centre + radius * 1.45],
        fill=(201, 169, 110, 70),
    )
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(size * 0.06)))
    hx, hy = centre - radius * 0.3, centre - radius * 0.35
    orb = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = orb.load()
    for y in range(size):
        for x in range(size):
            if (x - centre) ** 2 + (y - centre) ** 2 <= radius ** 2:
                d = (((x - hx) ** 2 + (y - hy) ** 2) ** 0.5) / (radius * 1.35)
                px[x, y] = (*colour(min(1.0, d)), 255)
    img.alpha_composite(orb)
    return img.convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    icon(192, 0.5).save(OUT / "icon-192.png")
    icon(512, 0.5).save(OUT / "icon-512.png")
    icon(512, 0.36).save(OUT / "icon-maskable-512.png")  # inside the maskable safe zone
    icon(180, 0.52).save(OUT / "apple-touch-icon.png")
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()

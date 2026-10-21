"""Generate a clean LG-style face mark PNG for the sidebar."""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

SIZE = 256
OUT = os.path.join(
    os.path.dirname(__file__),
    "..",
    "src",
    "assets",
    "lg-mark.png",
)


def main() -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, SIZE - 1, SIZE - 1), fill=(165, 0, 52, 255))

    def xy(x: float, y: float) -> tuple[float, float]:
        return x / 100 * SIZE, y / 100 * SIZE

    # L
    d.polygon(
        [xy(22, 22), xy(34, 22), xy(34, 66), xy(52, 66), xy(52, 78), xy(22, 78)],
        fill=(255, 255, 255, 255),
    )

    # G as ring with left mouth cut + stem
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    cx, cy = 62 / 100 * SIZE, 48 / 100 * SIZE
    R, r = 28 / 100 * SIZE, 14 / 100 * SIZE
    md.ellipse((cx - R, cy - R, cx + R, cy + R), fill=255)
    md.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    md.rectangle((cx - R - 2, cy - r * 0.55, cx, cy + r * 0.55), fill=0)
    md.rectangle((cx - 2, cy - r * 0.45, cx + R * 0.2, cy + r * 0.45), fill=255)

    clip = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(clip).rectangle(
        (48 / 100 * SIZE, 18 / 100 * SIZE, 92 / 100 * SIZE, 82 / 100 * SIZE),
        fill=255,
    )
    mask = Image.composite(mask, Image.new("L", (SIZE, SIZE), 0), clip)
    white = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))
    g_layer = Image.composite(white, Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)), mask)
    img = Image.alpha_composite(img, g_layer)

    d = ImageDraw.Draw(img)
    ex, ey, er = 72 / 100 * SIZE, 72 / 100 * SIZE, 6.5 / 100 * SIZE
    d.ellipse((ex - er, ey - er, ex + er, ey + er), fill=(255, 255, 255, 255))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(os.path.abspath(OUT), "PNG")
    print("saved", os.path.abspath(OUT))


if __name__ == "__main__":
    main()

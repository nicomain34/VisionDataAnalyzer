"""Generate Lucide-style PNG icons for ExcelMerger UI."""
from PIL import Image, ImageDraw
import math
import os

OUT = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(OUT, "icons")
os.makedirs(ICONS, exist_ok=True)

W = (245, 245, 247, 255)
BLUE = (10, 132, 255, 255)
WHITE = (255, 255, 255, 255)
MUTE = (161, 161, 170, 255)


def new(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def save(img, name):
    path = os.path.join(ICONS, name + ".png")
    img.save(path)
    print("wrote", name)


def rounded_rect(d, box, radius, outline=W, width=3, fill=None):
    d.rounded_rectangle(box, radius=radius, outline=outline, width=width, fill=fill)


def main():
    img, d = new()
    rounded_rect(d, (8, 22, 56, 52), 6, W, 3)
    d.line([(8, 22), (24, 22), (28, 16), (44, 16), (48, 22), (56, 22)], fill=W, width=3, joint="curve")
    save(img, "folder")

    img, d = new()
    rounded_rect(d, (8, 22, 56, 52), 6, BLUE, 3)
    d.line([(8, 22), (24, 22), (28, 16), (44, 16), (48, 22), (56, 22)], fill=BLUE, width=3, joint="curve")
    save(img, "folder-blue")

    img, d = new()
    d.line([(10, 24), (10, 50), (54, 50), (50, 28), (22, 28), (18, 24), (10, 24)], fill=W, width=3, joint="curve")
    d.line([(10, 24), (22, 24), (26, 18), (40, 18)], fill=W, width=3)
    save(img, "folder-open")

    img, d = new()
    rounded_rect(d, (14, 8, 50, 56), 4, W, 3)
    for y in (22, 34, 46):
        d.line([(14, y), (50, y)], fill=W, width=2)
    for x in (28, 39):
        d.line([(x, 22), (x, 56)], fill=W, width=2)
    save(img, "file-spreadsheet")

    img, d = new()
    rounded_rect(d, (14, 8, 50, 56), 4, BLUE, 3)
    for y in (22, 34, 46):
        d.line([(14, y), (50, y)], fill=BLUE, width=2)
    for x in (28, 39):
        d.line([(x, 22), (x, 56)], fill=BLUE, width=2)
    save(img, "file-spreadsheet-blue")

    img, d = new()
    d.rectangle((12, 36, 22, 52), outline=W, width=3)
    d.rectangle((28, 20, 38, 52), outline=W, width=3)
    d.rectangle((44, 28, 54, 52), outline=W, width=3)
    d.line([(10, 54), (56, 54)], fill=W, width=3)
    save(img, "bar-chart")

    img, d = new()
    d.ellipse((22, 22, 42, 42), outline=W, width=3)
    cx, cy, r1, r2 = 32, 32, 18, 11
    for i in range(8):
        a = i * math.pi / 4
        d.line(
            [
                (cx + r2 * math.cos(a), cy + r2 * math.sin(a)),
                (cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
            ],
            fill=W,
            width=4,
        )
    save(img, "settings")

    img, d = new()
    d.line([(12, 14), (52, 14), (36, 34), (28, 34), (12, 14)], fill=W, width=3, joint="curve")
    d.line([(32, 34), (32, 52)], fill=W, width=3)
    d.line([(28, 52), (36, 52)], fill=W, width=3)
    save(img, "filter")

    img, d = new()
    rounded_rect(d, (10, 14, 54, 54), 6, W, 3)
    d.line([(10, 26), (54, 26)], fill=W, width=3)
    d.line([(22, 10), (22, 20)], fill=W, width=3)
    d.line([(42, 10), (42, 20)], fill=W, width=3)
    for x in (20, 32, 44):
        for y in (34, 44):
            d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=W)
    save(img, "calendar")

    img, d = new()
    d.line([(18, 10), (36, 10), (48, 22), (48, 54), (18, 54), (18, 10)], fill=W, width=3, joint="curve")
    d.line([(36, 10), (36, 22), (48, 22)], fill=W, width=3)
    save(img, "file")

    img, d = new()
    rounded_rect(d, (10, 14, 54, 50), 4, W, 3)
    d.line([(10, 26), (54, 26)], fill=W, width=2)
    d.line([(10, 38), (54, 38)], fill=W, width=2)
    d.line([(26, 14), (26, 50)], fill=W, width=2)
    d.line([(40, 14), (40, 50)], fill=W, width=2)
    save(img, "table")

    img, d = new()
    d.polygon([(22, 12), (22, 52), (50, 32)], fill=WHITE)
    save(img, "play-white")

    img, d = new()
    d.line([(32, 10), (32, 40)], fill=W, width=4)
    d.line([(18, 30), (32, 44), (46, 30)], fill=W, width=4, joint="curve")
    d.line([(14, 50), (50, 50)], fill=W, width=4)
    save(img, "download")

    img, d = new()
    d.ellipse((10, 10, 54, 54), outline=MUTE, width=3)
    d.ellipse((29, 18, 35, 24), fill=MUTE)
    d.rectangle((30, 30, 34, 46), fill=MUTE)
    save(img, "info")

    img, d = new()
    d.line([(18, 18), (46, 46)], fill=MUTE, width=4)
    d.line([(46, 18), (18, 46)], fill=MUTE, width=4)
    save(img, "x")

    img, d = new()
    d.line([(16, 24), (32, 40), (48, 24)], fill=MUTE, width=4, joint="curve")
    save(img, "chevron-down")

    img, d = new()
    d.line([(16, 40), (32, 24), (48, 40)], fill=MUTE, width=4, joint="curve")
    save(img, "chevron-up")

    img, d = new()
    d.ellipse((20, 20, 44, 44), outline=MUTE, width=3)
    d.ellipse((28, 28, 36, 36), fill=MUTE)
    save(img, "status")

    # scroll / log list
    img, d = new()
    rounded_rect(d, (16, 8, 48, 56), 4, W, 3)
    for y in (20, 32, 44):
        d.line([(24, y), (40, y)], fill=MUTE, width=3)
    save(img, "list")

    img, d = new()
    rounded_rect(d, (10, 10, 30, 30), 4, BLUE, 0, fill=BLUE)
    rounded_rect(d, (34, 10, 54, 30), 4, W, 3)
    rounded_rect(d, (10, 34, 30, 54), 4, W, 3)
    rounded_rect(d, (34, 34, 54, 54), 4, BLUE, 0, fill=BLUE)
    save(img, "app")

    ico_path = os.path.join(os.path.dirname(OUT), "excelmerger.ico")
    try:
        ico = Image.open(ico_path).convert("RGBA")
        ico.resize((48, 48), Image.Resampling.LANCZOS).save(os.path.join(ICONS, "logo.png"))
        print("wrote logo")
    except Exception as e:
        print("logo skip", e)
        img, d = new()
        rounded_rect(d, (8, 8, 56, 56), 12, BLUE, 0, fill=BLUE)
        d.polygon([(22, 16), (22, 48), (48, 32)], fill=WHITE)
        save(img, "logo")

    print("done", len(os.listdir(ICONS)))


if __name__ == "__main__":
    main()

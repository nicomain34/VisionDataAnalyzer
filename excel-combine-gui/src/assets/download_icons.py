"""Download Lucide SVGs from GitHub and convert to PNG."""
import os
import re
import urllib.request

from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg
from PIL import Image
import io

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
os.makedirs(ICONS_DIR, exist_ok=True)

BASE = "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{}.svg"

# local_name: (lucide_name, color_hex, size)
ITEMS = {
    "folder": ("folder", "#F5F5F7", 64),
    "folder-blue": ("folder", "#0A84FF", 64),
    "folder-open": ("folder-open", "#F5F5F7", 64),
    "file-spreadsheet": ("file-spreadsheet", "#F5F5F7", 64),
    "file-spreadsheet-blue": ("file-spreadsheet", "#0A84FF", 64),
    "bar-chart": ("chart-column", "#F5F5F7", 64),
    "settings": ("settings", "#F5F5F7", 64),
    "filter": ("funnel", "#F5F5F7", 64),
    "calendar": ("calendar", "#F5F5F7", 64),
    "file": ("file", "#F5F5F7", 64),
    "table": ("table", "#F5F5F7", 64),
    "play-white": ("play", "#FFFFFF", 64),
    "download": ("download", "#F5F5F7", 64),
    "info": ("info", "#A1A1AA", 64),
    "x": ("x", "#A1A1AA", 64),
    "chevron-down": ("chevron-down", "#A1A1AA", 64),
    "chevron-up": ("chevron-up", "#A1A1AA", 64),
    "status": ("circle-dot", "#A1A1AA", 64),
    "app": ("combine", "#F5F5F7", 64),
}


def fetch_svg(name: str) -> str:
    url = BASE.format(name)
    with urllib.request.urlopen(url, timeout=20) as resp:
        return resp.read().decode("utf-8")


def colorize(svg: str, color: str) -> str:
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    svg = svg.replace('fill="currentColor"', f'fill="{color}"')
    # ensure transparent background
    if "fill=\"none\"" not in svg[:200]:
        pass
    return svg


def svg_to_png(svg_text: str, out_path: str, size: int = 64):
    tmp = out_path + ".svg"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(svg_text)
    drawing = svg2rlg(tmp)
    if drawing is None:
        raise RuntimeError("svg2rlg failed for " + out_path)
    scale = size / max(drawing.width, drawing.height, 1)
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    renderPM.drawToFile(drawing, out_path, fmt="PNG", dpi=144)
    # ensure RGBA size
    im = Image.open(out_path).convert("RGBA")
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    im.save(out_path)
    try:
        os.remove(tmp)
    except OSError:
        pass


def main():
    for local, (lucide, color, size) in ITEMS.items():
        try:
            svg = fetch_svg(lucide)
            svg = colorize(svg, color)
            out = os.path.join(ICONS_DIR, f"{local}.png")
            svg_to_png(svg, out, size)
            print("ok", local, "<-", lucide)
        except Exception as e:
            print("FAIL", local, e)

    # logo from ico
    ico = os.path.join(os.path.dirname(os.path.dirname(__file__)), "excelmerger.ico")
    # assets is under src/assets, ico is src/excelmerger.ico
    ico = os.path.join(os.path.dirname(ICONS_DIR), "..", "excelmerger.ico")
    ico = os.path.normpath(ico)
    try:
        Image.open(ico).convert("RGBA").resize((48, 48), Image.Resampling.LANCZOS).save(
            os.path.join(ICONS_DIR, "logo.png")
        )
        print("ok logo")
    except Exception as e:
        print("logo fail", e)


if __name__ == "__main__":
    main()

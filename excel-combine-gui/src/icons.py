"""Load and cache UI icons for ExcelMerger."""
import os
from PIL import Image, ImageTk

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")
_CACHE = {}


def icon_path(name: str) -> str:
    return os.path.join(_DIR, f"{name}.png")


def get_icon(name: str, size: int = 18):
    """Return a PhotoImage for the named icon, resized to size x size."""
    key = (name, size)
    if key in _CACHE:
        return _CACHE[key]
    path = icon_path(name)
    if not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGBA")
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(img)
    _CACHE[key] = photo
    return photo

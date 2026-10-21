"""Color de acento a partir del fondo del usuario.

GNOME sólo admite nueve acentos con nombre; se elige el más cercano al color
dominante (el más frecuente con saturación suficiente).
"""

import colorsys
from pathlib import Path

from PIL import Image

ACCENTS = [
    (345, 360, "red"), (0, 15, "red"), (15, 45, "orange"), (45, 70, "yellow"),
    (70, 160, "green"), (160, 195, "teal"), (195, 250, "blue"),
    (250, 290, "purple"), (290, 345, "pink"),
]


def dominant_rgb(path: Path) -> tuple[int, int, int]:
    image = Image.open(path).convert("RGB")
    image.thumbnail((160, 160))
    colors = image.quantize(colors=12).convert("RGB").getcolors(maxcolors=100000)
    best, best_score = (128, 128, 128), -1.0
    for count, rgb in colors:
        _, _, s = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        score = count * (0.2 + s)
        if score > best_score:
            best, best_score = rgb, score
    return best


def accent_name(rgb: tuple[int, int, int]) -> str:
    h, s, _ = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    if s < 0.15:
        return "slate"
    degrees = h * 360
    for low, high, name in ACCENTS:
        if low <= degrees < high:
            return name
    return "blue"


def accent_for_wallpaper(path: Path) -> str:
    return accent_name(dominant_rgb(path))



def accent_label(name: str) -> str:
    """Nombre del acento para mostrar al usuario, en su idioma."""
    from .i18n import _

    return _(name)

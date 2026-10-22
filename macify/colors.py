"""Color de acento a partir del fondo del usuario.

GNOME sólo admite nueve acentos con nombre; se elige el más cercano al color
dominante (el más frecuente con saturación suficiente).
"""

import colorsys
import functools
from pathlib import Path

from PIL import Image, ImageStat

ACCENTS = [
    (345, 360, "red"), (0, 15, "red"), (15, 45, "orange"), (45, 70, "yellow"),
    (70, 160, "green"), (160, 195, "teal"), (195, 250, "blue"),
    (250, 290, "purple"), (290, 345, "pink"),
]


def dominant_rgb(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return _dominant_rgb(str(path), stat.st_size, stat.st_mtime_ns)


@functools.lru_cache(maxsize=64)
def _dominant_rgb(path: str, _size: int, _mtime: int) -> tuple[int, int, int]:
    """El color con más presencia (y saturación); size y mtime invalidan la caché."""
    with Image.open(path) as source:
        source.draft("RGB", (320, 320))          # JPEG: se decodifica ya reducido, no en 4K
        image = source.convert("RGB")
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


def glass_tint(path: Path, dark: bool) -> tuple[float, float, float, float]:
    """Cristal del dock: claro u oscuro según el aspecto, con un toque del color del fondo."""
    base, amount = ((0.12, 0.12, 0.14), 0.18) if dark else ((1.0, 1.0, 1.0), 0.12)
    tint = tuple(round(c * (1 - amount) + v / 255 * amount, 3) for c, v in zip(base, dominant_rgb(path)))
    return (*tint, 0.35)


def top_brightness(path: Path) -> float:
    """Brillo (0–1) de la franja de arriba, donde va la barra de menús."""
    stat = path.stat()
    return _top_brightness(str(path), stat.st_size, stat.st_mtime_ns)


@functools.lru_cache(maxsize=16)
def _top_brightness(path: str, _size: int, _mtime: int) -> float:
    with Image.open(path) as source:
        source.draft("RGB", (640, 640))
        image = source.convert("L")
    strip = image.crop((0, 0, image.width, max(1, image.height // 25)))
    return ImageStat.Stat(strip).mean[0] / 255



def accent_label(name: str) -> str:
    """Nombre del acento para mostrar al usuario, en su idioma."""
    from .i18n import _

    return _(name)

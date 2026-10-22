"""Catálogo de fondos de pantalla, por secciones, como Ajustes › Fondo de pantalla en macOS.

Los fondos incluidos son originales de Macify (scripts/make_wallpapers.py). Las miniaturas
se guardan en la caché: la galería no abre las imágenes 4K cada vez.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .assets import CACHE_DIR, WALLPAPER_DIR, assets_root, load_config
from .i18n import _

THUMB_DIR = CACHE_DIR / "thumbnails"
THUMB_SIZE = (320, 180)
PHOTO_TYPES = (".jpg", ".jpeg", ".png", ".webp")

# archivo: (nombre, sección)
CATALOG = {
    "sand.jpg": ("Sand", "Ribbons"), "lilac.jpg": ("Lilac", "Ribbons"), "coral.jpg": ("Coral", "Ribbons"),
    "meadow.jpg": ("Meadow", "Ribbons"), "lagoon.jpg": ("Lagoon", "Ribbons"), "ember.jpg": ("Ember", "Ribbons"),
    "night.jpg": ("Night", "Ribbons"), "graphite.jpg": ("Graphite", "Ribbons"),
    "dawn.jpg": ("Dawn", "Gradients"), "blue.jpg": ("Blue", "Gradients"), "dusk.jpg": ("Dusk", "Gradients"),
}
SECTIONS = ["Ribbons", "Gradients", "Your Folder", "Your Photos"]


@dataclass(frozen=True)
class Wallpaper:
    path: Path
    title: str
    section: str


def _fingerprint(path: Path) -> str:
    """Huella rápida para no repetir fondos: tamaño y el primer trozo del archivo."""
    with path.open("rb") as file:
        head = file.read(65536)
    return f"{path.stat().st_size}:{hashlib.sha1(head).hexdigest()}"


def _photos(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_TYPES) if folder.is_dir() else []


def catalog() -> list[Wallpaper]:
    """Los fondos incluidos, los de la carpeta del proyecto y las fotos que agregó la persona."""
    found = []
    for path in _photos(WALLPAPER_DIR):
        title, section = CATALOG.get(path.name, (path.stem.replace("-", " ").title(), "Gradients"))
        found.append(Wallpaper(path, _(title), section))
    root = assets_root()
    if root:
        found += [Wallpaper(p, p.stem.replace("-", " ").title(), "Your Folder") for p in _photos(root / "wallpapers")]
    found += [Wallpaper(Path(p), Path(p).stem, "Your Photos")
              for p in load_config().get("user_wallpapers", []) if Path(p).is_file()]
    unique, seen = [], set()
    for wallpaper in found:
        key = _fingerprint(wallpaper.path)
        if key not in seen:
            seen.add(key)
            unique.append(wallpaper)
    order = {CATALOG[name][0]: i for i, name in enumerate(CATALOG)}
    return sorted(unique, key=lambda w: (SECTIONS.index(w.section), order.get(w.title, len(order)), w.title))


def thumbnail(path: Path) -> Path:
    """Miniatura 16:9 en la caché; se rehace si la imagen cambia."""
    stat = path.stat()
    key = hashlib.sha1(f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()[:16]
    target = THUMB_DIR / f"{key}.jpg"
    if not target.exists():
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as image:
            image.draft("RGB", (THUMB_SIZE[0] * 2, THUMB_SIZE[1] * 2))   # JPEG: decodifica ya reducida
            image = image.convert("RGB")
            ratio = max(THUMB_SIZE[0] / image.width, THUMB_SIZE[1] / image.height)
            image = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
            left, top = (image.width - THUMB_SIZE[0]) // 2, (image.height - THUMB_SIZE[1]) // 2
            image.crop((left, top, left + THUMB_SIZE[0], top + THUMB_SIZE[1])).save(target, "JPEG", quality=88)
    return target

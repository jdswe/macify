"""Catálogo de fondos de pantalla, por secciones, como Ajustes › Fondo de pantalla en macOS.

Los fondos incluidos son originales de Macify (scripts/make_wallpapers.py), cada uno con su
versión oscura («nombre-dark.jpg»), que se usa sola con el aspecto oscuro. La carpeta propia
de la persona puede tener subcarpetas: cada una es una sección de la galería. Las
miniaturas se guardan en la caché: la galería no abre las imágenes grandes cada vez.
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

MACIFY = "Macify"
# archivo: (nombre, sección)
CATALOG = {
    "lilac.jpg": ("Lilac", MACIFY), "sand.jpg": ("Sand", MACIFY), "coral.jpg": ("Coral", MACIFY),
    "meadow.jpg": ("Meadow", MACIFY), "lagoon.jpg": ("Lagoon", MACIFY), "ember.jpg": ("Ember", MACIFY),
    "night.jpg": ("Night", MACIFY), "graphite.jpg": ("Graphite", MACIFY),
    "dawn.jpg": ("Dawn", "Gradients"), "blue.jpg": ("Blue", "Gradients"), "dusk.jpg": ("Dusk", "Gradients"),
}
FIRST = [MACIFY, "Gradients"]
LAST = ["Your Folder", "Your Photos"]


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


def is_dark_twin(path: Path) -> bool:
    """«nombre-dark.jpg» con «nombre.jpg» al lado: no es un fondo aparte, es su versión oscura."""
    return path.stem.endswith("-dark") and path.with_name(path.stem[:-5] + path.suffix).is_file()


def _photos(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in PHOTO_TYPES and not is_dark_twin(p))


def title(path: Path) -> str:
    words = path.stem.replace("_", " ").replace("-", " ").split()
    return " ".join("macOS" if w.lower() == "macos" else w[:1].upper() + w[1:] for w in words)


def catalog() -> list[Wallpaper]:
    """Los fondos incluidos, los de la carpeta propia (y sus subcarpetas) y las fotos agregadas."""
    found = []
    for path in _photos(WALLPAPER_DIR):
        name, section = CATALOG.get(path.name, (title(path), "Gradients"))
        found.append(Wallpaper(path, _(name), section))
    root = assets_root()
    if root:
        folder = root / "wallpapers"
        found += [Wallpaper(p, title(p), "Your Folder") for p in _photos(folder)]
        if folder.is_dir():
            for sub in sorted(d for d in folder.iterdir() if d.is_dir() and not d.name.startswith(".")):
                found += [Wallpaper(p, title(p), sub.name) for p in _photos(sub)]
    found += [Wallpaper(Path(p), title(Path(p)), "Your Photos")
              for p in load_config().get("user_wallpapers", []) if Path(p).is_file()]
    unique, seen = [], set()
    for wallpaper in found:
        key = _fingerprint(wallpaper.path)
        if key not in seen:
            seen.add(key)
            unique.append(wallpaper)
    order = sections(unique)
    known = {CATALOG[name][0]: i for i, name in enumerate(CATALOG)}
    return sorted(unique, key=lambda w: (order.index(w.section), known.get(w.title, len(known)), w.title))


def sections(items: list[Wallpaper]) -> list[str]:
    """Macify y Degradados primero; luego las carpetas propias por nombre; al final lo suelto."""
    present = {w.section for w in items}
    folders = sorted(present - set(FIRST) - set(LAST), key=str.casefold)
    return [s for s in FIRST if s in present] + folders + [s for s in LAST if s in present]


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

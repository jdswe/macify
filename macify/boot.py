"""Pantallas del sistema: arranque (Plymouth) e inicio de sesión (GDM).

Son del sistema, no del usuario, así que se aplican con un único ayudante de
administrador (data/root/macify-root.sh) lanzado con pkexec: una sola contraseña.
"""

import io
import shutil
import subprocess
from importlib import resources
from pathlib import Path

from PIL import Image, ImageDraw

from . import extensions, themes
from .assets import CACHE_DIR, load_config, save_config_value
from .i18n import _

BUILD_DIR = CACHE_DIR / "plymouth"
LOGO_SIZE = 112
BAR_SIZE = (220, 6)


def _helper() -> Path:
    """El ayudante: el del paquete instalado (carpeta de root) o una copia en la caché."""
    packaged = Path(str(resources.files("macify").joinpath("data", "root", "macify-root.sh")))
    if packaged.is_file() and str(packaged).startswith("/usr/"):
        return packaged
    copy = CACHE_DIR / "macify-root.sh"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(resources.files("macify").joinpath("data", "root", "macify-root.sh").read_bytes())
    copy.chmod(0o755)
    return copy


def _logo() -> Image.Image:
    import gi

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    svg = BUILD_DIR / "logo.svg"
    svg.write_text(extensions.menubar_logo_svg())
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(svg), LOGO_SIZE, LOGO_SIZE, True)
    svg.unlink()
    ok, data = pixbuf.save_to_bufferv("png", [], [])
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _bar(color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", BAR_SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, BAR_SIZE[0] - 1, BAR_SIZE[1] - 1), BAR_SIZE[1] // 2, fill=color)
    return image


def build_theme() -> Path:
    """Prepara en la caché los archivos del tema de arranque Macify."""
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    BUILD_DIR.mkdir(parents=True)
    for item in resources.files("macify").joinpath("data", "plymouth").iterdir():
        (BUILD_DIR / item.name).write_bytes(item.read_bytes())
    _logo().save(BUILD_DIR / "logo.png")
    _bar((255, 255, 255, 64)).save(BUILD_DIR / "bar-background.png")
    _bar((255, 255, 255, 255)).save(BUILD_DIR / "bar-fill.png")
    return BUILD_DIR


def _run(arguments: list[str], log) -> None:
    process = subprocess.Popen(["pkexec", str(_helper()), *arguments], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        if line.strip():
            log(line.rstrip())
    if process.wait() != 0:
        raise RuntimeError(_("The startup and login screens could not be applied (cancelled or error)."))


def apply(wallpaper: Path, dry_run: bool, log) -> None:
    log(_("Startup and login screens: one administrator password"))
    if dry_run:
        return
    theme = build_theme()
    whitesur = themes.fetch("gtk", log)
    _run(["apply", str(theme), str(whitesur), str(wallpaper)], log)
    save_config_value("system_screens", True)


def revert(dry_run: bool, log) -> None:
    if not load_config().get("system_screens"):
        return
    log(_("Startup and login screens: back to the original"))
    if dry_run:
        return
    whitesur = themes.repo_dir("gtk")
    _run(["revert", str(whitesur) if whitesur.exists() else ""], log)
    save_config_value("system_screens", False)

"""Pantallas del sistema: arranque (Plymouth) e inicio de sesión (GDM).

Son del sistema, no del usuario, así que se aplican con un único ayudante de
administrador (data/root/macify-root.sh) lanzado con pkexec: una sola contraseña.
"""

import io
import json
import re
import shutil
import statistics
import subprocess
from importlib import resources
from pathlib import Path

from PIL import Image, ImageDraw

from . import extensions
from .assets import CACHE_DIR, load_config, save_config_value
from .i18n import _

BUILD_DIR = CACHE_DIR / "plymouth"
LOGO_SIZE = 112
BAR_SIZE = (220, 6)
SCRIPT = "macify.script"
DEFAULT_SHUTDOWN_SECONDS = 4.0
# Líneas del script que Macify ajusta a cada equipo e idioma (ver macify.script).
_CONFIG_LINE = re.compile(r'^config\.(shutdown_seconds|welcome|goodbye) = .*;$', re.MULTILINE)


def _helper() -> Path:
    """El ayudante del paquete instalado. Por seguridad, nunca uno de una carpeta del usuario."""
    packaged = Path(str(resources.files("macify").joinpath("data", "root", "macify-root.sh")))
    if packaged.is_file() and str(packaged).startswith("/usr/") and packaged.stat().st_uid == 0:
        return packaged
    raise RuntimeError(_("Startup and login screens need Macify installed from the .deb package."))


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


def shutdown_seconds() -> float:
    """Lo que tarda este equipo en apagarse: desde la pantalla de apagado hasta el
    último mensaje del registro, mediana de los últimos apagados."""
    try:
        boots = json.loads(subprocess.run(["journalctl", "--list-boots", "-o", "json", "--no-pager"],
                                          capture_output=True, text=True, timeout=10).stdout)
        last_entry = {b["boot_id"]: b["last_entry"] for b in boots}
        lines = subprocess.run(["journalctl", "-o", "json", "--no-pager", "--output-fields=_BOOT_ID",
                                "-u", "plymouth-poweroff.service", "-u", "plymouth-reboot.service",
                                "-u", "plymouth-halt.service"],
                               capture_output=True, text=True, timeout=10).stdout.splitlines()
    except (OSError, ValueError, subprocess.SubprocessError):
        return DEFAULT_SHUTDOWN_SECONDS
    started = {}
    for line in lines:
        entry = json.loads(line)
        started.setdefault(entry["_BOOT_ID"], int(entry["__REALTIME_TIMESTAMP"]))
    durations = [(last_entry[boot] - start) / 1e6 for boot, start in started.items() if boot in last_entry]
    durations = [d for d in durations if 0 < d < 60][-5:]
    if not durations:
        return DEFAULT_SHUTDOWN_SECONDS
    return round(min(max(statistics.median(durations), 2.5), 12.0), 1)


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "").replace('"', "") + '"'


def script_text(seconds: float | None = None) -> str:
    """El script de arranque con el tiempo de apagado de este equipo y los textos en su idioma."""
    text = resources.files("macify").joinpath("data", "plymouth", SCRIPT).read_text()
    values = {"shutdown_seconds": str(seconds or shutdown_seconds()),
              "welcome": _quote(_("Welcome")), "goodbye": _quote(_("See you soon"))}
    return _CONFIG_LINE.sub(lambda m: f"config.{m[1]} = {values[m[1]]};", text)


def same_script(installed: str, packaged: str) -> bool:
    """Compara scripts sin contar los valores propios de cada equipo."""
    return _CONFIG_LINE.sub("", installed) == _CONFIG_LINE.sub("", packaged)


def build_theme() -> Path:
    """Prepara en la caché los archivos del tema de arranque Macify."""
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    BUILD_DIR.mkdir(parents=True)
    for item in resources.files("macify").joinpath("data", "plymouth").iterdir():
        (BUILD_DIR / item.name).write_bytes(item.read_bytes())
    (BUILD_DIR / SCRIPT).write_text(script_text())
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
    _run(["apply", str(theme), str(wallpaper)], log)
    save_config_value("system_screens", True)


def revert(dry_run: bool, log) -> None:
    if not load_config().get("system_screens"):
        return
    log(_("Startup and login screens: back to the original"))
    if dry_run:
        return
    _run(["revert"], log)
    save_config_value("system_screens", False)

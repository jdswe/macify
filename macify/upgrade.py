"""Actualizar sin reinstalar: después de instalar una versión nueva de Macify, sólo se aplica
lo que cambió y se limpia lo viejo.

- Lo que la versión nueva fija distinto (temas en otra versión, extensiones, iconos, el
  inicio automático) lo encuentra la revisión de «Buscar problemas» y se arregla sólo eso.
- Los ajustes se vuelven a aplicar con las elecciones guardadas (sin descargas): así llegan
  los ajustes nuevos de cada versión.
- Se borra lo que ya no sirve: los paquetes descargados, copias de fondos que no se usan,
  miniaturas viejas y restos de versiones anteriores.

Lo corren el instalador y «Actualización de software» justo después de instalar, y el
inicio de sesión si la versión cambió por otro camino (por ejemplo, apt).
"""

import shutil
import time
from pathlib import Path

from . import __version__, doctor, extensions, icons, installer, profile, system, wallpapers
from .assets import CACHE_DIR, busy, load_config, save_config_value
from .i18n import _

THUMBNAIL_MAX_AGE = 60 * 24 * 3600          # miniaturas sin usar en dos meses
# Restos de versiones anteriores que ya no se usan (el ayudante de root sólo se usa desde /usr).
LEFTOVERS = ["debug-whitesur", "macify-root.sh"]


def needed() -> bool:
    """Macify está aplicado y esta versión todavía no se aplicó."""
    return system.BACKUP_FILE.exists() and load_config().get("applied_version") != __version__


def run(log) -> None:
    if not system.BACKUP_FILE.exists():
        log(_("Macify has not been applied yet: nothing to update."))
        return
    previous = load_config().get("applied_version") or _("an earlier version")
    if previous == __version__:
        log(_("Macify {version}: checking that everything is in place.").format(version=__version__))
    else:
        log(_("Updating from {old} to {new}: only what changed.").format(old=previous, new=__version__))
    with busy():
        # Lo mismo que revisa «Buscar problemas», salvo los ajustes (se aplican enteros justo
        # después), las herramientas del sistema (las instala apt con el paquete) y las
        # pantallas de arranque (piden contraseña: las ofrece la revisión).
        checks = [*doctor.check_themes(), doctor.check_theme_css(),
                  *doctor.check_extensions(online=False), doctor.check_icons(), doctor.check_fonts(),
                  doctor.check_upkeep()]
        for check in checks:
            if check.status != doctor.OK and check.fix:
                log(_("Updating: {name}").format(name=check.name))
                check.fix(log)
        installer.apply_look(profile.load_choices(), log)
        if icons.THEME_DIR.exists() and icons.mac_theme_ready():
            icons.ensure_theme(False, log)
            icons.generate(False, log)
        clean(log)
    save_config_value("applied_version", __version__)
    log(_("Macify {version} is ready. Log out and back in to see everything new.").format(version=__version__))


def clean(log) -> None:
    """Borra lo que Macify guardó y ya no se usa."""
    freed = 0
    for package in (CACHE_DIR / "updates").glob("*.deb"):
        freed += _remove(package)
    in_use = _wallpaper_in_use()
    for copy in wallpapers.FITTED_DIR.glob("*.jpg") if wallpapers.FITTED_DIR.exists() else []:
        if copy != in_use:
            freed += _remove(copy)
    old = time.time() - THUMBNAIL_MAX_AGE
    for thumb in wallpapers.THUMB_DIR.glob("*.jpg") if wallpapers.THUMB_DIR.exists() else []:
        if thumb.stat().st_mtime < old:
            freed += _remove(thumb)
    for name in LEFTOVERS:
        freed += _remove(CACHE_DIR / name)
    for archive in extensions.EXTENSIONS_DIR.glob("*.zip") if extensions.EXTENSIONS_DIR.exists() else []:
        if archive.name.removesuffix(".shell-extension.zip") not in extensions.PINS:
            freed += _remove(archive)          # extensiones que Macify ya no usa
    if freed:
        log(_("Cleaned up {size} MB of old files.").format(size=round(freed / 1048576, 1)))


def _wallpaper_in_use() -> Path | None:
    uri = profile.settings(profile.load_choices())["org.gnome.desktop.background"]["picture-uri"]
    return Path(uri.strip("'").removeprefix("file://"))


def _remove(path: Path) -> int:
    """Borra un archivo o carpeta y devuelve cuántos bytes ocupaba."""
    if not path.exists():
        return 0
    if path.is_dir():
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        shutil.rmtree(path, ignore_errors=True)
        return size
    size = path.stat().st_size
    path.unlink(missing_ok=True)
    return size

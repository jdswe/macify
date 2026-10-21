"""Desinstalación limpia: revierte los ajustes y borra solo lo que instaló Macify."""

import glob
import shutil
from pathlib import Path

from .i18n import _
import subprocess

from . import apps, boot, extensions, fonts, icons, launcher, session, system
from .assets import CACHE_DIR, CONFIG_DIR, DATA_DIR

HOME = Path.home()
GTK4_DIR = HOME / ".config" / "gtk-4.0"
# Archivos que el instalador de WhiteSur escribe en gtk-4.0 (no se toca el resto).
GTK4_FILES = ["gtk.css", "gtk-dark.css", "gtk-Light.css", "gtk-Dark.css", "assets", "windows-assets"]
# Enlaces de iconos y cursor que creaban versiones anteriores de Macify.
LEGACY_LINKS = ["Colloid-Purple", "Drop-Purple"]


def targets() -> list[Path]:
    """Rutas que la app creó. Sólo se borran estas."""
    paths = sorted(Path(p) for p in glob.glob(str(HOME / ".themes" / "WhiteSur*")))
    paths += sorted(Path(p) for p in glob.glob(str(HOME / ".local" / "share" / "icons" / "WhiteSur*")))
    paths += [GTK4_DIR / name for name in GTK4_FILES]
    paths += [HOME / ".local" / "bin" / "gnome-theme-switcher",
              HOME / ".local" / "share" / "applications" / "org.gnome.GTK4ThemeSwitcher.desktop"]
    paths += [HOME / ".local" / "share" / "icons" / name for name in LEGACY_LINKS]
    paths += [DATA_DIR, CACHE_DIR, CONFIG_DIR]
    return paths


def _remove(path: Path, dry_run: bool, log) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    log(_("Remove {path}").format(path=path))
    if dry_run:
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def uninstall(dry_run: bool, log) -> None:
    log(_("== Uninstalling Macify") + (_(" (dry run)") if dry_run else ""))
    boot.revert(dry_run, log)
    apps.restore(dry_run, log)
    session.remove(dry_run, log)
    system.restore(dry_run, log)
    extensions.remove(dry_run, log)
    if not dry_run:
        subprocess.run(["gnome-extensions", "enable", extensions.UBUNTU_DOCK], check=False, capture_output=True)
    icons.remove(dry_run, log)
    fonts.remove(dry_run, log)
    launcher.remove(dry_run, log)
    for path in targets():
        _remove(path, dry_run, log)
    if GTK4_DIR.is_dir() and not any(GTK4_DIR.iterdir()) and not dry_run:
        GTK4_DIR.rmdir()
    log(_("To remove the package from the system: sudo apt remove macify"))
    log(_("== Dry run finished.") if dry_run else _("== Uninstall complete. Restart your session."))

"""Tema WhiteSur dentro de las apps snap.

Una app snap no puede leer ~/.themes ni ~/.config/gtk-4.0: su $HOME es ~/snap/<app>/current,
y su lanzador convierte ~/.themes y ~/.local/share/themes en enlaces de sólo lectura a sus
propios temas (y los rehace en cada actualización). Por eso sus ventanas no tenían los
botones de semáforo. GTK también busca temas en cada carpeta de $XDG_DATA_DIRS, que incluye
la del snap: ~/snap/<app>/current/themes no la toca nadie. Ahí va el tema, y el de GTK 4 en
~/snap/<app>/current/.config/gtk-4.0, con enlaces duros: los mismos archivos, sin ocupar
espacio extra. Se repite al iniciar sesión y al instalar apps, así que también llega a las
apps snap que se instalen después. remove() lo deshace.
"""

import os
import shutil
from pathlib import Path

from .assets import HOME
from .i18n import _

SNAP_DIR = Path("/snap")
SNAP_HOMES = HOME / "snap"
SNAP_DESKTOP = Path("/var/lib/snapd/desktop/applications")
THEMES = HOME / ".themes"
GTK4 = HOME / ".config" / "gtk-4.0"
VARIANTS = ("WhiteSur-Dark-alt", "WhiteSur-Light-alt")
GTK4_FILES = ("gtk-Dark.css", "gtk-Light.css")
GTK4_DIRS = ("assets", "windows-assets")
MARKER = ".macify-theme"


def _themes_dir(home: Path) -> Path:
    return home / "themes"


def themed_snaps() -> list[str]:
    """Apps snap con ventanas GTK que ya se abrieron alguna vez (tienen su carpeta)."""
    names = []
    for meta in SNAP_DIR.glob("*/current/meta/snap.yaml"):
        name = meta.parts[-4]
        if "gtk-3-themes" not in meta.read_text(errors="ignore"):
            continue
        has_window = any(SNAP_DESKTOP.glob(f"{name}_*.desktop"))
        if has_window and (SNAP_HOMES / name / "current").is_dir():
            names.append(name)
    return sorted(names)


def _link(source: Path, target: Path) -> bool:
    """Enlace duro de source en target; copia si no se puede. True si cambió algo."""
    if target.exists() and not target.is_symlink():
        try:
            if os.path.samefile(source, target):
                return False
        except OSError:
            pass
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return True


def _mirror(source: Path, target: Path) -> int:
    changed = 0
    for path in source.rglob("*"):
        if path.is_file() and not path.is_symlink():
            changed += _link(path, target / path.relative_to(source))
    return changed


def _point(link: Path, name: str) -> None:
    """Enlace simbólico relativo (dentro del snap no se puede salir de su carpeta)."""
    if link.is_symlink() and os.readlink(link) == name:
        return
    link.unlink(missing_ok=True)
    link.symlink_to(name)


def sync(appearance: str, log=None) -> list[str]:
    """Pone o actualiza el tema en cada app snap. Devuelve las apps tocadas."""
    if not all((THEMES / v).is_dir() for v in VARIANTS) or not GTK4.is_dir():
        return []
    variant = "Dark" if appearance == "dark" else "Light"
    done = []
    for name in themed_snaps():
        home = SNAP_HOMES / name / "current"
        changed = 0
        for theme in VARIANTS:
            target = _themes_dir(home) / theme
            changed += _link(THEMES / theme / "index.theme", target / "index.theme")
            changed += _mirror(THEMES / theme / "gtk-3.0", target / "gtk-3.0")
        gtk4 = home / ".config" / "gtk-4.0"
        for file in GTK4_FILES:
            if (GTK4 / file).is_file():
                changed += _link(GTK4 / file, gtk4 / file)
        for folder in GTK4_DIRS:
            if (GTK4 / folder).is_dir():
                changed += _mirror(GTK4 / folder, gtk4 / folder)
        _point(gtk4 / "gtk.css", f"gtk-{variant}.css")
        _point(gtk4 / "gtk-dark.css", "gtk-Dark.css")
        (_themes_dir(home) / MARKER).touch()
        if changed and log:
            log(_("{app} (snap): macOS window buttons").format(app=name))
        done.append(name)
    return done


def remove(log=None) -> None:
    for marker in SNAP_HOMES.glob(f"*/current/themes/{MARKER}"):
        home = marker.parents[1]
        for theme in VARIANTS:
            shutil.rmtree(_themes_dir(home) / theme, ignore_errors=True)
        marker.unlink(missing_ok=True)
        gtk4 = home / ".config" / "gtk-4.0"
        for name in (*GTK4_FILES, "gtk.css", "gtk-dark.css"):
            (gtk4 / name).unlink(missing_ok=True)
        for folder in GTK4_DIRS:
            shutil.rmtree(gtk4 / folder, ignore_errors=True)
        if log:
            log(_("{app} (snap): original window buttons").format(app=home.parent.name))

"""Mantenimiento automático de Macify.

- Al iniciar sesión: cambia de dock (Ubuntu Dock se reactiva en cada sesión),
  aplica los ajustes de apps que estaban abiertas y revisa los iconos.
- Cuando se instala o quita una app (apt, snap o Flatpak): crea su icono estilo Mac.
"""

import shutil
import subprocess
import time
from pathlib import Path

from . import apps, extensions, icons, launcher, profile, snaps
from .assets import HOME, is_busy, load_config, save_config_value
from .i18n import _

AUTOSTART = HOME / ".config" / "autostart" / "dev.macify.Refresh.desktop"
UNIT_DIR = HOME / ".config" / "systemd" / "user"
SERVICE = "macify-icons.service"
PATH_UNIT = "macify-icons.path"
UPDATE_CHECK_EVERY = 24 * 60 * 60   # segundos


def refresh(log, login: bool = False) -> None:
    """Lo que se repite solo: al iniciar sesión (login=True) o al cambiar las apps."""
    if is_busy():
        return   # Macify está instalando o reparando: al terminar regenera los iconos él mismo.
    if login:
        installed = (extensions.INSTALL_DIR / "dash2dock-lite@icedman.github.com").exists()
        if installed:
            extensions.disable_other_docks(False, log)
        if extensions.menubar_outdated():
            # Macify se actualizó: su extensión nueva queda lista para el próximo inicio de sesión.
            extensions.install_menubar(False, log)
        apps.apply(False, log)
    if icons.THEME_DIR.exists() and icons.mac_theme_ready():
        icons.ensure_theme(False, log)
        icons.generate(False, log)
    # Apps snap abiertas por primera vez: también reciben el tema (enlaces, sin copiar).
    snaps.sync(profile.load_choices().appearance, log)
    if login:
        from . import doctor

        # Buscar actualizaciones en internet sólo una vez al día; el resto, revisión local.
        last = load_config().get("last_update_check", 0)
        online = time.time() - last > UPDATE_CHECK_EVERY
        doctor.notify_if_needed(doctor.run(online=online))
        if online:
            save_config_value("last_update_check", int(time.time()))


def _files() -> dict[Path, str]:
    """El inicio automático y las unidades de systemd que dejan a Macify al día solo."""
    run = " ".join(f'"{part}"' if " " in part else part for part in launcher.command())
    # Carpetas de apps (apt, snap, flatpak) y la de los snaps de cada usuario, que cambia la
    # primera vez que se abre una app snap recién instalada.
    folders = [path for path in [*icons.APP_DIRS, HOME / "snap"] if path.parent.exists()]
    watches = "".join(f"PathChanged={folder}\n" for folder in folders)
    return {
        AUTOSTART: ("[Desktop Entry]\nType=Application\nName=Macify\n"
                    f"Exec={run} refresh --login\n"
                    "NoDisplay=true\nX-GNOME-Autostart-enabled=true\n"),
        UNIT_DIR / SERVICE: ("[Unit]\nDescription=Macify: icono y tema estilo Mac para apps nuevas\n\n"
                             f"[Service]\nType=oneshot\nExecStart={run} refresh\n"),
        UNIT_DIR / PATH_UNIT: ("[Unit]\nDescription=Macify: vigila las carpetas de apps\n\n"
                               f"[Path]\n{watches}TriggerLimitIntervalSec=10\n\n[Install]\nWantedBy=default.target\n"),
    }


def current() -> bool:
    """¿Están las unidades como las escribe esta versión de Macify?"""
    return all(path.exists() and path.read_text() == text for path, text in _files().items())


def install(dry_run: bool, log) -> None:
    log(_("Automatic upkeep: at login and whenever an app is installed"))
    if dry_run:
        return
    for path, text in _files().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", PATH_UNIT], check=False, capture_output=True)


def remove(dry_run: bool, log) -> None:
    for path in (AUTOSTART, UNIT_DIR / SERVICE, UNIT_DIR / PATH_UNIT):
        if path.exists():
            log(_("Remove {path}").format(path=path))
    if dry_run:
        return
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "disable", "--now", PATH_UNIT], check=False, capture_output=True)
    for path in (AUTOSTART, UNIT_DIR / SERVICE, UNIT_DIR / PATH_UNIT):
        path.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)

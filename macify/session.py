"""Mantenimiento automático de Macify.

- Al iniciar sesión: cambia de dock (Ubuntu Dock se reactiva en cada sesión),
  aplica los ajustes de apps que estaban abiertas y revisa los iconos.
- Cuando se instala o quita una app (apt, snap o Flatpak): crea su icono estilo Mac.
"""

import shutil
import subprocess
from pathlib import Path

from . import apps, extensions, icons, launcher
from .assets import HOME
from .i18n import _

AUTOSTART = HOME / ".config" / "autostart" / "dev.macify.Refresh.desktop"
UNIT_DIR = HOME / ".config" / "systemd" / "user"
SERVICE = "macify-icons.service"
PATH_UNIT = "macify-icons.path"


def refresh(log, login: bool = False) -> None:
    """Lo que se repite solo: al iniciar sesión (login=True) o al cambiar las apps."""
    if login:
        installed = (extensions.INSTALL_DIR / "dash2dock-lite@icedman.github.com").exists()
        if installed:
            extensions.disable_other_docks(False, log)
        apps.apply(False, log)
    if icons.THEME_DIR.exists():
        icons.ensure_theme(False, log)
        icons.generate(False, log)
    if login:
        from . import doctor

        doctor.notify_if_needed(doctor.run(online=True))


def install(dry_run: bool, log) -> None:
    run = " ".join(f'"{part}"' if " " in part else part for part in launcher.command())
    folders = [path for path in icons.APP_DIRS if path.parent.exists()]
    log(_("Automatic upkeep: at login and whenever an app is installed"))
    if dry_run:
        return
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        "[Desktop Entry]\nType=Application\nName=Macify\n"
        f"Exec={run} refresh --login\n"
        "NoDisplay=true\nX-GNOME-Autostart-enabled=true\n"
    )
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    (UNIT_DIR / SERVICE).write_text(
        "[Unit]\nDescription=Macify: icono estilo Mac para apps nuevas\n\n"
        f"[Service]\nType=oneshot\nExecStart={run} refresh\n"
    )
    watches = "".join(f"PathChanged={folder}\n" for folder in folders)
    (UNIT_DIR / PATH_UNIT).write_text(
        "[Unit]\nDescription=Macify: vigila las carpetas de apps\n\n"
        f"[Path]\n{watches}TriggerLimitIntervalSec=10\n\n[Install]\nWantedBy=default.target\n"
    )
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

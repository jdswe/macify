"""Datos del sistema que se muestran al usuario antes de instalar."""

import shutil
import subprocess

from .i18n import _


def _os_name() -> str:
    try:
        with open("/etc/os-release") as file:
            for line in file:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "Linux"


def _gnome_version() -> str:
    if shutil.which("gnome-shell") is None:
        return "GNOME no detectado"
    result = subprocess.run(["gnome-shell", "--version"], capture_output=True, text=True)
    return result.stdout.strip() or "GNOME"


def summary() -> dict[str, str]:
    import os

    return {
        "os": _os_name(),
        "desktop": _gnome_version(),
        "session": (os.environ.get("XDG_SESSION_TYPE") or _("unknown")).capitalize(),
    }

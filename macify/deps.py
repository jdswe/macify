"""Dependencias de sistema que necesita el instalador de WhiteSur."""

import shutil
import subprocess

from .i18n import _

# comando necesario -> paquete de Ubuntu que lo provee
REQUIRED = {
    "sassc": "sassc",
    "xmllint": "libxml2-utils",
    "glib-compile-resources": "libglib2.0-dev-bin",
}


def missing_packages() -> list[str]:
    return sorted({pkg for cmd, pkg in REQUIRED.items() if shutil.which(cmd) is None})


def ensure(log) -> None:
    """Instala los paquetes que falten pidiendo la contraseña con pkexec."""
    install(missing_packages(), log)


def install(packages: list[str], log) -> None:
    if not packages:
        return
    log(_("Installing dependencies: {packages}").format(packages=" ".join(packages)))
    process = subprocess.Popen(
        ["pkexec", "apt-get", "install", "-y", *packages],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for line in process.stdout:
        log(line.rstrip())
    if process.wait() != 0:
        raise RuntimeError(_("Could not install dependencies (cancelled or apt error)."))

"""Dictado (opcional): dictado por voz y transcripción, en el propio equipo.

Dictado es otro proyecto (github.com/jdswe/dictado). Macify sólo ofrece instalarlo, lo revisa
en «Buscar problemas» si la persona lo eligió, y muestra en la isla cuándo está escuchando o
grabando. Ni el audio ni Whisper pasan por Macify: Dictado escribe el texto con su propia
extensión. Su instalador comprueba la huella SHA-256 de la versión que descarga y no usa sudo.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from . import deps
from .i18n import _

INSTALL_URL = "https://jdswe.github.io/dictado/install.sh"
EXTENSION = "dictado@dictado.dev"
BUS_NAME = "dev.dictado.Dictado"
HOME = Path.home()
EXTENSION_DIR = HOME / ".local" / "share" / "gnome-shell" / "extensions" / EXTENSION
UNINSTALLER = HOME / ".local" / "share" / "dictado" / "src" / "uninstall.sh"
SERVICE_FILE = HOME / ".local" / "share" / "dbus-1" / "services" / f"{BUS_NAME}.service"


def installed() -> bool:
    return EXTENSION_DIR.is_dir() or SERVICE_FILE.is_file()


def _venv_package() -> str:
    return f"python{sys.version_info.major}.{sys.version_info.minor}-venv"


def missing_packages() -> list[str]:
    """Lo que el instalador de Dictado pide y no trae Ubuntu de serie."""
    missing = []
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    if subprocess.run([sys.executable, "-c", "import venv, ensurepip"], capture_output=True).returncode:
        missing.append(_venv_package())
    return missing


def _run(command: list[str], log) -> None:
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        if line.strip():
            log(line.rstrip())
    if process.wait() != 0:
        raise RuntimeError(_("Dictado could not be installed. See the messages above."))


def install(dry_run: bool, log) -> None:
    if installed():
        log(_("Dictado is already installed."))
        return
    log(_("Install Dictado from {url} (about 350 MB of speech models download once)").format(url=INSTALL_URL))
    if dry_run:
        return
    deps.install(missing_packages(), log)
    _run(["bash", "-c", f"set -o pipefail; curl -fsSL {INSTALL_URL} | bash"], log)
    log(_("Dictado is installed. Log out and back in to use its shortcut."))


def uninstall(dry_run: bool, log) -> None:
    if not UNINSTALLER.is_file():
        return
    log(_("Uninstall Dictado"))
    if not dry_run:
        _run(["bash", str(UNINSTALLER)], log)

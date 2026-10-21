"""Lanzador de Macify: entrada en el menú de apps y su icono.

Si Macify está instalado con el .deb, el sistema ya trae ambos.
Si se ejecuta el .pyz, se crean en la carpeta del usuario.
"""

import sys
from importlib import resources
from pathlib import Path

from .i18n import _

APP_ID = "dev.macify.Macify"
HOME = Path.home()
DESKTOP_FILE = HOME / ".local" / "share" / "applications" / f"{APP_ID}.desktop"
ICON_FILE = HOME / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"
SYSTEM_DESKTOP = Path("/usr/share/applications") / f"{APP_ID}.desktop"


def desktop_entry(exec_line: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Name=Macify\n"
        "Comment=Turn Ubuntu into a Mac in one click\n"
        "Comment[es]=Convierte Ubuntu en un Mac con un clic\n"
        f"Exec={exec_line}\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Settings;DesktopSettings;\n"
        f"StartupWMClass={APP_ID}\n"
    )


def command() -> list[str]:
    """Cómo ejecutar Macify desde fuera: el paquete instalado, el .pyz o el código fuente."""
    if Path("/usr/bin/macify").exists():
        return ["/usr/bin/macify"]
    script = Path(sys.argv[0]).resolve()
    if script.suffix == ".pyz":
        return ["/usr/bin/python3", str(script)]
    return ["/usr/bin/env", f"PYTHONPATH={Path(__file__).resolve().parents[1]}", "/usr/bin/python3", "-m", "macify"]


def ensure() -> None:
    """Crea el lanzador del usuario cuando Macify no está instalado en el sistema."""
    if SYSTEM_DESKTOP.exists():
        # Instalado con el .deb: el lanzador del usuario (de un .pyz) taparía al del sistema.
        for path in (DESKTOP_FILE, ICON_FILE):
            path.unlink(missing_ok=True)
        return
    script = Path(sys.argv[0]).resolve()
    exec_line = f'python3 "{script}"' if script.suffix == ".pyz" else "python3 -m macify"
    ICON_FILE.parent.mkdir(parents=True, exist_ok=True)
    ICON_FILE.write_bytes(resources.files("macify").joinpath("data", f"{APP_ID}.svg").read_bytes())
    DESKTOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DESKTOP_FILE.exists() or DESKTOP_FILE.read_text() != desktop_entry(exec_line):
        DESKTOP_FILE.write_text(desktop_entry(exec_line))


def remove(dry_run: bool, log) -> None:
    for path in (DESKTOP_FILE, ICON_FILE):
        if path.exists():
            log(_("Remove {path}").format(path=path))
            if not dry_run:
                path.unlink()

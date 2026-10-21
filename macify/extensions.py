"""Extensiones de GNOME: descarga, instalación y activación.

Las extensiones se descargan de extensions.gnome.org, se verifican por UUID y
se instalan en la carpeta del usuario. Al desinstalar, se borran solo las de Macify.
"""

import ast
import json
import re
import shutil
import subprocess
import urllib.request
import zipfile
from importlib import resources
from pathlib import Path

from .i18n import _
from . import system
from .assets import CACHE_DIR

EXTENSIONS_DIR = CACHE_DIR / "extensions"
INSTALL_DIR = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"
BASE_URL = "https://extensions.gnome.org/download-extension/{uuid}.shell-extension.zip?shell_version=50"

# UUID -> descripción
EXTENSIONS = {
    "user-theme@gnome-shell-extensions.gcampax.github.com": "User Themes",
    "blur-my-shell@aunetx": "Blur my Shell",
    "just-perfection-desktop@just-perfection": "Just Perfection",
    "dash2dock-lite@icedman.github.com": "Dash2Dock Animated",
    "compiz-alike-magic-lamp-effect@hermes83.github.com": "Magic Lamp",
}
MAGIC_LAMP = "compiz-alike-magic-lamp-effect@hermes83.github.com"
# Extensión propia de Macify: viaja dentro de la app, no se descarga.
MENUBAR = "macify-menubar@macify.dev"
SYSTEM_LOGO = Path("/usr/share/pixmaps/ubuntu-logo.svg")
# Instaladas por versiones anteriores de Macify: se desactivan y se borran al desinstalar.
LEGACY = ["dash-to-dock@micxgx.gmail.com"]
UBUNTU_DOCK = "ubuntu-dock@ubuntu.com"


def zip_path(uuid: str) -> Path:
    return EXTENSIONS_DIR / f"{uuid}.shell-extension.zip"


def fetch(log) -> None:
    """Descarga cada zip si falta y comprueba que su UUID coincida."""
    EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    for uuid, name in EXTENSIONS.items():
        target = zip_path(uuid)
        if not target.exists():
            log(_("Downloading {name} from {source}").format(name=name, source="extensions.gnome.org"))
            with urllib.request.urlopen(BASE_URL.format(uuid=uuid), timeout=120) as response:
                target.write_bytes(response.read())
        with zipfile.ZipFile(target) as archive:
            metadata = json.loads(archive.read("metadata.json"))
        if metadata.get("uuid") != uuid:
            raise RuntimeError(_("The {name} file does not match its UUID.").format(name=name))


def install(dry_run: bool, log) -> None:
    for uuid, name in EXTENSIONS.items():
        log(_("Install extension {name}").format(name=name))
        if dry_run:
            continue
        subprocess.run(["gnome-extensions", "install", "--force", str(zip_path(uuid))], check=True)


def _copy_tree(source, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_dir():
            _copy_tree(item, target / item.name)
        else:
            (target / item.name).write_bytes(item.read_bytes())


def menubar_logo_svg() -> str:
    """Logo de una tinta para la barra, hecho a partir del logo de Ubuntu del sistema.

    Se quita el fondo naranja y se pinta en blanco, como la manzana en la barra de macOS.
    """
    if SYSTEM_LOGO.exists():
        svg = SYSTEM_LOGO.read_text()
        svg = re.sub(r"<rect[^>]*/>", "", svg)
        svg = re.sub(r"<style>.*?</style>", "<style>.cls-2{fill:#ffffff;}</style>", svg, flags=re.S)
        return svg
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            '<circle cx="16" cy="16" r="12" fill="none" stroke="#ffffff" stroke-width="4"/></svg>')


def install_menubar(dry_run: bool, log) -> None:
    target = INSTALL_DIR / MENUBAR
    log(_("Install Macify's own extension in {path}").format(path=target))
    if dry_run:
        return
    shutil.rmtree(target, ignore_errors=True)
    _copy_tree(resources.files("macify").joinpath("data", "extension", MENUBAR), target)
    (target / "icons").mkdir(exist_ok=True)
    (target / "icons" / "macify-logo-symbolic.svg").write_text(menubar_logo_svg())


def enabled_settings(magic_lamp: bool = True) -> dict:
    """Ajuste de enabled-extensions: añade las de Macify y quita los docks anteriores."""
    result = subprocess.run(["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
                            capture_output=True, text=True)
    try:
        current = ast.literal_eval(result.stdout.strip().replace("@as ", ""))
    except (ValueError, SyntaxError):
        current = []
    wanted = [uuid for uuid in EXTENSIONS if magic_lamp or uuid != MAGIC_LAMP] + [MENUBAR]
    dropped = {UBUNTU_DOCK, *LEGACY} | ({MAGIC_LAMP} - set(wanted))
    enabled = [uuid for uuid in current if uuid not in dropped]
    enabled += [uuid for uuid in wanted if uuid not in enabled]
    return {"org.gnome.shell": {"enabled-extensions": repr(enabled)}}


def remove(dry_run: bool, log) -> None:
    """Borra las extensiones instaladas por Macify (la lista enabled se restaura aparte)."""
    for uuid in [*EXTENSIONS, MENUBAR, *LEGACY]:
        path = INSTALL_DIR / uuid
        if path.exists():
            log(_("Remove {path}").format(path=path))
            if not dry_run:
                shutil.rmtree(path)


def disable_other_docks(dry_run: bool, log) -> None:
    """Ubuntu Dock sigue activo aunque no esté en la lista: se desactiva explícitamente."""
    for uuid in (UBUNTU_DOCK, *LEGACY):
        log(_("Disable {name}").format(name=uuid))
        if not dry_run:
            subprocess.run(["gnome-extensions", "disable", uuid], check=False, capture_output=True)

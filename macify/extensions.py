"""Extensiones de GNOME: descarga, instalación y activación.

Las extensiones se descargan de extensions.gnome.org, se verifican por UUID y
se instalan en la carpeta del usuario. Al desinstalar, se borran solo las de Macify.
"""

import ast
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
import zipfile
from importlib import resources
from pathlib import Path

from .i18n import _
from .assets import CACHE_DIR

EXTENSIONS_DIR = CACHE_DIR / "extensions"
INSTALL_DIR = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"
DOWNLOAD_URL = "https://extensions.gnome.org/download-extension/{uuid}.shell-extension.zip?version_tag={tag}"

# UUID -> descripción
EXTENSIONS = {
    "user-theme@gnome-shell-extensions.gcampax.github.com": "User Themes",
    "blur-my-shell@aunetx": "Blur my Shell",
    "just-perfection-desktop@just-perfection": "Just Perfection",
    "dash2dock-lite@icedman.github.com": "Dash2Dock Animated",
    "compiz-alike-magic-lamp-effect@hermes83.github.com": "Magic Lamp",
}
# Cada extensión se fija a la versión probada con Macify (su version_tag en
# extensions.gnome.org) y el zip se comprueba con su huella SHA-256, igual que los temas:
# corren dentro de GNOME con todos los permisos de la persona, así que una versión nueva llega
# sólo con una versión nueva de Macify, después de probarla. UUID -> (versión, tag, sha256)
PINS = {
    "user-theme@gnome-shell-extensions.gcampax.github.com":
        (79, 75092, "d002bcd7d5bf780b1b943fa3617d4bc067a2174be576ec5438fcb76467390c05"),
    "blur-my-shell@aunetx":
        (76, 76770, "0dfde0d3575b4c7e32647e94010fa37f15ac933f4fe61c46bfe200e772114d85"),
    "just-perfection-desktop@just-perfection":
        (37, 74466, "c54ccd627540d86e6baf06c699f624ba7d5229aedfc8b00b0dc7182c6538eda8"),
    "dash2dock-lite@icedman.github.com":
        (92, 71180, "14db6849ba6edcb63f25032007e182d2b7d842568e9c1386587d7a08c6c53abe"),
    "compiz-alike-magic-lamp-effect@hermes83.github.com":
        (25, 76122, "a3a445a0f0329b581fec6edd2c33f143eec9b267cbb9b028bb6d7bff990cc420"),
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


def _verified(path: Path, uuid: str) -> bool:
    return path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == PINS[uuid][2]


def fetch(log) -> None:
    """Descarga la versión fijada de cada extensión (si no está ya) y comprueba su huella y su UUID."""
    EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    for uuid, name in EXTENSIONS.items():
        target = zip_path(uuid)
        if not _verified(target, uuid):
            log(_("Downloading {name} from {source}").format(name=name, source="extensions.gnome.org"))
            with urllib.request.urlopen(DOWNLOAD_URL.format(uuid=uuid, tag=PINS[uuid][1]), timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != PINS[uuid][2]:
                raise RuntimeError(_("The {name} download does not match its fingerprint: not installed.").format(name=name))
            target.write_bytes(data)
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


def menubar_outdated() -> bool:
    """La extensión propia instalada es distinta de la que trae esta versión de Macify."""
    target = INSTALL_DIR / MENUBAR
    if not target.exists():
        return False
    packaged = resources.files("macify").joinpath("data", "extension", MENUBAR)
    return any(not (target / item.name).is_file() or (target / item.name).read_bytes() != item.read_bytes()
               for item in packaged.iterdir() if item.is_file())


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

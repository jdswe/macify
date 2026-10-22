"""Actualizaciones de Macify desde los releases oficiales de GitHub.

La descarga se verifica antes de instalar: debe ser el paquete «macify» y, si
GitHub publica la huella SHA-256 del archivo, debe coincidir.
"""

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

from . import __version__
from .assets import CACHE_DIR
from .i18n import _

REPO = "jdswe/macify"
API = f"https://api.github.com/repos/{REPO}/releases/latest"


def _parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.lstrip("v").split(".") if part.isdigit())


def latest() -> dict | None:
    """Última versión publicada: {"version", "url", "name", "size", "sha256", "notes", "date"} o None."""
    with urllib.request.urlopen(API, timeout=15) as response:
        release = json.load(response)
    asset = next((a for a in release.get("assets", []) if a["name"].endswith("_all.deb")), None)
    if asset is None:
        return None
    digest = asset.get("digest") or ""
    return {"version": release["tag_name"].lstrip("v"), "url": asset["browser_download_url"],
            "name": asset["name"], "size": asset.get("size", 0),
            "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else None,
            "notes": release.get("body") or "", "date": (release.get("published_at") or "")[:10]}


def notes(release: dict) -> list[str]:
    """Las novedades del release como lista de frases cortas (sin el formato Markdown)."""
    items = []
    for line in release.get("notes", "").splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ")):
            items.append(line[2:].replace("**", "").replace("`", ""))
    return items


def is_newer(remote: str, local: str = __version__) -> bool:
    return _parse(remote) > _parse(local)


def install(release: dict, log, progress=None) -> None:
    """Descarga, verifica e instala el release. progress(fracción) informa la descarga."""
    folder = CACHE_DIR / "updates"
    folder.mkdir(parents=True, exist_ok=True)
    package = folder / Path(release["name"]).name
    log(_("Downloading {name} from {source}").format(name=release["name"], source="GitHub"))
    with urllib.request.urlopen(release["url"], timeout=300) as response, package.open("wb") as out:
        total = int(response.headers.get("Content-Length") or release.get("size") or 0)
        done = 0
        while chunk := response.read(65536):
            out.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(min(done / total, 1.0))
    # Sin huella publicada no se instala (nunca un paquete sin verificar).
    if not release["sha256"] or hashlib.sha256(package.read_bytes()).hexdigest() != release["sha256"]:
        package.unlink()
        raise RuntimeError(_("The download does not match its published fingerprint."))
    name = subprocess.run(["dpkg-deb", "-f", str(package), "Package"], capture_output=True, text=True).stdout.strip()
    if name != "macify":
        package.unlink()
        raise RuntimeError(_("The download is not the Macify package."))
    log(_("Installing Macify {version}").format(version=release["version"]))
    result = subprocess.run(["pkexec", "apt-get", "install", "-y", str(package)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(_("Could not install dependencies (cancelled or apt error)."))
    # Sólo lo que cambió (la versión nueva sabe qué): extensión, temas, ajustes nuevos, y se
    # borra lo viejo. Ya, no al iniciar sesión: GNOME cargaría antes la extensión vieja.
    log(_("Applying only what changed…"))
    upgrade = subprocess.run(["/usr/bin/macify", "upgrade"], capture_output=True, text=True, timeout=1800)
    for line in upgrade.stdout.splitlines()[-3:]:
        log(line)
    log(_("Macify {version} installed. Open it again to use the new version.").format(version=release["version"]))

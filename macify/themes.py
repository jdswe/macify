"""Temas WhiteSur (GPL-3.0, de vinceliuice): ventanas, iconos, cursores y login.

Se descargan de sus repositorios oficiales de GitHub a la caché de Macify y se
instalan con sus propios instaladores, siempre en la carpeta del usuario,
salvo la pantalla de inicio de sesión, que necesita permisos de administrador.

Cada repositorio se fija a una versión probada (un commit) y su descarga se comprueba con
su huella SHA-256 antes de ejecutar nada: si el repositorio cambiara o lo atacaran, Macify no
correría código distinto del que se probó. Las versiones nuevas llegan con las de Macify.
"""

import hashlib
import io
import os
import re
import shutil
import subprocess
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .i18n import _
from .assets import CACHE_DIR

COMMIT_FILE = ".macify-commit"


@dataclass(frozen=True)
class Source:
    repo: str
    commit: str
    sha256: str          # huella del .tar.gz de ese commit en codeload.github.com


# El de «gtk» debe coincidir con WHITESUR_COMMIT de data/root/macify-root.sh.
REPOS = {
    "gtk": Source("vinceliuice/WhiteSur-gtk-theme", "d5782652d412137e26fb8ff55b55a5572e4c6995",
                  "9d8be3dca76f7be36dfb6513aa2c301be1ff265a9c1c4c1006b5ed0f89df29f1"),
    "icons": Source("vinceliuice/WhiteSur-icon-theme", "73d8040da51a9ed74e47c7366e7e9ff437601a5c",
                    "96661649071d8a9664b40d42abea75286175234473106156e9a4b25f54e6cb0c"),
    "cursors": Source("vinceliuice/WhiteSur-cursors", "e190baf618ed95ee217d2fd45589bd309b37672b",
                      "35c817c2c26bc4d2c06801cfe6c924a068ad771d3846c5203b04d1c893dd5664"),
}


def repo_dir(key: str) -> Path:
    return CACHE_DIR / REPOS[key].repo.split("/")[1]


def fetch(key: str, log) -> Path:
    """Descarga el repositorio una sola vez y devuelve su carpeta."""
    target = repo_dir(key)
    legacy = CACHE_DIR / f"{target.name}-master"   # nombre usado por versiones anteriores
    if not target.exists() and legacy.exists():
        legacy.rename(target)
    if target.exists() and installed_commit(key) == REPOS[key].commit:
        return target
    shutil.rmtree(target, ignore_errors=True)       # otra versión (o una descarga a medias)
    source = REPOS[key]
    url = f"https://codeload.github.com/{source.repo}/tar.gz/{source.commit}"
    log(_("Downloading {name} from {source}").format(name=source.repo, source="GitHub"))
    with urllib.request.urlopen(url, timeout=300) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise RuntimeError(_("The download does not match its published fingerprint."))
    log(_("Downloaded: {size:.1f} MB").format(size=len(data) / 1_048_576))
    staging = CACHE_DIR / f".descarga-{target.name}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        archive.extractall(staging, filter="data")
    (top,) = list(staging.iterdir())
    top.rename(target)
    staging.rmdir()
    (target / COMMIT_FILE).write_text(source.commit)
    return target


def installed_commit(key: str) -> str | None:
    """Commit descargado (None si se bajó con una versión anterior de Macify)."""
    path = repo_dir(key) / COMMIT_FILE
    return path.read_text().strip() if path.exists() else None


def _run(cmd: list[str], cwd: Path, log) -> None:
    # Los instaladores usan setterm, que falla si TERM no está definido.
    env = {**os.environ, "TERM": os.environ.get("TERM") or "xterm"}
    process = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        if line.strip():
            log(line.rstrip())
    if process.wait() != 0:
        raise RuntimeError(_("Failed: {command}").format(command=" ".join(cmd)))


def install_gtk(appearance: str, dry_run: bool, log) -> None:
    """Ventanas y botones tipo semáforo, en claro y oscuro; libadwaita en el elegido."""
    first, second = ("dark", "light") if appearance == "dark" else ("light", "dark")
    script = str(repo_dir("gtk") / "install.sh")
    # Con -l el instalador sólo escribe libadwaita y antes borra las variantes
    # existentes; por eso va primero y la instalación completa después.
    commands = [
        [script, "-c", first, "-o", "normal", "-a", "alt", "-l"],
        [script, "-c", first, "-c", second, "-o", "normal", "-a", "alt"],
    ]
    for cmd in commands:
        log(_("Install: {options}").format(options=" ".join(cmd[1:])))
        if not dry_run:
            _run(cmd, fetch("gtk", log), log)
    if not dry_run:
        repair_css(log)


def install_icons(dry_run: bool, log) -> None:
    folder = repo_dir("icons")
    cmd = [str(folder / "install.sh")]
    log(_("Install WhiteSur icons in ~/.local/share/icons"))
    if not dry_run:
        _run(cmd, fetch("icons", log), log)


def install_cursors(dry_run: bool, log) -> None:
    folder = repo_dir("cursors")
    cmd = [str(folder / "install.sh")]
    log(_("Install WhiteSur cursors"))
    if not dry_run:
        _run(cmd, fetch("cursors", log), log)


def firefox_theme(enable: bool, log) -> None:
    """Tema WhiteSur para Firefox (también la versión snap), con los botones «alt» del sistema."""
    folder = fetch("gtk", log)
    args = ["-f", "alt"] if enable else ["-f", "-r"]
    _run([str(folder / "tweaks.sh"), *args], folder, log)


def link_libadwaita(appearance: str, log) -> None:
    """Apps GTK 4: apunta gtk.css al estilo claro u oscuro que WhiteSur ya dejó instalado."""
    folder = Path.home() / ".config" / "gtk-4.0"
    target = folder / f"gtk-{'Dark' if appearance == 'dark' else 'Light'}.css"
    link = folder / "gtk.css"
    if not target.exists() or (link.is_symlink() and link.resolve() == target):
        return
    log(_("GTK 4 apps: {variant} style").format(variant=target.stem.split("-")[1]))
    link.unlink(missing_ok=True)
    link.symlink_to(target)


def variant_installed(appearance: str) -> bool:
    variant = "Dark" if appearance == "dark" else "Light"
    return (Path.home() / ".themes" / f"WhiteSur-{variant}-alt").is_dir()


# WhiteSur claro escribe «color-mix(in srgb, black 6% #2E7CF7)», sin la coma antes del
# segundo color; GTK 4 descarta esas reglas (bordes de los botones). Se repara aquí.
_COLOR_MIX_WITHOUT_COMMA = re.compile(r"(color-mix\(in \w+, [^,()]+? \d+(?:\.\d+)?%) (?=[#@\w])")


def _css_files() -> list[Path]:
    home = Path.home()
    files = list((home / ".config" / "gtk-4.0").glob("gtk-*.css"))
    files += list((home / ".themes").glob("WhiteSur-*/gtk-4.0/*.css"))
    return [f for f in files if f.is_file() and not f.is_symlink()]


def broken_css() -> list[Path]:
    """Archivos del tema con el error de color-mix de WhiteSur."""
    return [f for f in _css_files() if _COLOR_MIX_WITHOUT_COMMA.search(f.read_text(errors="ignore"))]


def repair_css(log) -> int:
    fixed = 0
    for path in broken_css():
        text, count = _COLOR_MIX_WITHOUT_COMMA.subn(r"\1, ", path.read_text())
        path.write_text(text)
        fixed += count
    if fixed:
        log(_("Theme: {count} style rules repaired").format(count=fixed))
    return fixed

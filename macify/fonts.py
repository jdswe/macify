"""Fuentes San Francisco (SF Pro y SF Mono).

Primero usa las que el usuario ya tenga en su carpeta de recursos. Si no hay,
descarga los instaladores oficiales del sitio de Apple para desarrolladores
y extrae las fuentes con 7zip. Las fuentes nunca se incluyen en el paquete.
"""

import shutil
import subprocess
import urllib.request
from pathlib import Path

from .i18n import _
from . import deps
from .assets import CACHE_DIR, HOME, assets_root

FONT_DIR = HOME / ".local" / "share" / "fonts" / "macify-sf"
FONT_SUFFIXES = {".otf", ".ttf"}
APPLE_FONTS = {
    "SF-Pro": "https://devimages-cdn.apple.com/design/resources/download/SF-Pro.dmg",
    "SF-Mono": "https://devimages-cdn.apple.com/design/resources/download/SF-Mono.dmg",
}
WORK_DIR = CACHE_DIR / "fonts"


def _local_fonts() -> list[Path]:
    root = assets_root()
    if root is None or not (root / "fonts").is_dir():
        return []
    return sorted(p for p in (root / "fonts").rglob("*") if p.suffix.lower() in FONT_SUFFIXES)


def _extract_fonts(archive: Path, workdir: Path) -> list[Path]:
    """Abre el .dmg capa por capa (dmg → pkg → Payload → cpio) hasta hallar fuentes."""
    queue = [archive]
    for depth in range(6):
        nested = []
        for index, item in enumerate(queue):
            out = workdir / f"capa{depth}-{index}"
            subprocess.run(["7z", "x", "-y", f"-o{out}", str(item)], capture_output=True)
            fonts = [p for p in out.rglob("*") if p.suffix.lower() in FONT_SUFFIXES]
            if fonts:
                return fonts
            nested += [p for p in out.rglob("*") if p.is_file() and (
                p.suffix.lower() in (".pkg", ".dmg", ".hfs", ".gz", ".cpio", ".xar") or p.name.startswith("Payload"))]
        queue = nested
        if not queue:
            break
    return []


def _apple_fonts(log) -> list[Path]:
    if shutil.which("7z") is None:
        deps.install(["7zip"], log)
    found: list[Path] = []
    for name, url in APPLE_FONTS.items():
        folder = WORK_DIR / name
        dmg = WORK_DIR / f"{name}.dmg"
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        if not dmg.exists():
            log(_("Downloading {name} from {source}").format(name=name, source="apple.com"))
            with urllib.request.urlopen(url, timeout=600) as response, open(dmg, "wb") as out:
                shutil.copyfileobj(response, out)
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        fonts = _extract_fonts(dmg, folder)
        log(_("{name}: {count} fonts extracted").format(name=name, count=len(fonts)))
        found += fonts
    return found


def install(dry_run: bool, log) -> None:
    fonts = _local_fonts()
    source = _("your resources folder")
    if not fonts:
        source = "apple.com"
        if dry_run:
            log(_("No local fonts: SF Pro and SF Mono would be downloaded from apple.com"))
            return
        fonts = _apple_fonts(log)
    log(_("SF fonts: {count} files from {source}").format(count=len(fonts), source=source))
    if dry_run:
        return
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for font in fonts:
        target = FONT_DIR / font.name
        if not target.exists() or target.stat().st_size != font.stat().st_size:
            shutil.copy2(font, target)
    subprocess.run(["fc-cache", "-f", str(FONT_DIR)], check=False)


def remove(dry_run: bool, log) -> None:
    if FONT_DIR.exists():
        log(_("Remove {path}").format(path=FONT_DIR))
        if not dry_run:
            shutil.rmtree(FONT_DIR)

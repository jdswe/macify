"""Fuentes de Macify: Inter (interfaz) y JetBrains Mono (monoespaciada).

Ambas van incluidas en el proyecto en macify/data/fonts y se licencian bajo la
SIL Open Font License 1.1 (ver macify/data/fonts/OFL.txt). Macify no descarga
fuentes de terceros ni usa fuentes propietarias.
"""

import shutil
import subprocess
from pathlib import Path

from .i18n import _
from .assets import HOME

FONT_DIR = HOME / ".local" / "share" / "fonts" / "macify"
LEGACY_FONT_DIR = HOME / ".local" / "share" / "fonts" / "macify-sf"  # fonts from older versions
FONT_SUFFIXES = {".otf", ".ttf"}


BUNDLED_DIR = Path(__file__).parent / "data" / "fonts"


def _bundled_fonts() -> list[Path]:
    return sorted(p for p in BUNDLED_DIR.iterdir() if p.suffix.lower() in FONT_SUFFIXES)


def install(dry_run: bool, log) -> None:
    fonts = _bundled_fonts()
    log(_("Fonts: {count} files included with Macify (SIL Open Font License)").format(count=len(fonts)))
    if dry_run:
        return
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for font in fonts:
        target = FONT_DIR / font.name
        if not target.exists() or target.stat().st_size != font.stat().st_size:
            shutil.copy2(font, target)
    subprocess.run(["fc-cache", "-f", str(FONT_DIR)], check=False)


def remove(dry_run: bool, log) -> None:
    for folder in (FONT_DIR, LEGACY_FONT_DIR):
        if folder.exists():
            log(_("Remove {path}").format(path=folder))
            if not dry_run:
                shutil.rmtree(folder)

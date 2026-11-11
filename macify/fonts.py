"""Install the bundled, freely redistributable Inter and JetBrains Mono fonts."""

import shutil
import subprocess
from pathlib import Path

from .assets import HOME
from .i18n import _

FONT_DIR = HOME / ".local" / "share" / "fonts" / "macify"
LEGACY_FONT_DIR = HOME / ".local" / "share" / "fonts" / "macify-sf"
BUNDLED_DIR = Path(__file__).parent / "data" / "fonts"
FONT_FILES = ("Inter-Regular.otf", "Inter-SemiBold.otf", "JetBrainsMono-Regular.ttf")


def install(dry_run: bool, log) -> None:
    fonts = [BUNDLED_DIR / name for name in FONT_FILES]
    missing = [font.name for font in fonts if not font.is_file()]
    if missing:
        raise FileNotFoundError(_("Bundled font files are missing: {files}").format(files=", ".join(missing)))
    log(_("Installing bundled fonts: {count} files").format(count=len(fonts)))
    if dry_run:
        return
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for font in fonts:
        target = FONT_DIR / font.name
        if not target.exists() or target.stat().st_size != font.stat().st_size:
            shutil.copy2(font, target)
    for pattern in ("SF-Pro*", "SF-Mono*"):
        for legacy_font in FONT_DIR.glob(pattern):
            legacy_font.unlink()
        for legacy_font in LEGACY_FONT_DIR.glob(pattern):
            legacy_font.unlink()
    if LEGACY_FONT_DIR.exists():
        LEGACY_FONT_DIR.rmdir()
    subprocess.run(["fc-cache", "-f", str(FONT_DIR)], check=True)
    if LEGACY_FONT_DIR.exists():
        subprocess.run(["fc-cache", "-f", str(LEGACY_FONT_DIR)], check=True)


def remove(dry_run: bool, log) -> None:
    for folder in (FONT_DIR, LEGACY_FONT_DIR):
        if folder.exists():
            log(_("Remove {path}").format(path=folder))
            if not dry_run:
                shutil.rmtree(folder)

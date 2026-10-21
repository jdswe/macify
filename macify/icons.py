"""Tema de iconos «Macify»: nunca deja iconos rotos y crea los que faltan.

- Hereda del tema estilo Mac instalado (WhiteSur, o Colloid como respaldo),
  luego de Adwaita y hicolor: cualquier icono que falte cae en uno que existe.
- Para cada app sin icono estilo Mac genera uno nuevo: el icono original
  sobre un «squircle» con el tamaño y la forma de los iconos de macOS.
- Las apps snap apuntan a una imagen fija; para ellas se crea una copia del
  lanzador en ~/.local/share/applications que usa el icono nuevo.
"""

import configparser
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .i18n import _

HOME = Path.home()
THEME_NAME = "Macify"
THEME_DIR = HOME / ".local" / "share" / "icons" / THEME_NAME
ICON_SIZE = 512
OVERRIDES_DIR = HOME / ".local" / "share" / "applications"
OVERRIDE_MARK = "X-Macify-Override=true"
OWN_ICONS = {"dev.macify.Macify"}     # ya tienen forma de macOS

ICON_ROOTS = [HOME / ".local" / "share" / "icons", HOME / ".icons", Path("/usr/share/icons"),
              HOME / ".local" / "share" / "flatpak" / "exports" / "share" / "icons",
              Path("/var/lib/flatpak/exports/share/icons"), Path("/usr/share/pixmaps")]
APP_DIRS = [OVERRIDES_DIR, Path("/var/lib/snapd/desktop/applications"),
            HOME / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
            Path("/var/lib/flatpak/exports/share/applications"),
            Path("/usr/local/share/applications"), Path("/usr/share/applications")]
MAC_THEMES = ["WhiteSur-dark", "WhiteSur", "Colloid-Purple"]


def base_theme() -> str:
    """El tema estilo Mac más completo que esté instalado."""
    for name in MAC_THEMES:
        if any((root / name / "index.theme").exists() for root in ICON_ROOTS):
            return name
    return "Adwaita"


def mac_theme_ready() -> bool:
    """El set estilo Mac está completo (no a medio instalar ni ausente)."""
    return base_theme() == MAC_THEMES[0] and len(_theme_stems(MAC_THEMES[0])) > 5000


def ensure_theme(dry_run: bool, log) -> None:
    """Crea el tema Macify con una cadena de herencia sin huecos."""
    inherits = [base_theme(), "Adwaita", "hicolor"]
    log(_("Icon theme {theme}: inherits from {parents}").format(theme=THEME_NAME, parents=", ".join(inherits)))
    if dry_run:
        return
    (THEME_DIR / "apps" / str(ICON_SIZE)).mkdir(parents=True, exist_ok=True)
    _write_if_changed(THEME_DIR / "index.theme",
        "[Icon Theme]\n"
        f"Name={THEME_NAME}\n"
        "Comment=macOS-style icons made by Macify\n"
        f"Inherits={','.join(inherits)}\n"
        f"Directories=apps/{ICON_SIZE}\n\n"
        f"[apps/{ICON_SIZE}]\n"
        f"Size={ICON_SIZE}\nMinSize=16\nMaxSize=1024\nType=Scalable\nContext=Applications\n")


def _write_if_changed(path: Path, text: str) -> bool:
    """Escribe sólo si el contenido cambia (menos escrituras, menos avisos a GNOME)."""
    if path.exists() and path.read_text(errors="ignore") == text:
        return False
    path.write_text(text)
    return True


# ----- búsqueda de iconos -----
#
# El vigilante corre como proceso nuevo cada vez, así que nada puede depender de
# recorrer todas las carpetas de iconos: los nombres de cada tema se guardan en
# disco (se releen sólo si el tema cambia) y el icono original de una app se busca
# primero en las rutas estándar, comprobando archivos concretos.

STEMS_CACHE = HOME / ".cache" / "macify" / "icon-stems.json"
HICOLOR_SIZES = ["scalable", "512x512", "256x256", "192x192", "128x128", "96x96", "64x64", "48x48"]
_STEMS: dict[str, set[str]] = {}


def _theme_dirs(theme: str) -> list[Path]:
    return [root / theme for root in ICON_ROOTS if (root / theme).is_dir()]


def _theme_key(theme: str) -> list:
    """Cambia cuando el tema se reinstala o cambian sus carpetas de primer nivel."""
    key = []
    for folder in _theme_dirs(theme):
        key.append([str(folder), folder.stat().st_mtime_ns])
        key += [[entry.path, entry.stat().st_mtime_ns] for entry in os.scandir(folder) if entry.is_dir()]
    return key


def _theme_stems(theme: str) -> set[str]:
    """Nombres de icono de un tema. Sigue enlaces: WhiteSur-dark enlaza sus carpetas a WhiteSur."""
    if theme in _STEMS:
        return _STEMS[theme]
    key = _theme_key(theme)
    try:
        cache = json.loads(STEMS_CACHE.read_text())
    except (OSError, ValueError):
        cache = {}
    if cache.get(theme, {}).get("key") == key:
        stems = set(cache[theme]["stems"])
    else:
        stems = set()
        for folder in _theme_dirs(theme):
            for _dirpath, _dirs, files in os.walk(folder, followlinks=True):
                stems.update(name.rsplit(".", 1)[0] for name in files if name.endswith((".svg", ".png")))
        cache[theme] = {"key": key, "stems": sorted(stems)}
        try:
            STEMS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            STEMS_CACHE.write_text(json.dumps(cache))
        except OSError:
            pass
    _STEMS[theme] = stems
    return stems


def _score(path: Path) -> int:
    if "symbolic" in path.name:
        return -1
    if path.suffix == ".svg":
        return 10_000
    return max((int(part.split("x")[0]) for part in path.parts if part.split("x")[0].isdigit()), default=0)


def _find_source(icon: str) -> Path | None:
    """Mejor archivo original para un icono: rutas estándar primero, búsqueda completa al final."""
    for root in ICON_ROOTS:
        for size in HICOLOR_SIZES:
            for suffix in (".svg", ".png"):
                candidate = root / "hicolor" / size / "apps" / f"{icon}{suffix}"
                if candidate.is_file():
                    return candidate
    for suffix in (".svg", ".png"):
        candidate = Path("/usr/share/pixmaps") / f"{icon}{suffix}"
        if candidate.is_file():
            return candidate
    best, best_score = None, -1
    for root in ICON_ROOTS:
        if root.is_dir():
            for path in root.rglob(f"{icon}.*"):
                if path.suffix in (".svg", ".png") and THEME_NAME not in path.parts and _score(path) > best_score:
                    best, best_score = path, _score(path)
    return best


def _render(source: Path, size: int) -> Image.Image:
    if source.suffix == ".svg":
        import gi

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(source), size, size, True)
        ok, data = pixbuf.save_to_bufferv("png", [], [])
        return Image.open(io.BytesIO(data)).convert("RGBA")
    image = Image.open(source).convert("RGBA")
    image.thumbnail((size, size), Image.LANCZOS)
    return image


def _plate_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    """Si el icono ya es una placa sólida (cuadrado con fondo propio), su recuadro."""
    alpha = image.getchannel("A").point(lambda a: 255 if a > 200 else 0)
    box = alpha.getbbox()
    if not box:
        return None
    w, h = image.size
    bw, bh = box[2] - box[0], box[3] - box[1]
    if bw < 0.7 * w or bh < 0.7 * h or abs(bw - bh) > 0.08 * max(bw, bh):
        return None
    filled = sum(1 for a in _pixels(alpha.crop(box)) if a) / (bw * bh)
    return box if filled > 0.82 else None


def _pixels(image: Image.Image):
    """Píxeles de la imagen (getdata desaparece en Pillow 14)."""
    return image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()


def _is_light(image: Image.Image) -> bool:
    """True si el dibujo es casi blanco: entonces necesita un fondo oscuro."""
    small = image.resize((48, 48))
    pixels = [(r, g, b) for r, g, b, a in _pixels(small) if a > 128]
    if not pixels:
        return False
    luminance = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels) / (255 * len(pixels))
    return luminance > 0.72


def _background(canvas: int, dark: bool) -> Image.Image:
    gradient = Image.new("RGBA", (canvas, canvas))
    draw = ImageDraw.Draw(gradient)
    for y in range(canvas):
        t = y / canvas
        tone = int(78 - 40 * t) if dark else int(252 - 22 * t)
        draw.line([(0, y), (canvas, y)], fill=(tone, tone, min(255, tone + 6), 255))
    return gradient


def mac_icon(source: Path) -> Image.Image:
    """Icono estilo macOS: forma redondeada de macOS con el icono original encima."""
    canvas = ICON_SIZE
    body = int(canvas * 0.805)            # proporción de la rejilla de iconos de macOS
    margin = (canvas - body) // 2
    radius = int(body * 0.225)

    mask = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle((margin, margin, margin + body, margin + body), radius, fill=255)

    shadow = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    shadow.paste((10, 10, 30, 255), (0, int(canvas * 0.02)), mask.point(lambda a: int(a * 0.35)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(canvas * 0.02))
    result = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    result.alpha_composite(shadow)

    art = _render(source, ICON_SIZE)
    plate = _plate_box(art)
    if plate:
        # El icono ya trae su propio fondo: ocupa toda la forma de macOS.
        filled = art.crop(plate).resize((body, body), Image.LANCZOS)
        layer = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        layer.paste(filled, (margin, margin))
        result.paste(layer, (0, 0), mask)
    else:
        result.paste(_background(canvas, dark=_is_light(art)), (0, 0), mask)
        inner = int(body * 0.68)
        art.thumbnail((inner, inner), Image.LANCZOS)
        result.alpha_composite(art, ((canvas - art.width) // 2, (canvas - art.height) // 2))

    ImageDraw.Draw(result).rounded_rectangle((margin, margin, margin + body, margin + body), radius,
                                             outline=(255, 255, 255, 90), width=max(2, canvas // 256))
    return result


# ----- lanzadores -----

def _read_entry(path: Path) -> configparser.SectionProxy | None:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return None
    if "Desktop Entry" not in parser:
        return None
    entry = parser["Desktop Entry"]
    if entry.get("NoDisplay") == "true" or entry.get("Hidden") == "true" or entry.get("Type") != "Application":
        return None
    return entry


def app_entries() -> dict[str, Path]:
    """Lanzadores visibles: el primero de cada id gana (el del usuario primero)."""
    found: dict[str, Path] = {}
    for folder in APP_DIRS:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.desktop")):
            if path.name in found:
                continue
            if folder == OVERRIDES_DIR and OVERRIDE_MARK in path.read_text(errors="ignore"):
                continue  # nuestra copia: se mira el original
            found[path.name] = path
    return found


def _override_text(source: Path, icon_name: str) -> str:
    lines = source.read_text(errors="ignore").splitlines()
    out, in_entry, replaced = [], False, False
    for line in lines:
        if line.startswith("["):
            in_entry = line.strip() == "[Desktop Entry]"
            out.append(line)
            if in_entry:
                out.append(OVERRIDE_MARK)
            continue
        if in_entry and not replaced and line.startswith("Icon="):
            out.append(f"Icon={icon_name}")
            replaced = True
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def _draw(source: Path, target: Path) -> bool:
    """Dibuja el icono sólo si falta o si el original cambió después."""
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return False
    mac_icon(source).save(target)
    return True


def generate(dry_run: bool, log) -> int:
    """Crea iconos estilo Mac para las apps que no tienen uno. Devuelve cuántas apps lo usan.

    Es incremental: no rehace lo que ya está al día y borra sólo lo que sobra.
    """
    mac = _theme_stems(base_theme()) if base_theme() != "Adwaita" else set()
    folder = THEME_DIR / "apps" / str(ICON_SIZE)
    icons_wanted: set[str] = set()
    overrides_wanted: set[str] = set()
    handled = 0
    changed = False
    for desktop_id, path in app_entries().items():
        entry = _read_entry(path)
        if entry is None or not entry.get("Icon") or entry["Icon"] in OWN_ICONS:
            continue
        icon = entry["Icon"]
        stem = desktop_id.removesuffix(".desktop")
        app = entry.get("Name", stem)
        if icon.startswith("/"):
            # Snap y similares: imagen fija. Se usa un nombre del tema si existe.
            if path.parent == OVERRIDES_DIR:
                continue  # lanzador propio del usuario: no se toca
            alias = next((n for n in (stem.split("_")[0], stem, entry.get("Name", "").lower()) if n in mac), None)
            name = alias or f"macify-{stem}"
            log(_("{app}: fixed image icon → {name}").format(app=app, name=name))
            handled += 1
            overrides_wanted.add(desktop_id)
            if alias is None and Path(icon).exists():
                icons_wanted.add(name)
                if not dry_run:
                    changed |= _draw(Path(icon), folder / f"{name}.png")
            if not dry_run:
                OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
                changed |= _write_if_changed(OVERRIDES_DIR / desktop_id, _override_text(path, name))
        elif icon not in mac:
            source = _find_source(icon)
            if source is None:
                continue
            log(_("{app}: no macOS-style icon → created").format(app=app))
            handled += 1
            icons_wanted.add(icon)
            if not dry_run:
                changed |= _draw(source, folder / f"{icon}.png")
    if not dry_run:
        changed |= _prune(folder, icons_wanted, overrides_wanted, log)
        if changed and shutil.which("gtk-update-icon-cache"):
            subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(THEME_DIR)], capture_output=True)
    return handled


def _prune(folder: Path, icons_wanted: set[str], overrides_wanted: set[str], log) -> bool:
    """Borra iconos generados y lanzadores de Macify que ya no hacen falta."""
    removed = False
    if folder.is_dir():
        for png in folder.glob("*.png"):
            if png.stem not in icons_wanted:
                png.unlink()
                removed = True
    if OVERRIDES_DIR.is_dir():
        for launcher in OVERRIDES_DIR.glob("*.desktop"):
            if launcher.name not in overrides_wanted and OVERRIDE_MARK in launcher.read_text(errors="ignore"):
                log(_("Remove launcher {path}").format(path=launcher))
                launcher.unlink()
                removed = True
    return removed


def remove(dry_run: bool, log) -> None:
    """Borra el tema Macify y sólo las copias de lanzadores que marcó Macify."""
    if THEME_DIR.exists():
        log(_("Remove {path}").format(path=THEME_DIR))
        if not dry_run:
            shutil.rmtree(THEME_DIR)
    if OVERRIDES_DIR.is_dir():
        for path in OVERRIDES_DIR.glob("*.desktop"):
            if OVERRIDE_MARK in path.read_text(errors="ignore"):
                log(_("Remove launcher {path}").format(path=path))
                if not dry_run:
                    path.unlink()


# ----- auditoría -----

def _theme_chain(name: str, seen: set[str] | None = None) -> list[str]:
    """El tema y todos los que hereda, en orden, como los resuelve GTK."""
    seen = seen if seen is not None else set()
    if name in seen:
        return []
    seen.add(name)
    chain = [name]
    for root in ICON_ROOTS:
        index = root / name / "index.theme"
        if index.exists():
            for line in index.read_text(errors="ignore").splitlines():
                if line.startswith("Inherits="):
                    for parent in line.split("=", 1)[1].split(","):
                        chain += _theme_chain(parent.strip(), seen)
            break
    if "hicolor" not in chain:
        chain.append("hicolor")
    return chain


def audit(theme: str = THEME_NAME) -> dict[str, list[str]]:
    """Comprueba que cada icono que usan las apps se encuentre en la cadena del tema.

    Devuelve {"missing_apps": [...], "chain": [...]} para mostrarlo al usuario.
    """
    chain = _theme_chain(theme)
    available: set[str] = set()
    for name in chain:
        available |= _theme_stems(name)
    available |= {p.stem for p in Path("/usr/share/pixmaps").glob("*")}
    missing = []
    for desktop_id, path in app_entries().items():
        entry = _read_entry(path)
        if entry is None or not entry.get("Icon"):
            continue
        icon = entry["Icon"]
        if icon.startswith("/"):
            if not Path(icon).exists():
                missing.append(f"{entry.get('Name', desktop_id)} ({icon})")
        elif icon not in available:
            missing.append(f"{entry.get('Name', desktop_id)} ({icon})")
    return {"missing_apps": missing, "chain": chain}

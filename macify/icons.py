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


def ensure_theme(dry_run: bool, log) -> None:
    """Crea el tema Macify con una cadena de herencia sin huecos."""
    inherits = [base_theme(), "Adwaita", "hicolor"]
    log(_("Icon theme {theme}: inherits from {parents}").format(theme=THEME_NAME, parents=", ".join(inherits)))
    if dry_run:
        return
    # Se regenera desde cero: un icono viejo no debe tapar al del tema estilo Mac.
    shutil.rmtree(THEME_DIR / "apps", ignore_errors=True)
    (THEME_DIR / "apps" / str(ICON_SIZE)).mkdir(parents=True, exist_ok=True)
    (THEME_DIR / "index.theme").write_text(
        "[Icon Theme]\n"
        f"Name={THEME_NAME}\n"
        "Comment=macOS-style icons made by Macify\n"
        f"Inherits={','.join(inherits)}\n"
        f"Directories=apps/{ICON_SIZE}\n\n"
        f"[apps/{ICON_SIZE}]\n"
        f"Size={ICON_SIZE}\nMinSize=16\nMaxSize=1024\nType=Scalable\nContext=Applications\n"
    )


# ----- búsqueda de iconos -----

def _theme_stems(theme: str) -> set[str]:
    """Nombres de icono de un tema. Sigue enlaces: WhiteSur-dark enlaza sus carpetas a WhiteSur."""
    stems: set[str] = set()
    for root in ICON_ROOTS:
        folder = root / theme
        if folder.is_dir():
            for _dirpath, _dirs, files in os.walk(folder, followlinks=True):
                stems.update(name.rsplit(".", 1)[0] for name in files if name.endswith((".svg", ".png")))
    return stems


def _find_source(icon: str) -> Path | None:
    """Archivo más grande disponible para un nombre de icono, en cualquier tema."""
    best, best_score = None, -1
    for root in ICON_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob(f"{icon}.*"):
            if path.suffix not in (".svg", ".png") or THEME_NAME in path.parts:
                continue
            score = 10_000 if path.suffix == ".svg" else max(
                (int(part.split("x")[0]) for part in path.parts if part.split("x")[0].isdigit()), default=0)
            if "symbolic" in path.name:
                score = -1
            if score > best_score:
                best, best_score = path, score
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


def _write_override(source: Path, icon_name: str) -> None:
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
    OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    (OVERRIDES_DIR / source.name).write_text("\n".join(out) + "\n")


def generate(dry_run: bool, log) -> int:
    """Crea iconos estilo Mac para las apps que no tienen uno. Devuelve cuántos."""
    mac = _theme_stems(base_theme()) if base_theme() != "Adwaita" else set()
    created = 0
    for desktop_id, path in app_entries().items():
        entry = _read_entry(path)
        if entry is None or not entry.get("Icon"):
            continue
        icon = entry["Icon"]
        stem = desktop_id.removesuffix(".desktop")
        if icon in OWN_ICONS:
            continue
        if icon.startswith("/"):
            # Snap y similares: imagen fija. Se usa un nombre del tema si existe.
            alias = next((n for n in (stem.split("_")[0], stem, entry.get("Name", "").lower()) if n in mac), None)
            name = alias or f"macify-{stem}"
            source = Path(icon)
            if path.parent == OVERRIDES_DIR:
                continue  # lanzador propio del usuario: no se toca
            log(_("{app}: fixed image icon → {name}").format(app=entry.get("Name", stem), name=name))
            if not dry_run:
                if alias is None and source.exists():
                    mac_icon(source).save(THEME_DIR / "apps" / str(ICON_SIZE) / f"{name}.png")
                _write_override(path, name)
            created += 1
        elif icon not in mac:
            source = _find_source(icon)
            if source is None:
                continue
            log(_("{app}: no macOS-style icon → created").format(app=entry.get("Name", stem)))
            if not dry_run:
                mac_icon(source).save(THEME_DIR / "apps" / str(ICON_SIZE) / f"{icon}.png")
            created += 1
    if not dry_run and shutil.which("gtk-update-icon-cache"):
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(THEME_DIR)], capture_output=True)
    return created


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

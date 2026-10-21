"""Rutas de Macify: configuración, caché, datos propios y recursos del usuario."""

import json
import os
from importlib import resources
from pathlib import Path

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "macify"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = HOME / ".cache" / "macify"
DATA_DIR = HOME / ".local" / "share" / "macify"
WALLPAPER_DIR = DATA_DIR / "wallpapers"
LEGACY_WALLPAPERS = ("amanecer.jpg", "azul.jpg", "atardecer.jpg")   # nombres de versiones anteriores


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except ValueError:
            return {}
    return {}


def save_config_value(key: str, value) -> None:
    config = load_config()
    config[key] = value
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))


def assets_root() -> Path | None:
    """Carpeta opcional con recursos propios del usuario (fuentes, fondos).

    Orden: variable MACIFY_ASSETS, «assets_dir» de la configuración y,
    al ejecutar desde el proyecto, la carpeta que contiene la app.
    """
    candidates = []
    if os.environ.get("MACIFY_ASSETS"):
        candidates.append(Path(os.environ["MACIFY_ASSETS"]))
    if load_config().get("assets_dir"):
        candidates.append(Path(load_config()["assets_dir"]))
    candidates.append(Path(__file__).resolve().parents[2])
    for path in candidates:
        if (path / "fonts").is_dir() or (path / "wallpapers").is_dir():
            return path
    return None


def save_assets_dir(path: Path) -> None:
    save_config_value("assets_dir", str(path))


def install_bundled_data() -> None:
    """Copia los fondos incluidos en la app a ~/.local/share/macify (archivos reales)."""
    WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    for name in LEGACY_WALLPAPERS:
        (WALLPAPER_DIR / name).unlink(missing_ok=True)
    for item in resources.files("macify").joinpath("data", "wallpapers").iterdir():
        target = WALLPAPER_DIR / item.name
        if not target.exists():
            target.write_bytes(item.read_bytes())


def user_wallpaper() -> Path | None:
    value = load_config().get("wallpaper")
    return Path(value) if value and Path(value).is_file() else None


# Mientras instala o repara, Macify deja una marca; el vigilante de apps nuevas
# espera a que desaparezca para no generar iconos con los temas a medio instalar.
BUSY_FILE = CACHE_DIR / ".busy"
BUSY_MAX_AGE = 30 * 60   # segundos: una marca más vieja es de un proceso que se cortó


class busy:
    def __enter__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        BUSY_FILE.write_text(str(os.getpid()))
        return self

    def __exit__(self, *_exc):
        BUSY_FILE.unlink(missing_ok=True)


def is_busy() -> bool:
    import time

    return BUSY_FILE.exists() and time.time() - BUSY_FILE.stat().st_mtime < BUSY_MAX_AGE

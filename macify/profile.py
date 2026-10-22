"""Perfil estilo macOS: las elecciones del usuario y los ajustes de GNOME que producen.

Los valores usan el formato de texto GVariant que entiende `gsettings set`.
Las claves que no existan en el sistema se omiten al aplicar (ver system.py).
"""

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .assets import CONFIG_DIR, WALLPAPER_DIR, load_config, save_config_value
from .colors import accent_for_wallpaper, glass_tint, top_brightness

DEFAULT_WALLPAPER = "lilac.jpg"       # con su versión oscura, lilac-dark.jpg


def q(text: str) -> str:
    """String GVariant: 'texto'."""
    return "'" + text.replace("'", "\\'") + "'"


def q_list(*items: str) -> str:
    """Lista GVariant de strings: ['a', 'b']."""
    return "[" + ", ".join(q(item) for item in items) + "]"


@dataclass
class Choices:
    appearance: str = "dark"        # "dark" o "light"
    wallpaper: str = ""             # ruta elegida; vacío = fondo incluido por defecto
    dock_size: int = 48
    magnify: bool = True            # ampliar iconos del dock al pasar el ratón
    magic_lamp: bool = True         # efecto lámpara mágica al minimizar
    dock_autohide: bool = True      # se esconde cuando una ventana lo tapa; reaparece en el borde inferior
    login_screen: bool = True       # arranque e inicio de sesión estilo macOS (pide contraseña)


def load_choices() -> Choices:
    saved = load_config().get("choices", {})
    known = {f.name for f in fields(Choices)}
    return Choices(**{k: v for k, v in saved.items() if k in known})


def save_choices(choices: Choices) -> None:
    save_config_value("choices", asdict(choices))


def wallpaper_path(choices: Choices) -> Path:
    chosen = Path(choices.wallpaper) if choices.wallpaper else None
    return chosen if chosen and chosen.is_file() else WALLPAPER_DIR / DEFAULT_WALLPAPER


def dark_variant(path: Path) -> Path:
    """«nombre-dark.jpg» junto a «nombre.jpg» es su versión oscura, como en los fondos de macOS."""
    twin = path.with_name(f"{path.stem}-dark{path.suffix}")
    return twin if twin.is_file() else path


def desktop_wallpaper(choices: Choices) -> Path:
    """El fondo que se ve: la versión oscura con el aspecto oscuro, si la hay."""
    path = wallpaper_path(choices)
    return dark_variant(path) if choices.appearance == "dark" else path


def accent(choices: Choices) -> str:
    wallpaper = desktop_wallpaper(choices)
    return accent_for_wallpaper(wallpaper) if wallpaper.exists() else "blue"


LOOK_FILE = CONFIG_DIR / "look.json"
BRIGHT_BAR = 0.62          # con un fondo más claro que esto arriba, la barra usa texto oscuro


def _bar_text(wallpaper: Path) -> str:
    return "dark-text" if wallpaper.exists() and top_brightness(wallpaper) > BRIGHT_BAR else "light-text"


def look(choices: Choices) -> dict:
    """Lo que Macify Menubar ajusta en vivo: el texto de la barra según el fondo de cada aspecto,
    y el aspecto aplicado (si se cambia desde el Centro de control, Macify lo sigue)."""
    light = wallpaper_path(choices)
    return {"appearance": choices.appearance,
            "bar": {"light": _bar_text(light), "dark": _bar_text(dark_variant(light))}}


def write_look(choices: Choices) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOOK_FILE.write_text(json.dumps(look(choices)))


def _tuple(values) -> str:
    return "(" + ", ".join(str(v) for v in values) + ")"


# Dash2Dock Animated elige el tamaño por posición en esta lista (ver dock.js de la extensión).
DOCK_ICON_SIZES = [32, *range(16, 129, 4)]
DOCK_DOT_INDICATOR = 2      # opción «dot»: un punto bajo la app abierta, como en macOS
DOCK_RADIUS_24PX = 4        # posición de 24 px en su lista de radios


def _blur(name: str, effect: str, radius: int, brightness: float) -> str:
    params = f"{{'unscaled_radius': <{radius}>, 'brightness': <{brightness}>}}"
    effects = f"[<{{'type': <'dual_kawase_blur'>, 'id': <'{effect}'>, 'params': <{params}>}}>]"
    return f"{{'name': <'{name}'>, 'effects': <{effects}>}}"


BLUR_PIPELINES = ("{'pipeline_default': " + _blur("Default", "effect_000000000000", 30, 0.6)
                  + ", 'pipeline_macify': " + _blur("Macify", "effect_macify_overview", 90, 0.8) + "}")


def dock_icon_size(pixels: int) -> str:
    pixels = min(DOCK_ICON_SIZES[1:], key=lambda size: abs(size - pixels))   # el tamaño válido más cercano
    index = DOCK_ICON_SIZES.index(pixels)
    return f"{(index + 0.5) / len(DOCK_ICON_SIZES):.4f}"


def settings(choices: Choices) -> dict:
    dark = choices.appearance == "dark"
    variant = "Dark" if dark else "Light"
    light = wallpaper_path(choices)
    uri = q("file://" + str(light))
    dark_uri = q("file://" + str(dark_variant(light)))
    shown = q("file://" + str(desktop_wallpaper(choices)))
    glass = glass_tint(desktop_wallpaper(choices), dark) if light.exists() else (
        (0.12, 0.12, 0.14, 0.35) if dark else (1.0, 1.0, 1.0, 0.35))
    return {
        "org.gnome.desktop.interface": {
            "gtk-theme": q(f"WhiteSur-{variant}-alt"),
            "icon-theme": q("Macify"),
            "cursor-theme": q("WhiteSur-cursors"),
            "font-name": q("SF Pro Text 11"),
            "document-font-name": q("SF Pro Text 11"),
            "monospace-font-name": q("SF Mono 11"),
            "color-scheme": q("prefer-dark" if dark else "prefer-light"),
            "accent-color": q(accent(choices)),
            "enable-animations": "true",
            "clock-show-date": "true",
            "clock-show-weekday": "true",
            "clock-show-seconds": "false",
            "clock-format": q("12h"),                  # «mié 21 oct 4:05 p. m.», como macOS
            "show-battery-percentage": "false",       # como macOS: sólo el icono
        },
        "org.gnome.desktop.wm.preferences": {
            "button-layout": q("close,minimize,maximize:"),
            "titlebar-font": q("SF Pro Text Semibold 11"),
            "theme": q(f"WhiteSur-{variant}-alt"),
        },
        "org.gnome.desktop.background": {
            "picture-uri": uri,
            "picture-uri-dark": dark_uri,           # con «-dark» al lado, cambia con el aspecto
            "picture-options": q("zoom"),
        },
        "org.gnome.desktop.screensaver": {
            "picture-uri": shown,
            "picture-options": q("zoom"),
            "lock-enabled": "true",
        },
        "org.gnome.desktop.sound": {"event-sounds": "true"},
        # Cmd (Super) + Tab cambia de app; Cmd + ` entre ventanas de la misma app.
        "org.gnome.desktop.wm.keybindings": {
            "switch-applications": q_list("<Super>Tab"),
            "switch-applications-backward": q_list("<Shift><Super>Tab"),
            "switch-group": q_list("<Super>grave"),
            "switch-group-backward": q_list("<Shift><Super>grave"),
        },
        "org.gnome.Ptyxis": {
            "use-system-font": "false",
            "font-name": q("SF Mono 12"),
        },
        # Extensiones: tema del Shell, barra superior y cristal.
        "org.gnome.shell.extensions.user-theme": {"name": q(f"WhiteSur-{variant}-alt")},
        "org.gnome.shell.extensions.just-perfection": {
            "activities-button": "false",       # sin la píldora de Ubuntu
            "clock-menu-position": "1",         # reloj a la derecha, como macOS
            "clock-menu-position-offset": "20",  # y al final, después de los iconos de estado
            "startup-status": "0",              # arrancar en el escritorio
            "workspace-popup": "false",
            "ripple-box": "false",
            "panel-size": "28",                 # barra delgada, como la de macOS
            "workspaces-in-app-grid": "false",  # «Apps» de macOS: sólo las apps, sin escritorios
        },
        # «Apps» (la vista de aplicaciones) sobre vidrio esmerilado, como en macOS 27: un desenfoque
        # propio más fuerte para la vista general, sin tocar el que usa Blur my Shell en lo demás.
        "org.gnome.shell.extensions.blur-my-shell": {"pipelines": BLUR_PIPELINES},
        "org.gnome.shell.extensions.blur-my-shell.overview": {"pipeline": q("pipeline_macify")},
        # La barra superior va transparente e integrada con el fondo (lo pinta Macify Menubar).
        "org.gnome.shell.extensions.blur-my-shell.panel": {"blur": "false"},
        # El dock animado hace su propio desenfoque; el módulo de Blur my Shell para
        # Dash to Dock falla con él («object.connect is not a function»).
        "org.gnome.shell.extensions.blur-my-shell.dash-to-dock": {"blur": "false"},
        "org.gnome.shell.extensions.dash2dock-lite": {
            "dock-location": "0",                       # abajo
            "autohide-dash": "true" if choices.dock_autohide else "false",
            "autohide-dodge": "true",                   # sólo se esconde cuando una ventana lo tapa
            "multi-monitor-preference": "1",            # un dock en cada pantalla
            "icon-size": dock_icon_size(choices.dock_size),
            "animate-icons": "true",
            "animation-magnify": "0.5" if choices.magnify else "0.0",
            "animation-spread": "0.6",
            "animation-rise": "0.2",
            "open-app-animation": "true",               # rebote al abrir una app
            "lamp-app-animation": "false",              # de eso se encarga Magic Lamp
            "blur-background": "true",
            # Cristal del aspecto elegido teñido con el fondo; en claro, un filo de luz más visible.
            "background-color": _tuple(glass),
            "border-radius": str(float(DOCK_RADIUS_24PX)),
            "border-thickness": "1",
            "border-color": "(1.0, 1.0, 1.0, 0.18)" if dark else "(1.0, 1.0, 1.0, 0.6)",
            "running-indicator-style": str(DOCK_DOT_INDICATOR),
            "icon-shadow": "true",
            "trash-icon": "true",
            "separator-thickness": "1",
            "separator-color": "(1.0, 1.0, 1.0, 0.25)" if dark else "(0.0, 0.0, 0.0, 0.15)",
            "notification-badge-style": "0",            # globo rojo con número (lo dibuja Macify Menubar)
            "notification-badge-color": "(1.0, 0.23, 0.19, 1.0)",
        },
        "org.gnome.shell.extensions.blur-my-shell.applications": {
            "blur": "true",
            "whitelist": q_list("dev.macify.Macify"),
        },
    }

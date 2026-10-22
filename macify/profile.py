"""Perfil estilo macOS: las elecciones del usuario y los ajustes de GNOME que producen.

Los valores usan el formato de texto GVariant que entiende `gsettings set`.
Las claves que no existan en el sistema se omiten al aplicar (ver system.py).
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .assets import WALLPAPER_DIR, load_config, save_config_value
from .colors import accent_for_wallpaper

DEFAULT_WALLPAPER = "dawn.jpg"


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


def accent(choices: Choices) -> str:
    wallpaper = wallpaper_path(choices)
    return accent_for_wallpaper(wallpaper) if wallpaper.exists() else "blue"


# Dash2Dock Animated elige el tamaño por posición en esta lista (ver dock.js de la extensión).
DOCK_ICON_SIZES = [32, *range(16, 129, 4)]
DOCK_DOT_INDICATOR = 2      # opción «dot»: un punto bajo la app abierta, como en macOS
DOCK_RADIUS_24PX = 4        # posición de 24 px en su lista de radios


def dock_icon_size(pixels: int) -> str:
    pixels = min(DOCK_ICON_SIZES[1:], key=lambda size: abs(size - pixels))   # el tamaño válido más cercano
    index = DOCK_ICON_SIZES.index(pixels)
    return f"{(index + 0.5) / len(DOCK_ICON_SIZES):.4f}"


def settings(choices: Choices) -> dict:
    dark = choices.appearance == "dark"
    variant = "Dark" if dark else "Light"
    uri = q("file://" + str(wallpaper_path(choices)))
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
            "show-battery-percentage": "true",
        },
        "org.gnome.desktop.wm.preferences": {
            "button-layout": q("close,minimize,maximize:"),
            "titlebar-font": q("SF Pro Text Semibold 11"),
            "theme": q(f"WhiteSur-{variant}-alt"),
        },
        "org.gnome.desktop.background": {
            "picture-uri": uri,
            "picture-uri-dark": uri,
            "picture-options": q("zoom"),
        },
        "org.gnome.desktop.screensaver": {
            "picture-uri": uri,
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
            "startup-status": "0",              # arrancar en el escritorio
            "workspace-popup": "false",
            "ripple-box": "false",
            "panel-size": "28",                 # barra delgada, como la de macOS
        },
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
            "background-color": "(0.12, 0.12, 0.14, 0.35)" if dark else "(1.0, 1.0, 1.0, 0.35)",
            "border-radius": str(float(DOCK_RADIUS_24PX)),
            "border-thickness": "1",
            "border-color": "(1.0, 1.0, 1.0, 0.18)",
            "running-indicator-style": str(DOCK_DOT_INDICATOR),
            "icon-shadow": "true",
            "trash-icon": "true",
            "separator-thickness": "1",
            "separator-color": "(1.0, 1.0, 1.0, 0.25)",
        },
        "org.gnome.shell.extensions.blur-my-shell.applications": {
            "blur": "true",
            "whitelist": q_list("dev.macify.Macify"),
        },
    }

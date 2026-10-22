"""Iconos de la barra superior al estilo de macOS, dibujados por Macify.

Batería horizontal con nivel y rayo de carga, abanico de Wi‑Fi por niveles, altavoz con
ondas según el volumen (y tachado al silenciarlo), Centro de control y lupa. Son iconos simbólicos de 16 px (GNOME los colorea como el resto de la
barra) con los nombres que usa GNOME, así que sustituyen a los del sistema sin tocar nada
más. Sólo se usan formas rellenas: el coloreado simbólico ignora los trazos.
"""

import math
from pathlib import Path

FOLDER = "status/symbolic"
DIM = 0.3


def _svg(body: str, defs: str = "") -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            f"{defs}{body}</svg>\n")


def _rounded(x: float, y: float, w: float, h: float, r: float) -> str:
    r = min(r, w / 2, h / 2)
    return (f"M{x + r:.2f},{y:.2f}H{x + w - r:.2f}A{r:.2f},{r:.2f} 0 0 1 {x + w:.2f},{y + r:.2f}"
            f"V{y + h - r:.2f}A{r:.2f},{r:.2f} 0 0 1 {x + w - r:.2f},{y + h:.2f}"
            f"H{x + r:.2f}A{r:.2f},{r:.2f} 0 0 1 {x:.2f},{y + h - r:.2f}"
            f"V{y + r:.2f}A{r:.2f},{r:.2f} 0 0 1 {x + r:.2f},{y:.2f}Z")


def _sector(cx: float, cy: float, inner: float, outer: float, half_angle: float = 45) -> str:
    """Trozo de anillo que abre hacia arriba (el abanico del Wi‑Fi)."""
    a0, a1 = math.radians(-90 - half_angle), math.radians(-90 + half_angle)

    def point(r, a):
        return f"{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f}"
    if inner <= 0:
        return f"M{cx:.2f},{cy:.2f}L{point(outer, a0)}A{outer:.2f},{outer:.2f} 0 0 1 {point(outer, a1)}Z"
    return (f"M{point(inner, a0)}L{point(outer, a0)}A{outer:.2f},{outer:.2f} 0 0 1 {point(outer, a1)}"
            f"L{point(inner, a1)}A{inner:.2f},{inner:.2f} 0 0 0 {point(inner, a0)}Z")


# ---------- batería ----------

BODY = (0.2, 3.6, 14.0, 8.8)        # x, y, ancho, alto: casi todo el ancho, como en macOS
BOLT = "M8.4,2.6 L4.6,8.4 H7.3 L6.5,13.4 L10.4,7.4 H7.6 Z"


def battery(level: int, charging: bool = False) -> str:
    x, y, w, h = BODY
    shell = _rounded(x, y, w, h, 2.6) + _rounded(x + 1.1, y + 1.1, w - 2.2, h - 2.2, 1.6)
    nub = _rounded(x + w + 0.4, y + 2.9, 1.2, h - 5.8, 0.6)
    inner_w = (w - 4.0) * max(0, min(level, 100)) / 100
    css = ""
    if charging:
        css = ' class="success"'
    elif level <= 10:
        css = ' class="error"'
    fill = _rounded(x + 2.0, y + 2.0, max(inner_w, 1.0), h - 4.0, 1.0) if level > 0 or charging else ""
    parts = [f'<path fill-rule="evenodd" d="{shell}"/>', f'<path opacity="0.45" d="{nub}"/>']
    if fill:
        parts.append(f'<path{css} d="{fill}"/>')
    if not charging:
        return _svg("".join(parts))
    # Rayo encima, con un hueco alrededor para que se lea sobre la batería.
    defs = ('<defs><mask id="m"><rect width="16" height="16" fill="#fff"/>'
            f'<path d="{BOLT}" fill="#000" stroke="#000" stroke-width="2.2" stroke-linejoin="round"/></mask></defs>')
    return _svg(f'<g mask="url(#m)">{"".join(parts)}</g><path d="{BOLT}"/>', defs)


def battery_icons() -> dict[str, str]:
    icons = {}
    for level in range(0, 101, 10):
        icons[f"battery-level-{level}-symbolic"] = battery(level)
        icons[f"battery-level-{level}-charging-symbolic"] = battery(level, charging=True)
    icons["battery-level-100-charged-symbolic"] = battery(100, charging=True)
    icons["battery-full-charged-symbolic"] = battery(100, charging=True)
    icons["battery-full-charging-symbolic"] = battery(100, charging=True)
    icons["battery-full-symbolic"] = battery(100)
    icons["battery-good-symbolic"] = battery(70)
    icons["battery-low-symbolic"] = battery(30)
    icons["battery-caution-symbolic"] = battery(10)
    icons["battery-empty-symbolic"] = battery(0)
    icons["battery-missing-symbolic"] = battery(0)
    return icons


# ---------- Wi‑Fi ----------

WIFI_CENTER = (8.0, 13.6)
WIFI_BANDS = [(0, 3.4), (5.0, 7.3), (8.9, 11.2)]


def wifi(bars: int) -> str:
    cx, cy = WIFI_CENTER
    parts = []
    for i, (inner, outer) in enumerate(WIFI_BANDS):
        opacity = "" if i < bars else f' opacity="{DIM}"'
        parts.append(f'<path{opacity} d="{_sector(cx, cy, inner, outer)}"/>')
    return _svg("".join(parts))


def wifi_icons() -> dict[str, str]:
    levels = {"excellent": 3, "good": 3, "ok": 2, "weak": 1, "none": 0}
    icons = {f"network-wireless-signal-{name}-symbolic": wifi(bars) for name, bars in levels.items()}
    for name in ("acquiring", "offline", "no-route", "disabled"):
        icons[f"network-wireless-{name}-symbolic"] = wifi(0)
    icons["network-wireless-connected-symbolic"] = wifi(3)
    icons["network-wireless-symbolic"] = wifi(3)
    return icons


# ---------- sonido ----------

SPEAKER = "M1.0,6.0 Q1.0,5.4 1.6,5.4 H3.8 L7.2,2.6 Q7.8,2.2 7.8,2.9 V13.1 Q7.8,13.8 7.2,13.4 L3.8,10.6 H1.6 Q1.0,10.6 1.0,10.0 Z"
SOUND_CENTER = (6.4, 8.0)
SOUND_WAVES = [(2.6, 3.8), (4.7, 5.9), (6.8, 8.0)]
MUTE_SLASH = "M1.6,1.2 L14.8,14.4 L13.7,15.5 L0.5,2.3 Z"


def _wave(cx: float, cy: float, inner: float, outer: float, half_angle: float = 42) -> str:
    """Onda del altavoz: trozo de anillo que abre hacia la derecha."""
    a0, a1 = math.radians(-half_angle), math.radians(half_angle)

    def point(r, a):
        return f"{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f}"
    return (f"M{point(inner, a0)}L{point(outer, a0)}A{outer:.2f},{outer:.2f} 0 0 1 {point(outer, a1)}"
            f"L{point(inner, a1)}A{inner:.2f},{inner:.2f} 0 0 0 {point(inner, a0)}Z")


def speaker(waves: int, muted: bool = False) -> str:
    cx, cy = SOUND_CENTER
    parts = [f'<path d="{SPEAKER}"/>']
    for i, (inner, outer) in enumerate(SOUND_WAVES):
        if muted:
            break
        opacity = "" if i < waves else f' opacity="{DIM}"'
        parts.append(f'<path{opacity} d="{_wave(cx, cy, inner, outer)}"/>')
    if not muted:
        return _svg("".join(parts))
    # Tachado, con un hueco alrededor para que se lea sobre el altavoz.
    defs = ('<defs><mask id="m"><rect width="16" height="16" fill="#fff"/>'
            f'<path d="{MUTE_SLASH}" fill="#000" stroke="#000" stroke-width="2.2"/></mask></defs>')
    return _svg(f'<g mask="url(#m)">{"".join(parts)}</g><path d="{MUTE_SLASH}"/>', defs)


def sound_icons() -> dict[str, str]:
    return {
        "audio-volume-muted-symbolic": speaker(0, muted=True),
        "audio-volume-low-symbolic": speaker(1),
        "audio-volume-medium-symbolic": speaker(2),
        "audio-volume-high-symbolic": speaker(3),
        "audio-volume-overamplified-symbolic": speaker(3),
    }


# ---------- Centro de control y Spotlight ----------

def control_center() -> str:
    top = _rounded(1.0, 2.2, 14.0, 5.0, 2.5) + _rounded(2.1, 3.3, 11.8, 2.8, 1.4)
    bottom = _rounded(1.0, 8.8, 14.0, 5.0, 2.5) + _rounded(2.1, 9.9, 11.8, 2.8, 1.4)
    knob_top = '<circle cx="4.0" cy="4.7" r="1.9"/>'
    knob_bottom = '<circle cx="12.0" cy="11.3" r="1.9"/>'
    return _svg(f'<path fill-rule="evenodd" d="{top}{bottom}"/>{knob_top}{knob_bottom}')


def spotlight() -> str:
    cx, cy, outer, inner = 6.6, 6.6, 5.2, 3.7
    ring = (f"M{cx - outer},{cy}a{outer},{outer} 0 1 0 {2 * outer},0a{outer},{outer} 0 1 0 {-2 * outer},0Z"
            f"M{cx - inner},{cy}a{inner},{inner} 0 1 0 {2 * inner},0a{inner},{inner} 0 1 0 {-2 * inner},0Z")
    handle = "M10.1,9.0 L14.9,13.8 A0.8,0.8 0 0 1 13.8,14.9 L9.0,10.1 Z"
    return _svg(f'<path fill-rule="evenodd" d="{ring}"/><path d="{handle}"/>')


def all_icons() -> dict[str, str]:
    icons = {**battery_icons(), **wifi_icons(), **sound_icons()}
    icons["macify-control-center-symbolic"] = control_center()
    icons["macify-spotlight-symbolic"] = spotlight()
    return icons


def write(theme_dir: Path) -> bool:
    """Escribe los iconos en el tema; True si alguno cambió."""
    folder = theme_dir / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    changed = False
    for name, svg in all_icons().items():
        path = folder / f"{name}.svg"
        if not path.exists() or path.read_text() != svg:
            path.write_text(svg)
            changed = True
    return changed

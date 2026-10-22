#!/usr/bin/env python3
"""Genera los fondos originales de Macify: láminas plegadas con un borde de luz, nítidas.

Cada fondo tiene dos versiones, como en macOS: clara (nombre.jpg) y oscura
(nombre-dark.jpg); el escritorio usa la que corresponde al aspecto elegido.

Cada lámina es una curva en S que cruza la imagen de arriba abajo. Su borde se dibuja al
doble de tamaño y se reduce, así queda definido y sin dientes; sólo la luz y la sombra que
lo acompañan son suaves: un filo brillante, un reflejo junto al borde y la sombra que la
lámina deja sobre la de abajo. Un grano muy fino evita las bandas de los degradados.

Uso: scripts/make_wallpapers.py [carpeta] [nombre…]   (por defecto macify/data/wallpapers)
"""

import colorsys
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

WIDTH, HEIGHT = 3840, 2160
SUPERSAMPLE = 2
QUALITY = 88
SHEETS = 4

# nombre: (tono del fondo, tonos de las láminas de izquierda a derecha), tonos de 0 a 360
HUES = {
    "sand": (36, [34, 28, 40, 250, 30]),
    "lilac": (265, [270, 285, 300, 255, 320]),
    "coral": (8, [10, 350, 20, 330, 15]),
    "meadow": (110, [100, 130, 70, 150, 90]),
    "lagoon": (190, [185, 200, 170, 210, 195]),
    "ember": (18, [20, 8, 32, 350, 12]),
    "night": (235, [230, 250, 215, 270, 240]),
    "graphite": (220, [220, 225, 215, 230, 220]),
}
# Grafito es casi sin color, como el gris espacial.
SATURATION = {"graphite": 0.12, "sand": 0.55}


def hsv(hue, saturation, value):
    r, g, b = colorsys.hsv_to_rgb(hue / 360 % 1, max(0.0, min(1.0, saturation)), max(0.0, min(1.0, value)))
    return round(r * 255), round(g * 255), round(b * 255)


def ramp(size, start, end, vertical=False):
    """Máscara L que va de 0 en start a 255 en end (en píxeles), a lo ancho o a lo alto."""
    w, h = size
    length = h if vertical else w
    values = bytes(max(0, min(255, round(255 * (i - start) / max(1, end - start)))) for i in range(length))
    line = Image.frombytes("L", (1, length) if vertical else (length, 1), values)
    return line.resize(size, Image.Resampling.NEAREST)


def blend(size, first, second, mask):
    return Image.composite(Image.new("RGB", size, second), Image.new("RGB", size, first), mask)


def sheet_mask(size, curve):
    """La lámina: todo lo que queda a la derecha de su curva, con el borde suavizado."""
    w, h = size
    s = SUPERSAMPLE
    points = []
    for i in range(241):
        t = i / 240
        x, y = curve(t)
        points.append((x * s, y * s))
    points += [((w + 20) * s, (h * 1.2) * s), ((w + 20) * s, -h * 0.2 * s)]
    big = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(big).polygon(points, fill=255)
    return big.resize(size, Image.Resampling.LANCZOS)


def variant_colors(name, dark):
    """Colores de una versión: fondo, y por lámina (cerca del borde, lejos, filo, sombra)."""
    base, hues = HUES[name]
    sat = SATURATION.get(name, 0.42)
    if dark:
        background = (hsv(base, sat * 1.1, 0.10), hsv(base, sat * 1.2, 0.04))
        sheets = [(hsv(hue, sat * 1.25, 0.36 + 0.05 * (i % 2)), hsv(hue, sat * 1.4, 0.08),
                   hsv(hue, sat * 0.7, 1.0), 0.6) for i, hue in enumerate(hues)]
    else:
        background = (hsv(base, sat * 0.25, 0.97), hsv(base, sat * 0.5, 0.80))
        sheets = [(hsv(hue, sat * 0.18, 0.99), hsv(hue, sat * (0.55 + 0.1 * (i % 2)), 0.70 - 0.04 * (i % 3)),
                   (255, 255, 255), 0.30) for i, hue in enumerate(hues)]
    return background, sheets


def curves(size, seed):
    """Las curvas de las láminas: las mismas en las dos versiones de un fondo."""
    w, h = size
    rng = random.Random(seed)
    found = []
    for k in range(SHEETS):
        center = 0.04 + 0.25 * k + rng.uniform(-0.04, 0.04)
        amplitude = rng.uniform(0.09, 0.19)
        frequency = rng.uniform(0.5, 0.85)
        phase = rng.uniform(-0.9, 0.9) + math.pi * 0.25 * k
        skew = rng.uniform(0.35, 0.6)

        def curve(t, c=center, a=amplitude, f=frequency, p=phase, sk=skew):
            y = (-0.1 + 1.2 * t) * h
            x = (c + a * math.sin(2 * math.pi * f * t + p) + sk * (t - 0.5)) * w
            return x, y
        found.append((curve, center))
    return found


def render(name, dark, seed):
    size = (WIDTH, HEIGHT)
    w, h = size
    (bg_top, bg_bottom), sheets = variant_colors(name, dark)
    image = blend(size, bg_top, bg_bottom, ramp(size, 0, h, vertical=True))
    for (curve, center), (near, far, rim_color, shadow) in zip(curves(size, seed), sheets):
        mask = sheet_mask(size, curve)
        # Sombra sobre la lámina de abajo, sólo fuera de ésta y pegada a su borde.
        cast = ImageChops.subtract(mask.filter(ImageFilter.GaussianBlur(h * 0.045)), mask)
        image = Image.composite(Image.new("RGB", size, (0, 0, 0)), image,
                                cast.point(lambda v, s=shadow: int(min(255, v * 2 * s))))
        # Cuerpo: claro junto al borde y más oscuro hacia la derecha, con algo de luz arriba.
        edge_x = curve(0.5)[0]
        body = blend(size, near, far, ramp(size, edge_x - w * 0.12, edge_x + w * 0.55))
        body = Image.composite(Image.new("RGB", size, near), body,
                               ramp(size, h, 0, vertical=True).point(lambda v: v // 5))
        image = Image.composite(body, image, mask)
        # Reflejo ancho junto al borde y un filo de luz fino y nítido.
        sheen = ImageChops.subtract(mask, mask.filter(ImageFilter.GaussianBlur(h * 0.03)))
        image = Image.composite(Image.new("RGB", size, near), image, sheen.point(lambda v: min(255, v * 2)))
        rim = ImageChops.subtract(mask, mask.filter(ImageFilter.GaussianBlur(2.0)))
        image = Image.composite(Image.new("RGB", size, rim_color), image,
                                rim.point(lambda v, d=dark: min(255, int(v * (3.2 if d else 2.4)))))
    # Grano fino: evita las bandas de los degradados en pantallas de 8 bits.
    grain = Image.effect_noise(size, 3)
    return ImageChops.add(image, Image.merge("RGB", [grain] * 3), scale=1.0, offset=-128)


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "macify" / "data" / "wallpapers"
    names = sys.argv[2:] or list(HUES)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        seed = 7 + list(HUES).index(name)
        for dark in (False, True):
            path = out_dir / f"{name}{'-dark' if dark else ''}.jpg"
            render(name, dark, seed).save(path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            print(f"{path.name}: {path.stat().st_size // 1024} KB", flush=True)


if __name__ == "__main__":
    main()

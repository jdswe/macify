#!/usr/bin/env python3
"""Genera los fondos originales de Macify: cintas de color que fluyen, al estilo de macOS.

Cada fondo es un degradado de base con varias cintas curvas encima (degradado propio,
sombra suave y un brillo en el borde) y un grano muy fino que evita las bandas de color.
Se dibuja a la mitad de tamaño y se amplía: las formas suaves no pierden nada y es rápido.

Uso: scripts/make_wallpapers.py [carpeta]   (por defecto macify/data/wallpapers)
"""

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

WIDTH, HEIGHT = 3840, 2160
DRAW_SCALE = 0.5
QUALITY = 86

# nombre: (degradado de fondo arriba-izquierda → abajo-derecha, cintas [(color claro, color oscuro)])
PALETTES = {
    "sand": ((246, 236, 222), (196, 170, 140), [((255, 248, 236), (214, 186, 150)),
                                                ((232, 206, 172), (150, 116, 84)),
                                                ((250, 230, 205), (190, 150, 110)),
                                                ((210, 196, 226), (120, 108, 150))]),
    "night": ((14, 18, 38), (46, 24, 64), [((84, 96, 196), (24, 30, 82)),
                                            ((150, 82, 170), (52, 24, 76)),
                                            ((60, 140, 200), (16, 40, 86)),
                                            ((220, 120, 150), (90, 36, 70))]),
    "lagoon": ((196, 236, 236), (40, 120, 150), [((220, 250, 246), (100, 190, 196)),
                                                  ((90, 190, 200), (20, 90, 120)),
                                                  ((160, 220, 220), (40, 130, 150)),
                                                  ((30, 110, 150), (10, 50, 90))]),
    "ember": ((40, 12, 20), (190, 70, 40), [((255, 170, 90), (190, 60, 40)),
                                             ((250, 110, 80), (120, 24, 40)),
                                             ((255, 210, 140), (220, 110, 60)),
                                             ((150, 40, 70), (60, 10, 30))]),
    "lilac": ((240, 230, 250), (150, 130, 210), [((250, 240, 255), (196, 170, 236)),
                                                  ((200, 170, 240), (110, 80, 180)),
                                                  ((255, 220, 236), (210, 150, 200)),
                                                  ((150, 130, 220), (70, 60, 150))]),
    "graphite": ((50, 52, 58), (14, 15, 18), [((120, 124, 134), (40, 42, 48)),
                                               ((80, 84, 94), (22, 24, 28)),
                                               ((150, 152, 160), (60, 62, 70)),
                                               ((96, 100, 112), (30, 32, 38))]),
    "meadow": ((226, 240, 210), (70, 130, 90), [((240, 250, 220), (150, 200, 130)),
                                                 ((150, 200, 140), (60, 120, 80)),
                                                 ((250, 240, 200), (200, 190, 120)),
                                                 ((80, 150, 120), (30, 80, 70))]),
    "coral": ((255, 222, 210), (230, 110, 120), [((255, 238, 226), (250, 170, 150)),
                                                  ((250, 150, 140), (200, 70, 100)),
                                                  ((255, 200, 170), (240, 130, 110)),
                                                  ((180, 90, 150), (110, 40, 100))]),
}


def gradient(size, top, bottom, angle=0.0):
    """Degradado lineal de top a bottom, girado angle radianes."""
    w, h = size
    # Lienzo tres veces mayor: al girarlo, el centro que se recorta queda siempre cubierto.
    line = Image.linear_gradient("L").resize((w * 3, h * 3))
    line = line.rotate(math.degrees(angle), resample=Image.Resampling.BICUBIC).crop((w, h, w * 2, h * 2))
    return Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), line)


def ribbon_mask(size, rng, base_y, amplitude, thickness, phase, waves):
    """Una cinta entre dos curvas suaves que cruza la imagen de lado a lado."""
    w, h = size
    top, bottom = [], []
    for i in range(0, 121):
        x = w * (i / 120) * 1.2 - w * 0.1
        t = i / 120
        y = base_y + amplitude * math.sin(t * math.pi * waves + phase) + amplitude * 0.35 * math.sin(t * math.pi * 3.1 + phase * 1.7)
        thick = thickness * (0.55 + 0.45 * math.sin(t * math.pi * 1.3 + phase))
        top.append((x, y))
        bottom.append((x, y + thick))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(top + bottom[::-1], fill=255)
    edge = Image.new("L", size, 0)
    ImageDraw.Draw(edge).line(top, fill=255, width=max(2, int(h * 0.004)))
    return mask, edge


def render(name, out_dir: Path, seed: int):
    (bg_top, bg_bottom, ribbons) = PALETTES[name]
    rng = random.Random(seed)
    size = (int(WIDTH * DRAW_SCALE), int(HEIGHT * DRAW_SCALE))
    w, h = size
    image = gradient(size, bg_top, bg_bottom, angle=rng.uniform(-0.5, 0.5))
    for index, (light, dark) in enumerate(ribbons):
        base_y = h * (0.12 + 0.2 * index) + rng.uniform(-h * 0.05, h * 0.05)
        mask, edge = ribbon_mask(size, rng, base_y, amplitude=h * rng.uniform(0.12, 0.22),
                                 thickness=h * rng.uniform(0.18, 0.34), phase=rng.uniform(0, math.tau),
                                 waves=rng.uniform(0.8, 1.6))
        # Sombra suave debajo de la cinta.
        blurred = mask.filter(ImageFilter.GaussianBlur(h * 0.03)).point(lambda v: int(v * 0.35))
        shadow = Image.new("L", size, 0)
        shadow.paste(blurred, (0, int(h * 0.02)))         # hacia abajo, sin dar la vuelta
        image = Image.composite(Image.new("RGB", size, (0, 0, 0)), image, shadow)
        # La cinta con su degradado y un borde de luz.
        fill = gradient(size, light, dark, angle=rng.uniform(-0.3, 0.3) + math.pi / 2 * (index % 2))
        image = Image.composite(fill, image, mask.filter(ImageFilter.GaussianBlur(1.2)))
        glow = edge.filter(ImageFilter.GaussianBlur(h * 0.006)).point(lambda v: int(v * 0.55))
        image = Image.composite(Image.new("RGB", size, (255, 255, 255)), image, glow)
    image = image.filter(ImageFilter.GaussianBlur(h * 0.0025)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    # Grano fino: evita las bandas de los degradados en pantallas de 8 bits.
    grain = Image.effect_noise((WIDTH, HEIGHT), 4)
    image = ImageChops.add(image, Image.merge("RGB", [grain] * 3), scale=1.0, offset=-128)
    path = out_dir / f"{name}.jpg"
    image.save(path, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return path


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "macify" / "data" / "wallpapers"
    out_dir.mkdir(parents=True, exist_ok=True)
    for seed, name in enumerate(PALETTES, start=7):
        path = render(name, out_dir, seed)
        print(f"{path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()

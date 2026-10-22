#!/usr/bin/env python3
"""Video de presentación de Macify: 1920x1080, 30 fps, con música original.

Uso: render.py <carpeta-de-capturas> <salida.mp4>
La carpeta tiene app/ (pantallas de la app, capture.py), shell/ (GNOME, tests/shell en modo
demo) y web.png (la web). Los cuadros se dibujan con PIL y GStreamer los codifica en H.264
con el audio de music.py.
"""

import io
import math
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAPTURES = Path(sys.argv[1])
OUT = Path(sys.argv[2])
APP_SHOTS, SHELL_SHOTS = CAPTURES / "app", CAPTURES / "shell"
WALLPAPER = REPO / "macify" / "data" / "wallpapers" / "lilac.jpg"     # fondo original, no de Apple
BOOT = Path.home() / ".cache" / "macify" / "plymouth"
FONTS = Path.home() / ".local" / "share" / "fonts" / "macify-sf"
W, H, FPS = 1920, 1080, 30
OVERLAP = 0.6
BOLD, SEMI, REG, MONO = "SF-Pro-Display-Bold", "SF-Pro-Display-Semibold", "SF-Pro-Display-Regular", "SF-Mono-Regular"


def font(name, size):
    return ImageFont.truetype(str(FONTS / f"{name}.otf"), size)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def svg(path, size):
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), size, size, True)
    _ok, data = pixbuf.save_to_bufferv("png", [], [])
    return Image.open(io.BytesIO(data)).convert("RGBA")


def cover(image, size):
    ratio = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left, top = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    return image.crop((left, top, left + size[0], top + size[1]))


# ---------- recursos preparados una vez ----------

_wall = Image.open(WALLPAPER).convert("RGB")
BLURRED = cover(_wall, (int(W * 1.15), int(H * 1.15))).filter(ImageFilter.GaussianBlur(40))
BLURRED = Image.blend(BLURRED, Image.new("RGB", BLURRED.size, (8, 8, 16)), 0.45)
ICON = svg(REPO / "docs" / "icon.svg", 280)


def background(t):
    """Fondo difuminado que se mueve despacio."""
    dx = (BLURRED.width - W) * (0.5 + 0.5 * math.sin(t * 0.05))
    dy = (BLURRED.height - H) * (0.5 + 0.5 * math.cos(t * 0.04))
    return BLURRED.crop((int(dx), int(dy), int(dx) + W, int(dy) + H)).convert("RGBA")


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(ImageChops.multiply(out.getchannel("A"), mask))
    return out


def with_shadow(img, radius=22, blur=40, offset=24):
    """Imagen con esquinas redondeadas, sombra suave y un filo claro."""
    win = rounded(img, radius)
    pad = blur * 2
    canvas = Image.new("RGBA", (win.width + pad * 2, win.height + pad * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((pad, pad + offset, pad + win.width, pad + win.height + offset),
                                             radius, fill=(0, 0, 0, 150))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
    canvas.alpha_composite(win, (pad, pad))
    ImageDraw.Draw(canvas).rounded_rectangle((pad, pad, pad + win.width - 1, pad + win.height - 1), radius,
                                             outline=(255, 255, 255, 40), width=1)
    return canvas, pad


def place(frame, layer, x, y, opacity=1.0):
    if opacity < 1:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda a: int(a * opacity)))
    frame.alpha_composite(layer, (int(x), int(y)))


def centered_text(layer, y, text, size, weight=REG, fill=(255, 255, 255, 255)):
    draw = ImageDraw.Draw(layer)
    f = font(weight, size)
    draw.text(((layer.width - draw.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)


def caption(frame, t, title, sub=""):
    """Título arriba, con entrada suave."""
    k = ease(t / 0.7)
    layer = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    centered_text(layer, 40, title, 60, BOLD)
    if sub:
        centered_text(layer, 120, sub, 30, REG, (255, 255, 255, 200))
    place(frame, layer, 0, 10 * (1 - k), k)


_cards = {}


def card(key, image_factory, max_w, max_h, radius=22):
    """Imagen lista para poner en escena (cacheada): escalada, redondeada y con sombra."""
    if key not in _cards:
        image = image_factory()
        ratio = min(max_w / image.width, max_h / image.height)
        image = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
        _cards[key] = with_shadow(image, radius)
    return _cards[key]


def shot_scene(path, title, sub="", crop=None, max_w=1500, max_h=800):
    """Una captura (o un recorte ampliado) bajo el título, entrando desde abajo."""
    def factory():
        image = Image.open(path).convert("RGB")
        return image.crop(crop) if crop else image

    def draw(t, dur):
        frame = background(t)
        caption(frame, t, title, sub)
        layer, pad = card(f"{path}{crop}", factory, max_w, max_h)
        k = ease(t / 0.8)
        top = 215 + (H - 215 - (layer.height - 2 * pad)) / 2 - 20
        place(frame, layer, (W - layer.width) / 2, top - pad + 60 * (1 - k), min(1.0, 0.2 + k))
        return frame
    return draw


def pair_scene(paths_crops, title, sub=""):
    """Dos o tres recortes lado a lado (por ejemplo, los menús de batería, Wi‑Fi y sonido)."""
    def draw(t, dur):
        frame = background(t)
        caption(frame, t, title, sub)
        count = len(paths_crops)
        layers = [card(f"{p}{c}", lambda p=p, c=c: Image.open(p).convert("RGB").crop(c), 1700 // count - 40, 760)
                  for p, c in paths_crops]
        total = sum(layer.width - 2 * pad for layer, pad in layers) + 40 * (count - 1)
        x = (W - total) / 2
        for i, (layer, pad) in enumerate(layers):
            k = ease((t - 0.15 * i) / 0.8)
            place(frame, layer, x - pad, 230 - pad + 60 * (1 - k), max(0.0, min(1.0, 0.2 + k)))
            x += layer.width - 2 * pad + 40
        return frame
    return draw


def app_scene(name, title, sub=""):
    return shot_scene(APP_SHOTS / f"{name}.png", title, sub, max_w=1240, max_h=800)


def two_app_scene(first, second, title, sub=""):
    """La misma ventana en dos momentos que se funden (el progreso de la instalación)."""
    def draw(t, dur):
        frame = background(t)
        caption(frame, t, title, sub)
        a, pad = card(first, lambda: Image.open(APP_SHOTS / f"{first}.png").convert("RGB"), 1240, 800)
        b, _ = card(second, lambda: Image.open(APP_SHOTS / f"{second}.png").convert("RGB"), 1240, 800)
        k = ease(t / 0.8)
        x, y = (W - a.width) / 2, 215 + (H - 215 - (a.height - 2 * pad)) / 2 - 20 - pad + 60 * (1 - k)
        mix = ease((t - dur * 0.45) / 0.6)
        if mix < 1:
            place(frame, a, x, y, min(1.0, 0.2 + k) * (1 - mix))
        if mix > 0:
            place(frame, b, x, y, mix)
        return frame
    return draw


# ---------- escenas propias ----------

def coming(t, dur):
    """Apertura: pantalla negra, el texto aparece letra a letra y se ilumina antes del golpe."""
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W / 2 - 700, H / 2 - 260, W / 2 + 700, H / 2 + 260),
                                 fill=(70, 90, 200, int(255 * ease(t / dur) * 0.55)))
    frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160)))
    text = "Something new is coming"
    f = font(SEMI, 78)
    draw = ImageDraw.Draw(frame)
    x = (W - draw.textlength(text, font=f)) / 2
    for i, char in enumerate(text):
        k = ease((t - 0.3 - i * 0.06) / 0.5)
        if k > 0:
            layer = Image.new("RGBA", (120, 130), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((10, 10), char, font=f, fill=(255, 255, 255, 255))
            place(frame, layer, x - 10, H / 2 - 60 + 18 * (1 - k), k)
        x += draw.textlength(char, font=f)
    k2 = ease((t - 2.0) / 0.8)
    if k2 > 0:
        layer = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
        centered_text(layer, 0, "to Ubuntu", 34, REG, (180, 195, 255, 255))
        place(frame, layer, 0, H / 2 + 50, k2)
    flash = max(0.0, (t - (dur - 0.45)) / 0.45)
    if flash > 0:
        frame = Image.blend(frame, Image.new("RGBA", (W, H), (255, 255, 255, 255)), flash * 0.85)
    return frame


def intro(t, dur):
    frame = background(t)
    k = ease(t / 1.0)
    size = int(220 + 60 * k)
    place(frame, ICON.resize((size, size), Image.Resampling.LANCZOS), (W - size) / 2, 230 + 40 * (1 - k), k)
    layer = Image.new("RGBA", (W, 400), (0, 0, 0, 0))
    centered_text(layer, 0, "Macify", 150, BOLD)
    centered_text(layer, 190, "A one-click macOS look for Ubuntu 26.04.1", 40, REG, (255, 255, 255, 215))
    k2 = ease((t - 0.5) / 1.0)
    place(frame, layer, 0, 560 + 30 * (1 - k2), k2)
    return frame


BROWSER_W, BROWSER_H = 1500, 800


def _browser_chrome():
    bar = Image.new("RGB", (BROWSER_W, 52), (36, 34, 46))
    d = ImageDraw.Draw(bar)
    for i, color in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        d.ellipse((22 + i * 26, 18, 36 + i * 26, 32), fill=color)
    d.rounded_rectangle((BROWSER_W / 2 - 260, 10, BROWSER_W / 2 + 260, 42), 10, fill=(56, 54, 68))
    f = font(REG, 20)
    url = "jdswe.github.io/macify"
    d.text((BROWSER_W / 2 - d.textlength(url, font=f) / 2, 14), url, font=f, fill=(220, 220, 230))
    return bar


_web = None


def website(t, dur):
    global _web
    if _web is None:
        page = Image.open(CAPTURES / "web.png").convert("RGB")
        _web = (page.resize((BROWSER_W, int(page.height * BROWSER_W / page.width)), Image.Resampling.LANCZOS),
                _browser_chrome())
    page_image, chrome = _web
    frame = background(t)
    caption(frame, t, "Start at the website", "jdswe.github.io/macify  ·  download, one-command install, all the details")
    stops = [(0.0, 0), (1.6, 0), (3.6, 1150), (5.0, 1150), (6.8, 2120), (dur, 2120)]
    scroll = 0
    for (t0, y0), (t1, y1) in zip(stops, stops[1:]):
        if t <= t1:
            scroll = y0 + (y1 - y0) * (0.5 - 0.5 * math.cos(math.pi * (t - t0) / (t1 - t0)))
            break
    view = Image.new("RGB", (BROWSER_W, BROWSER_H))
    view.paste(chrome, (0, 0))
    view.paste(page_image.crop((0, int(scroll), BROWSER_W, int(scroll) + BROWSER_H - 52)), (0, 52))
    layer, pad = with_shadow(view, 18)
    k = ease(t / 0.8)
    place(frame, layer, (W - layer.width) / 2, 225 - pad + 60 * (1 - k), min(1.0, 0.2 + k))
    return frame


COMMAND = "curl -fsSL https://jdswe.github.io/macify/install.sh | bash"
OUTPUT = [
    (3.1, "Downloading https://github.com/jdswe/macify/releases/latest/download/macify_all.deb"),
    (3.6, "[sudo: authenticate] Password: ••••••••"),
    (4.3, "Unpacking macify…"),
    (4.8, "Setting up macify…"),
    (5.5, None),
]


def terminal(t, dur):
    frame = background(t)
    caption(frame, t, "Install with one command", "It downloads the latest release, checks its fingerprint and installs it")
    tw, th = 1560, 600
    term = Image.new("RGB", (tw, th), (22, 22, 28))
    d = ImageDraw.Draw(term)
    d.rectangle((0, 0, tw, 50), fill=(40, 40, 50))
    for i, color in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        d.ellipse((22 + i * 26, 18, 36 + i * 26, 32), fill=color)
    ft = font(SEMI, 20)
    d.text((tw / 2 - d.textlength("Terminal", font=ft) / 2, 13), "Terminal", font=ft, fill=(210, 210, 220))
    fm = font(MONO, 23)
    prompt = "you@ubuntu:~$ "
    typed = COMMAND[:int(len(COMMAND) * max(0.0, min(1.0, (t - 0.6) / 2.0)))]
    y = 80
    d.text((30, y), prompt, font=fm, fill=(130, 200, 255))
    px = 30 + d.textlength(prompt, font=fm)
    d.text((px, y), typed, font=fm, fill=(240, 240, 245))
    if t < 2.9 and int(t * 2) % 2 == 0:
        cx = px + d.textlength(typed, font=fm)
        d.rectangle((cx + 2, y + 4, cx + 15, y + 30), fill=(240, 240, 245))
    for at, line in OUTPUT:
        y += 42
        if t >= at and line:
            d.text((30, y), line, font=fm, fill=(200, 200, 210))
    if t >= 5.5:
        d.text((30, y + 42), "Macify is installed. Open it from your apps.", font=fm, fill=(120, 230, 140))
    layer, pad = with_shadow(term, 16)
    k = ease(t / 0.8)
    place(frame, layer, (W - layer.width) / 2, 250 - pad + 60 * (1 - k), min(1.0, 0.2 + k))
    return frame


_boot = {}


def _boot_assets():
    if not _boot:
        scale = 1.5
        for name in ("logo", "bar-background", "bar-fill"):
            image = Image.open(BOOT / f"{name}.png").convert("RGBA")
            _boot[name] = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    return _boot


def boot_frame(fraction, text, text_opacity, label, t):
    """Igual que macify.script: logo, barra y saludo bajo la barra."""
    assets = _boot_assets()
    logo, bar_bg, bar_fill = assets["logo"], assets["bar-background"], assets["bar-fill"]
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    ly = H / 2 - logo.height / 2 - 60
    frame.alpha_composite(logo, (int((W - logo.width) / 2), int(ly)))
    by, bx = int(ly + logo.height + 96), int((W - bar_bg.width) / 2)
    frame.alpha_composite(bar_bg, (bx, by))
    frame.alpha_composite(bar_fill.resize((max(3, int(bar_fill.width * fraction)), bar_fill.height)), (bx, by))
    if text and text_opacity > 0:
        layer = Image.new("RGBA", (W, 80), (0, 0, 0, 0))
        centered_text(layer, 0, text, 34)
        place(frame, layer, 0, by + 50, text_opacity)
    layer = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
    centered_text(layer, 0, label, 26, REG, (255, 255, 255, 130))
    place(frame, layer, 0, H - 90, ease(t / 0.6))
    return frame


def shutdown(t, dur):
    p = min(1.0, t / 3.4)
    return boot_frame((1 - p) ** 2, "See you soon", min(1.0, t / 0.6),
                      "Shutting down: the bar empties in your PC's real shutdown time", t)


def startup(t, dur):
    p = min(1.0, t / (dur - 1.4))
    return boot_frame(p * (2 - p), "Welcome", ease((p - 0.85) / 0.15) if p > 0.85 else 0,
                      "Starting up: it fills in your PC's real boot time and ends with Welcome", t)


def outro(t, dur):
    frame = background(t)
    k = ease(t / 1.0)
    place(frame, ICON.resize((220, 220), Image.Resampling.LANCZOS), (W - 220) / 2, 190 + 30 * (1 - k), k)
    layer = Image.new("RGBA", (W, 500), (0, 0, 0, 0))
    centered_text(layer, 0, "Macify", 110, BOLD)
    centered_text(layer, 150, "jdswe.github.io/macify", 46, SEMI, (150, 190, 255, 255))
    centered_text(layer, 230, "Free and open source · GPL-3.0 · github.com/jdswe/macify", 30, REG, (255, 255, 255, 200))
    centered_text(layer, 290, "© 2026 Jose David Carranza Angarita", 26, REG, (255, 255, 255, 150))
    k2 = ease((t - 0.4) / 1.0)
    place(frame, layer, 0, 450 + 30 * (1 - k2), k2)
    fade = max(0.0, (t - (dur - 0.8)) / 0.8)
    if fade > 0:
        frame = Image.blend(frame, Image.new("RGBA", (W, H), (0, 0, 0, 255)), fade)
    return frame


S = SHELL_SHOTS
SCENES = [
    (4.4, coming),
    (4.5, intro),
    (9.5, website),
    (7.5, terminal),
    (3.2, app_scene("01-welcome", "Open Macify", "A setup assistant, like a new Mac")),
    (3.0, app_scene("02-appearance", "Light or dark", "Windows, menus and apps follow your choice")),
    (3.8, app_scene("03-wallpaper", "Eight new wallpapers", "Original 4K art in a gallery, or your own photos")),
    (3.4, app_scene("04-dock", "Set up your dock", "Size, magnification, magic lamp and auto-hide, with a live preview")),
    (3.0, app_scene("05-summary", "Review every change", "Everything is backed up first and can be undone")),
    (4.8, two_app_scene("06-progress-a", "07-progress-b", "Watch it work", "Real-time progress, step by step")),
    (2.8, app_scene("08-done", "Restart", "One restart and the whole system looks like a Mac")),
    (4.4, shutdown),
    (6.0, startup),
    (4.6, shot_scene(S / "desktop.png", "Your new desktop", "Menu bar, floating glass dock and macOS icons")),
    (4.4, shot_scene(S / "menu-edit.png", "Menus for every app", "File, Edit, View, Window and Help work in any app",
                     crop=(0, 0, 760, 560), max_h=780)),
    (3.8, shot_scene(S / "menu-window.png", "Window, like on a Mac", "Minimize, Zoom, tile, move to another display",
                     crop=(0, 0, 900, 480), max_h=780)),
    (4.6, pair_scene([(S / "menu-battery.png", (1180, 0, 1720, 330)), (S / "menu-wifi.png", (1230, 0, 1770, 330)),
                      (S / "menu-sound.png", (1270, 0, 1810, 330))],
                     "Every icon has its own menu", "Battery and Energy Mode, Wi‑Fi networks, sound output")),
    (4.4, pair_scene([(S / "control-center.png", (1380, 0, 1920, 330)), (S / "osd.png", (1380, 0, 1920, 330))],
                     "Control Center, the Apple way", "Only what has no menu of its own · volume at the top right")),
    (4.0, shot_scene(S / "date-menu.png", "Calendar like the macOS widget", "Today and the month in red, on glass cards",
                     crop=(1160, 0, 1920, 600), max_h=780)),
    (4.0, shot_scene(S / "screenshot-preview.png", "Screenshots, like on a Mac",
                     "A thumbnail slides in — already copied, paste it with Ctrl+V", crop=(1200, 600, 1920, 1080),
                     max_h=700)),
    (4.8, shot_scene(S / "now-playing.png", "Live Activities", "Music, charging, connection — click for Now Playing",
                     crop=(560, 0, 1360, 420), max_h=780)),
    (4.2, shot_scene(S / "app-grid.png", "Apps on frosted glass", "Show Apps works like the Apps view in macOS 27")),
    (3.6, shot_scene(S / "badge.png", "Notification badges", "A red count on the app's dock icon, like on a Mac",
                     crop=(360, 880, 1560, 1080), max_h=500)),
    (3.0, app_scene("09-manage", "Macify stays with you", "Customize live, check for problems, restore or uninstall")),
    (3.0, app_scene("10-update-available", "Software Update", "New versions from GitHub, verified before installing")),
    (3.2, app_scene("13-doctor", "Doctor", "Finds outdated or broken pieces and fixes them in one click")),
    (5.5, outro),
]


def main():
    starts, at = [], 0.0
    for dur, _ in SCENES:
        starts.append(at)
        at += dur - OVERLAP
    total = at + OVERLAP
    frames = int(total * FPS)
    print(f"{total:.1f} s, {frames} frames", flush=True)
    music = CAPTURES / "music.wav"
    reveal = starts[1] + OVERLAP * 0.5
    subprocess.run([sys.executable, str(HERE / "music.py"), str(music), f"{total:.2f}", f"{reveal:.2f}"], check=True)
    encoder = subprocess.Popen(
        ["gst-launch-1.0", "-q", "-e", "mp4mux", "name=mux", "faststart=true", "!", "filesink", f"location={OUT}",
         "filesrc", f"location={music}", "!", "wavparse", "!", "audioconvert", "!", "audioresample", "!",
         "audio/x-raw,rate=44100", "!", "avenc_aac", "bitrate=192000", "!", "queue", "!", "mux.",
         "fdsrc", "fd=0", "!", "rawvideoparse", f"width={W}", f"height={H}", "format=rgb", f"framerate={FPS}/1", "!",
         "videoconvert", "!", "video/x-raw,format=I420", "!",
         "x264enc", "speed-preset=slow", "bitrate=4000", "key-int-max=60", "!",
         "video/x-h264,profile=high", "!", "queue", "!", "mux."],
        stdin=subprocess.PIPE)
    for n in range(frames):
        t = n / FPS
        active = [i for i, s in enumerate(starts) if s <= t < s + SCENES[i][0]]
        i = active[-1]
        img = SCENES[i][1](t - starts[i], SCENES[i][0])
        if len(active) > 1:                      # cruce suave con la escena anterior
            j = active[-2]
            prev = SCENES[j][1](t - starts[j], SCENES[j][0])
            img = Image.blend(prev, img, max(0.0, min(1.0, (t - starts[i]) / OVERLAP)))
        encoder.stdin.write(img.convert("RGB").tobytes())
        if n % 300 == 0:
            print(f"{n}/{frames}", flush=True)
    encoder.stdin.close()
    encoder.wait()
    print("done", OUT)


if __name__ == "__main__":
    main()

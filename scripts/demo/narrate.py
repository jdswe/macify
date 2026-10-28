"""Narración del video de la demo con una voz de ElevenLabs. Herramienta de desarrollo.

    python3 scripts/demo/narrate.py docs/demo.mp4 dist/demo-narrated.mp4

Cada frase se coloca al empezar su escena (las duraciones se leen de render.py) y la música
baja sola mientras habla la voz. La clave se lee de ELEVENLABS_API_KEY o de
~/.config/elevenlabs/api_key (fuera del repositorio) y nunca se imprime. Las voces generadas se
guardan en ~/.cache/macify-narration para no gastar créditos dos veces.
Opcional: MACIFY_VOICE (id de la voz; por defecto «Moon Code EN - Jessa»).
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://api.elevenlabs.io/v1"
KEY_FILE = Path.home() / ".config" / "elevenlabs" / "api_key"
CACHE = Path.home() / ".cache" / "macify-narration"
VOICE = os.environ.get("MACIFY_VOICE", "yj30vwTGJxSHezdAGsv9")      # Moon Code EN - Jessa
MODEL = "eleven_multilingual_v2"
# Tono calmado y relajado: muy estable, sin teatralidad y un poco más lento.
SETTINGS = {"stability": 0.75, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True, "speed": 0.94}
LEAD = 0.35            # segundos entre el inicio de la escena y la voz
GAP = 0.3              # silencio mínimo antes de la siguiente frase
MAX_SPEEDUP = 1.12     # si una frase no cabe, se acelera hasta este punto (no más: sonaría rara)

# Índice de la escena en render.py → lo que dice la voz. Con 29 escenas; si cambian, se
# comprueba abajo y hay que revisar estos índices.
# La entrada («Something new is coming» y el golpe de música) va sin voz: la narradora
# empieza cuando aparece Macify.
NARRATION = {
    1: "This is Macify. macOS, made for Ubuntu.",
    2: "It all starts on the website. Download the installer, or copy one command into your terminal.",
    3: "Macify verifies every download before it installs, so your system stays safe.",
    4: "Open Macify, and a setup assistant guides you, like a new Mac.",
    6: "Choose light or dark, pick a wallpaper, and shape your dock with a live preview.",
    8: "Review every change before it happens. Everything is backed up first, "
       "and you can follow each step as it works.",
    11: "Restart once. Even the startup and shutdown screens now feel like a Mac, "
        "with a progress bar that follows your real boot.",
    13: "Here is your new desktop. A real menu bar with menus for every app, "
        "a floating glass dock, and icons that finally match.",
    16: "Every icon in the menu bar opens its own menu. "
        "Control Center works the Apple way, and switching displays takes one shortcut.",
    19: "Every wallpaper comes in light and dark. "
        "The calendar looks like the macOS widget, and screenshots slide in, ready to paste or crop.",
    22: "Live Activities keep your music and charging at a glance. "
        "Apps open on frosted glass, and the dock counts your notifications.",
    25: "Macify stays with you. Updates install only what's new, and Doctor fixes problems in one click.",
    28: "Macify. Free, open source, and made for Ubuntu.",
}
SCENE_COUNT = 29
# Algunas frases esperan un poco más: la primera deja sonar el golpe de música antes de hablar.
EXTRA_LEAD = {1: 1.0, 2: 0.7}


def scene_starts() -> list[float]:
    """Inicio de cada escena, igual que lo calcula render.py (cada escena se funde con la anterior).

    Se leen las duraciones del texto de render.py en vez de importarlo: render.py usa sus
    argumentos de línea de comandos al cargarse.
    """
    source = (HERE / "render.py").read_text()
    block = source[source.index("SCENES = ["):]
    block = block[:block.index("\n]\n")]
    durations = [float(d) for d in re.findall(r"^    \((\d+\.\d+),", block, re.M)]
    overlap = float(re.search(r"^OVERLAP = (\d+\.\d+)", source, re.M).group(1))
    if len(durations) != SCENE_COUNT:
        sys.exit(f"render.py has {len(durations)} scenes, expected {SCENE_COUNT}: update NARRATION")
    starts, at = [], 0.0
    for duration in durations:
        starts.append(at)
        at += duration - overlap
    return starts + [at + overlap]                      # el último valor es el final del video


def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY") or (KEY_FILE.read_text().strip() if KEY_FILE.exists() else "")
    if not key:
        sys.exit("No ElevenLabs key: set ELEVENLABS_API_KEY or save it in ~/.config/elevenlabs/api_key")
    return key


def speak(text: str, key: str) -> Path:
    digest = hashlib.sha256(f"{VOICE}|{MODEL}|{json.dumps(SETTINGS, sort_keys=True)}|{text}".encode()).hexdigest()[:16]
    target = CACHE / f"{digest}.mp3"
    if target.exists():
        return target
    body = {"text": text, "model_id": MODEL, "language_code": "en",
            "voice_settings": SETTINGS}
    request = urllib.request.Request(
        f"{API}/text-to-speech/{VOICE}?output_format=mp3_44100_128", data=json.dumps(body).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=120) as response:
        audio = response.read()
    CACHE.mkdir(parents=True, exist_ok=True)
    target.write_bytes(audio)
    print(f"  voice: {text[:48]}…")
    return target


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    video, out = Path(sys.argv[1]), Path(sys.argv[2])
    starts = scene_starts()
    key = api_key()
    scenes = sorted(NARRATION)

    def start_of(scene: int) -> float:
        return starts[scene] + LEAD + EXTRA_LEAD.get(scene, 0.0)

    clips = []
    for n, scene in enumerate(scenes):
        clip = speak(NARRATION[scene], key)
        begin = start_of(scene)
        end = (start_of(scenes[n + 1]) if n + 1 < len(scenes) else starts[-1]) - GAP
        length = duration(clip)
        speed = max(1.0, length / (end - begin))
        if speed > MAX_SPEEDUP:
            sys.exit(f"scene {scene}: the line lasts {length:.1f} s but only {end - begin:.1f} s fit — shorten it")
        print(f"  scene {scene:2}: {begin:6.1f} s  {length:4.1f} s of {end - begin:4.1f} s"
              + (f"  (×{speed:.2f})" if speed > 1 else ""))
        clips.append((clip, begin, speed))

    inputs = ["-i", str(video)]
    voices = []
    for i, (clip, begin, speed) in enumerate(clips, start=1):
        inputs += ["-i", str(clip)]
        delay = int(begin * 1000)
        voices.append(f"[{i}:a]atempo={speed:.3f},aresample=44100,adelay={delay}|{delay}[v{i}]")
    labels = "".join(f"[v{i}]" for i in range(1, len(clips) + 1))
    graph = ";".join(voices) + (
        # La voz se rellena con silencio hasta el final, para que el video no se corte antes.
        f";{labels}amix=inputs={len(clips)}:normalize=0,apad=whole_dur={duration(video):.3f}[voice]"
        ";[voice]asplit=2[voice1][voice2]"
        # La música baja mientras habla la voz y vuelve sola en los silencios.
        ";[0:a]volume=0.8[music];[music][voice1]sidechaincompress=threshold=0.02:ratio=10:attack=30:release=600[ducked]"
        ";[ducked][voice2]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[mix]")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "0:v", "-map", "[mix]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)],
                   check=True)
    print(f"done {out}")


if __name__ == "__main__":
    main()

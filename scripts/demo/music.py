"""Música original para el video: subida y golpe al revelar Macify, luego acordes suaves con ritmo."""
import math
import random
import struct
import sys
import wave
from array import array

RATE = 22050
TOTAL = float(sys.argv[2])          # segundos
REVEAL = float(sys.argv[3])         # momento del golpe (aparece Macify)
OUT = sys.argv[1]
N = int(TOTAL * RATE) + RATE
left = array("f", bytes(4 * N))
right = array("f", bytes(4 * N))
random.seed(7)

TABLE_SIZE = 4096
PAD = array("f", [math.sin(2 * math.pi * i / TABLE_SIZE) + 0.32 * math.sin(4 * math.pi * i / TABLE_SIZE)
                  + 0.12 * math.sin(6 * math.pi * i / TABLE_SIZE) for i in range(TABLE_SIZE)])
SINE = array("f", [math.sin(2 * math.pi * i / TABLE_SIZE) for i in range(TABLE_SIZE)])


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def tone(start, length, freq, amp, pan=0.0, table=PAD, attack=0.01, decay=None, release=0.3):
    """Una nota: envolvente de ataque, sostenido (o caída exponencial) y salida."""
    i0 = int(start * RATE)
    n = int(length * RATE)
    step = freq * TABLE_SIZE / RATE
    phase = random.random() * TABLE_SIZE
    gl, gr = amp * (1 - pan) / 2 ** 0.5, amp * (1 + pan) / 2 ** 0.5
    a, r = max(1, int(attack * RATE)), max(1, int(release * RATE))
    k = math.exp(-1.0 / (decay * RATE)) if decay else 1.0
    env_decay = 1.0
    mask = TABLE_SIZE - 1
    for i in range(n):
        j = i0 + i
        if j >= N:
            break
        env = i / a if i < a else 1.0
        if i > n - r:
            env *= (n - i) / r
        env *= env_decay
        env_decay *= k
        v = table[int(phase) & mask] * env
        phase += step
        left[j] += v * gl
        right[j] += v * gr


def kick(start, amp=0.55):
    i0 = int(start * RATE)
    n = int(0.35 * RATE)
    phase = 0.0
    for i in range(n):
        t = i / RATE
        f = 45 + 90 * math.exp(-t * 28)
        phase += 2 * math.pi * f / RATE
        v = math.sin(phase) * math.exp(-t * 9) * amp
        if i0 + i < N:
            left[i0 + i] += v
            right[i0 + i] += v


def hat(start, amp=0.05, pan=0.0):
    i0 = int(start * RATE)
    n = int(0.05 * RATE)
    prev = 0.0
    for i in range(n):
        x = random.uniform(-1, 1)
        v = (x - prev) * math.exp(-i / RATE * 70) * amp     # ruido agudo que cae rápido
        prev = x
        if i0 + i < N:
            left[i0 + i] += v * (1 - pan)
            right[i0 + i] += v * (1 + pan)


# ---------- apertura: subida hasta el golpe ----------
for m in (38, 45):                                   # nota grave sostenida
    tone(0.0, REVEAL + 0.4, hz(m), 0.10, attack=1.5, release=0.6)
n = int(REVEAL * RATE)
low = 0.0
for i in range(n):                                   # ruido que sube y se aclara
    t = i / RATE
    p = t / REVEAL
    x = random.uniform(-1, 1)
    low += (x - low) * (0.02 + 0.5 * p ** 2)
    v = low * 0.22 * p ** 2.2
    left[i] += v
    right[i] += v * 0.9
for b in range(int(REVEAL)):                         # latido
    kick(b + 0.0, 0.25 + 0.1 * b / REVEAL)

# ---------- golpe ----------
kick(REVEAL, 0.9)
i0 = int(REVEAL * RATE)
for i in range(int(2.5 * RATE)):                     # boom grave
    t = i / RATE
    v = math.sin(2 * math.pi * (55 * t - 8 * t * t)) * math.exp(-t * 1.6) * 0.35
    if i0 + i < N:
        left[i0 + i] += v
        right[i0 + i] += v
for m, pan in ((60, -0.4), (64, 0.4), (67, -0.2), (71, 0.2), (76, 0.0)):    # acorde brillante
    tone(REVEAL, 3.2, hz(m), 0.07, pan, attack=0.02, decay=1.4, release=1.0)

# ---------- canción: acordes, bajo, arpegio y ritmo suave ----------
BPM = 96
BEAT = 60 / BPM
CHORDS = [  # (bajo, notas del acorde)
    (41, (57, 60, 64, 65)),   # Fmaj7
    (43, (55, 59, 62, 64)),   # G6
    (40, (55, 59, 62, 64)),   # Em7
    (45, (57, 60, 64, 67)),   # Am7
]
start = REVEAL + 1.2
end = TOTAL - 0.5
bars_per_chord = 2
chord_len = BEAT * 4 * bars_per_chord
t = start
index = 0
while t < end:
    bass, notes = CHORDS[index % len(CHORDS)]
    length = min(chord_len, end - t)
    for k, m in enumerate(notes):                                   # colchón
        tone(t, length + 0.6, hz(m), 0.045, pan=(-0.5 + k / 3), attack=0.9, release=1.0)
    for beat in range(int(length / BEAT)):
        bt = t + beat * BEAT
        tone(bt, BEAT * 0.95, hz(bass), 0.16, table=SINE, attack=0.005, decay=0.35, release=0.05)
        arp = [notes[0] + 12, notes[2] + 12, notes[1] + 12, notes[3] + 12]
        for half in range(2):
            m = arp[(beat * 2 + half) % 4]
            tone(bt + half * BEAT / 2, 0.6, hz(m), 0.05, pan=0.5 if half else -0.5,
                 table=SINE, attack=0.003, decay=0.18, release=0.05)
        if bt > start + chord_len:                                  # el ritmo entra después
            if beat % 2 == 0:
                kick(bt, 0.32)
            hat(bt + BEAT / 2, 0.06, pan=0.3)
    t += chord_len
    index += 1

# ---------- final: salida suave y mezcla ----------
fade = int(3.0 * RATE)
last = int(TOTAL * RATE)
for i in range(fade):
    g = 1 - i / fade
    j = last - fade + i
    left[j] *= g
    right[j] *= g
for j in range(last, N):
    left[j] = right[j] = 0.0
peak = max(max(abs(v) for v in left), max(abs(v) for v in right))
gain = 0.89 / peak
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(RATE)
    frames = bytearray()
    for a, b in zip(left[:last], right[:last]):
        a, b = math.tanh(a * gain * 1.1), math.tanh(b * gain * 1.1)      # limitador suave
        frames += struct.pack("<hh", int(a * 32000), int(b * 32000))
    w.writeframes(bytes(frames))
print("music", OUT, f"{TOTAL:.1f}s")

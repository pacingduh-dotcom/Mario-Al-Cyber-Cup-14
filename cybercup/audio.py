import math
import random
import numpy as np
import pygame

RATE = 22050


def _wave(kind, ph):
    if kind == "square":
        return np.sign(np.sin(ph)) * 0.6
    if kind == "saw":
        return ((ph / (2 * math.pi)) % 1.0) * 2 - 1
    if kind == "tri":
        return 2 * np.abs(((ph / (2 * math.pi)) % 1.0) * 2 - 1) - 1
    return np.sin(ph)


def tone(f0, dur, kind="square", vol=0.5, f1=None, decay=3.0):
    n = int(RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    f = np.linspace(f0, f1 if f1 else f0, n)
    ph = np.cumsum(f) * 2 * math.pi / RATE
    env = np.exp(-decay * t / max(dur, 1e-3)) * np.minimum(1.0, t * 200)
    return _wave(kind, ph) * env * vol


def noise(dur, vol=0.4, decay=5.0):
    n = int(RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    rng = np.random.default_rng(3)
    return rng.uniform(-1, 1, n) * np.exp(-decay * t / dur) * vol


def seq(notes, kind="square", step=0.09, vol=0.4):
    return np.concatenate([tone(f, step * 1.4, kind, vol, decay=4) if f else np.zeros(int(RATE * step)) for f in notes]
                          + [np.zeros(int(RATE * 0.05))])


def mix(*arrs):
    n = max(len(a) for a in arrs)
    out = np.zeros(n)
    for a in arrs:
        out[:len(a)] += a
    return out


def to_sound(a):
    a = np.clip(a, -1, 1)
    pcm = (a * 32000).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack((pcm, pcm))))


def note(n):
    return 440.0 * 2 ** (n / 12)


MOODS = [
    (-9, "major", 128, "square"), (-12, "minor", 140, "saw"), (-10, "phryg", 120, "tri"), (-7, "minor", 110, "sine"),
    (-14, "minor", 132, "square"), (-11, "dim", 126, "saw"), (-5, "major", 138, "tri"), (-16, "phryg", 146, "saw"),
    (-13, "dim", 150, "square"), (-15, "minor", 156, "saw")]
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "phryg": [0, 1, 3, 5, 7, 8, 10],
          "dim": [0, 2, 3, 5, 6, 8, 9]}


def make_track(mood, seed=None, bars=4):
    root, scale, bpm, lead = MOODS[mood % len(MOODS)]
    rng = random.Random(seed if seed is not None else mood * 31 + 5)
    sc = SCALES[scale]
    step = 60.0 / bpm / 2
    steps = 8 * bars
    out = np.zeros(int(RATE * step * steps) + RATE)
    prog = [0, 5, 3, 4] * bars
    for s in range(steps):
        deg = prog[s // 8]
        pos = int(RATE * step * s)
        if s % 2 == 0:
            b = tone(note(root - 12 + sc[deg % 7]), step * 1.6, "tri", 0.30, decay=2.5)
            out[pos:pos + len(b)] += b[:len(out) - pos]
        if s % 4 == 0:
            k = tone(110, 0.12, "sine", 0.35, f1=40, decay=6)
            out[pos:pos + len(k)] += k[:len(out) - pos]
        if s % 4 == 2:
            h = noise(0.05, 0.12, 6)
            out[pos:pos + len(h)] += h[:len(out) - pos]
        if rng.random() < 0.8:
            idx = (deg + rng.choice([0, 2, 4, 7, 9])) % 14
            f = note(root + sc[idx % 7] + 12 * (idx // 7))
            m = tone(f, step * 0.95, lead, 0.16, decay=3.5)
            out[pos:pos + len(m)] += m[:len(out) - pos]
    n = int(RATE * step * steps)
    return out[:n]


class Audio:
    def __init__(self):
        self.ok = False
        self.master = self.music_v = self.sfx_v = 0.7
        self.duck = 1.0
        self.sounds, self.tracks, self.ch, self.current = {}, {}, None, None
        try:
            pygame.mixer.init(RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(12)
            self.ch = pygame.mixer.Channel(0)
            self._build()
            self.ok = True
        except Exception:
            self.ok = False

    def _build(self):
        S = self.sounds
        S["jump"] = to_sound(tone(300, 0.16, "square", 0.25, 720, 2))
        S["land"] = to_sound(noise(0.05, 0.12, 6))
        S["coin"] = to_sound(seq([988, 1319], "square", 0.06, 0.22))
        S["gem"] = to_sound(seq([784, 988, 1175, 1568], "tri", 0.06, 0.3))
        S["stomp"] = to_sound(mix(tone(420, 0.16, "square", 0.3, 90, 4), noise(0.08, 0.2)))
        S["hit"] = to_sound(tone(200, 0.08, "saw", 0.3, 120, 4))
        S["clang"] = to_sound(mix(tone(900, 0.12, "sine", 0.3, 700, 5), noise(0.04, 0.2)))
        S["attack"] = to_sound(noise(0.12, 0.25, 6))
        S["dash"] = to_sound(tone(200, 0.15, "saw", 0.18, 600, 3))
        S["hurt"] = to_sound(tone(330, 0.3, "saw", 0.35, 70, 3))
        S["death"] = to_sound(seq([440, 392, 330, 262, 196, 130], "square", 0.1, 0.3))
        S["checkpoint"] = to_sound(seq([523, 659, 784, 1047], "tri", 0.08, 0.35))
        S["complete"] = to_sound(seq([523, 659, 784, 659, 784, 1047, 0, 1047, 1319], "square", 0.1, 0.3))
        S["boss_intro"] = to_sound(mix(tone(70, 1.4, "saw", 0.4, 140, 1.2), tone(105, 1.4, "square", 0.2, 210, 1.2)))
        S["boss_attack"] = to_sound(mix(tone(180, 0.25, "saw", 0.3, 60, 3), noise(0.2, 0.25)))
        S["boss_hit"] = to_sound(mix(tone(500, 0.2, "square", 0.3, 120, 3), noise(0.15, 0.3)))
        S["boss_phase"] = to_sound(seq([200, 300, 400, 600, 800], "saw", 0.07, 0.3))
        S["boss_die"] = to_sound(mix(noise(1.2, 0.5, 2.5), tone(200, 1.2, "saw", 0.3, 30, 2)))
        S["gameover"] = to_sound(seq([392, 370, 349, 330, 294, 262, 196], "tri", 0.18, 0.4))
        S["menu"] = to_sound(tone(660, 0.05, "square", 0.15, 880, 4))
        S["select"] = to_sound(seq([660, 990], "square", 0.05, 0.2))
        S["victory"] = to_sound(seq([523, 523, 523, 659, 784, 0, 784, 880, 1047, 0, 1319, 1047, 1319, 1568], "square", 0.12, 0.3))

    def track(self, key):
        if key not in self.tracks:
            if key == "menu":
                a = make_track(0, 11)
            elif key == "victory":
                a = make_track(6, 99, 2)
            elif key == "boss":
                a = make_track(9, 7)
            else:
                a = make_track(int(key))
            self.tracks[key] = to_sound(a)
        return self.tracks[key]

    def music(self, key):
        if not self.ok or key == self.current:
            return
        try:
            self.current = key
            self.ch.play(self.track(key), loops=-1)
            self.apply()
        except Exception:
            pass

    def stop_music(self):
        if self.ok:
            self.ch.stop()
            self.current = None

    def apply(self, master=None, music=None, sfx=None):
        if master is not None:
            self.master, self.music_v, self.sfx_v = master / 100, music / 100, sfx / 100
        if self.ok and self.ch:
            self.ch.set_volume(self.master * self.music_v * self.duck)

    def play(self, name):
        if not self.ok:
            return
        s = self.sounds.get(name)
        if s:
            s.set_volume(self.master * self.sfx_v)
            s.play()

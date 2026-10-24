import math
import random
import pygame
from .ui import W, H, text, heart
from .config import DOOR_HIDE_T

PIT_COLOR = (10, 5, 25)
_ATTACK_FX = None


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_sky(top, bottom):
    s = pygame.Surface((W, H))
    for y in range(0, H, 4):
        pygame.draw.rect(s, lerp(top, bottom, y / H), (0, y, W, 4))
    return s.convert()


def make_layer(style, i, base, rng):
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    col = (*lerp(base, (10, 10, 40), 0.35 + 0.2 * i), 255 - i * 30)
    top = 250 + i * 90

    def wrap(fn):
        fn(0)
        fn(-W)
    if style in ("hills", "desert"):
        k = 2 + i
        pts = [(x, top + 40 - 50 * math.sin(2 * math.pi * k * x / W + i) - 20 * math.sin(2 * math.pi * (k + 2) * x / W))
               for x in range(0, W + 1, 16)]
        pygame.draw.polygon(s, col, pts + [(W, H), (0, H)])
        if style == "desert" and i == 0:
            for _ in range(3):
                px = rng.randint(100, W - 200)
                pygame.draw.polygon(s, lerp(base, (80, 40, 20), 0.5), [(px, top + 40), (px + 90, top - 80), (px + 180, top + 40)])
    elif style in ("city", "factory", "sky", "arena", "quantum"):
        x = 0
        while x < W:
            w = rng.randint(50, 120)
            h = rng.randint(80, 260) if style != "sky" else rng.randint(30, 90)
            y = top + 120 - h if style != "sky" else top - 60 + rng.randint(0, 120)
            if style == "quantum":
                c = (x + w // 2, y + 40)
                pygame.draw.polygon(s, col, [(c[0], c[1] - 40), (c[0] + 30, c[1]), (c[0], c[1] + 40), (c[0] - 30, c[1])], 2)
            elif style == "sky":
                pygame.draw.ellipse(s, (255, 255, 255, 120), (x, y + 150, w * 2, 40))
                pygame.draw.polygon(s, col, [(x, y + 80), (x + w, y + 80), (x + w // 2, y + 120)])
            else:
                pygame.draw.rect(s, col, (x, y, w, H))
                for wy in range(y + 10, y + h - 5, 22):
                    for wx in range(x + 8, x + w - 8, 18):
                        if rng.random() < 0.35:
                            pygame.draw.rect(s, (255, 230, 120, 160) if style != "arena" else (255, 60, 180, 160), (wx, wy, 6, 8))
            x += w + rng.randint(4, 24)
    elif style == "mountain":
        for _ in range(5):
            cx = rng.randint(0, W)
            hh = rng.randint(140, 260) - i * 30
            for off in (0, -W, W):
                pygame.draw.polygon(s, col, [(cx + off - hh, H), (cx + off, top + 100 - hh), (cx + off + hh, H)])
                pygame.draw.polygon(s, (240, 250, 255, 220), [(cx + off - hh // 4, top + 100 - hh * 3 // 4), (cx + off, top + 100 - hh),
                                                                (cx + off + hh // 4, top + 100 - hh * 3 // 4)])
    elif style == "forest":
        for _ in range(16):
            x = rng.randint(0, W)
            h = rng.randint(120, 300)
            for off in (0, -W):
                pygame.draw.rect(s, col, (x + off, top + 100 - h, 14, h + 400))
                pygame.draw.circle(s, (*lerp(base, (255, 0, 255), 0.3), 150), (x + off + 7, top + 100 - h), rng.randint(30, 55))
    elif style == "lava":
        x = 0
        while x < W:
            w = rng.randint(60, 140)
            h = rng.randint(80, 240)
            pygame.draw.polygon(s, col, [(x, H), (x + w // 2, top + 100 - h), (x + w, H)])
            x += w - 20
        pygame.draw.rect(s, (255, 90, 20, 90), (0, H - 90, W, 90))
    return s.convert_alpha()


class Background:
    def __init__(self, spec, idx):
        rng = random.Random(900 + idx)
        self.sky = make_sky(*spec["sky"])
        self.layers = [(make_layer(spec["style"], i, spec["sky"][1] if spec["style"] in ("hills", "desert", "mountain") else spec["accent"], rng), 0.12 + 0.16 * i)
                       for i in range(3)]
        self.style = spec["style"]
        self.stars = [(rng.randint(0, W), rng.randint(0, 300), rng.random()) for _ in range(50)]
        self.clouds = [(rng.randint(0, W), rng.randint(40, 220), rng.randint(60, 130)) for _ in range(6)]

    def draw(self, surf, cam, t):
        surf.blit(self.sky, (0, 0))
        if self.style in ("quantum", "arena", "city", "forest", "lava", "factory"):
            for (x, y, p) in self.stars:
                if int(t * 2 + p * 10) % 3:
                    surf.fill((255, 255, 255), (x, y, 2, 2))
        if self.style in ("hills", "sky", "desert", "mountain"):
            for (x, y, w) in self.clouds:
                cx = (x + t * 8 - cam * 0.05) % (W + 200) - 100
                pygame.draw.ellipse(surf, (255, 255, 255), (cx, y, w, w // 3))
                pygame.draw.ellipse(surf, (255, 255, 255), (cx + w // 5, y - w // 8, w // 2, w // 3))
        for layer, f in self.layers:
            off = int(-cam * f) % W
            surf.blit(layer, (off - W, 0))
            surf.blit(layer, (off, 0))
        if self.style in ("arena", "quantum"):
            for gx in range(0, W, 80):
                x = (gx - int(cam * 0.3)) % W
                pygame.draw.line(surf, (90, 20, 130), (x, 420), (W // 2 + (x - W // 2) * 3, H), 1)


def solid_colors(spec, kind):
    g, a = spec["ground"], spec["accent"]
    return {"normal": (g, a), "ice": ((120, 190, 235), (220, 250, 255)), "conveyor": ((70, 70, 80), (255, 200, 40)),
            "moving": ((50, 60, 110), (80, 230, 255)), "collapsing": ((150, 100, 60), (255, 160, 60)),
            "vanishing": ((120, 40, 160), (255, 100, 255)), "wall": ((40, 20, 90), (255, 60, 200))}[kind]


def draw_solid(surf, o, cam, spec, t):
    x = int(o.x - cam)
    if x > W or x + o.w < 0:
        return
    body, edge = solid_colors(spec, o.kind)
    y = int(o.y)
    if o.kind == "collapsing" and o.state == "shaking":
        x += int(math.sin(t * 90) * 2)
    if o.kind == "vanishing":
        if not o.active:
            pygame.draw.rect(surf, edge, (x, y, int(o.w), 24), 1)
            return
        if o.warn and int(t * 14) % 2:
            return
    if o.kind == "collapsing" and not o.active:
        return
    h = int(min(o.h, H - y + 10))
    pygame.draw.rect(surf, body, (x, y, int(o.w), h))
    pygame.draw.rect(surf, edge, (x, y, int(o.w), 6))
    if o.kind == "conveyor":
        d = 1 if o.belt > 0 else -1
        for cx in range(int(x) + int((t * 60 * d) % 24), int(x + o.w) - 8, 24):
            pygame.draw.polygon(surf, edge, [(cx, y + 9), (cx + 8 * d, y + 14), (cx, y + 19)])
    elif o.kind == "wall":
        pygame.draw.line(surf, edge, (x + 4, y), (x + 4, y + h), 2)
    elif o.h > 100 and o.kind in ("normal", "ice"):
        for gx in range(x + 20, x + int(o.w), 64):
            pygame.draw.line(surf, tuple(max(0, c - 25) for c in body), (gx, y + 14), (gx, y + 70), 1)


def draw_player(surf, p, cam, t):
    if p.inv_t > 0 and int(t * 20) % 2:
        return
    x, y = int(p.x - cam), int(p.y)
    f = p.facing
    body = (60, 120, 255) if p.state != "hurt" else (255, 80, 80)
    if p.dash_t > 0:
        for i in range(1, 4):
            pygame.draw.rect(surf, (80, 200, 255), (x - f * i * 14, y + 8, p.W, 28), border_radius=5, width=1)
    run = math.sin(t * 16) * 5 if p.state == "run" else 0
    air = p.state in ("jump", "fall")
    pygame.draw.rect(surf, (30, 30, 70), (x + 3 + int(run), y + 30, 8, 10 - (3 if air else 0)), border_radius=2)
    pygame.draw.rect(surf, (30, 30, 70), (x + 15 - int(run), y + 30, 8, 10 - (3 if air else 0)), border_radius=2)
    bob = int(math.sin(t * 4)) if p.state == "idle" else 0
    pygame.draw.rect(surf, body, (x + 1, y + 13 + bob, 24, 18), border_radius=5)
    pygame.draw.rect(surf, (230, 60, 140), (x + 1, y + 24 + bob, 24, 4))
    pygame.draw.rect(surf, (235, 235, 255), (x + 2, y + 1 + bob, 22, 15), border_radius=6)
    pygame.draw.rect(surf, (0, 230, 255), (x + (11 if f > 0 else 2), y + 5 + bob, 11, 6), border_radius=3)
    pygame.draw.rect(surf, (230, 60, 140), (x + 1, y - 1 + bob, 24, 5), border_radius=3)
    if p.state == "celebrate":
        pygame.draw.line(surf, body, (x, y + 16), (x - 8, y + 2), 5)
        pygame.draw.line(surf, body, (x + 26, y + 16), (x + 34, y + 2), 5)
    if p.attack_t > 0:
        ax = x + p.W if f > 0 else x - 40
        global _ATTACK_FX
        if _ATTACK_FX is None:
            _ATTACK_FX = pygame.Surface((40, 30), pygame.SRCALPHA)
            pygame.draw.ellipse(_ATTACK_FX, (160, 255, 255, 200), (0, 4, 40, 22), 4)
        surf.blit(_ATTACK_FX, (ax, y + 4))


def draw_enemy(surf, e, cam, t):
    x, y = int(e.x - cam), int(e.y)
    if x > W + 50 or x < -80:
        return
    if not e.alive:
        k = max(0, e.dead_t / 0.45)
        pygame.draw.rect(surf, (255, 255, 255), (x, y + int(e.h * (1 - k)), e.w, max(2, int(e.h * k))), 2)
        return
    k = e.kind
    fl = e.hurt_flash > 0
    if k == "walker":
        c = (255, 255, 255) if fl else (230, 60, 80)
        pygame.draw.rect(surf, c, (x, y + 4, e.w, e.h - 8), border_radius=8)
        pygame.draw.rect(surf, (60, 10, 30), (x + 2 + int(math.sin(t * 10) * 2), y + e.h - 6, 10, 6))
        pygame.draw.rect(surf, (60, 10, 30), (x + e.w - 12 - int(math.sin(t * 10) * 2), y + e.h - 6, 10, 6))
        pygame.draw.circle(surf, (255, 255, 255), (x + 9, y + 12), 4)
        pygame.draw.circle(surf, (255, 255, 255), (x + e.w - 9, y + 12), 4)
        pygame.draw.line(surf, (60, 10, 30), (x + 5, y + 6), (x + 13, y + 9), 3)
        pygame.draw.line(surf, (60, 10, 30), (x + e.w - 5, y + 6), (x + e.w - 13, y + 9), 3)
    elif k == "armored":
        c = (255, 255, 255) if fl else (130, 140, 160)
        pygame.draw.rect(surf, c, (x, y, e.w, e.h), border_radius=6)
        pygame.draw.rect(surf, (80, 90, 110), (x + 4, y + 4, e.w - 8, e.h - 14), 3, border_radius=4)
        pygame.draw.rect(surf, (255, 190, 40), (x + 7, y + 12, e.w - 14, 5))
        for i in range(e.hp):
            pygame.draw.rect(surf, (255, 190, 40), (x + 4 + i * 10, y - 7, 8, 4))
    elif k == "jumper":
        c = (255, 255, 255) if fl else (255, 150, 40)
        pygame.draw.rect(surf, c, (x + 2, y, e.w - 4, e.h - 10), border_radius=6)
        pygame.draw.line(surf, (200, 200, 220), (x + 8, y + e.h), (x + 14, y + e.h - 10), 3)
        pygame.draw.line(surf, (200, 200, 220), (x + e.w - 8, y + e.h), (x + e.w - 14, y + e.h - 10), 3)
        pygame.draw.circle(surf, (20, 20, 40), (x + e.w // 2, y + 9), 5)
    elif k == "drone":
        c = (255, 255, 255) if fl else (40, 220, 240)
        pygame.draw.ellipse(surf, c, (x, y + 4, e.w, e.h - 4))
        rw = int(math.sin(t * 40) * 14)
        pygame.draw.line(surf, (220, 255, 255), (x + e.w // 2 - 14 - rw // 3, y), (x + e.w // 2 + 14 + rw // 3, y), 3)
        pygame.draw.circle(surf, (255, 60, 90), (x + e.w // 2, y + 12), 3)
    elif k == "turret":
        pygame.draw.rect(surf, (90, 90, 110), (x, y + 14, e.w, e.h - 14), border_radius=4)
        pygame.draw.circle(surf, (255, 80, 80) if (e.warn and int(t * 16) % 2) else (150, 150, 170), (x + e.w // 2, y + 12), 12)
        if e.warn:
            text(surf, "!", 22, (255, 220, 60), (x + e.w // 2, y - 14))
    elif k == "teleporter":
        if e.ghost:
            pygame.draw.rect(surf, (200, 100, 255), (x, y, e.w, e.h), 1, border_radius=8)
            return
        if e.fading and int(t * 20) % 2:
            return
        c = (255, 255, 255) if fl else (170, 80, 255)
        pygame.draw.rect(surf, c, (x, y, e.w, e.h), border_radius=10)
        pygame.draw.rect(surf, (255, 90, 255), (x + 5, y + 8, e.w - 10, 6))
        pygame.draw.rect(surf, (255, 90, 255), (x + 5, y + 20, e.w - 10, 3))


def draw_boss(surf, b, spec, cam, t):
    x, y = int(b.x - cam), int(b.y)
    col = spec["accent"]
    if b.flash > 0:
        col = (255, 255, 255)
    if not b.alive and int(t * 20) % 2:
        return
    pygame.draw.rect(surf, (40, 30, 70), (x, y, b.w, b.h), border_radius=14)
    pygame.draw.rect(surf, col, (x, y, b.w, b.h), 4, border_radius=14)
    eye_y = y + b.h // 4
    pygame.draw.rect(surf, (255, 255, 255), (x + 12, eye_y, b.w - 24, 12), border_radius=4)
    pygame.draw.circle(surf, (255, 40, 60), (x + b.w // 2 + int(b.dir * 8), eye_y + 6), 6)
    core = (0, 255, 255) if b.vulnerable and int(t * 8) % 2 else (255, 60, 160)
    pygame.draw.circle(surf, core, (x + b.w // 2, y + b.h * 2 // 3), 14)
    pygame.draw.circle(surf, (255, 255, 255), (x + b.w // 2, y + b.h * 2 // 3), 14, 2)
    if b.max_hp >= 15:
        for i in range(5):
            pygame.draw.polygon(surf, col, [(x + i * b.w // 5, y), (x + i * b.w // 5 + b.w // 10, y - 22), (x + (i + 1) * b.w // 5, y)])
    if b.state == "telegraph":
        r = int(b.w * (0.6 + (1 - b.timer / 0.8) * 0.9))
        pygame.draw.circle(surf, (255, 220, 60), (x + b.w // 2, y + b.h // 2), r, 3)
        text(surf, "!", 40, (255, 220, 60), (x + b.w // 2, y - 36))
    elif b.state == "tired":
        for i in range(3):
            a = t * 4 + i * 2.1
            pygame.draw.circle(surf, (255, 255, 120), (x + b.w // 2 + int(math.cos(a) * 26), y - 12 + int(math.sin(a) * 5)), 4)
        text(surf, "HIT ME!", 16, (0, 255, 255), (x + b.w // 2, y - 34))


def draw_world(surf, w, cam, t, bg, particles):
    spec = w.lv.spec
    bg.draw(surf, cam, t)
    lvw = w.lv
    for o in w.solids:
        draw_solid(surf, o, cam, spec, t)
    for (sx, sy, sw, sh) in lvw.spikes:
        for i in range(int(sw // 16)):
            bx = int(sx - cam + i * 16)
            pygame.draw.polygon(surf, (230, 230, 245), [(bx, sy + sh), (bx + 8, sy), (bx + 16, sy + sh)])
    for ic in w.icicles:
        shake = int(math.sin(t * 80) * 2) if ic["state"] == "shake" else 0
        if ic["state"] != "reset":
            ix = int(ic["x"] - cam) + shake
            pygame.draw.polygon(surf, (190, 240, 255), [(ix - 9, int(ic["y"])), (ix + 9, int(ic["y"])), (ix, int(ic["y"]) + 36)])
    for o, (ox, oy) in zip(lvw.orbiters, w.orbit_pos):
        pygame.draw.circle(surf, (90, 50, 20), (int(o["cx"] - cam), int(o["cy"])), 4)
        pygame.draw.circle(surf, (255, 120, 30), (int(ox - cam), int(oy)), 11)
        pygame.draw.circle(surf, (255, 240, 120), (int(ox - cam), int(oy)), 5)
    for i, (cx, cy) in enumerate(lvw.checkpoints):
        x = int(cx - cam)
        on = i in w.cp_done
        pygame.draw.line(surf, (200, 200, 220), (x, cy), (x, cy - 70), 4)
        pygame.draw.polygon(surf, (60, 255, 140) if on else (120, 120, 150),
                            [(x + 2, cy - 70), (x + 38, cy - 58 + int(math.sin(t * 5) * 3)), (x + 2, cy - 46)])
        if on:
            pygame.draw.circle(surf, (60, 255, 140), (x, cy - 74), 6)
    for g in w.gems:
        if g[2]:
            gx, gy = int(g[0] - cam), int(g[1] + math.sin(t * 3 + g[0]) * 3)
            pygame.draw.polygon(surf, (255, 80, 220), [(gx, gy - 13), (gx + 11, gy), (gx, gy + 13), (gx - 11, gy)])
            pygame.draw.polygon(surf, (255, 255, 255), [(gx, gy - 13), (gx + 11, gy), (gx, gy + 13), (gx - 11, gy)], 2)
    if not w.has_key:
        kx, ky = lvw.key
        kx = int(kx - cam)
        ky = int(ky + math.sin(t * 3) * 4)
        if -40 < kx < W + 40:
            glow = 14 + int(math.sin(t * 6) * 3)
            pygame.draw.circle(surf, (120, 90, 10), (kx, ky), glow + 6, 2)
            pygame.draw.circle(surf, (255, 215, 50), (kx - 7, ky - 4), 8, 4)
            pygame.draw.rect(surf, (255, 215, 50), (kx - 2, ky - 1, 18, 5))
            pygame.draw.rect(surf, (255, 215, 50), (kx + 9, ky + 3, 4, 7))
            pygame.draw.rect(surf, (255, 215, 50), (kx + 15, ky + 3, 4, 5))
            text(surf, "KEY", 14, (255, 240, 150), (kx, ky - 30))
    ex, ey, ew, eh = lvw.exit
    exx = int(ex - cam)
    ok = w.exit_open
    col = (60, 255, 160) if ok else (255, 70, 90)
    op = getattr(w, "door_open", 0.0)
    pygame.draw.rect(surf, (20, 20, 50), (exx, ey, ew, eh))
    if op > 0:
        pygame.draw.rect(surf, (200, 255, 230), (exx + 6, ey + 6, ew - 12, eh - 6))
    half = ew // 2
    pw = int(half * (1.0 - op))
    pygame.draw.rect(surf, (36, 36, 80), (exx, ey, pw, eh))
    pygame.draw.rect(surf, (36, 36, 80), (exx + ew - pw, ey, pw, eh))
    pygame.draw.rect(surf, col, (exx, ey, ew, eh), 4)
    if ok:
        if op < 1.0:
            pygame.draw.rect(surf, (*col,), (exx + 10, ey + 10, ew - 20, eh - 10), 1)
        text(surf, "EXIT", 18, col, (exx + ew // 2, ey - 14))
    else:
        text(surf, "LOCKED" if w.has_key else "NEED KEY", 14, col, (exx + ew // 2, ey - 14))
    for e in w.enemies:
        draw_enemy(surf, e, cam, t)
    if w.boss:
        draw_boss(surf, w.boss, spec, cam, t)
        for (cx, warn, active) in w.boss.columns:
            x = int(cx - cam)
            if active > 0:
                pygame.draw.rect(surf, (255, 255, 255), (x - 28, int(w.boss.floor) - 600, 56, 600))
                pygame.draw.rect(surf, (255, 60, 160), (x - 28, int(w.boss.floor) - 600, 56, 600), 3)
            else:
                fl = int(t * 12) % 2
                pygame.draw.rect(surf, (255, 220, 60) if fl else (255, 90, 60), (x - 28, int(w.boss.floor) - 8, 56, 8))
                pygame.draw.polygon(surf, (255, 220, 60), [(x - 14, int(w.boss.floor) - 30), (x + 14, int(w.boss.floor) - 30), (x, int(w.boss.floor) - 12)])
    for s in w.shots:
        pygame.draw.circle(surf, (255, 90, 200), (int(s.x - cam), int(s.y)), s.r + 3)
        pygame.draw.circle(surf, (255, 255, 255), (int(s.x - cam), int(s.y)), s.r - 2)
    if w.state == "complete" and w.complete_t > DOOR_HIDE_T:
        pass
    elif w.state != "dead":
        draw_player(surf, w.player, cam, t)
    else:
        p = w.player
        k = 1.5 - w.dead_t
        pygame.draw.rect(surf, (255, 80, 80), (int(p.x - cam), int(p.y - 60 * math.sin(min(k, 1) * 3)), p.W, p.H), 3, border_radius=6)
    for (px, py, vx, vy, life, col, size) in particles:
        pygame.draw.rect(surf, col, (int(px - cam), int(py), size, size))
    if spec["style"] == "lava":
        pygame.draw.rect(surf, (255, 90, 20), (0, H - 24 + int(math.sin(t * 3) * 3), W, 40))

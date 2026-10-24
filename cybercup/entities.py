import math
import random
from .physics import overlap

RNG = random.Random(7)


class Projectile:
    def __init__(self, x, y, vx, vy, life=4.0, r=8):
        self.x, self.y, self.vx, self.vy, self.life, self.r = x, y, vx, vy, life, r

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def rect(self):
        return (self.x - self.r, self.y - self.r, self.r * 2, self.r * 2)


SIZES = {"walker": (30, 28), "jumper": (28, 32), "drone": (32, 20), "turret": (30, 34),
         "armored": (34, 34), "teleporter": (28, 34)}


class Enemy:
    def __init__(self, kind, px, py, pw, speed_mul):
        self.kind = kind
        self.w, self.h = SIZES[kind]
        self.left, self.right = px + 8, px + pw - 8
        self.floor = py
        self.hp = 3 if kind == "armored" else 1
        self.alive = True
        self.dead_t = 0.0
        self.t = RNG.random() * 6
        self.dir = RNG.choice([-1, 1])
        self.speed = {"walker": 60, "armored": 45, "jumper": 70, "teleporter": 55}.get(kind, 0) * speed_mul
        self.x = RNG.uniform(self.left + 40, max(self.left + 41, self.right - 40 - self.w))
        self.y = py - self.h
        self.vy = 0.0
        self.timer = RNG.uniform(0.5, 2.0)
        self.warn = False
        self.ghost = False
        self.fading = False
        self.cx = px + pw / 2
        self.hurt_flash = 0.0
        if kind == "turret":
            self.x = self.right - self.w
        if kind == "drone":
            self.y = py - 105
            self.base_y = self.y

    def damage(self, n=1):
        self.hp -= n
        self.hurt_flash = 0.15
        if self.hp <= 0:
            self.alive, self.dead_t = False, 0.45
            return True
        return False

    def update(self, dt, player, shots, speed_mul):
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        if not self.alive:
            self.dead_t -= dt
            return
        k = self.kind
        if k in ("walker", "armored"):
            self.x += self.dir * self.speed * dt
            if self.x < self.left:
                self.x, self.dir = self.left, 1
            elif self.x + self.w > self.right:
                self.x, self.dir = self.right - self.w, -1
        elif k == "jumper":
            self.timer -= dt
            on_floor = self.y + self.h >= self.floor - 0.01 and self.vy >= 0
            if on_floor:
                self.y, self.vy = self.floor - self.h, 0.0
                if self.timer <= 0 and abs(player.x - self.x) < 420:
                    self.vy = -520
                    self.dir = 1 if player.x > self.x else -1
                    self.timer = 1.5 / speed_mul
            else:
                self.vy += 1800 * dt
                self.y += self.vy * dt
                self.x += self.dir * 130 * speed_mul * dt
                self.x = max(self.left, min(self.right - self.w, self.x))
                if self.y + self.h >= self.floor and self.vy > 0:
                    self.y, self.vy = self.floor - self.h, 0.0
        elif k == "drone":
            self.t += dt
            self.x = self.cx + 150 * math.sin(self.t * 1.1 * speed_mul) - self.w / 2
            self.y = self.base_y + 10 * math.sin(self.t * 3)
        elif k == "turret":
            self.timer -= dt
            self.warn = 0 < self.timer < 0.7
            if self.timer <= 0:
                self.timer = 2.4 / speed_mul
                dirx = -1 if player.x < self.x else 1
                shots.append(Projectile(self.x + self.w / 2, self.y + 12, dirx * 290, 0, 3.5))
        elif k == "teleporter":
            self.t += dt
            cyc = self.t % 3.0
            self.fading = 1.2 < cyc < 1.6
            was = self.ghost
            self.ghost = 1.6 <= cyc < 2.2
            if was and not self.ghost:
                off = RNG.choice([-1, 1]) * RNG.uniform(90, 160)
                self.x = max(self.left, min(self.right - self.w, player.x + off))
            if not self.ghost:
                self.x += self.dir * self.speed * dt
                if self.x < self.left:
                    self.x, self.dir = self.left, 1
                elif self.x + self.w > self.right:
                    self.x, self.dir = self.right - self.w, -1

    def solid_to_player(self):
        return self.alive and not self.ghost






BOSS_MOVE_T = 0.6
BOSS_TELEGRAPH_T = 0.5
BOSS_ATTACK_T = 1.1
BOSS_SHOT_LIFE = 1.05
BOSS_COL_WARN, BOSS_COL_ACTIVE = 0.65, 0.4
BOSS_TIRED_T = 3.0
BOSS_RECOVER_T = 0.5


class Boss:
    def __init__(self, spec, arena, floor_y, level_idx, speed_mul):
        self.name, self.max_hp, self.phases = spec["name"], spec["hp"], spec["phases"]
        self.w, self.h = spec["w"], spec["h"]
        self.hp = self.max_hp
        self.left, self.right = arena["x"] + 90, arena["x"] + arena["w"] - 20
        self.floor, self.x = floor_y, arena["x"] + arena["w"] - 300
        self.y = floor_y - self.h
        self.state, self.timer = "intro", 2.2
        self.dir, self.phase, self.alive = -1, 0, True
        self.dying = 0.0
        self.invuln = 0.0
        self.speed_mul = speed_mul * (0.9 + 0.04 * level_idx)
        self.columns = []
        self.flash = 0.0
        self.pattern_i = 0
        self.age = 0.0

    @property
    def vulnerable(self):
        return self.state == "tired" and self.invuln <= 0 and self.alive

    def hit(self):
        self.hp -= 1
        self.invuln, self.flash = 0.5, 0.2
        newp = min(self.phases - 1, int((1 - self.hp / self.max_hp) * self.phases))
        ev = ["boss_hit"]
        if self.hp <= 0:
            self.alive, self.dying, self.state = False, 2.2, "dying"
            ev.append("boss_die")
        elif newp != self.phase:
            self.phase = newp
            self.state, self.timer = "phase", 1.4
            ev.append("boss_phase")
        return ev

    def clear_hazards(self, shots):
        shots[:] = [s for s in shots if not getattr(s, "boss", False)]
        self.columns = []

    def tempo(self):
        return (1.0 + 0.25 * self.phase) * self.speed_mul

    def update(self, dt, player, shots):
        ev = []
        self.age += dt
        self.invuln = max(0.0, self.invuln - dt)
        self.flash = max(0.0, self.flash - dt)
        for c in self.columns:
            if c[1] > 0:
                c[1] -= dt
                if c[1] <= 0:
                    c[2] = BOSS_COL_ACTIVE
                    ev.append("boss_attack")
            elif c[2] > 0:
                c[2] -= dt
        self.columns = [c for c in self.columns if c[1] > 0 or c[2] > 0]
        if self.state == "dying":
            self.dying -= dt
            return ev
        self.timer -= dt
        st = self.state
        if st in ("intro", "phase"):
            if self.timer <= 0:
                self.state, self.timer = "move", BOSS_MOVE_T / self.tempo()
        elif st == "move":
            self.x += self.dir * 90 * self.tempo() * dt
            if self.x < self.left:
                self.x, self.dir = self.left, 1
            elif self.x + self.w > self.right:
                self.x, self.dir = self.right - self.w, -1
            if self.timer <= 0:
                self.state, self.timer = "telegraph", BOSS_TELEGRAPH_T / min(1.4, self.tempo())
        elif st == "telegraph":
            if self.timer <= 0:
                ev += self._attack(player, shots)
                self.state, self.timer = "attack", BOSS_ATTACK_T
        elif st == "attack":
            if self.timer <= 0:
                self.clear_hazards(shots)
                self.state, self.timer = "tired", BOSS_TIRED_T / min(1.3, self.tempo())
        elif st == "tired":
            if self.timer <= 0:
                self.state, self.timer = "move", BOSS_RECOVER_T / self.tempo()
                self.dir = 1 if player.x > self.x else -1
        return ev

    def _attack(self, player, shots):
        cx, cy = self.x + self.w / 2, self.y + self.h * 0.45
        base = math.atan2((player.y + 20) - cy, (player.x + 13) - cx)
        n_shots = (1, 3, 5)[self.phase]
        spread = 0.28
        base = max(-0.5, min(0.5, base)) if abs(math.cos(base)) < 0.5 else base
        sp = 330 + 40 * self.phase
        for i in range(n_shots):
            a = base + (i - (n_shots - 1) / 2) * spread
            p = Projectile(cx, cy, math.cos(a) * sp, math.sin(a) * sp, BOSS_SHOT_LIFE, 9)
            p.boss = True
            shots.append(p)
        if self.phase >= 1:
            n_cols = 2 + self.phase
            span = self.right - self.left
            for i in range(n_cols):
                cxp = self.left + span * (i + 0.5) / n_cols + RNG.uniform(-60, 60)
                self.columns.append([cxp, BOSS_COL_WARN, 0.0])
        return ["boss_attack"]

    def rect(self):
        return (self.x, self.y, self.w, self.h)

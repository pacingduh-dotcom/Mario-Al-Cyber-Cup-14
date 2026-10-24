import math

GRAVITY = 2200.0
MAX_FALL = 1000.0
RUN_SPEED = 320.0
GROUND_ACCEL = 2600.0
GROUND_FRICTION = 3200.0
ICE_ACCEL = 900.0
ICE_FRICTION = 450.0
AIR_ACCEL = 1900.0
AIR_DRAG = 500.0
JUMP_VELOCITY = 780.0
RISE_CUT_GRAVITY = 2.4
COYOTE_TIME = 0.10
JUMP_BUFFER = 0.12
DASH_SPEED = 650.0
DASH_TIME = 0.16
DASH_COOLDOWN = 0.6
ATTACK_TIME = 0.22
FLY_SPEED = 380.0
FLY_ACCEL = 4200.0
MAX_JUMP_HEIGHT = JUMP_VELOCITY ** 2 / (2 * GRAVITY)
MAX_JUMP_DISTANCE = RUN_SPEED * 2 * JUMP_VELOCITY / GRAVITY


def approach(v, target, step):
    if v < target:
        return min(v + step, target)
    return max(v - step, target)


class Solid:

    def __init__(self, x, y, w, h, kind="normal", **kw):
        self.x, self.y, self.w, self.h = float(x), float(y), float(w), float(h)
        self.kind = kind
        self.active = True
        self.dx = 0.0
        self.belt = kw.get("belt", 0.0)
        self.ax = kw.get("ax", self.x)
        self.bx = kw.get("bx", self.x)
        self.period = kw.get("period", 4.0)
        self.offset = kw.get("offset", 0.0)
        self.on_time = kw.get("on_time", 1.8)
        self.off_time = kw.get("off_time", 1.0)
        self.state = "idle"
        self.timer = 0.0
        self.warn = False
        self.home_x = self.x

    def touch(self):
        if self.kind == "collapsing" and self.state == "idle":
            self.state, self.timer = "shaking", 0.5

    def update(self, dt, t):
        self.dx = 0.0
        if self.kind == "moving":
            k = (1 - math.cos(2 * math.pi * (t + self.offset) / self.period)) / 2
            nx = self.ax + (self.bx - self.ax) * k
            self.dx = nx - self.x
            self.x = nx
        elif self.kind == "collapsing":
            if self.state == "shaking":
                self.timer -= dt
                if self.timer <= 0:
                    self.state, self.timer, self.active = "fallen", 2.5, False
            elif self.state == "fallen":
                self.timer -= dt
                if self.timer <= 0:
                    self.state, self.active = "idle", True
        elif self.kind == "vanishing":
            cyc = self.on_time + self.off_time
            ph = (t + self.offset) % cyc
            self.active = ph < self.on_time
            self.warn = self.active and ph > self.on_time - 0.5


def overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


class Player:
    W, H = 26, 40

    def __init__(self, x, y):
        self.speed_mul = 1.0
        self.jump_mul = 1.0
        self.fly = False
        self.noclip = False
        self.reset(x, y)

    def reset(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.ground = None
        self.coyote = 0.0
        self.buffer = 0.0
        self.facing = 1
        self.dash_t = 0.0
        self.dash_cd = 0.0
        self.hurt_t = 0.0
        self.inv_t = 0.0
        self.attack_t = 0.0
        self.attack_hit = set()
        self.state = "idle"
        self.celebrate = False

    def hit(self, o):
        return overlap(self.x, self.y, self.W, self.H, o.x, o.y, o.w, o.h)

    def move_x(self, dx, solids):
        self.x += dx
        for o in solids:
            if o.active and self.hit(o):
                if dx > 0:
                    self.x = o.x - self.W
                elif dx < 0:
                    self.x = o.x + o.w
                self.vx = 0.0

    def move_y(self, dy, solids):
        self.y += dy
        self.on_ground, self.ground = False, None
        for o in solids:
            if o.active and self.hit(o):
                if self.vy >= 0:
                    self.y = o.y - self.H
                    self.on_ground, self.ground = True, o
                else:
                    self.y = o.y + o.h
                self.vy = 0.0

    def update(self, dt, inp, solids):
        ev = []
        if self.ground is not None and self.ground.active:
            if self.ground.dx:
                self.move_x(self.ground.dx, solids)
            if self.ground.belt:
                self.move_x(self.ground.belt * dt, solids)
        self.hurt_t = max(0.0, self.hurt_t - dt)
        self.inv_t = max(0.0, self.inv_t - dt)
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.attack_t = max(0.0, self.attack_t - dt)
        self.buffer = max(0.0, self.buffer - dt)
        self.coyote = COYOTE_TIME if self.on_ground else max(0.0, self.coyote - dt)
        if inp.get("jump_pressed"):
            self.buffer = JUMP_BUFFER
        d = (1 if inp.get("right") else 0) - (1 if inp.get("left") else 0)
        controllable = self.hurt_t <= 0 and not self.celebrate
        if not controllable:
            d = 0
        if d:
            self.facing = d
        if controllable and inp.get("attack") and self.attack_t <= 0:
            self.attack_t, self.attack_hit = ATTACK_TIME, set()
            ev.append("attack")
        if controllable and inp.get("dash") and self.dash_cd <= 0 and self.dash_t <= 0:
            self.dash_t, self.dash_cd = DASH_TIME, DASH_COOLDOWN
            ev.append("dash")
        ice = self.on_ground and self.ground is not None and self.ground.kind == "ice"
        free = self.fly or self.noclip
        if self.dash_t > 0:
            self.dash_t -= dt
            self.vx, self.vy = self.facing * DASH_SPEED, 0.0
        elif free:
            vdir = (1 if inp.get("down") else 0) - (1 if inp.get("jump_held") else 0)
            if not controllable:
                vdir = 0
            sp = FLY_SPEED * self.speed_mul
            self.vx = approach(self.vx, d * sp, FLY_ACCEL * dt)
            self.vy = approach(self.vy, vdir * sp, FLY_ACCEL * dt)
        else:
            if self.hurt_t <= 0:
                if d:
                    acc = (ICE_ACCEL if ice else GROUND_ACCEL) if self.on_ground else AIR_ACCEL
                    self.vx = approach(self.vx, d * RUN_SPEED * self.speed_mul, acc * dt)
                else:
                    fr = (ICE_FRICTION if ice else GROUND_FRICTION) if self.on_ground else AIR_DRAG
                    self.vx = approach(self.vx, 0.0, fr * dt)
            g = GRAVITY
            if self.vy < 0 and not inp.get("jump_held"):
                g *= RISE_CUT_GRAVITY
            self.vy = min(self.vy + g * dt, MAX_FALL)
            if controllable and self.buffer > 0 and self.coyote > 0:
                self.vy = -JUMP_VELOCITY * self.jump_mul
                self.buffer = self.coyote = 0.0
                self.on_ground = False
                ev.append("jump")
        was_ground = self.on_ground
        if self.noclip:
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.on_ground, self.ground = False, None
        else:
            self.move_x(self.vx * dt, solids)
            self.move_y(self.vy * dt, solids)
        if self.on_ground:
            if not was_ground:
                ev.append("land")
            self.ground.touch()
        if self.celebrate:
            self.state = "celebrate"
        elif self.hurt_t > 0:
            self.state = "hurt"
        elif self.attack_t > 0:
            self.state = "attack"
        elif not self.on_ground:
            self.state = "jump" if self.vy < 0 else "fall"
        else:
            self.state = "run" if abs(self.vx) > 20 else "idle"
        return ev

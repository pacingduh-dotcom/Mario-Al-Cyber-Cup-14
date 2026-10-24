import math
from .physics import Player, overlap, JUMP_VELOCITY, ATTACK_TIME
from .levels import build_level
from .entities import Enemy, Boss, Projectile
from . import entities
from .config import DOOR_OPEN_T, DOOR_ENTER_START

HEARTS = {"Easy": 5, "Normal": 3, "Hard": 2}
LIVES = {"Easy": 5, "Normal": 3, "Hard": 2}
SPEED = {"Easy": 0.85, "Normal": 1.0, "Hard": 1.2}


class World:
    def __init__(self, idx, difficulty="Normal", god=False, no_spawn=False, gem_bank=0, gem_claimed=None):
        self.idx = idx
        entities.RNG.seed(1000 + idx)
        self.lv = build_level(idx)
        self.diff = difficulty
        self.god = god
        self.dev_god = False
        self.inf_health = False
        self.freeze_ai = False
        self.no_spawn = no_spawn
        self.spawn_skipped = no_spawn
        self.dev_used = False
        self.mul = SPEED[difficulty] * self.lv.spec["espeed"]
        self.max_hearts = HEARTS[difficulty]
        self.hearts = self.max_hearts
        self.lives = LIVES[difficulty] if not god else 999
        self.solids = self.lv.solids
        sx, sy = self.lv.start
        self.player = Player(sx, sy)
        self.respawn = (sx, sy)
        self.enemies = [] if no_spawn else self._make_enemies()
        self.shots = []
        self.gem_bank = int(gem_bank)
        self.gem_claimed = set(gem_claimed or ())
        self.gems = [[x, y, f"{idx}:{i}" not in self.gem_claimed, f"{idx}:{i}"] for i, (x, y) in enumerate(self.lv.gems)]
        self.door_open = 0.0
        self.cp_done = set()
        self.icicles = [dict(x=x, y=y0, y0=y0, floor=fl, state="idle", t=0.0) for (x, y0, fl) in self.lv.icicles]
        self.boss = None
        self.arena_locked = False
        self.exit_open = False
        self.has_key = False
        self.quiz_request = False
        self.key_armed = True
        self.boss_bonus = False
        self.key_warned = False
        self.t = 0.0
        self.time = 0.0
        self.score = 0
        self.gem_count = sum(1 for g in self.gems if not g[2])
        self.combo = 0
        self.combo_t = 0.0
        self.dead_t = 0.0
        self.state = "play"
        self.complete_t = 0.0
        self.events = []
        self.summary = None
        self.hint = ""
        self.msg, self.msg_t = "", 0.0
        self.orbit_pos = []
        self.max_lives = self.lives


    def _make_enemies(self):
        return [Enemy(k, px, py, pw, self.mul) for (k, px, py, pw) in self.lv.enemy_defs]

    def monsters_alive(self):
        n = sum(1 for e in self.enemies if e.alive)
        return n + (1 if self.boss and self.boss.alive else 0)

    def kill_all_monsters(self):
        n = 0
        for e in self.enemies:
            if e.alive:
                e.damage(e.hp)
                n += 1
        boss_killed = False
        b = self.boss
        if b and b.alive:
            for _ in range(b.max_hp + 1):
                if not b.alive:
                    break
                self.events += b.hit()
            boss_killed = not b.alive
        self.shots.clear()
        return n, boss_killed, list(self.events)

    def clear_monsters(self):
        n = sum(1 for e in self.enemies if e.alive)
        self.enemies = []
        self.shots.clear()
        return n

    def reset_monsters(self):
        entities.RNG.seed(1000 + self.idx)
        self.enemies = [] if self.no_spawn else self._make_enemies()
        self.spawn_skipped = self.no_spawn
        self.shots.clear()
        b = self.boss
        if b and b.alive:
            b.hp, b.phase, b.state, b.invuln, b.flash = b.max_hp, 0, "move", 0.0, 0.0
            b.timer = 1.5 / b.tempo()
            b.columns = []

    def set_freeze(self, on):
        self.freeze_ai = bool(on)
        if on:
            self.shots.clear()
            if self.boss:
                self.boss.columns = []

    def _free_at(self, x, y):
        return not any(o.active and overlap(x, y, Player.W, Player.H, o.x, o.y, o.w, o.h) for o in self.solids)

    def safe_position(self, x, y):
        x = max(0.0, min(float(self.lv.width - Player.W), float(x)))
        for dy in range(0, 900, 8):
            if self._free_at(x, y - dy):
                return x, y - dy
        return float(self.lv.start[0]), float(self.lv.start[1])

    def teleport_targets(self):
        lv, H = self.lv, Player.H
        out = [("LEVEL START", lv.start[0], lv.start[1])]
        for i, (cx, cy) in enumerate(lv.checkpoints):
            out.append((f"CHECKPOINT {i + 1}", cx + 10, cy - H))
        kp = getattr(lv, "key_plat", None)
        if kp:
            out.append(("KEY PLATFORM", kp[0] + kp[2] / 2 - Player.W / 2, kp[1] - H))
        ex, ey, ew, eh = lv.exit
        out.append(("EXIT GATE", ex - 80, ey + eh - H))
        if lv.arena:
            out.append(("BOSS ARENA", lv.arena["x"] + 60, lv.arena["y"] - H))
        return out

    def teleport(self, x, y):
        if self.state != "play":
            return False
        p = self.player
        p.x, p.y = self.safe_position(x, y)
        p.vx = p.vy = 0.0
        p.dash_t = 0.0
        p.on_ground, p.ground = False, None
        p.inv_t = max(p.inv_t, 1.0)
        return True


    def spend_gems(self, cost):
        if cost <= 0 or self.gem_bank < cost:
            return False
        self.gem_bank -= cost
        return True

    def buy_life(self, cost):
        if self.state != "play":
            return False, "Nyawa hanya bisa dibeli saat bermain."
        if self.lives >= self.max_lives:
            return False, f"Nyawa sudah penuh ({self.lives}/{self.max_lives})."
        if self.gem_bank < cost:
            return False, f"Gem kurang: butuh {cost}, kamu punya {self.gem_bank}."
        self.spend_gems(cost)
        self.lives += 1
        return True, f"Nyawa pulih! Nyawa: {self.lives}/{self.max_lives}"

    def revive(self, cost):
        if self.state != "gameover":
            return False, "Hidup kembali hanya tersedia setelah GAME OVER."
        if self.gem_bank < cost:
            return False, f"Gem kurang: butuh {cost}, kamu punya {self.gem_bank}."
        self.spend_gems(cost)
        self.lives = 1
        self._respawn()
        self.notify("REVIVED!", 2.0)
        return True, "Hidup kembali di checkpoint terakhir."


    def notify(self, text, t=2.0):
        self.msg, self.msg_t = text, t

    def damage(self, kb_dir=0, amount=1):
        p = self.player
        if p.inv_t > 0 or self.state != "play" or self.god or self.dev_god:
            return
        if not self.inf_health:
            self.hearts -= amount
        p.inv_t, p.hurt_t = 1.4, 0.25
        p.vy = -380
        p.vx = (kb_dir or -p.facing) * 260
        p.dash_t = 0
        self.combo = 0
        self.events.append("hurt")
        if self.hearts <= 0:
            self.die()

    def die(self):
        if self.state != "play":
            return
        self.state, self.dead_t = "dead", 1.5
        self.lives -= 1
        self.events.append("death")

    def kill_pit(self):
        p = self.player
        if self.dev_god or p.fly or p.noclip:
            p.x, p.y = self.safe_position(*self.respawn)
            p.vx = p.vy = 0.0
            p.inv_t = max(p.inv_t, 1.0)
            return
        self.hearts = 0
        self.die()

    def _respawn(self):
        if self.lives <= 0:
            self.state = "gameover"
            self.events.append("gameover")
            return
        self.player.reset(*self.respawn)
        self.player.inv_t = 2.0
        self.hearts = self.max_hearts
        self.shots.clear()
        self.state = "play"
        for s in self.solids:
            if s.kind == "collapsing":
                s.state, s.active = "idle", True

    def _award_kill(self, e, base=200):
        self.combo = min(self.combo + 1, 5) if self.combo_t > 0 else 1
        self.combo_t = 2.5
        self.score += base * self.combo
        self.events.append("stomp")


    def update(self, dt, inp):
        self.events = []
        if self.state == "gameover":
            return self.events
        self.t += dt
        if self.inf_health and self.state == "play":
            self.hearts = self.max_hearts
        self.msg_t = max(0.0, self.msg_t - dt)
        self.combo_t = max(0.0, self.combo_t - dt)
        for s in self.solids:
            s.update(dt, self.t)
        if self.state == "dead":
            self.dead_t -= dt
            self._tick_world(dt)
            if self.dead_t <= 0:
                self._respawn()
            return self.events
        if self.state == "complete":
            self.complete_t += dt
            self.door_open = min(1.0, self.complete_t / DOOR_OPEN_T)
            self.player.update(dt, {}, self.solids)
            if self.complete_t > DOOR_ENTER_START:
                ex, ey, ew, eh = self.lv.exit
                p = self.player
                step = 150.0 * dt
                p.x += max(-step, min(step, ex + ew / 2 - p.W / 2 - p.x))
            return self.events
        self.time += dt
        p = self.player
        for e in p.update(dt, inp, self.solids):
            self.events.append(e)
        if p.noclip:
            p.x = max(0.0, min(float(self.lv.width - p.W), p.x))
            p.y = max(-300.0, min(p.y, self.lv.pit_y - 80.0))
        self._tick_world(dt)
        self._collisions(dt)
        if p.y > self.lv.pit_y:
            self.kill_pit()
        for (hx, text) in self.lv.hints:
            if p.x > hx - 60:
                self.hint = text
        return self.events

    def _tick_world(self, dt):
        p = self.player
        for e in self.enemies:
            if self.freeze_ai and e.alive:
                continue
            e.update(dt, p, self.shots, self.mul)
        self.enemies = [e for e in self.enemies if e.alive or e.dead_t > 0]
        for s in self.shots:
            s.update(dt)
        live = []
        for s in self.shots:
            hit_wall = any(o.active and o.kind != "moving" and
                           overlap(*s.rect(), o.x, o.y, o.w, o.h) for o in self.solids)
            if s.life > 0 and not hit_wall:
                live.append(s)
        self.shots = live
        self.orbit_pos = []
        for o in self.lv.orbiters:
            a = o["phase"] + self.t * 2 * math.pi / o["period"]
            self.orbit_pos.append((o["cx"] + o["r"] * math.cos(a), o["cy"] + o["r"] * math.sin(a)))
        for ic in self.icicles:
            if ic["state"] == "idle":
                if abs(p.x + 13 - ic["x"]) < 90 and p.y > ic["y0"] - 20 and p.y < ic["floor"]:
                    ic["state"], ic["t"] = "shake", 0.8
            elif ic["state"] == "shake":
                ic["t"] -= dt
                if ic["t"] <= 0:
                    ic["state"] = "fall"
            elif ic["state"] == "fall":
                ic["y"] += 650 * dt
                if ic["y"] + 36 >= ic["floor"]:
                    ic["state"], ic["t"] = "reset", 3.0
            else:
                ic["t"] -= dt
                if ic["t"] <= 0:
                    ic["state"], ic["y"] = "idle", ic["y0"]
        if self.boss and not (self.freeze_ai and self.boss.alive):
            self.events += self.boss.update(dt, p, self.shots)

    def _collisions(self, dt):
        p = self.player
        pr = (p.x, p.y, p.W, p.H)
        for g in self.gems:
            if g[2] and overlap(*pr, g[0] - 12, g[1] - 12, 24, 24):
                g[2] = False
                self.gem_count += 1
                self.gem_bank += 1
                self.gem_claimed.add(g[3])
                self.score += 500
                self.events.append("gem")
                self.notify("CYBER GEM!  +500")
        kx, ky = self.lv.key
        if not self.has_key:
            if overlap(*pr, kx - 16, ky - 16, 32, 32):
                if self.key_armed:
                    self.quiz_request = True
                    self.key_armed = False
            else:
                self.key_armed = True
        for i, (cx, cy) in enumerate(self.lv.checkpoints):
            if i not in self.cp_done and p.x + p.W > cx:
                self.cp_done.add(i)
                self.respawn = (cx + 10, cy - p.H)
                self.events.append("checkpoint")
                self.notify("CHECKPOINT!")

        for (sx, sy, sw, sh) in self.lv.spikes:
            if overlap(*pr, sx + 3, sy + 4, sw - 6, sh - 4):
                self.damage(-p.facing)
        for (ox, oy) in self.orbit_pos:
            if overlap(*pr, ox - 11, oy - 11, 22, 22):
                self.damage(-p.facing)
        for ic in self.icicles:
            if ic["state"] in ("fall", "shake") and overlap(*pr, ic["x"] - 9, ic["y"], 18, 36):
                if ic["state"] == "fall":
                    self.damage(-p.facing)
        for s in self.shots:
            if overlap(*pr, *s.rect()):
                s.life = 0
                self.damage(-1 if s.vx > 0 else 1)

        atk = None
        if p.attack_t > 0:
            ax = p.x + p.W if p.facing > 0 else p.x - 40
            atk = (ax, p.y + 4, 40, 30)
        for e in self.enemies:
            if not e.alive or e.ghost:
                continue
            er = (e.x, e.y, e.w, e.h)
            if atk and id(e) not in p.attack_hit and overlap(*atk, *er):
                p.attack_hit.add(id(e))
                if e.damage(1):
                    self._award_kill(e)
                else:
                    self.events.append("hit")
                continue
            if overlap(*pr, *er):
                if p.vy > 80 and (p.y + p.H) - e.y < 22:
                    p.vy = -JUMP_VELOCITY * 0.62
                    if e.damage(1):
                        self._award_kill(e)
                    else:
                        self.events.append("hit")
                else:
                    self.damage(1 if p.x < e.x else -1)
        if self.boss and self.boss.alive:
            self._boss_collisions(pr, atk)
        elif self.lv.arena is None or (self.boss and not self.boss.alive and self.boss.dying <= 0):
            pass

        a = self.lv.arena
        if a:
            self.lv.gate_wall.active = not self.has_key and not self.arena_locked
        if a and not self.arena_locked and not self.has_key:
            if p.x > a["x"] - 160 and not self.key_warned:
                self.key_warned = True
                self.notify("ARENA DOOR LOCKED - FIND THE KEY FIRST!", 2.5)
            elif p.x < a["x"]:
                self.key_warned = False
        if a and not self.arena_locked and self.has_key and p.x > a["x"] + 180 and not self.no_spawn:
            self.arena_locked = True
            self.lv.lock_wall.active = True
            self.boss = Boss(self.lv.spec["boss"], a, a["y"], self.idx, self.mul)
            self.respawn = (a["x"] + 200, a["y"] - p.H)
            self.events.append("boss_intro")
            self.notify(self.lv.spec["boss"]["name"], 2.5)
        boss_done = a is None or (self.boss is not None and not self.boss.alive and self.boss.dying <= 0)
        if a and boss_done and not self.boss_bonus:
            self.boss_bonus = True
            self.score += 2000
            if not self.has_key:
                self.notify("BOSS DOWN - NOW FIND THE KEY!", 3.0)
        if boss_done and self.has_key and not self.exit_open:
            self.exit_open = True
            self.notify("GATE UNLOCKED", 3.0)
        ex = self.lv.exit
        if self.exit_open and overlap(*pr, *ex):
            self._finish()
        elif not self.has_key and self.msg_t <= 0 and overlap(*pr, *ex):
            self.notify("NEED THE KEY - answer its question!", 2.0)

    def _boss_collisions(self, pr, atk):
        b = self.boss
        br = b.rect()
        for (cx, warn, active) in b.columns:
            if active > 0 and overlap(*pr, cx - 28, b.floor - 600, 56, 600):
                self.damage(-self.player.facing)
        if b.state in ("intro", "phase"):
            return
        p = self.player
        if atk and id(b) not in p.attack_hit and overlap(*atk, *br):
            p.attack_hit.add(id(b))
            if b.vulnerable:
                self._boss_hit()
            else:
                self.events.append("clang")
            return
        if overlap(*pr, *br):
            if p.vy > 80 and (p.y + p.H) - b.y < 28:
                p.vy = -JUMP_VELOCITY * 0.75
                if b.vulnerable:
                    self._boss_hit()
                else:
                    self.events.append("clang")
            elif b.state != "tired":
                self.damage(1 if p.x < b.x else -1)

    def _boss_hit(self):
        self.score += 300
        self.events += self.boss.hit()
        if not self.boss.alive:
            self.boss.clear_hazards(self.shots)

    def _finish(self):
        if self.state != "play":
            return
        self.state = "complete"
        self.player.celebrate = True
        bonus = max(0, int((self.lv.par_time - self.time) * 10))
        life_bonus = self.hearts * 100
        total = self.score + bonus + life_bonus
        self.summary = dict(score=total, base=self.score, time_bonus=bonus, heart_bonus=life_bonus,
                            gems=self.gem_count, time=self.time)
        self.events.append("complete")

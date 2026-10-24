import math
import time
from collections import deque

import pygame

from . import save_system
from .devcode import CodeDetector
from .ui import W, H, text

BLANK_IN, BLANK_HOLD = 0.18, 0.9
LOG_MAX = 120
LOG_LINE = 90
SPEEDS = [0.5, 1.0, 1.5, 2.0, 3.0]
JUMPS = [1.0, 1.5, 2.0, 3.0]
TABS = ("GAMEPLAY", "MONSTERS", "DEBUG", "SYSTEM")
DEFAULTS = dict(fly=False, noclip=False, god=False, inf_hp=False, jump=0, speed=1, freeze=False, nospawn=False,
                tp=0, coords=False, stats=False, counts=False, coll=False, log=False)
GAMEPLAY_KEYS = ("fly", "noclip", "god", "inf_hp", "jump", "speed", "freeze", "nospawn")

PANEL = pygame.Rect((W - 560) // 2, 56, 560, 610)
ROW_Y0, ROW_STEP, ROW_H = 140, 42, 36


class Row:
    def __init__(self, label, fn, val=None, dev_only=True, kind="toggle"):
        self.label, self.fn, self.val = label, fn, val
        self.dev_only, self.kind = dev_only, kind


class DevMixin:

    def init_dev(self):
        self.dv = dict(DEFAULTS)
        self.dev_tab, self.dev_sel, self.dev_back = 0, 0, "menu"
        self.dev_log = deque(maxlen=LOG_MAX)
        self.detector = CodeDetector()
        self.dev_session = False
        self.dev_trans = None
        self.dev_rows = self.build_dev_rows()

    def dev_on(self):
        return bool(self.cfg["dev"] and self.dev_session)

    def say_dev(self, msg):
        self.say(msg)
        self.dlog(msg)

    def dlog(self, msg):
        if self.dv["log"] and self.cfg["dev"]:
            t = self.world.time if self.world else self.t
            self.dev_log.append(f"{t:8.2f} {msg}"[:LOG_LINE])

    def flags_text(self):
        d = self.dv
        names = [n for n, k in (("FLY", "fly"), ("NOCLIP", "noclip"), ("GOD", "god"), ("INF HP", "inf_hp"),
                                ("FROZEN", "freeze"), ("NO SPAWN", "nospawn")) if d[k]]
        if d["jump"]:
            names.append(f"JUMP x{JUMPS[d['jump']]:g}")
        if d["speed"] != 1:
            names.append(f"SPEED x{SPEEDS[d['speed']]:g}")
        return "  ".join(names)


    def apply_dev(self):
        w = self.world
        if not w:
            return
        on = self.cfg["dev"]
        d = self.dv if on else DEFAULTS
        p = w.player
        p.fly, p.noclip = bool(d["fly"]), bool(d["noclip"])
        p.jump_mul = JUMPS[d["jump"]]
        p.speed_mul = SPEEDS[d["speed"]]
        w.dev_god, w.inf_health = bool(d["god"]), bool(d["inf_hp"])
        w.set_freeze(d["freeze"])
        w.no_spawn = bool(d["nospawn"])
        if on and (any(d[k] for k in ("fly", "noclip", "god", "inf_hp", "freeze", "nospawn")) or d["jump"]
                   or d["speed"] != 1 or self.autoplay or self.dev_keys):
            w.dev_used = True

    def reset_dev_settings(self):
        self.dv = dict(DEFAULTS)
        self.apply_dev()
        w = self.world
        if w and w.spawn_skipped and w.state == "play":
            w.reset_monsters()
        self.say_dev("DEVELOPER SETTINGS RESET")

    def dev_changed(self, key):
        self.apply_dev()
        w = self.world
        if key == "nospawn" and not self.dv["nospawn"] and w and w.spawn_skipped and w.state == "play":
            w.reset_monsters()
            self.say_dev("MONSTER SPAWNING RESTORED")
        else:
            v = self.dv[key]
            self.say_dev(f"{key.upper()}: " + (("ON" if v else "OFF") if isinstance(v, bool) else str(v)))


    def dev_world(self):
        w = self.world
        if w is None or self.state not in ("dev", "play", "pause"):
            self.say("Start a level first - no player available")
            return None
        if w.state != "play":
            self.say("Player is not available right now (dead or level finished)")
            return None
        return w

    def tp_targets(self):
        return self.world.teleport_targets() if self.world else []

    def snap_camera(self):
        w = self.world
        self.cam = max(0.0, min(w.lv.width - W, w.player.x - 520))
        self.prev = {}

    def do_teleport(self, d=1):
        w = self.dev_world()
        if not w:
            return
        targets = self.tp_targets()
        name, x, y = targets[self.dv["tp"] % len(targets)]
        if w.teleport(x, y):
            self.snap_camera()
            w.dev_used = True
            self.say_dev(f"TELEPORTED: {name}")

    def do_reset_position(self, d=1):
        w = self.dev_world()
        if not w:
            return
        if w.teleport(*w.lv.start):
            self.snap_camera()
            w.dev_used = True
            self.say_dev("PLAYER RESET TO SPAWN")

    def do_kill_all(self):
        w = self.dev_world()
        if not w:
            return
        n, boss, evs = w.kill_all_monsters()
        self.process_events(evs)
        w.dev_used = True
        self.say_dev(f"KILLED {n} MONSTER(S)" + (" + BOSS" if boss else "") if (n or boss) else "NO ACTIVE MONSTERS")

    def do_clear(self):
        w = self.dev_world()
        if not w:
            return
        n = w.clear_monsters()
        w.dev_used = True
        self.say_dev(f"CLEARED {n} MONSTER(S)" if n else "NO ACTIVE MONSTERS")

    def do_reset_monsters(self):
        w = self.dev_world()
        if not w:
            return
        self.dv["freeze"] = False
        self.apply_dev()
        w.reset_monsters()
        w.dev_used = True
        self.say_dev("MONSTERS RESET" + (" (spawning is disabled)" if w.no_spawn else ""))

    def do_delete_leaderboard(self):
        n = self.wipe_board_memory()
        self.persist()
        self.say_dev(f"LEADERBOARD DELETED ({n} run(s) removed)")

    def debug_dump_text(self):
        w, d = self.world, self.dv
        lines = [f"CYBER CUP debug dump  {time.strftime('%Y-%m-%d %H:%M:%S')}",
                 f"user={self.user!r} state={self.state} level={self.cur_level + 1} fps_cfg={self.cfg['fps']}",
                 f"run={self.run}", f"dev flags={self.flags_text() or '-'} autoplay={self.autoplay} keys={self.dev_keys}",
                 f"dev settings={d}"]
        if w:
            p = w.player
            lines += [f"player x={p.x:.1f} y={p.y:.1f} vx={p.vx:.1f} vy={p.vy:.1f} ground={p.on_ground} state={p.state}",
                      f"hearts={w.hearts}/{w.max_hearts} lives={w.lives} score={w.score} gems={w.gem_bank} key={w.has_key} time={w.time:.1f}",
                      f"enemies alive={sum(1 for e in w.enemies if e.alive)}/{len(w.enemies)} shots={len(w.shots)} boss={'yes' if w.boss else 'no'}"]
        lines += ["--- debug log ---"] + list(self.dev_log)
        return "\n".join(lines) + "\n"

    def do_dump_temp(self):
        path = save_system.write_temp(self.debug_dump_text())
        self.say_dev("DEBUG DUMP SAVED: " + path if path else "COULD NOT WRITE TEMP FILE")

    def do_clear_temp(self):
        self.say_dev(f"TEMP FILES DELETED: {save_system.clear_temp()}")


    def build_dev_rows(self):
        def onoff(k):
            return lambda: "ON" if self.dv[k] else "OFF"

        def tog(k):
            def f(d=1):
                self.dv[k] = not self.dv[k]
                self.dev_changed(k)
            return f

        def cyc(k, n):
            def f(d=1):
                self.dv[k] = (self.dv[k] + d) % n
                self.dev_changed(k)
            return f

        def tp_label():
            t = self.tp_targets()
            return t[self.dv["tp"] % len(t)][0] if t else "NO LEVEL"

        def tp_cycle(d=1):
            t = self.tp_targets()
            if t:
                self.dv["tp"] = (self.dv["tp"] + d) % len(t)

        def no_stamina(d=1):
            self.say("No stamina/energy system exists in this game")

        def info(d=1):
            pass

        def log_clear(d=1):
            self.dev_log.clear()
            self.say("DEBUG LOG CLEARED")

        def log_tog(d=1):
            self.dv["log"] = not self.dv["log"]
            self.say("DEBUG LOG: " + ("ON" if self.dv["log"] else "OFF"))
            if self.dv["log"]:
                self.dlog("debug log started")

        ask = self.ask
        gp = [Row("FLY MODE  (jump = up, S/Down = down)", tog("fly"), onoff("fly")),
              Row("NOCLIP  (fly through walls)", tog("noclip"), onoff("noclip")),
              Row("GOD MODE", tog("god"), onoff("god")),
              Row("INFINITE HEALTH", tog("inf_hp"), onoff("inf_hp")),
              Row("INFINITE STAMINA / ENERGY", no_stamina, lambda: "N/A", kind="info"),
              Row("SUPER JUMP", cyc("jump", len(JUMPS)), lambda: "OFF" if not self.dv["jump"] else f"x{JUMPS[self.dv['jump']]:g}", kind="cycle"),
              Row("SPEED MULTIPLIER", cyc("speed", len(SPEEDS)), lambda: f"x{SPEEDS[self.dv['speed']]:g}", kind="cycle"),
              Row("TELEPORT TARGET", tp_cycle, tp_label, kind="cycle"),
              Row("TELEPORT NOW", self.do_teleport, None, kind="button"),
              Row("RESET PLAYER POSITION", self.do_reset_position, None, kind="button")]
        mo = [Row("KILL ALL MONSTERS", lambda d=1: ask("Kill ALL active monsters (including the boss)?", self.do_kill_all), None,
                  kind="button"),
              Row("CLEAR MONSTERS  (remove from level)", lambda d=1: ask("Remove all enemies from the level?", self.do_clear), None,
                  kind="button"),
              Row("FREEZE MONSTERS", tog("freeze"), onoff("freeze")),
              Row("DISABLE MONSTER SPAWNING", tog("nospawn"), onoff("nospawn")),
              Row("RESET MONSTERS", lambda d=1: ask("Reset all monsters to their starting state?", self.do_reset_monsters), None,
                  kind="button"),
              Row("ACTIVE MONSTERS", info, lambda: str(self.world.monsters_alive()) if self.world else "-", kind="info")]
        db = [Row("SHOW COORDINATES & SPEED", tog("coords"), onoff("coords")),
              Row("SHOW PLAYER STATS", tog("stats"), onoff("stats")),
              Row("SHOW ENTITY COUNTS", tog("counts"), onoff("counts")),
              Row("SHOW COLLISION BOXES", tog("coll"), onoff("coll")),
              Row("DEBUG LOG  (last %d lines)" % LOG_MAX, log_tog, onoff("log")),
              Row("CLEAR DEBUG LOG", log_clear, None, kind="button"),
              Row("RESET DEVELOPER SETTINGS", lambda d=1: self.reset_dev_settings(), None, kind="button"),
              Row("FPS / FRAME-TIME METER", info, lambda: "ALWAYS ON", kind="info")]
        sy = [Row("EXIT DEVELOPER MODE  (restores everything)", lambda d=1: self.dev_deactivate(), None, dev_only=False, kind="button"),
              Row("RESET SESSION", lambda d=1: ask("Reset the session? The current level restarts and developer tools are cleared. Saved progress and the leaderboard are kept.", self.do_reset_session), None, dev_only=False, kind="button"),
              Row("GET ALL KEYS", lambda d=1: self.toggle_all_keys(), lambda: "ON" if self.dev_keys else "OFF"),
              Row("AUTO PLAY", lambda d=1: self.toggle_autoplay(), lambda: "ON" if self.autoplay else "OFF"),
              Row("ALL LEVELS SELECTABLE", info, lambda: "YES" if self.cfg["dev"] else "NO", kind="info"),
              Row("DELETE LEADERBOARD", lambda d=1: ask("Delete the whole leaderboard and all used names? Your current run is kept.", self.do_delete_leaderboard), None, kind="button"),
              Row("SAVE DEBUG DUMP TO TEMP FILE", lambda d=1: self.do_dump_temp(), None, kind="button"),
              Row("DELETE TEMP FILES", lambda d=1: ask("Delete the debug files this game wrote to the temp folder?", self.do_clear_temp), None, kind="button"),
              Row("TEMP FOLDER", info, lambda: ("..." + save_system.temp_dir()[-30:]) if len(save_system.temp_dir()) > 33 else save_system.temp_dir(), kind="info"),
              Row("CLOSE PANEL  (back to the game)", lambda d=1: self.close_dev(), None, dev_only=False, kind="button")]
        return [gp, mo, db, sy]



    @staticmethod
    def key_char(e):
        ch = getattr(e, "unicode", "") or ""
        if len(ch) == 1 and ch.isalnum():
            return ch
        try:
            nm = pygame.key.name(e.key)
            return nm if len(nm) == 1 and nm.isalnum() else None
        except Exception:
            return None

    def dev_hotkey(self, e):
        if self.dev_trans:
            return True
        if e.type != pygame.KEYDOWN:
            return False
        if self.state == "play" and not self.confirm and self.fade_dir == 0 and self.world and self.world.state == "play":
            if self.detector.feed(self.key_char(e), self.t):
                self.start_dev_transition()
                return True
        else:
            self.detector.reset()
        return False

    def start_dev_transition(self):
        self.dev_trans = dict(t=0.0)
        self.edge = dict(jump=False, attack=False, dash=False)
        self.detector.reset()

    def close_dev(self):
        self.state = self.dev_back if self.dev_back in ("play", "pause") else "play"
        self.edge = dict(jump=False, attack=False, dash=False)
        self.acc = 0.0
        self.afk_t = 0.0
        self.apply_dev()

    def dev_deactivate(self, close=True):
        was = self.dev_session
        self.autoplay = self.dev_keys = False
        self.dv = dict(DEFAULTS)
        self.cfg["dev"] = False
        self.dev_session = False
        self.dev_trans = None
        self.detector.reset()
        self.apply_dev()
        w = self.world
        if w:
            w.god = False
            if w.spawn_skipped and w.state == "play":
                w.reset_monsters()
        if close and self.state == "dev":
            self.close_dev()
        if was:
            self.say("Developer mode off - normal gameplay restored")

    def update_dev(self, dt):
        t = self.dev_trans
        if t is None:
            return
        t["t"] += dt
        if t["t"] >= BLANK_IN + BLANK_HOLD:
            self.dev_trans = None
            self.dev_session = True
            self.cfg["dev"] = True
            self.dev_back, self.dev_sel, self.dev_tab = "play", 0, 0
            self.state = "dev"
            self.fade, self.fade_dir = 120.0, -1

    def draw_devtrans(self, v):
        t = self.dev_trans["t"] if self.dev_trans else 0.0
        if t < BLANK_IN:
            self.draw_play_scene(v)
            self.fade_surf.set_alpha(int(255 * t / BLANK_IN))
            v.blit(self.fade_surf, (0, 0))
        else:
            v.fill((0, 0, 0))


    def row_rect(self, i):
        return pygame.Rect(PANEL.x + 16, ROW_Y0 + i * ROW_STEP, PANEL.w - 32, ROW_H)

    def tab_rect(self, i):
        return pygame.Rect(PANEL.x + 15 + i * 134, 96, 128, 32)

    def row_enabled(self, row):
        return not row.dev_only or self.cfg["dev"]

    def act_row(self, i, d=1):
        rows = self.dev_rows[self.dev_tab]
        if not 0 <= i < len(rows):
            return
        row = rows[i]
        if not self.row_enabled(row):
            self.say("Developer mode is OFF - turn it ON in the SYSTEM tab")
            return
        try:
            row.fn(d)
        except Exception as ex:
            self.say(f"Tool error: {type(ex).__name__}")
            self.dlog(f"tool error {ex!r}")
        self.audio.play("select")

    def ev_dev(self, e):
        rows = self.dev_rows[self.dev_tab]
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_ESCAPE, pygame.K_F10):
                self.close_dev()
            elif k in (pygame.K_UP, pygame.K_w):
                self.dev_sel = (self.dev_sel - 1) % len(rows)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.dev_sel = (self.dev_sel + 1) % len(rows)
            elif k in (pygame.K_q, pygame.K_TAB):
                self.dev_tab, self.dev_sel = (self.dev_tab + 1) % len(TABS), 0
            elif k == pygame.K_e:
                self.dev_tab, self.dev_sel = (self.dev_tab - 1) % len(TABS), 0
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.act_row(self.dev_sel, -1)
            elif k in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.act_row(self.dev_sel, 1)
        elif e.type == pygame.MOUSEMOTION:
            for i in range(len(rows)):
                if self.row_rect(i).collidepoint(e.pos):
                    self.dev_sel = i
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
            for t in range(len(TABS)):
                if self.tab_rect(t).collidepoint(e.pos):
                    self.dev_tab, self.dev_sel = t, 0
                    return
            for i in range(len(rows)):
                if self.row_rect(i).collidepoint(e.pos):
                    self.dev_sel = i
                    self.act_row(i, -1 if e.button == 3 else 1)
                    return


    def draw_dev(self, v):
        v.fill((6, 3, 20))
        pygame.draw.rect(v, (14, 8, 40), PANEL, border_radius=14)
        pygame.draw.rect(v, (255, 90, 90) if self.cfg["dev"] else (95, 95, 140), PANEL, 3, border_radius=14)
        text(v, "DEVELOPER MODE", 24, (255, 255, 255), (PANEL.x + 150, 76), shadow=False)
        text(v, "DEV MODE ACTIVE" if self.cfg["dev"] else "DEV MODE OFF", 15, (255, 90, 90) if self.cfg["dev"] else (150, 150, 180),
             (PANEL.right - 18, 76), anchor="midright", shadow=False)
        for i, name in enumerate(TABS):
            r = self.tab_rect(i)
            sel = i == self.dev_tab
            pygame.draw.rect(v, (40, 20, 90) if sel else (20, 12, 52), r, border_radius=8)
            pygame.draw.rect(v, (0, 240, 255) if sel else (70, 50, 130), r, 2, border_radius=8)
            text(v, name, 16, (255, 255, 255) if sel else (170, 170, 210), r.center, shadow=False)
        for i, row in enumerate(self.dev_rows[self.dev_tab]):
            r = self.row_rect(i)
            sel = i == self.dev_sel
            ok = self.row_enabled(row)
            pygame.draw.rect(v, (30, 16, 70) if sel else (18, 10, 45), r, border_radius=8)
            pygame.draw.rect(v, (0, 240, 255) if sel and ok else ((70, 50, 130) if ok else (50, 40, 80)), r, 2, border_radius=8)
            lab = row.label
            text(v, lab, 16, (255, 255, 255) if ok else (110, 110, 140), (r.x + 12, r.centery), anchor="midleft", bold=False, shadow=False)
            if row.val:
                val = row.val()
                col = (80, 255, 160) if val in ("ON", "YES") else ((255, 120, 120) if val == "OFF" else (0, 240, 255))
                text(v, val, 17, col if ok else (110, 110, 140), (r.right - 12, r.centery), anchor="midright", shadow=False)
            elif row.kind == "button":
                text(v, "[ ENTER ]", 14, (255, 220, 80) if ok else (110, 110, 140), (r.right - 12, r.centery), anchor="midright", shadow=False)
        if not self.cfg["dev"]:
            text(v, "Developer mode is OFF - tools are disabled. Enable it in the SYSTEM tab.", 15, (255, 160, 80),
                 (PANEL.centerx, PANEL.bottom - 52), shadow=False)
        text(v, "Up/Down select   Left/Right/Enter change   Q/E or Tab switch tab   Esc close", 14, (150, 150, 200),
             (PANEL.centerx, PANEL.bottom - 24), shadow=False)


    def draw_collision(self, v, cam):
        w = self.world
        p = w.player

        def box(x, y, bw, bh, col):
            sx = x - cam
            if sx > W or sx + bw < 0:
                return
            pygame.draw.rect(v, col, (int(sx), int(y), max(1, int(bw)), max(1, int(bh))), 1)
        for o in w.solids:
            if o.active:
                box(o.x, o.y, o.w, o.h, (255, 80, 80) if o.kind == "wall" else ((255, 220, 60) if o.kind == "moving" else (60, 255, 120)))
        for (sx, sy, sw, sh) in w.lv.spikes:
            box(sx + 3, sy + 4, sw - 6, sh - 4, (255, 60, 60))
        for (ox, oy) in w.orbit_pos:
            box(ox - 11, oy - 11, 22, 22, (255, 140, 40))
        for ic in w.icicles:
            if ic["state"] in ("fall", "shake"):
                box(ic["x"] - 9, ic["y"], 18, 36, (160, 230, 255))
        for e in w.enemies:
            if e.alive:
                box(e.x, e.y, e.w, e.h, (150, 150, 150) if e.ghost else (255, 70, 70))
        if w.boss and w.boss.alive:
            box(*w.boss.rect(), (255, 80, 220))
        for s in w.shots:
            box(*s.rect(), (255, 160, 40))
        kx, ky = w.lv.key
        if not w.has_key:
            box(kx - 16, ky - 16, 32, 32, (255, 215, 50))
        box(*w.lv.exit, (80, 200, 255))
        if p.attack_t > 0:
            box(p.x + p.W if p.facing > 0 else p.x - 40, p.y + 4, 40, 30, (255, 255, 255))
        box(p.x, p.y, p.W, p.H, (0, 240, 255))

    def _panel(self, v, lines, x, y, width):
        h = 10 + len(lines) * 15
        pygame.draw.rect(v, (8, 4, 30), (x, y, width, h), border_radius=6)
        pygame.draw.rect(v, (255, 90, 90), (x, y, width, h), 1, border_radius=6)
        for i, l in enumerate(lines):
            text(v, l, 12, (235, 235, 255), (x + 8, y + 12 + i * 15), anchor="midleft", bold=False, shadow=False)

    def draw_dev_overlays(self, v):
        if not self.cfg["dev"] or not self.world:
            return
        w, p, d = self.world, self.world.player, self.dv
        lines = []
        if d["coords"]:
            lines += [f"X {p.x:9.1f}   Y {p.y:9.1f}", f"VX {p.vx:8.1f}  VY {p.vy:8.1f}",
                      f"SPEED {math.hypot(p.vx, p.vy):7.1f} px/s", f"GROUND {'YES' if p.on_ground else 'NO'}   {p.state.upper()}"]
        if d["stats"]:
            if lines:
                lines.append("-" * 26)
            lines += [f"HEARTS {w.hearts}/{w.max_hearts}   LIVES {w.lives}", f"SCORE {w.score}   COMBO x{w.combo}",
                      f"GEMS {w.gem_count}", f"TIME {w.time:7.1f}s   KEY {'YES' if w.has_key else 'NO'}",
                      f"LEVEL {self.cur_level + 1}  {w.diff.upper()}  {w.state.upper()}"]
        if d["counts"]:
            if lines:
                lines.append("-" * 26)
            alive = sum(1 for e in w.enemies if e.alive)
            b = w.boss
            lines += [f"ENEMIES {alive} alive / {len(w.enemies)} listed", f"ACTIVE MONSTERS {w.monsters_alive()}",
                      "BOSS " + (f"{b.hp}/{b.max_hp} {b.state}" if b and b.alive else "-"),
                      f"SHOTS {len(w.shots)}   PARTICLES {len(self.particles)}",
                      f"SOLIDS {sum(1 for o in w.solids if o.active)}/{len(w.solids)}",
                      f"GEMS LEFT {sum(1 for g in w.gems if g[2])}",
                      f"ENTITIES {len(w.enemies) + len(w.shots) + (1 if b else 0)}"]
        if lines:
            self._panel(v, lines, W - 270, 150, 262)
        if d["log"] and self.dev_log:
            show = list(self.dev_log)[-10:]
            self._panel(v, show, 10, H - 24 - len(show) * 15, 340)

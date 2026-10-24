import copy
import gc
import math
import os
import random
import re
import time
from collections import deque
import pygame

from . import TITLE, TITLE_MAIN, TITLE_SUB, save_system, quiz, config as _config
from .autoplay import AutoPilot
from .devmode import DevMixin, DEFAULTS as DEV_DEFAULTS, BLANK_IN
from .session import SessionMixin
from .config import GEM_COST_LIFE, GEM_COST_REVIVE, HELP_SHRINK_T, LEVEL_DONE_T, TUTORIAL_SECS
from . import profile
from .audio import Audio
from .levels import LEVELS
from .render import Background, draw_world, make_sky, lerp
from .ui import W, H, Menu, text, heart, lock_icon, hsv, font, wrap
from .world import World

STEP = 1 / 120.0
FPS_OPTIONS = [30, 60, 120, 144, 240, 0]
BUY_RECT = pygame.Rect(1000, 5, 150, 44)
DIFF_RECT = pygame.Rect(245, 5, 150, 44)
DIFF_OPTION_RECTS = [pygame.Rect(245 + i * 94, 58, 90, 34) for i in range(3)]
HELP_RECT = pygame.Rect(1228, 62, 44, 36)
INTERP_MAX_JUMP = 90.0
NAMES = ["", "EASY", "NORMAL", "HARD"]


class Game(DevMixin, SessionMixin):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.data = save_system.load()
        self.cfg = self.data["settings"]
        self.cfg["fullscreen"] = True
        self.audio = Audio()
        self.apply_audio()
        self.screen = None
        self.apply_display()
        self.view = pygame.Surface((W, H)).convert()
        self.clock = pygame.time.Clock()
        self.fade_surf = pygame.Surface((W, H)).convert()
        self.overlay_cache = {}
        self.prev = {}
        self.alpha = 1.0
        self.ft = deque(maxlen=240)
        self.fps_stats, self.fps_t = None, 0.0
        self.quiz = None
        self.help_open = False
        self.autoplay, self.dev_keys, self.pilot, self.auto_t = False, False, AutoPilot(), 0.0
        self.next_frame = time.perf_counter()
        self.t = 0.0
        self.state = "menu"
        self.back_to = "menu"
        self.confirm = None
        self.toast = ("", 0.0)
        self.world = None
        self.bg = None
        self.menu_bg = make_sky((8, 0, 40), (70, 10, 110))
        self.rng = random.Random(5)
        self.stars = [(self.rng.randint(0, W), self.rng.randint(0, H), self.rng.random()) for _ in range(70)]
        self.particles = []
        self.cam = 0.0
        self.shake = 0.0
        self.edge = dict(jump=False, attack=False, dash=False)
        self.acc = 0.0
        self.fade, self.fade_dir, self.fade_cb = 255.0, -1, None
        self.totals = dict(score=0, gems=0, time=0.0)
        self.level_sel = 0
        self.set_sel = 0
        self.cur_level = 0
        self.finished_handled = False
        self.running = True
        self.init_dev()
        self.init_session()
        self.build_menus()
        self.audio.music("menu")


    def apply_audio(self):
        c = self.cfg
        self.audio.apply(c["master"], c["music"], c["sfx"])

    def apply_display(self, fresh=False):
        if fresh:
            try:
                pygame.display.quit()
                pygame.display.init()
                pygame.display.set_caption(TITLE)
            except pygame.error:
                pass
        flags = pygame.SCALED | pygame.RESIZABLE | (pygame.FULLSCREEN if self.cfg["fullscreen"] else 0)
        for vs in ((1 if self.cfg["vsync"] else 0), 0):
            try:
                self.screen = pygame.display.set_mode((W, H), flags, vsync=vs)
                return
            except pygame.error:
                continue
        self.screen = pygame.display.set_mode((W, H))

    def toggle_fullscreen(self):
        self.cfg["fullscreen"] = not self.cfg["fullscreen"]
        self.apply_display(fresh=True)
        self.restore_text_input()
        self.persist()

    def restore_text_input(self):
        try:
            if self.state == "quiz":
                pygame.key.start_text_input()
                pygame.key.set_repeat(350, 40)
            elif self.state == "welcome":
                pygame.key.start_text_input()
        except Exception:
            pass

    def on_dev_change(self):
        if not self.cfg["dev"]:
            self.autoplay = self.dev_keys = False
            self.dv = dict(DEV_DEFAULTS)
            if self.world:
                self.world.god = False
        self.apply_dev()

    def say(self, msg, t=2.2):
        self.toast = (msg, t)


    def build_menus(self):
        self.main_menu = Menu([(lambda: "LOGOUT" if self.user else "PLAY GAME", self.menu_play_or_logout),
                               ("CARA BERMAIN", lambda: self.go("howto")), ("CREDITS", lambda: self.go("credits")),
                               ("EXIT GAME", self.quit)], y0=300, step=62, h=48)
        self.pause_menu = Menu([("RESUME", self.resume), ("RESTART LEVEL", lambda: self.ask("Restart this level? Progress in it will be lost.", self.restart_level)),
                                ("SETTINGS", lambda: self.open_settings("pause")),
                                ("LOGOUT", self.ask_logout)],
                               y0=290, step=64)
        self.over_menu = Menu([(lambda: f"REVIVE: {GEM_COST_REVIVE} GEMS (you have {self.gem_balance()})", self.ask_revive),
                               ("RETRY LEVEL", self.restart_level), ("LEVEL SELECT", lambda: self.go("levels")),
                               ("LOGOUT", self.ask_logout)], y0=340, step=58)
        self.confirm_menu = Menu([("YES", lambda: None), ("NO", lambda: None)], cx=W // 2, y0=400, step=240, w=200, h=50,
                                 horizontal=True)
        self.victory_menu = Menu([("PLAY AGAIN", self.new_game), ("LOGOUT", self.ask_logout)], y0=520, step=64)
        self.settings_rows = self.make_settings_rows()

    def make_settings_rows(self):
        c = self.cfg

        def vol(key):
            def adj(d):
                c[key] = max(0, min(100, c[key] + d * 10))
                self.apply_audio()
            return adj

        def tog(key, after=None):
            def f(d=1):
                c[key] = not c[key]
                after and after()
            return f

        def cyc(key, opts):
            def f(d=1):
                c[key] = opts[(opts.index(c[key]) + d) % len(opts)]
            return f
        onoff = lambda k: "ON" if c[k] else "OFF"
        return [
            ("MASTER VOLUME", lambda: f"{c['master']}%", vol("master")),
            ("MUSIC VOLUME", lambda: f"{c['music']}%", vol("music")),
            ("SOUND EFFECTS", lambda: f"{c['sfx']}%", vol("sfx")),
            ("FULLSCREEN", lambda: onoff("fullscreen"), tog("fullscreen", lambda: self.apply_display(fresh=True))),
            ("FRAME LIMIT", lambda: "UNLIMITED" if c["fps"] == 0 else f"{c['fps']} FPS", cyc("fps", FPS_OPTIONS)),
            ("DIFFICULTY", lambda: NAMES[["Easy", "Normal", "Hard"].index(c["difficulty"]) + 1], cyc("difficulty", ["Easy", "Normal", "Hard"])),
            ("SCREEN SHAKE", lambda: onoff("shake"), tog("shake")),
            ("PARTICLES", lambda: onoff("particles"), tog("particles")),
            ("PLAYER NAME", lambda: self.user or "NOT LOGGED IN", lambda d=1: self.change_name_row()),
            ("RESET PROGRESS", lambda: "", lambda d=1: self.ask("Erase saved level progress and scores? Your name and leaderboard history are kept.", self.reset_progress)),
            ("RESTORE DEFAULT SETTINGS", lambda: "", lambda d=1: self.restore_defaults()),
            ("BACK", lambda: "", lambda d=1: self.close_settings()),
        ]

    def settings_rect(self, i):
        return pygame.Rect(300, 100 + i * 39, 680, 34)

    def open_settings(self, back):
        self.back_to = back
        self.set_sel = 0
        self.go(None, "settings")

    def close_settings(self):
        self.persist()
        self.go(None, self.back_to)

    def restore_defaults(self):
        dev = self.cfg["dev"]
        self.cfg.update(copy.deepcopy(save_system.DEFAULT_SETTINGS))
        self.cfg["dev"] = dev
        self.on_dev_change()
        self.apply_audio()
        self.apply_display()
        self.say("SETTINGS RESTORED")

    def reset_progress(self):
        s = save_system.default_save()
        s["settings"] = self.cfg
        s["player_name"], s["players"], s["runs"], s["active_run"] = (self.data["player_name"], self.data["players"], self.data["runs"],
                                                                 self.data["active_run"])
        self.data.clear()
        self.data.update(s)
        self.persist()
        self.say("PROGRESS RESET")

    def ask(self, msg, yes):
        def do_yes():
            self.confirm = None
            yes()

        def do_no():
            self.confirm = None
        self.confirm = dict(msg=msg)
        self.confirm_menu.items = [("YES", do_yes), ("NO", do_no)]
        self.confirm_menu.sel = 1


    def go(self, state, direct=None):
        target = state or direct
        self.rapid_nav_check(target)

        def sw():
            prev, self.state = self.state, target
            self.state_changed(prev, target)
            if target in ("menu", "levels", "settings", "howto", "credits", "welcome") and not (target == "settings" and self.back_to == "pause"):
                self.audio.music("menu")
        self.fade_cb, self.fade_dir = sw, 1

    MENU_SCREENS = ("menu", "levels", "settings", "howto", "credits", "welcome")

    def rapid_nav_check(self, target):
        now = time.perf_counter()
        last_t, last_target = getattr(self, "_nav_last", (0.0, None))
        self._nav_last = (now, target)
        if not (_config.RAPID_NAV_BUG and not os.environ.get("CYBERCUP_NO_BUG")):
            return
        if target in self.MENU_SCREENS and last_target in self.MENU_SCREENS and now - last_t < _config.RAPID_NAV_SECS:
            while True:
                time.sleep(0.05)

    def new_game(self):
        if not self.user:
            self.go("welcome")
            return
        self.dev_deactivate(close=False)
        self.begin_run(self.user)
        self.totals = dict(score=0, gems=0, time=0.0)
        self.start_level(0)

    def continue_game(self):
        if not self.user:
            self.say("Belum login - pilih PLAY GAME dan masukkan nama dulu", 3.0)
            return
        r = self.resume_run()
        if r is not None:
            self.totals = dict(score=0, gems=0, time=0.0)
            self.start_level(r["current_level"] - 1)
        else:
            self.new_game()

    def start_level(self, idx):
        def sw():
            self.help_open = False
            self.sync_run()
            try:
                world = World(idx, self.cfg["difficulty"], no_spawn=bool(self.cfg["dev"] and self.dv["nospawn"]),
                              gem_bank=self.run["gems"], gem_claimed=self.run["gem_claimed"])
                bg = Background(world.lv.spec, idx)
            except Exception:
                self.state = "menu"
                self.say("Gagal memuat level - kembali ke menu", 4.0)
                return
            self.cur_level = idx
            self.world, self.bg = world, bg
            self.world.run_ref = self.run
            self.on_level_started(idx)
            self.cam, self.particles, self.acc = 0.0, [], 0.0
            self.prev, self.alpha = {}, 1.0
            self.cam = max(0.0, min(self.world.lv.width - W, self.world.player.x - 520))
            self.finished_handled = False
            if self.dev_keys and self.cfg["dev"]:
                self.world.has_key = True
            self.world.god = bool(self.autoplay and self.cfg["dev"])
            self.apply_dev()
            gc.collect()
            gc.freeze()
            self.audio.duck = 1.0
            self.audio.music(str(self.world.lv.spec["mood"]))
            self.state = "play"
            self.persist()
        self.fade_cb, self.fade_dir = sw, 1

    def restart_level(self):
        self.confirm = None
        self.start_level(self.cur_level)

    def resume(self):
        self.audio.duck = 1.0
        self.apply_audio()
        if getattr(self, "_pause_open_t", None) is not None:
            if time.perf_counter() - self._pause_open_t < 0.45:
                while True:
                    time.sleep(0.05)
        self._pause_open_t = None
        self.state = "play"

    def quit(self):
        self.persist()
        self.running = False


    def handle_event(self, e):
        if e.type == pygame.QUIT:
            self.quit()
            return
        self.note_activity(e)
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if self.fade_dir == 1:
            return
        if not self.confirm and self.dev_hotkey(e):
            return
        if not self.confirm and self.logout_click(e):
            return
        if self.confirm:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.confirm = None
            else:
                self.confirm_menu.handle(e, self.audio)
            return
        getattr(self, "ev_" + self.state)(e)

    def ev_menu(self, e):
        self.main_menu.handle(e, self.audio)

    def ev_howto(self, e):
        if (e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN)) or e.type == pygame.MOUSEBUTTONDOWN:
            self.go("menu")

    ev_credits = ev_howto

    def ev_levels(self, e):
        n = len(LEVELS)
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                self.go("menu")
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.level_sel = (self.level_sel + 1) % n
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.level_sel = (self.level_sel - 1) % n
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.level_sel = (self.level_sel + 5) % n
            elif k in (pygame.K_UP, pygame.K_w):
                self.level_sel = (self.level_sel - 5) % n
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self.pick_level(self.level_sel)
        elif e.type == pygame.MOUSEMOTION:
            for i in range(n):
                if self.card_rect(i).collidepoint(e.pos):
                    self.level_sel = i
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i in range(n):
                if self.card_rect(i).collidepoint(e.pos):
                    self.level_sel = i
                    self.pick_level(i)

    def pick_level(self, i):
        if i + 1 > self.data["highest_unlocked"] and not self.cfg["dev"]:
            self.say("TERKUNCI - selesaikan level sebelumnya dulu")
            return
        self.audio.play("select")
        self.run, self.run_tracked = profile.practice_run(len(LEVELS)), False
        self.totals = dict(score=0, gems=0, time=0.0)
        self.start_level(i)

    def ev_settings(self, e):
        rows = self.settings_rows
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                self.close_settings()
            elif k in (pygame.K_UP, pygame.K_w):
                self.set_sel = (self.set_sel - 1) % len(rows)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.set_sel = (self.set_sel + 1) % len(rows)
            elif k in (pygame.K_LEFT, pygame.K_a):
                rows[self.set_sel][2](-1)
                self.audio.play("menu")
            elif k in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                rows[self.set_sel][2](1)
                self.audio.play("select")
        elif e.type == pygame.MOUSEMOTION:
            for i in range(len(rows)):
                if self.settings_rect(i).collidepoint(e.pos):
                    self.set_sel = i
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
            for i in range(len(rows)):
                r = self.settings_rect(i)
                if r.collidepoint(e.pos):
                    self.set_sel = i
                    d = -1 if (e.button == 3 or abs(e.pos[0] - (r.right - 190)) < 30) else 1
                    rows[i][2](d)
                    self.audio.play("select")

    def ev_pause(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_p):
            self.resume()
        else:
            self.pause_menu.handle(e, self.audio)

    def ev_gameover(self, e):
        self.over_menu.handle(e, self.audio)

    def ev_victory(self, e):
        self.victory_menu.handle(e, self.audio)

    def ev_complete(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.after_complete(0)
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.go("levels")
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
            self.after_complete(1)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.after_complete(0)

    def after_complete(self, which):
        if which == 1:
            self.start_level(self.cur_level)
        elif self.cur_level < len(LEVELS) - 1:
            self.start_level(self.cur_level + 1)
        else:
            self.go("levels")


    def open_quiz(self):
        self.quiz = dict(text="", msg="", tries=0, ok=False, ok_t=0.0, shake=0.0)
        self.state = "quiz"
        self.edge = dict(jump=False, attack=False, dash=False)
        self.acc = 0.0
        try:
            pygame.key.start_text_input()
            pygame.key.set_repeat(350, 40)
        except Exception:
            pass

    def close_quiz(self, cancel=False):
        try:
            pygame.key.stop_text_input()
            pygame.key.set_repeat()
        except Exception:
            pass
        if cancel:
            self.world.key_armed = False
        self.quiz = None
        self.state = "play"

    def submit_quiz(self):
        q = self.quiz
        if not q["text"].strip():
            q["msg"] = "Ketik jawabanmu dulu, lalu tekan ENTER."
            return
        if quiz.check(self.cur_level, q["text"]):
            q["ok"], q["ok_t"], q["msg"] = True, 1.3, ""
            self.world.has_key = True
            self.world.score += 1000
            self.audio.play("gem")
        else:
            q["tries"] += 1
            q["shake"] = 0.35
            q["msg"] = "SALAH! Coba lagi."
            q["msg"] += "  " + quiz.tip(self.cur_level)
            self.audio.play("hurt")

    def ev_quiz(self, e):
        q = self.quiz
        if q is None or q["ok"]:
            return
        if e.type == pygame.TEXTINPUT:
            ch = "".join(c for c in e.text if c.isprintable())
            if ch and len(q["text"]) + len(ch) <= 40:
                q["text"] += ch
                q["msg"] = ""
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                q["text"] = q["text"][:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit_quiz()
            elif e.key == pygame.K_ESCAPE:
                self.close_quiz(cancel=True)


    def enter_pause(self):
        self.help_open = False
        self._pause_open_t = time.perf_counter()
        self.persist()
        self.state = "pause"
        self.audio.duck = 0.3
        self.apply_audio()
        self.refresh_pause()
        self.pause_menu.sel = 0

    def refresh_pause(self):
        items = [("RESUME", self.resume)]
        dev = self.cfg["dev"]
        if dev:
            items += [(lambda: f"GET ALL KEYS: {'ON' if self.dev_keys else 'OFF'}", self.toggle_all_keys),
                      (lambda: f"AUTO PLAY: {'ON' if self.autoplay else 'OFF'}", self.toggle_autoplay)]
        items += [("RESTART LEVEL", lambda: self.ask("Restart this level? Progress in it will be lost.", self.restart_level)),
                  ("SETTINGS", lambda: self.open_settings("pause")),
                  ("LOGOUT", self.ask_logout)]
        self.pause_menu = Menu(items, y0=250 if dev else 290, step=58 if dev else 64)

    def toggle_all_keys(self):
        self.dev_keys = not self.dev_keys
        if self.dev_keys and self.world:
            self.world.has_key = True
        self.apply_dev()
        self.say("GET ALL KEYS: " + ("ON - every level starts with its key" if self.dev_keys else "OFF"))

    def toggle_autoplay(self):
        self.autoplay = not self.autoplay
        self.pilot = AutoPilot()
        if self.world:
            self.world.god = self.autoplay
        self.apply_dev()
        self.say("AUTO PLAY: " + ("ON (invincible)" if self.autoplay else "OFF"))

    def ev_play(self, e):
        if self.help_open:
            if (e.type == pygame.KEYDOWN and e.key in (pygame.K_i, pygame.K_ESCAPE, pygame.K_RETURN)) or \
                    (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                self.close_help()
            elif e.type == pygame.WINDOWFOCUSLOST:
                self.enter_pause()
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_i:
            self.open_help()
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and HELP_RECT.collidepoint(e.pos):
            self.open_help()
            return
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_ESCAPE, pygame.K_p):
                self.enter_pause()
            elif k == pygame.K_F5 and self.cfg["dev"]:
                self.toggle_all_keys()
            elif k == pygame.K_F6 and self.cfg["dev"]:
                self.toggle_autoplay()
            elif k == pygame.K_b:
                self.ask_buy_life()
            elif k in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                self.edge["jump"] = True
            elif k in (pygame.K_t, pygame.K_j):
                self.edge["attack"] = True
            elif k in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_c):
                self.edge["dash"] = True
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if getattr(self, "diff_open", False):
                selected = False
                for i, rect in enumerate(DIFF_OPTION_RECTS):
                    if rect.collidepoint(e.pos):
                        value = ["Easy", "Normal", "Hard"][i]
                        self.cfg["difficulty"] = value
                        if self.world:
                            self.world.diff = value
                        self.persist()
                        self.say("DIFICULTY: " + ["EASY", "MEDIUM", "HARD"][i])
                        selected = True
                        break
                self.diff_open = False
                if selected:
                    return
            elif DIFF_RECT.collidepoint(e.pos):
                self.diff_open = True
                return
            if BUY_RECT.collidepoint(e.pos):
                self.ask_buy_life()
        elif e.type == pygame.WINDOWFOCUSLOST:
            self.enter_pause()
        return

    def spawn(self, x, y, n, col, spread=120, up=100, size=4, life=0.5):
        if not self.cfg["particles"]:
            return
        for _ in range(min(n, 40)):
            if len(self.particles) > 220:
                return
            self.particles.append([x, y, self.rng.uniform(-spread, spread), self.rng.uniform(-up, 0) - 20, life, col, size])

    def update_particles(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 500 * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]

    def do_shake(self, amt):
        if self.cfg["shake"]:
            self.shake = max(self.shake, amt)

    def process_events(self, evs):
        w = self.world
        p = w.player
        for ev in evs:
            if ev != "land":
                self.dlog("event " + ev)
            if ev in self.audio.sounds:
                self.audio.play(ev)
            if ev == "jump":
                self.spawn(p.x + 13, p.y + 40, 6, (230, 230, 255), 60, 30)
            elif ev == "land":
                self.spawn(p.x + 13, p.y + 40, 5, (230, 230, 255), 70, 30)
            elif ev == "gem":
                self.spawn(p.x + 13, p.y + 10, 14, (255, 80, 220), 130, 130)
            elif ev == "stomp":
                self.spawn(p.x + 13, p.y + 40, 12, (255, 255, 255), 150, 120)
                self.do_shake(3)
            elif ev == "hurt":
                self.do_shake(8)
                self.spawn(p.x + 13, p.y + 20, 14, (255, 80, 80), 160, 120)
            elif ev == "death":
                self.spawn(p.x + 13, p.y + 20, 30, (255, 90, 90), 220, 220, 5, 1.0)
            elif ev in ("boss_attack", "boss_hit", "boss_phase"):
                self.do_shake(10 if ev != "boss_attack" else 5)
            elif ev == "boss_intro":
                self.audio.music("boss")
                self.do_shake(12)
            elif ev == "boss_die":
                self.audio.music(str(w.lv.spec["mood"]))
                b = w.boss
                self.spawn(b.x + b.w / 2, b.y + b.h / 2, 40, (255, 200, 80), 300, 300, 6, 1.4)
                self.do_shake(14)
            elif ev == "checkpoint":
                self.spawn(p.x, p.y, 14, (80, 255, 160), 120, 120)

    def tracked(self):
        w = self.world
        yield w.player
        yield from w.enemies
        if w.boss:
            yield w.boss
        for sd in w.solids:
            if sd.kind == "moving":
                yield sd
        yield from w.shots

    def snapshot(self):
        self.prev = {id(o): (o.x, o.y) for o in self.tracked()}

    def update_play(self, dt):
        w = self.world
        keys = pygame.key.get_pressed()
        inp = dict(left=keys[pygame.K_LEFT] or keys[pygame.K_a], right=keys[pygame.K_RIGHT] or keys[pygame.K_d],
                   jump_held=keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP],
                   down=keys[pygame.K_DOWN] or keys[pygame.K_s], jump_pressed=False, attack=False, dash=False)
        if inp["left"] or inp["right"] or inp["jump_held"] or inp["down"] or (self.autoplay and self.cfg["dev"]):
            self.afk_t = 0.0
        self.acc += min(dt, 0.05)
        while self.acc >= STEP:
            self.acc -= STEP
            self.snapshot()
            inp["jump_pressed"], inp["attack"], inp["dash"] = self.edge["jump"], self.edge["attack"], self.edge["dash"]
            self.edge = dict(jump=False, attack=False, dash=False)
            auto = self.autoplay and self.cfg["dev"]
            self.process_events(w.update(STEP, self.pilot.step(w, STEP) if auto else inp))
        if w.quiz_request:
            w.quiz_request = False
            if self.autoplay and self.cfg["dev"]:
                w.has_key = True
            if w.state == "play":
                self.open_quiz()
        self.alpha = self.acc / STEP
        self.update_particles(dt)
        p = w.player
        pp = self.prev.get(id(p))
        px = p.x
        if pp and abs(p.x - pp[0]) < INTERP_MAX_JUMP:
            px = pp[0] + (p.x - pp[0]) * self.alpha
        tx = max(0, min(w.lv.width - W, px - 520))
        rate = 6.0
        if w.state == "complete":
            ex, ey, ew, eh = w.lv.exit
            tx, rate = max(0, min(w.lv.width - W, ex + ew / 2 - W / 2 + 140)), 3.5
        elif w.arena_locked and w.lv.arena:
            tx = max(0, min(w.lv.width - W, w.lv.arena["x"] - 40))
        self.cam += (tx - self.cam) * (1.0 - math.exp(-rate * min(dt, 0.05)))
        if w.state == "gameover":
            self.audio.stop_music()
            self.go("gameover")
        elif w.state == "complete" and w.complete_t > LEVEL_DONE_T and not self.finished_handled:
            self.finish_level()

    def finish_level(self):
        self.finished_handled = True
        w = self.world
        s = w.summary
        lvl = self.cur_level + 1
        save_system.record_level(self.data, lvl, s["score"], s["time"], 0, progress_only=w.dev_used)
        self.on_level_cleared(lvl, w.dev_used)
        if w.dev_used:
            self.say("DEV TOOLS DIPAKAI - progres tersimpan, skor/waktu tidak dicatat", 3.0)
        self.persist()
        self.totals["score"] += s["score"]
        self.totals["gems"] += s["gems"]
        self.totals["time"] += s["time"]
        if lvl == len(LEVELS):
            self.audio.music("victory")
            self.audio.play("victory")
            self.go("victory")
        else:
            self.go("complete")

    def update(self, dt):
        self.t += dt
        self.toast = (self.toast[0], max(0.0, self.toast[1] - dt))
        self.board_poll(dt)
        if self.fade_dir:
            self.fade += self.fade_dir * 900 * dt
            if self.fade_dir == 1 and self.fade >= 255:
                self.fade, self.fade_dir = 255.0, -1
                cb, self.fade_cb = self.fade_cb, None
                cb and cb()
            elif self.fade_dir == -1 and self.fade <= 0:
                self.fade, self.fade_dir = 0.0, 0
        self.shake = max(0.0, self.shake - dt * 30)
        self.update_dev(dt)
        self.run_clock(dt)
        if self.state == "play" and not self.confirm and self.fade_dir != 1 and not self.dev_trans and not self.help_open:
            self.update_play(dt)
        elif self.state == "quiz" and self.quiz:
            q = self.quiz
            q["shake"] = max(0.0, q["shake"] - dt)
            if q["ok"]:
                q["ok_t"] -= dt
                if q["ok_t"] <= 0:
                    self.close_quiz()
                    self.world.notify("KEY OBTAINED!  GATE CAN BE OPENED  +1000", 3.0)
                    self.spawn(self.world.player.x + 13, self.world.player.y + 10, 30, (255, 215, 50), 200, 200, 5, 1.0)
        elif self.state in ("victory", "complete"):
            self.update_particles(dt)
            if self.state == "complete" and self.autoplay and self.cfg["dev"] and self.fade_dir == 0:
                self.auto_t += dt
                if self.auto_t > 2.5:
                    self.auto_t = 0.0
                    self.after_complete(0)
            if self.state == "victory" and self.rng.random() < 0.3:
                self.spawn(self.rng.randint(0, W), 0, 3, hsv(self.rng.random() * 360), 40, 0, 5, 2.5)
        self.afk_update(dt)


    def draw_menu_bg(self, v):
        v.blit(self.menu_bg, (0, 0))
        for (x, y, p) in self.stars:
            if int(self.t * 2 + p * 9) % 3:
                v.fill((200, 200, 255), (x, y, 2, 2))
        off = (self.t * 40) % 80
        for i in range(-1, 18):
            x = i * 80 - off
            pygame.draw.line(v, (90, 30, 150), (x, 430), (W // 2 + (x - W // 2) * 4, H), 1)
        for j in range(8):
            y = 430 + int((j + (self.t * 0.6) % 1) ** 2 * 5)
            pygame.draw.line(v, (90, 30, 150), (0, y), (W, y), 1)
        pygame.draw.rect(v, (20, 10, 60), (0, 640, W, 80))
        pygame.draw.rect(v, (0, 240, 255), (0, 640, W, 4))

    def draw_title(self, v, y=120):
        col = hsv(180 + math.sin(self.t * 1.5) * 50 + 40)
        text(v, TITLE_MAIN, 64, (255, 255, 255), (W // 2, y), glow=col)
        text(v, TITLE_SUB, 36, (255, 120, 220), (W // 2, y + 56))

    def draw_menu(self, v):
        self.draw_menu_bg(v)
        self.draw_title(v)
        from .physics import Player
        from .render import draw_player
        pl = Player(200, 600)
        pl.facing = 1
        pl.state = "idle"
        draw_player(v, pl, 0, self.t)
        self.main_menu.draw(v, self.t)
        text(v, "Panah/Enter atau mouse   |   F11: layar penuh", 16, (150, 150, 200), (W // 2, 700), shadow=False)

    def card_rect(self, i):
        return pygame.Rect(50 + (i % 5) * 236, 215 + (i // 5) * 255, 220, 235)

    def draw_levels(self, v):
        self.draw_menu_bg(v)
        text(v, "LEVEL SELECT", 44, (255, 255, 255), (W // 2, 70), glow=(0, 200, 255))
        for i, spec in enumerate(LEVELS):
            r = self.card_rect(i)
            unlocked = i + 1 <= self.data["highest_unlocked"] or self.cfg["dev"]
            sel = i == self.level_sel
            pygame.draw.rect(v, (22, 12, 55) if unlocked else (14, 10, 30), r, border_radius=12)
            pygame.draw.rect(v, spec["accent"] if unlocked else (70, 70, 90), r, 4 if sel else 2, border_radius=12)
            if sel:
                pygame.draw.rect(v, (255, 255, 255), r.inflate(8, 8), 1, border_radius=14)
            text(v, str(i + 1), 40, spec["accent"] if unlocked else (110, 110, 130), (r.centerx, r.y + 34))
            words = spec["name"].split(" ")
            mid = (len(words) + 1) // 2
            for li, line in enumerate((" ".join(words[:mid]), " ".join(words[mid:]))):
                text(v, line, 17, (240, 240, 255) if unlocked else (120, 120, 140), (r.centerx, r.y + 76 + li * 22), shadow=False)
            for d in range(5):
                pygame.draw.rect(v, spec["accent"] if d < spec["diff"] and unlocked else (50, 50, 70),
                                 (r.x + 22 + d * 36, r.y + 130, 30, 8))
            text(v, f"KESULITAN {spec['diff']}/5", 13, (170, 170, 200), (r.centerx, r.y + 152), shadow=False)
            if not unlocked:
                lock_icon(v, r.centerx, r.y + 195, 30, (200, 200, 220))
            else:
                done = (i + 1) in self.data["completed"]
                text(v, "COMPLETED" if done else "UNLOCKED", 15, (80, 255, 160) if done else (255, 220, 80), (r.centerx, r.y + 180), shadow=False)
                best = self.data["best_score"].get(str(i + 1))
                text(v, f"BEST {best}" if best else "NO SCORE YET", 14, (200, 200, 230), (r.centerx, r.y + 206), shadow=False)
        text(v, "ENTER: play   ESC: back", 16, (150, 150, 200), (W // 2, 690), shadow=False)

    def draw_settings(self, v):
        self.draw_menu_bg(v)
        text(v, "SETTINGS", 44, (255, 255, 255), (W // 2, 60), glow=(0, 200, 255))
        for i, (label, getter, fn) in enumerate(self.settings_rows):
            r = self.settings_rect(i)
            sel = i == self.set_sel
            pygame.draw.rect(v, (30, 16, 70) if sel else (18, 10, 45), r, border_radius=8)
            pygame.draw.rect(v, (0, 240, 255) if sel else (70, 50, 130), r, 2, border_radius=8)
            val = getter()
            text(v, label, 20, (255, 255, 255), (r.x + 16, r.centery), anchor="midleft", shadow=False)
            if val:
                text(v, val, 20, (0, 240, 255), (r.right - 90, r.centery), shadow=False)
                text(v, "<", 22, (255, 255, 255), (r.right - 190, r.centery), shadow=False)
                text(v, ">", 22, (255, 255, 255), (r.right - 20, r.centery), shadow=False)
        text(v, "Kiri/Kanan ubah - Enter pilih - Esc kembali.  Tingkat kesulitan berlaku mulai level berikutnya.", 15,
             (150, 150, 200), (W // 2, 686), shadow=False)

    def draw_howto(self, v):
        self.draw_menu_bg(v)
        text(v, "CARA BBERMAIN", 44, (255, 255, 255), (W // 2, 70), glow=(0, 200, 255))
        lines = ["GERAK           Tombol panah  atau  A / D", "LOMPAT          Spasi / W / Atas  (tahan untuk lompat lebih tinggi)",
                 "SERANG          T  atau  J   (atau injak musuh dari atas)", "DASH            Shift Kiri  atau  C",
                 "JEDA            Esc  atau  P", "",
                 "Kumpulkan gem siber (500), gem tersembunyi di platform rahasiaa",
                 "Sentuh bendera untuk menyimpan checkpoint, capai gerbang EXIT untuk menyelesaiikan level",
                 "Boss cuma bisa dilukai saat inti-nya menyala setelah menyerang, hindari lalu serang",
                 "Beli nyawa, tombol BUY LIFE di HUD (atau tekan B) memakai gem, tekan I untuk bantuan",
                 "Bunuh musuh beruntun untuk pengali combo, selesaikan cepat untuk bonus waktu",
                 "Jatuh ke jurang mengurangi nyawa, jika nyawa habis level berakhir (progres tersimpan)"]
        for i, l in enumerate(lines):
            m = re.match(r"^([A-Z]+)\s{2,}(\S.*)$", l)
            if m:
                text(v, m.group(1), 21, (0, 240, 255), (260, 150 + i * 40), anchor="midleft", bold=True, shadow=False)
                text(v, m.group(2), 21, (230, 230, 255), (430, 150 + i * 40), anchor="midleft", bold=False, shadow=False)
            else:
                text(v, l, 21, (230, 230, 255), (260, 150 + i * 40), anchor="midleft", bold=False, shadow=False)
        text(v, "Tekan tombol apa saja untuk kembali", 16, (150, 150, 200), (W // 2, 690), shadow=False)

    def draw_credits(self, v):
        self.draw_menu_bg(v)
        text(v, "CREDITS", 44, (255, 255, 255), (W // 2, 70), glow=(0, 200, 255))
        text(v, TITLE, 26, (255, 120, 220), (W // 2, 135))
        people = [("REVANDO", "Base Game Maker  -  Idea Maker  -  Design Maker  -  Developer", (255, 220, 60)),
                  ("BRAMANTYA", "Co-Dev  -  Bug Fixer", (0, 240, 255)),
                  ("RADIT", "Tester  -  Bug Fixer", (120, 255, 160))]
        for i, (name, role, col) in enumerate(people):
            y = 205 + i * 100
            text(v, name, 44, col, (W // 2, y), glow=(40, 10, 90))
            text(v, role, 24, (230, 230, 255), (W // 2, y + 44), bold=False, shadow=False)
        lines = ["Terima kasih sudah bermain!"]
        for i, l in enumerate(lines):
            text(v, l, 18, (200, 200, 230), (W // 2, 515 + i * 30), bold=False, shadow=False)
        text(v, "Tekan tombol apa saja untuk kembali", 16, (150, 150, 200), (W // 2, 690), shadow=False)

    HELP_ROWS = (("A / D / Panah Kiri-Kanan", "Gerak kiri / kanan"), ("W / Spasi / Panah Atas", "Lompat (tahan = lebih tinggi)"),
                 ("T / J", "Serang (atau injak musuh)"), ("Shift Kiri / C", "Dash"),
                 ("Esc / P", "Jeda"), ("B", "Beli nyawa dengan gem"), ("I", "Buka bantuan ini"), ("Mouse", "Klik tombol di HUD"))

    @staticmethod
    def card_phase(age):
        if age < TUTORIAL_SECS:
            return 0.0
        k = (age - TUTORIAL_SECS) / HELP_SHRINK_T
        return k if k < 1.0 else None

    @staticmethod
    def shrink_rect(r, k):
        e = k * k * (3 - 2 * k)
        return pygame.Rect(*[int(a + (b - a) * e) for a, b in zip((r.x, r.y, r.w, r.h), (HELP_RECT.x, HELP_RECT.y, HELP_RECT.w, HELP_RECT.h))])

    def draw_shrinking(self, v, r, k, col):
        rr = self.shrink_rect(r, k)
        pygame.draw.rect(v, (12, 6, 38), rr, border_radius=12)
        pygame.draw.rect(v, col, rr, 2, border_radius=12)

    def draw_tutorial(self, v, age):
        k = self.card_phase(age)
        if k is None:
            return
        r = pygame.Rect(W // 2 - 430, 566, 860, 142)
        if k > 0:
            self.draw_shrinking(v, r, k, (0, 240, 255))
            return
        pygame.draw.rect(v, (12, 6, 38), r, border_radius=12)
        pygame.draw.rect(v, (0, 240, 255), r, 2, border_radius=12)
        text(v, "CARA BBERMAIN   (tekan I kapan saja untuk membukanya lagi)", 18, (255, 215, 50), (r.centerx, r.y + 18), shadow=False)
        for i, (k_, d) in enumerate(self.HELP_ROWS):
            x, y = r.x + 18 + (i // 4) * 430, r.y + 46 + (i % 4) * 24
            text(v, k_, 15, (0, 240, 255), (x, y), anchor="midleft", bold=True, shadow=False)
            text(v, d, 15, (230, 230, 255), (x + 212, y), anchor="midleft", bold=False, shadow=False)

    def help_visible(self):
        return bool(self.help_open and self.state == "play")

    def open_help(self):
        self.help_open = True
        self.edge = dict(jump=False, attack=False, dash=False)

    def close_help(self):
        self.help_open = False
        self.edge = dict(jump=False, attack=False, dash=False)
        self.acc = 0.0

    def draw_help_button(self, v):
        on = self.help_visible()
        pygame.draw.rect(v, (30, 70, 90) if on else (12, 6, 38), HELP_RECT, border_radius=8)
        pygame.draw.rect(v, (255, 215, 50) if on else (0, 240, 255), HELP_RECT, 2, border_radius=8)
        text(v, "i", 24, (255, 255, 255), HELP_RECT.center, shadow=False)

    def draw_help(self, v):
        self.overlay(v, 190)
        r = pygame.Rect(W // 2 - 460, 70, 920, 560)
        pygame.draw.rect(v, (14, 8, 44), r, border_radius=14)
        pygame.draw.rect(v, (0, 240, 255), r, 3, border_radius=14)
        text(v, "CARA BBERMAIN", 30, (255, 215, 50), (r.centerx, r.y + 30), shadow=False)
        for i, (k_, d) in enumerate(self.HELP_ROWS):
            x, y = r.x + 40 + (i // 4) * 430, r.y + 78 + (i % 4) * 30
            text(v, k_, 17, (0, 240, 255), (x, y), anchor="midleft", bold=True, shadow=False)
            text(v, d, 17, (230, 230, 255), (x + 215, y), anchor="midleft", bold=False, shadow=False)
        text(v, "CARA MENGALAHKAN BOSS", 24, (255, 120, 220), (r.centerx, r.y + 232), shadow=False)
        for i, line in enumerate(self.BOSS_HELP):
            text(v, f"{i + 1}. {line}", 17, (235, 235, 255), (r.x + 40, r.y + 272 + i * 32), anchor="midleft", bold=False, shadow=False)
        text(v, "Temukan KUNCI dan jawab soal-nya untuk membuka gerbang keluar. Gem bisa buat beli nyawa (B).", 16, (200, 200, 230),
             (r.centerx, r.y + 430), bold=False, shadow=False)
        text(v, "Permainan dijeda.   Tekan I, Esc, atau klik untuk melanjutkan.", 18, (150, 255, 200), (r.centerx, r.bottom - 36), shadow=False)

    def draw_hud(self, v):
        w = self.world
        pygame.draw.rect(v, (10, 5, 35), (0, 0, W, 54))
        pygame.draw.rect(v, w.lv.spec["accent"], (0, 54, W, 2))
        for i in range(w.max_hearts):
            heart(v, 28 + i * 27, 24, 26, (255, 70, 110) if i < w.hearts else (70, 40, 70))
        text(v, f"LIVES x{max(0, w.lives)}", 18, (255, 255, 255), (28 + w.max_hearts * 27 + 5, 26), anchor="midleft", shadow=False)
        diff = self.cfg.get("difficulty", "Normal")
        diff_label = {"Easy": "EASY", "Normal": "MEDIUM", "Hard": "HARD"}.get(diff, "EASY")
        pygame.draw.rect(v, (16, 10, 42), DIFF_RECT, border_radius=7)
        pygame.draw.rect(v, (120, 100, 220), DIFF_RECT, 1, border_radius=7)
        text(v, "MODE " + diff_label, 15, (220, 210, 255), DIFF_RECT.center, shadow=False)
        if getattr(self, "diff_open", False):
            for i, rect in enumerate(DIFF_OPTION_RECTS):
                pygame.draw.rect(v, (20, 12, 50), rect, border_radius=5)
                pygame.draw.rect(v, (80, 255, 160) if ["Easy", "Normal", "Hard"][i] == diff else (130, 110, 200), rect, 2, border_radius=5)
                text(v, ["EASY", "MEDIUM", "HARD"][i], 14, (255, 255, 255), rect.center, shadow=False)
        text(v, f"SCORE {w.score:07d}", 20, (255, 255, 255), (480, 27), shadow=False)
        fps_now = self.fps_stats[0] if self.fps_stats else 0.0
        text(v, f"FPS {fps_now:.0f}", 15, (80, 255, 160), (610, 27), shadow=False)
        text(v, f"GEMS {w.gem_bank}", 18, (255, 220, 60), (690, 27), shadow=False)
        text(v, f"LEVEL {self.cur_level + 1}", 19, w.lv.spec["accent"], (805, 27), shadow=False)
        text(v, f"{int(w.time // 60):02d}:{int(w.time % 60):02d}", 19, (255, 255, 255), (920, 27), shadow=False)
        self.draw_buy_button(v)
        self.draw_help_button(v)
        if w.combo > 1 and w.combo_t > 0:
            text(v, f"COMBO x{w.combo}", 24, (255, 120, 220), (W // 2, 84))
        if w.boss and w.boss.alive or (w.boss and w.boss.dying > 0):
            b = w.boss
            bw = 560
            pygame.draw.rect(v, (20, 10, 40), (W // 2 - bw // 2 - 3, 660, bw + 6, 28), border_radius=6)
            pygame.draw.rect(v, (255, 50, 120), (W // 2 - bw // 2, 663, int(bw * max(0, b.hp) / b.max_hp), 22), border_radius=4)
            text(v, f"{b.name}   PHASE {b.phase + 1}/{b.phases}", 16, (255, 255, 255), (W // 2, 646), shadow=True)
        if w.boss and w.boss.alive:
            self.draw_boss_help(v, w.boss)
        heart_end = 28 + w.max_hearts * 34
        text(v, "KUNCI: DITEMUKAN" if w.has_key else "KUNCI: BELUM ADA - jawab soal di kunci!", 16,
             (80, 255, 160) if w.has_key else (255, 215, 50), (20, 102), anchor="midleft", shadow=True)
        if self.cfg["dev"]:
            flags = self.flags_text()
            text(v, "DEV MODE" + ("  AUTO PLAY" if self.autoplay else "") + ("  " + flags if flags else ""),
                 14, (255, 90, 90), (20, 122), anchor="midleft", shadow=True)
        boss_card = bool(w.boss and w.boss.alive and w.boss.age < TUTORIAL_SECS)
        if w.msg_t > 0 and not (boss_card and w.msg == w.boss.name):
            text(v, w.msg, 40, (255, 255, 255), (W // 2, 160), glow=w.lv.spec["accent"])
        if w.hint and w.time < 400 and self.cur_level == 0:
            text(v, w.hint, 22, (255, 255, 255), (W // 2, 112), bold=True)
        if w.time < 2.4 and not w.boss:
            text(v, f"LEVEL {self.cur_level + 1}", 30, w.lv.spec["accent"], (W // 2, 250))
        if self.cur_level == 0 and not w.boss:
            self.draw_tutorial(v, w.time)
        if self.cur_level == 0 and w.time < TUTORIAL_SECS and not w.boss:
            text(v, w.lv.spec["name"], 44, (255, 255, 255), (W // 2, 300), glow=w.lv.spec["accent"])
            text(v, "Temukan KUNCI dan jawab soalnya untuk membuka gerbang!", 22, (255, 215, 50), (W // 2, 350))

    def draw_buy_button(self, v):
        w = self.world
        full = w.lives >= w.max_lives
        short = w.gem_bank < GEM_COST_LIFE
        can = w.state == "play" and not full and not short
        col = (80, 255, 160) if can else (120, 120, 150)
        pygame.draw.rect(v, (14, 44, 46) if can else (28, 22, 50), BUY_RECT, border_radius=8)
        pygame.draw.rect(v, col, BUY_RECT, 2, border_radius=8)
        sub = "LIVES FULL" if full else (f"{GEM_COST_LIFE} GEMS (not enough)" if short else f"{GEM_COST_LIFE} GEMS")
        text(v, "BUY LIFE [B]", 13, (255, 255, 255) if can else (170, 170, 200), (BUY_RECT.centerx, BUY_RECT.y + 14), shadow=False)
        text(v, sub, 13, col, (BUY_RECT.centerx, BUY_RECT.y + 32), shadow=False)

    BOSS_HELP = ("Hindari tembakan dan tiang api boss (tanda kuning di lantai = peringatan).",
                 "Saat serangannya selesai, semua bahaya hilang dan inti boss menyala (HIT ME!).",
                 "Serang dengan T / J atau injak dari atas saat inti menyala. Di luar itu serangan tidak berefek.",
                 "Ulangi sampai boss tumbang, lalu ambil kunci dan masuk ke gerbang keluar.")

    def boss_tip(self, b):
        st = b.state
        if st == "intro":
            return "Boss datang! Bersiaplah...", (255, 255, 255)
        if st == "phase":
            return "Boss makin ganas! Waspadai pola serangan baru...", (255, 160, 80)
        if st == "move":
            return "Jaga jarak - boss akan segera menyerang", (255, 215, 50)
        if st == "telegraph":
            return "AWAS! Boss akan menembak - bersiap menghindar!", (255, 120, 80)
        if st == "attack":
            return "HINDARI tembakan" + (" dan tiang api!" if (b.phase >= 1 or b.columns) else "!"), (255, 90, 110)
        if st == "tired" and b.vulnerable:
            return "INTI MENYALA - semua bahaya hilang! Serang sekarang: T / J atau injak!", (0, 255, 255)
        return "Bagus! Tunggu inti menyala lagi, lalu serang.", (180, 255, 200)

    def draw_boss_help(self, v, b):
        k = self.card_phase(b.age) if self.state == "play" else None
        cx, cy = W // 2 - 390, 66
        if k is not None and k > 0:
            self.draw_shrinking(v, pygame.Rect(cx, cy, 780, 176), k, (255, 215, 50))
        elif k == 0.0:
            card = self.overlay_cache.get("bosshelp")
            if card is None:
                card = pygame.Surface((780, 176), pygame.SRCALPHA)
                pygame.draw.rect(card, (10, 5, 35, 215), card.get_rect(), border_radius=10)
                self.overlay_cache["bosshelp"] = card = card.convert_alpha()
            v.blit(card, (cx, cy))
            pygame.draw.rect(v, (255, 215, 50), (cx, cy, 780, 176), 3, border_radius=10)
            text(v, "CARA MENGALAHKAN BOSS   (tekan I untuk membuka lagi)", 22, (255, 215, 50), (W // 2, cy + 22), shadow=False)
            for i, line in enumerate(self.BOSS_HELP):
                text(v, f"{i + 1}. {line}", 16, (235, 235, 255), (cx + 18, cy + 56 + i * 28), anchor="midleft", bold=False, shadow=False)
        tip, col = self.boss_tip(b)
        text(v, tip, 22, col, (W // 2, 614), shadow=True)

    def overlay(self, v, a=170):
        s = self.overlay_cache.get(a)
        if s is None:
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            s.fill((5, 0, 25, a))
            self.overlay_cache[a] = s = s.convert_alpha()
        v.blit(s, (0, 0))

    def draw_play_scene(self, v):
        a = self.alpha if self.state == "play" else 1.0
        swapped = []
        if a < 1.0 and self.prev:
            for o in self.tracked():
                q = self.prev.get(id(o))
                if q and abs(o.x - q[0]) < INTERP_MAX_JUMP and abs(o.y - q[1]) < INTERP_MAX_JUMP:
                    swapped.append((o, o.x, o.y))
                    o.x, o.y = q[0] + (o.x - q[0]) * a, q[1] + (o.y - q[1]) * a
        try:
            draw_world(v, self.world, round(self.cam), self.t, self.bg, self.particles)
            if self.cfg["dev"] and self.dv["coll"]:
                self.draw_collision(v, round(self.cam))
        finally:
            for o, x, y in swapped:
                o.x, o.y = x, y
        self.draw_hud(v)
        self.draw_dev_overlays(v)
        self.draw_session_overlays(v)

    def draw_play(self, v):
        self.draw_play_scene(v)
        if self.help_visible():
            self.draw_help(v)

    def draw_quiz(self, v):
        self.draw_play_scene(v)
        self.overlay(v, 190)
        q = self.quiz
        if not q:
            return
        subj, question = quiz.get(self.cur_level)[:2]
        ox = int(math.sin(self.t * 90) * 6) if q["shake"] > 0 else 0
        r = pygame.Rect(W // 2 - 460 + ox, 130, 920, 440)
        pygame.draw.rect(v, (20, 10, 55), r, border_radius=16)
        pygame.draw.rect(v, (255, 215, 50), r, 3, border_radius=16)
        text(v, f"SOAL KUNCI - LEVEL {self.cur_level + 1}", 34, (255, 215, 50), (W // 2 + ox, 178), glow=(90, 60, 0))
        text(v, subj, 22, (0, 240, 255), (W // 2 + ox, 222), shadow=False)
        for i, line in enumerate(wrap(question, 26, 840)):
            text(v, line, 26, (255, 255, 255), (W // 2 + ox, 275 + i * 36), bold=False, shadow=False)
        box = pygame.Rect(r.x + 60, 410, r.w - 120, 54)
        pygame.draw.rect(v, (8, 4, 30), box, border_radius=10)
        pygame.draw.rect(v, (80, 255, 160) if q["ok"] else (0, 240, 255), box, 3, border_radius=10)
        cursor = "_" if int(self.t * 2) % 2 and not q["ok"] else ""
        text(v, q["text"] + cursor, 28, (255, 255, 255), (box.x + 16, box.centery), anchor="midleft", shadow=False)
        if q["ok"]:
            text(v, "BENAR!  KUNCI DIDAPET  +1000", 30, (80, 255, 160), (W // 2, 505), glow=(0, 80, 40))
        else:
            if q["msg"]:
                for i, line in enumerate(wrap(q["msg"], 18, 840)):
                    text(v, line, 18, (255, 90, 110), (W // 2 + ox, 486 + i * 23), shadow=False)
            text(v, "Ketik jawabanmu, lalu tekan ENTER     ESC: batal (balik ke game)", 16, (150, 150, 200), (W // 2, 556), shadow=False)

    def draw_pause(self, v):
        self.draw_play_scene(v)
        self.overlay(v)
        text(v, "PAUSED", 56, (255, 255, 255), (W // 2, 190), glow=(0, 200, 255))
        self.pause_menu.draw(v, self.t)

    def draw_gameover(self, v):
        self.draw_play_scene(v)
        self.overlay(v, 200)
        text(v, "GAME OVER", 64, (255, 70, 90), (W // 2, 210), glow=(120, 0, 30))
        text(v, "Progres tersimpanmu aman.", 20, (230, 230, 255), (W // 2, 290), shadow=False)
        self.over_menu.draw(v, self.t, (255, 80, 100))

    def draw_complete(self, v):
        self.draw_menu_bg(v)
        s = self.world.summary
        text(v, "LEVEL COMPLETE!", 56, (255, 255, 255), (W // 2, 120), glow=(0, 255, 160))
        text(v, self.world.lv.spec["name"], 28, self.world.lv.spec["accent"], (W // 2, 180))
        rows = [("Score from play", s["base"]), ("Time bonus", s["time_bonus"]), ("Health bonus", s["heart_bonus"]),
                ("Cyber gems", s["gems"])]
        for i, (a, b) in enumerate(rows):
            text(v, a, 26, (230, 230, 255), (430, 250 + i * 46), anchor="midleft", bold=False, shadow=False)
            text(v, str(b), 26, (255, 255, 255), (850, 250 + i * 46), anchor="midright", shadow=False)
        text(v, f"TOTAL  {s['score']}", 38, (255, 220, 60), (W // 2, 520))
        best = self.data["best_score"].get(str(self.cur_level + 1), 0)
        text(v, f"Best: {best}   Time: {s['time']:.1f}s", 20, (200, 200, 230), (W // 2, 566), shadow=False)
        nxt = "ENTER: next level" if self.cur_level < len(LEVELS) - 1 else "ENTER: level select"
        text(v, f"{nxt}     R: replay     ESC: level select", 20, (150, 255, 200), (W // 2, 640), shadow=False)
        self.draw_particles(v)

    def draw_particles(self, v):
        for (px, py, vx, vy, life, col, size) in self.particles:
            pygame.draw.rect(v, col, (int(px), int(py), size, size))

    def draw_victory(self, v):
        self.draw_menu_bg(v)
        text(v, "CONGRATULATIONS!", 66, hsv(self.t * 120), (W // 2, 110), glow=(255, 255, 255))
        text(v, "YOU HAVE COMPLETED " + TITLE, 34, (255, 255, 255), (W // 2, 190), glow=(0, 200, 255))
        r = self.totals
        for i, l in enumerate([f"TOTAL SCORE   {r['score']}", f"GEM SIBER DIKUMPULKAN   {r['gems']}",
                               f"CAMPAIGN TIME   {int(r['time'] // 60):02d}:{int(r['time'] % 60):02d}"]):
            text(v, l, 32, (255, 220, 60), (W // 2, 290 + i * 60))
        run = profile.latest_run(self.data["runs"], self.user) if self.user else None
        if run and run["completed"] and not run["dev"]:
            text(v, f"COMPLETION TIME   {profile.fmt_time(run['completion_time'])}", 30, (80, 255, 160), (W // 2, 440))
            text(v, "Congratulations! You've completed all levels!", 20, (255, 255, 255), (W // 2, 480), shadow=False)
        else:
            text(v, "This run is not counted as completed (practice or developer tools).", 18, (200, 200, 230), (W // 2, 450),
                 bold=False, shadow=False)
        self.victory_menu.draw(v, self.t)
        self.draw_particles(v)

    def draw_confirm(self, v):
        self.overlay(v, 190)
        r = pygame.Rect(W // 2 - 400, 260, 800, 240)
        pygame.draw.rect(v, (20, 10, 55), r, border_radius=14)
        pygame.draw.rect(v, (255, 80, 200), r, 3, border_radius=14)
        text(v, self.confirm["msg"], 24, (255, 255, 255), (W // 2, 320), shadow=False)
        self.confirm_menu.draw(v, self.t, (255, 80, 200))

    def draw_fps(self, v):
        avg, ms, low1, fmin, fmax = self.fps_stats
        rows = [f"FPS      {avg:9.3f}", f"FRAME    {ms:9.3f} ms", f"1% LOW   {low1:9.3f}",
                f"MIN FPS  {fmin:9.3f}", f"MAX FPS  {fmax:9.3f}"]
        r = pygame.Rect(W - 156, 60, 148, 8 + len(rows) * 14)
        pygame.draw.rect(v, (8, 4, 30), r, border_radius=4)
        pygame.draw.rect(v, (80, 255, 160), r, 1, border_radius=4)
        for i, l in enumerate(rows):
            text(v, l, 12, (80, 255, 160) if i == 0 else (200, 255, 225), (r.x + 7, r.y + 11 + i * 14),
                 anchor="midleft", bold=False, shadow=False)

    def update_fps_stats(self, dt):
        self.ft.append(max(dt, 1e-6))
        self.fps_t += dt
        if self.fps_t >= 0.25 and len(self.ft) >= 4:
            self.fps_t = 0.0
            srt = sorted(self.ft)
            n, tot = len(srt), sum(srt)
            self.fps_stats = (n / tot, tot / n * 1000.0, 1.0 / srt[min(n - 1, int(n * 0.99))], 1.0 / srt[-1], 1.0 / srt[0])

    def draw(self):
        v = self.view
        if self.dev_trans:
            self.draw_devtrans(v)
            if self.dev_trans["t"] >= BLANK_IN:
                self.screen.blit(v, (0, 0))
                pygame.display.flip()
                return
        else:
            getattr(self, "draw_" + self.state)(v)
        self.draw_logout_button(v)
        if self.confirm:
            self.draw_confirm(v)
        self.draw_afk_warning(v)
        if self.toast[1] > 0:
            r = pygame.Rect(0, 0, 760, 44)
            r.center = (W // 2, 692 if self.state == "dev" else 620)
            pygame.draw.rect(v, (20, 10, 55), r, border_radius=10)
            pygame.draw.rect(v, (255, 220, 60), r, 2, border_radius=10)
            text(v, self.toast[0], 20, (255, 255, 255), r.center, shadow=False)
        if self.fade > 0:
            self.fade_surf.set_alpha(int(self.fade))
            v.blit(self.fade_surf, (0, 0))
        ox = oy = 0
        if self.shake > 0 and self.cfg["shake"]:
            ox, oy = self.rng.randint(-int(self.shake), int(self.shake)), self.rng.randint(-int(self.shake), int(self.shake))
        self.screen.blit(v, (ox, oy))
        pygame.display.flip()


    def pace(self):
        fps = self.cfg["fps"]
        now = time.perf_counter()
        if fps:
            period = 1.0 / fps
            self.next_frame += period
            if self.next_frame < now - period:
                self.next_frame = now
            while True:
                rem = self.next_frame - time.perf_counter()
                if rem <= 0:
                    break
                if rem > 0.002:
                    time.sleep(rem - 0.0015)
            now = time.perf_counter()
        dt = now - self.last_t
        self.last_t = now
        return dt

    def main_loop(self):
        self.last_t = self.next_frame = time.perf_counter()
        try:
            while self.running:
                raw = self.pace()
                self.update_fps_stats(raw)
                dt = min(raw, 0.25)
                for e in pygame.event.get():
                    self.handle_event(e)
                self.update(dt)
                self.draw()
        finally:
            self.persist()
            pygame.quit()

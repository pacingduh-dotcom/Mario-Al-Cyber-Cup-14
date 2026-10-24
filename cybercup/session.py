import math

import pygame

from . import profile, save_system
from .config import (AFK_GAME_SECS, AFK_GAME_WARN, AFK_MENU_SECS, AFK_MENU_WARN, GEM_COST_LIFE, GEM_COST_REVIVE, LEADERBOARD_ROWS, NAME_MAX)
from .levels import LEVELS
from .ui import W, H, text, wrap

NAME_BOX = pygame.Rect(40, 150, 420, 50)
BTN_START = pygame.Rect(40, 250, 420, 48)
BTN_MENU = pygame.Rect(40, 308, 420, 44)
RIGHT = pygame.Rect(490, 100, 750, 540)
LOGOUT_RECT = pygame.Rect(1160, 5, 112, 44)


def afk_label(secs):
    m, sec = divmod(int(secs), 60)
    if m and not sec:
        return f"{m} minute" + ("s" if m != 1 else "")
    return f"{m} min {sec} s" if m else f"{sec} seconds"



GAME_KEYS = frozenset(getattr(pygame, n) for n in (
    "K_LEFT", "K_RIGHT", "K_UP", "K_DOWN", "K_a", "K_d", "K_w", "K_s", "K_SPACE", "K_t", "K_j", "K_LSHIFT", "K_RSHIFT",
    "K_c", "K_b", "K_i", "K_p", "K_ESCAPE") if hasattr(pygame, n))

class SessionMixin:

    def init_session(self):
        n = len(LEVELS)
        self.run, self.run_tracked = profile.practice_run(n), False
        self.afk_t, self.afk_mode = 0.0, "menu"
        self.board_seen, self.board_check_t = save_system.board_exists(), 0.0
        self.user = None
        self.data["player_name"] = ""
        self.name_text, self.name_msg, self.name_shake, self.wfocus = "", "", 0.0, 0

    def text_input(self, on):
        try:
            (pygame.key.start_text_input if on else pygame.key.stop_text_input)()
        except Exception:
            pass

    def state_changed(self, prev, target):
        if target == "welcome":
            self.enter_welcome()
        elif prev == "welcome":
            self.text_input(False)
        if target == "welcome":
            self.world, self.quiz = None, None


    def sync_run(self):
        w, r = self.world, self.run
        if w is None or r is None or getattr(w, "run_ref", None) is not r:
            return
        r["gems"], r["gem_claimed"] = w.gem_bank, sorted(w.gem_claimed)[:200]
        r["difficulty"] = self.cfg.get("difficulty", "Normal")
        if self.run_tracked and w.dev_used:
            r["dev"] = True


    def wipe_board_memory(self):
        keep = self.run if (self.user and self.run_tracked and self.run in self.data["runs"]) else None
        n = len(self.data["runs"]) - (1 if keep else 0)
        self.data["runs"] = [keep] if keep else []
        self.data["active_run"] = keep["id"] if keep and not keep["completed"] else None
        self.data["players"] = [self.user] if self.user else []
        return n

    def board_watch(self):
        present = save_system.board_exists()
        if self.board_seen and not present:
            self.wipe_board_memory()
        self.board_seen = present

    def board_poll(self, dt):
        self.board_check_t += dt
        if self.board_check_t >= 1.0:
            self.board_check_t = 0.0
            self.board_watch()

    def persist(self):
        self.board_watch()
        self.sync_run()
        d = dict(self.data)
        d["settings"] = dict(self.cfg, dev=False, dev_unlocked=False)
        save_system.save(d)
        self.board_seen = save_system.board_exists()

    def begin_run(self, name):
        r = profile.new_run(name, len(LEVELS))
        self.data["runs"].append(r)
        self.data["active_run"] = r["id"]
        profile.prune(self.data["runs"], r["id"])
        self.run, self.run_tracked = r, True
        self.afk_t = 0.0
        return r

    def resume_run(self):
        for r in self.data["runs"]:
            if self.user and r["id"] == self.data["active_run"] and not r["completed"] and r["name"] == self.user:
                self.run, self.run_tracked = r, True
                return r
        return None

    def run_clock(self, dt):
        w = self.world
        if not self.run_tracked or w is None or self.fade_dir != 0 or self.confirm or self.dev_trans or w.state != "play":
            return
        if self.state in ("play", "quiz"):
            self.run["play_time"] += min(dt, 0.25)
            if w.dev_used or (self.cfg["dev"] and (self.autoplay or self.dev_keys)):
                self.run["dev"] = True

    def on_level_started(self, idx):
        r = self.run
        r["current_level"] = idx + 1
        r["level_reached"] = max(r["level_reached"], idx + 1)
        self.afk_t = 0.0

    def on_level_cleared(self, lvl, dev_used):
        r = self.run
        self.sync_run()
        if dev_used and self.run_tracked:
            r["dev"] = True
        if self.run_tracked and lvl == len(LEVELS) and not r["completed"] and r["level_reached"] >= lvl and not r["dev"]:
            r["completed"], r["completion_time"] = True, max(0.01, r["play_time"])
            r["gem_claimed"] = []
            self.data["active_run"] = None
        elif self.run_tracked and lvl == len(LEVELS):
            self.data["active_run"] = None
        self.persist()


    def afk_active(self):
        if not self.user or self.fade_dir != 0 or self.dev_trans or self.state in ("welcome", "dev"):
            return False
        if self.autoplay and self.cfg["dev"]:
            return False
        if self.state == "play":
            w = self.world
            return bool(w is not None and w.state == "play")
        return True

    def afk_gameplay(self):
        w = self.world
        return bool(self.state == "play" and w is not None and w.state == "play" and not self.confirm and not self.help_open)

    def afk_limit(self):
        return (AFK_GAME_SECS, AFK_GAME_WARN) if self.afk_gameplay() else (AFK_MENU_SECS, AFK_MENU_WARN)

    def note_activity(self, e):
        if self.afk_gameplay():
            if (e.type == pygame.KEYDOWN and e.key in GAME_KEYS) or e.type == pygame.MOUSEBUTTONDOWN:
                self.afk_t = 0.0
        elif e.type in (pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN, pygame.TEXTINPUT, pygame.MOUSEMOTION, getattr(pygame, "MOUSEWHEEL", -1)):
            self.afk_t = 0.0

    def afk_update(self, dt):
        if not self.afk_active():
            self.afk_t = 0.0
            return
        mode = "game" if self.afk_gameplay() else "menu"
        if mode != self.afk_mode:
            self.afk_mode, self.afk_t = mode, 0.0
        limit, _ = self.afk_limit()
        self.afk_t += min(dt, 0.25)
        if self.afk_t >= limit:
            self.afk_t = 0.0
            self.logout("afk", idle=limit)

    def logout_button_visible(self):
        return bool(self.user and self.state not in ("welcome", "dev") and not self.dev_trans)

    def logout_click(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.logout_button_visible() and LOGOUT_RECT.collidepoint(e.pos):
            self.audio.play("select")
            self.ask_logout()
            return True
        return False

    def draw_logout_button(self, v):
        if not self.logout_button_visible():
            return
        pygame.draw.rect(v, (60, 20, 40), LOGOUT_RECT, border_radius=8)
        pygame.draw.rect(v, (255, 110, 140), LOGOUT_RECT, 2, border_radius=8)
        text(v, "LOGOUT", 18, (255, 255, 255), LOGOUT_RECT.center, shadow=False)

    def menu_play_or_logout(self):
        if self.user:
            self.ask_logout()
        else:
            self.go("welcome")

    def ask_logout(self):
        self.ask(f"Log out '{self.user}'? Your level progress is lost and this name can't be used again.", self.logout)

    def change_name_row(self):
        if self.user:
            self.say("Nama tidak bisa diubah. Logout dulu, lalu pakai nama baru.", 3.0)
        else:
            self.go("welcome")

    def logout(self, reason="manual", idle=0.0):
        if not self.user:
            return
        if reason == "afk" and self.state in ("play", "quiz") and self.run_tracked:
            self.run["play_time"] = max(0.0, self.run["play_time"] - idle)
        self.sync_run()
        if self.run_tracked:
            self.run["ended"] = "afk" if reason == "afk" else "logout"
            self.run["resets"] = self.run.get("resets", 0)
        self.confirm = None
        self.autoplay = self.dev_keys = False
        self.dev_deactivate(close=False)
        self.data["active_run"] = None
        self.data["player_name"] = ""
        self.user = None
        self.run, self.run_tracked = profile.practice_run(len(LEVELS)), False
        self.totals = dict(score=0, gems=0, time=0.0)
        self.afk_t = 0.0
        self.back_to = "menu"
        self.audio.duck = 1.0
        self.cfg["difficulty"] = save_system.DEFAULT_SETTINGS["difficulty"]
        self.persist()
        self.say(f"Auto logout: no activity for {afk_label(idle)}." if reason == "afk" else "Logged out.", 5.0)
        self.go("welcome")

    def can_reset_session(self):
        w = self.world
        return bool(w and w.state == "play" and self.fade_dir == 0 and not self.dev_trans and not self.confirm
                    and (self.state == "play" or (self.state == "dev" and self.dev_back == "play")))

    def reset_session(self, reason):
        if not self.can_reset_session():
            return False
        self.afk_t = 0.0
        r = self.run
        r["resets"] += 1
        if self.run_tracked:
            r["dev"] = True
        self.sync_run()
        self.dev_deactivate(close=False)
        self.say("Session reset.", 3.5)
        self.start_level(self.cur_level)
        return True

    def do_reset_session(self):
        if not self.reset_session("dev"):
            self.say_dev("Reset unavailable right now (loading, paused or in a transition)")


    def gem_balance(self):
        return self.world.gem_bank if self.world else 0

    def ask_buy_life(self):
        w = self.world
        if not w or w.state != "play":
            self.say("Nyawa hanya bisa dibeli saat bermain.")
        elif w.lives >= w.max_lives:
            self.say(f"Nyawa sudah penuh ({w.lives}/{w.max_lives}).")
        elif w.gem_bank < GEM_COST_LIFE:
            self.say(f"Gem kurang: butuh {GEM_COST_LIFE}, kamu punya {w.gem_bank}.")
        else:
            self.ask(f"Pakai {GEM_COST_LIFE} gem untuk memulihkan 1 nyawa? Kamu punya {w.gem_bank} gem.", self.do_buy_life)

    def do_buy_life(self):
        ok, msg = self.world.buy_life(GEM_COST_LIFE) if self.world else (False, "No active level.")
        if ok:
            self.sync_run()
            self.audio.play("gem")
        self.say(msg)
        self.refresh_pause()

    def ask_revive(self):
        w = self.world
        if not w or w.state != "gameover":
            self.say("Hidup kembali hanya tersedia setelah GAME OVER.")
        elif w.gem_bank < GEM_COST_REVIVE:
            self.say(f"Gem kurang: butuh {GEM_COST_REVIVE}, kamu punya {w.gem_bank}.")
        else:
            self.ask(f"Pakai {GEM_COST_REVIVE} gem untuk hidup lagi di checkpoint terakhir? Kamu punya {w.gem_bank} gem.", self.do_revive)

    def do_revive(self):
        ok, msg = self.world.revive(GEM_COST_REVIVE) if self.world else (False, "No active level.")
        self.say(msg)
        if ok:
            self.sync_run()
            self.audio.music(str(self.world.lv.spec["mood"]))
            self.edge = dict(jump=False, attack=False, dash=False)
            self.acc, self.afk_t = 0.0, 0.0
            self.state = "play"


    def enter_welcome(self):
        self.name_text, self.name_msg, self.wfocus = "", "", 0
        self.lb_scroll = 0
        self.text_input(True)

    def welcome_start(self):
        if self.user:
            self.new_game()
            return
        ok, val = profile.valid_name(self.name_text)
        if not ok:
            self.name_msg, self.name_shake, self.wfocus = val, 0.35, 0
            self.audio.play("hurt")
            return
        if profile.name_taken(self.data, val):
            self.name_msg, self.name_shake, self.wfocus = "Name already taken. Use another name.", 0.35, 0
            self.audio.play("hurt")
            return
        profile.register_name(self.data, val)
        self.user = self.data["player_name"] = val
        self.persist()
        self.new_game()

    def welcome_menu(self):
        self.go("menu")

    def ev_welcome(self, e):
        if e.type == pygame.TEXTINPUT and self.wfocus == 0:
            ch = "".join(c for c in e.text if c.isprintable())
            if ch and len(self.name_text) + len(ch) <= NAME_MAX:
                self.name_text += ch
                self.name_msg = ""
        elif e.type == getattr(pygame, "MOUSEWHEEL", None):
            self.lb_scroll = max(0, getattr(self, "lb_scroll", 0) - e.y * 2)
        elif e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                self.lb_scroll = max(0, getattr(self, "lb_scroll", 0) + (LEADERBOARD_ROWS if k == pygame.K_PAGEDOWN else -LEADERBOARD_ROWS))
            elif k == pygame.K_BACKSPACE and self.wfocus == 0:
                self.name_text = self.name_text[:-1]
                self.name_msg = ""
            elif k in (pygame.K_DOWN, pygame.K_TAB):
                self.wfocus = (self.wfocus + 1) % 3
            elif k == pygame.K_UP:
                self.wfocus = (self.wfocus - 1) % 3
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.welcome_menu() if self.wfocus == 2 else self.welcome_start()
            elif k == pygame.K_ESCAPE:
                self.welcome_menu()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if NAME_BOX.collidepoint(e.pos):
                self.wfocus = 0
            elif BTN_START.collidepoint(e.pos):
                self.welcome_start()
            elif BTN_MENU.collidepoint(e.pos):
                self.welcome_menu()

    def _button(self, v, r, label, focus):
        pygame.draw.rect(v, (50, 30, 100) if focus else (20, 12, 52), r, border_radius=10)
        pygame.draw.rect(v, (0, 240, 255) if focus else (90, 70, 150), r, 3 if focus else 2, border_radius=10)
        text(v, label, 24, (255, 255, 255), r.center, shadow=False)

    def draw_welcome(self, v):
        self.draw_menu_bg(v)
        self.name_shake = max(0.0, self.name_shake - 1 / 60)
        text(v, "WELCOME!", 38, (255, 255, 255), (250, 62), glow=(0, 200, 255))
        text(v, "Enter your name:", 20, (200, 200, 230), (40, 128), anchor="midleft", bold=False, shadow=False)
        ox = 6 if self.name_shake > 0 and int(self.t * 30) % 2 else 0
        box = NAME_BOX.move(ox, 0)
        pygame.draw.rect(v, (8, 4, 30), box, border_radius=10)
        pygame.draw.rect(v, (255, 80, 110) if self.name_msg else ((0, 240, 255) if self.wfocus == 0 else (90, 70, 150)), box, 3, border_radius=10)
        cur = "_" if self.wfocus == 0 and int(self.t * 2) % 2 else ""
        text(v, self.name_text + cur, 28, (255, 255, 255), (box.x + 14, box.centery), anchor="midleft", shadow=False)
        text(v, f"{len(self.name_text)}/{NAME_MAX}", 14, (150, 150, 200), (box.right - 10, box.bottom + 12), anchor="midright", shadow=False)
        text(v, self.name_msg or "1-16 characters. Each name can only be used once.", 15,
             (255, 90, 110) if self.name_msg else (150, 150, 200), (40, box.bottom + 12), anchor="midleft", bold=False, shadow=False)
        self._button(v, BTN_START, "START GAME", self.wfocus == 1)
        self._button(v, BTN_MENU, "MAIN MENU", self.wfocus == 2)
        self.draw_leaderboard(v)
        text(v, "Tips: tanpa aktivitas 10 dtk saat bermain (1 menit di menu / kuis) akan logout otomatis.", 15,
             (150, 150, 200), (W // 2, 690), bold=False, shadow=False)

    def draw_leaderboard(self, v):
        r = RIGHT
        pygame.draw.rect(v, (20, 10, 55), r, border_radius=14)
        pygame.draw.rect(v, (255, 80, 200), r, 2, border_radius=14)
        text(v, "LEADERBOARD", 26, (255, 120, 220), (r.centerx, r.y + 28))
        cols = (("NO", 24, "midleft"), ("PLAYER", 84, "midleft"), ("STATUS", 250, "midleft"), ("LEVEL", 385, "midleft"), ("MODE", 465, "midleft"),
                ("PLAY TIME", 545, "midleft"), ("FINISH", 660, "midleft"))
        for h, dx, al in cols:
            text(v, h, 14, (150, 150, 200), (r.x + dx, r.y + 66), anchor=al, shadow=False)
        allrows = profile.leaderboard(self.data["runs"], 100000)
        rows_max = LEADERBOARD_ROWS
        self.lb_scroll = max(0, min(getattr(self, "lb_scroll", 0), len(allrows) - rows_max))
        rows = allrows[self.lb_scroll:self.lb_scroll + rows_max]
        if len(allrows) > rows_max:
            track = pygame.Rect(r.right - 12, r.y + 88, 6, rows_max * 41)
            pygame.draw.rect(v, (50, 30, 100), track, border_radius=3)
            th = max(24, int(track.h * rows_max / len(allrows)))
            ty = track.y + int((track.h - th) * self.lb_scroll / (len(allrows) - rows_max))
            pygame.draw.rect(v, (255, 120, 220), (track.x, ty, track.w, th), border_radius=3)
        if not rows:
            text(v, "No runs yet. Press START GAME to set the first record!", 18, (200, 200, 230), r.center, bold=False, shadow=False)
        me = (self.user or "").lower()
        for i, e in enumerate(rows):
            y = r.y + 104 + i * 41
            col = (80, 255, 160) if e["status"] == "Completed" else (255, 255, 255)
            if e["name"].lower() == me:
                pygame.draw.rect(v, (50, 30, 100), (r.x + 10, y - 17, r.w - 20, 34), border_radius=6)
            vals = (str(e["rank"]), e["name"], e["status"], f"{e['level']}/{e['total']}",
                    {"Easy": "EASY", "Normal": "MEDIUM", "Hard": "HARD"}.get(e.get("difficulty", "Normal"), "MEDIUM"),
                    profile.fmt_time(e["play_time"]), profile.fmt_time(e["completion_time"]) if e["completion_time"] else "-")
            for (h, dx, al), val in zip(cols, vals):
                text(v, val, 18, col, (r.x + dx, y), anchor=al, shadow=False)


    def draw_afk_warning(self, v):
        if not self.afk_active():
            return
        limit, warn = self.afk_limit()
        if self.afk_t < limit - warn:
            return
        left = max(1, math.ceil(limit - self.afk_t))
        rr = pygame.Rect(0, 0, 820, 44)
        rr.center = (W // 2, 262 if self.afk_gameplay() else (150 if self.state in ("play", "pause", "quiz", "gameover") else 664))
        pygame.draw.rect(v, (60, 20, 20), rr, border_radius=10)
        pygame.draw.rect(v, (255, 160, 80), rr, 2, border_radius=10)
        text(v, f"No activity detected! Auto logout in {left} s - press any key", 20, (255, 255, 255), rr.center, shadow=False)

    def draw_session_overlays(self, v):
        w = self.world
        if w is None:
            return
        if w.state == "complete" and w.complete_t > 1.0:
            final = self.cur_level + 1 >= len(LEVELS)
            text(v, "ALL LEVELS CLEARED!" if final else f"LEVEL {self.cur_level + 2}  >>", 46, (255, 255, 255), (W // 2, 220),
                 glow=(0, 255, 160))

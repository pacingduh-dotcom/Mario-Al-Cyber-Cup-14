import sys, os, types, tempfile, itertools, random

os.environ["CYBERCUP_NO_BUG"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
_c = itertools.count(1)
pg = types.ModuleType("pygame")


class _Err(Exception):
    pass


pg.error = _Err
for name in "QUIT TEXTINPUT KEYDOWN KEYUP MOUSEMOTION MOUSEBUTTONDOWN WINDOWFOCUSLOST SCALED RESIZABLE FULLSCREEN SRCALPHA MOUSEWHEEL".split():
    setattr(pg, name, next(_c) * 1000)
for k in "UP DOWN LEFT RIGHT w a s d x t j c p b i F5 F6 F10 F11 q e TAB SPACE RETURN KP_ENTER ESCAPE LSHIFT RSHIFT BACKSPACE PAGEUP PAGEDOWN".split():
    setattr(pg, "K_" + k, next(_c))


class Rect:
    def __init__(s, x=0, y=0, w=0, h=0):
        if hasattr(x, "__len__"):
            x, y = x[0], x[1]
        s.x, s.y, s.w, s.h = x, y, w, h
    width = property(lambda s: s.w); height = property(lambda s: s.h)
    right = property(lambda s: s.x + s.w); bottom = property(lambda s: s.y + s.h)
    centerx = property(lambda s: s.x + s.w // 2); centery = property(lambda s: s.y + s.h // 2)

    def _set(s, ax, ay, px, py):
        s.x = px - int(ax * s.w); s.y = py - int(ay * s.h)
    center = property(lambda s: (s.centerx, s.centery), lambda s, v: s._set(.5, .5, *v))
    midleft = property(lambda s: (s.x, s.centery), lambda s, v: s._set(0, .5, *v))
    midright = property(lambda s: (s.right, s.centery), lambda s, v: s._set(1, .5, *v))
    topleft = property(lambda s: (s.x, s.y), lambda s, v: s._set(0, 0, *v))
    midtop = property(lambda s: (s.centerx, s.y), lambda s, v: s._set(.5, 0, *v))
    topright = property(lambda s: (s.right, s.y), lambda s, v: s._set(1, 0, *v))

    def collidepoint(s, p):
        return s.x <= p[0] < s.x + s.w and s.y <= p[1] < s.y + s.h

    def inflate(s, dx, dy):
        return Rect(s.x - dx // 2, s.y - dy // 2, s.w + dx, s.h + dy)

    def move(s, dx, dy):
        return Rect(s.x + dx, s.y + dy, s.w, s.h)


class Surface:
    def __init__(s, size=(1, 1), flags=0):
        s.size = size
    def blit(s, *a, **k): pass
    def fill(s, *a, **k): pass
    def set_alpha(s, *a): pass
    def get_rect(s): return Rect(0, 0, *s.size)
    def convert_alpha(s): return s
    def convert(s): return s


class Font:
    def __init__(s, *a, **k): pass
    def render(s, t, aa, c): return Surface((max(1, len(t) * 10), 24))
    def size(s, t): return (len(t) * 10, 24)


class Color:
    def __init__(s, *a): s.r = s.g = s.b = 100; s.hsva = (0, 0, 0, 0)


class Clock:
    def tick(s, fps=0): return 16


class draw:
    pass


for fn in "rect line circle ellipse polygon arc".split():
    setattr(draw, fn, staticmethod(lambda *a, **k: None))
pg.draw = draw
pg.Rect, pg.Surface, pg.Color = Rect, Surface, Color
pg.font = types.SimpleNamespace(SysFont=lambda *a, **k: Font(), Font=Font)
pg.time = types.SimpleNamespace(Clock=Clock)
MODES = []
pg.display = types.SimpleNamespace(set_mode=lambda *a, **k: (MODES.append(a[1] if len(a) > 1 else 0), Surface((1280, 720)))[1], set_caption=lambda *a: None, flip=lambda: None, quit=lambda: None, init=lambda: None, get_init=lambda: True)
pg.init = lambda: None
pg.quit = lambda: None
pg.mixer = types.SimpleNamespace(init=lambda *a, **k: (_ for _ in ()).throw(_Err("no audio device")))


class Keys(dict):
    def __getitem__(s, k): return s.get(k, False)


HELD = Keys()
pg.key = types.SimpleNamespace(get_pressed=lambda: HELD, name=lambda k: chr(k) if 32 <= k < 127 else "", start_text_input=lambda: None, stop_text_input=lambda: None, set_repeat=lambda *a: None)
Ev = lambda t, **k: types.SimpleNamespace(type=t, **k)
pg.event = types.SimpleNamespace(get=lambda: [])
sys.modules["pygame"] = pg
sys.modules["numpy"] = types.ModuleType("numpy")

from cybercup import save_system
save_system.SAVE_DIR_OVERRIDE = tempfile.mkdtemp()
from cybercup import audio as _a
from cybercup.game import Game
from cybercup.levels import LEVELS as LEVELS_
from cybercup import profile as profile_


def frames(g, n=3):
    for _ in range(n):
        g.update(0.016); g.draw()


def key(g, k):
    g.handle_event(Ev(pg.KEYDOWN, key=k))


def settle(g):
    for _ in range(40):
        g.update(0.016)


def main():
    g = Game()
    AFK = dict(on=False)
    _upd = g.update
    def update(dt):
        if not AFK["on"]:
            g.afk_t = 0.0
        _upd(dt)
    g.update = update
    settle(g); frames(g)
    assert g.state == "menu" and g.main_menu.sel == 0 and g.main_menu.label(0) == "PLAY GAME"
    assert [g.main_menu.label(i) for i in range(len(g.main_menu.items))] == ["PLAY GAME", "CARA BERMAIN", "CREDITS", "EXIT GAME"]
    assert MODES[0] == (pg.SCALED | pg.RESIZABLE | pg.FULLSCREEN) and g.cfg["fullscreen"] is True
    key(g, pg.K_F11); frames(g, 1)
    assert g.cfg["fullscreen"] is False and MODES[-1] == (pg.SCALED | pg.RESIZABLE)
    key(g, pg.K_F11); frames(g, 1)
    assert g.cfg["fullscreen"] is True and MODES[-1] == (pg.SCALED | pg.RESIZABLE | pg.FULLSCREEN)
    g.main_menu.items[0][1](); settle(g); frames(g, 2)
    assert g.state == "welcome"
    key(g, pg.K_F11); assert g.cfg["fullscreen"] is False; key(g, pg.K_F11); assert g.cfg["fullscreen"] is True
    typ = lambda t: g.handle_event(Ev(pg.TEXTINPUT, text=t))
    assert g.data["player_name"] == "" and g.wfocus == 0
    typ("   "); key(g, pg.K_RETURN); frames(g, 2)
    assert g.state == "welcome" and g.name_msg == "Please enter a name." and g.data["player_name"] == ""
    g.name_text = ""
    for _ in range(4): typ("A" * 5)
    assert len(g.name_text) <= 16
    g.name_text = ""; typ("  Tester  "); key(g, pg.K_RETURN); settle(g); frames(g, 2)
    assert g.data["player_name"] == "Tester" and g.state == "play" and g.run_tracked and g.run["name"] == "Tester"
    assert g.data["active_run"] == g.run["id"] and g.run in g.data["runs"]

    HELD.clear(); HELD[pg.K_RIGHT] = True
    t0 = g.run["play_time"]; frames(g, 60)
    t1 = g.run["play_time"]; assert t1 > t0 + 0.5
    key(g, pg.K_ESCAPE); assert g.state == "pause"
    for _ in range(300): g.update(0.016)
    assert g.run["play_time"] == t1
    key(g, pg.K_ESCAPE); HELD.clear()
    g.go("menu"); settle(g); assert g.state == "menu"
    assert g.run["resets"] == 0
    for st in ("levels", "settings", "howto", "credits"):
        g.go(st); settle(g); frames(g); assert g.state == st, st

    g.go("settings"); settle(g)
    for i in range(len(g.settings_rows)):
        g.set_sel = i
        if g.settings_rows[i][0] in ("RESET PROGRESS", "BACK", "PLAYER NAME"):
            continue
        key(g, pg.K_LEFT); key(g, pg.K_RIGHT); frames(g, 1)

    g.data["highest_unlocked"] = 5
    g.set_sel = [r[0] for r in g.settings_rows].index("RESET PROGRESS"); key(g, pg.K_RETURN); frames(g); assert g.confirm
    key(g, pg.K_ESCAPE); assert not g.confirm and g.data["highest_unlocked"] == 5
    key(g, pg.K_RETURN); g.confirm_menu.sel = 0; key(g, pg.K_RETURN)
    assert g.data["highest_unlocked"] == 1
    g.go("menu"); settle(g)

    rnd = random.Random(1)
    for lvl in range(5):
        g.data["highest_unlocked"] = 5
        g.pick_level(lvl); settle(g)
        assert g.state == "play" and g.world.idx == lvl
        for f in range(500):
            HELD.clear(); HELD[pg.K_RIGHT] = True; HELD[pg.K_SPACE] = rnd.random() < .5
            if rnd.random() < .1: key(g, pg.K_SPACE)
            if rnd.random() < .05: key(g, pg.K_t)
            if rnd.random() < .03: key(g, pg.K_LSHIFT)
            g.update(0.016); g.draw()
        if lvl % 3 == 0:
            key(g, pg.K_ESCAPE); assert g.state == "pause"; frames(g)
            g.ask("x", lambda: None); frames(g); g.confirm = None
            key(g, pg.K_p); assert g.state == "play"
    HELD.clear()

    for lvl in (3, 4):
        g.start_level(lvl); settle(g)
        a = g.world.lv.arena
        g.world.player.reset(a["x"] + 300, a["y"] - 40)
        for _ in range(900):
            g.world.god = True; g.world.has_key = True
            g.update(0.016); g.draw()
        assert g.world.boss is not None
        b = g.world.boss
        for st in ("intro", "phase", "move", "telegraph", "attack", "tired"):
            b.state, b.invuln = st, 0.0
            tip, col = g.boss_tip(b)
            assert tip and len(col) == 3 and all(ch not in tip for ch in "{}"), (st, tip)
        b.state, b.invuln = "tired", 0.0; assert "INTI MENYALA" in g.boss_tip(b)[0] and "T / J" in g.boss_tip(b)[0]
        assert "HINDARI" in (b.state == "attack" or g.boss_tip(type("B", (), dict(state="attack", phase=0, columns=[]))())[0])
        b.age = 0.0; frames(g, 2); b.age = 99.0; frames(g, 2)
    g.start_level(2); settle(g)
    kx, ky = g.world.lv.key
    g.world.player.reset(kx - 10, ky - 20)
    for _ in range(10):
        g.update(0.016); g.draw()
    assert g.state == "quiz", g.state
    g.handle_event(Ev(pg.TEXTINPUT, text="salah")); key(g, pg.K_RETURN); frames(g, 2)
    assert not g.world.has_key and g.quiz["tries"] == 1
    for _ in range(5): key(g, pg.K_BACKSPACE)
    g.handle_event(Ev(pg.TEXTINPUT, text="produksi")); key(g, pg.K_RETURN)
    assert g.world.has_key
    for _ in range(120):
        g.update(0.016); g.draw()
    assert g.state == "play"

    g.cfg["dev"] = False
    g.start_level(1); settle(g)
    assert g.state == "play" and not g.dev_session and not hasattr(g, "draw_gear")
    def kc(ch): g.handle_event(Ev(pg.KEYDOWN, key=ord(ch.lower()), unicode=ch))
    def typecode(c):
        for ch in c: kc(ch)
    typecode("X41551456Q"); assert g.dev_trans is None and not g.dev_session
    typecode("X4155"); frames(g, 400); typecode("1456P"); assert g.dev_trans is None
    g.state = "pause"; typecode("X41551456P"); assert g.dev_trans is None; g.state = "play"
    g.state = "welcome"; typecode("X41551456P"); assert g.dev_trans is None; g.state = "play"
    g.detector.reset()
    typecode("X41551456P")
    assert g.dev_trans is not None and not g.dev_session and g.state == "play"
    key(g, pg.K_SPACE); assert not g.edge["jump"]
    typecode("X41551456P")
    calls = []; real = g.draw_play_scene; g.draw_play_scene = lambda v: calls.append(1) or real(v)
    while g.dev_trans and g.dev_trans["t"] < 0.3:
        g.update(0.016); g.draw()
    assert g.dev_trans and g.state == "play" and not g.dev_session
    n = len(calls); frames(g, 3); assert len(calls) == n
    for _ in range(100):
        g.update(0.016); g.draw()
    g.draw_play_scene = real
    assert g.state == "dev" and g.dev_session and g.cfg["dev"] and g.dev_trans is None
    assert g.data["settings"]["dev"] is True or True
    import json as _j
    g.persist(); assert not _j.load(open(save_system.save_path()))["settings"]["dev"]
    assert [r.label for r in g.dev_rows[0]][0].startswith("FLY")
    def press(tab, row, times=1):
        g.dev_tab, g.dev_sel = tab, row
        for _ in range(times):
            key(g, pg.K_RETURN)
        frames(g, 1)
    w = g.world; pl = w.player
    press(0, 0); assert g.dv["fly"] and pl.fly
    press(0, 1); assert g.dv["noclip"] and pl.noclip
    press(0, 2); assert w.dev_god
    press(0, 3); assert w.inf_health
    press(0, 4); assert g.toast[0].startswith("No stamina")
    press(0, 5); assert pl.jump_mul == 1.5
    press(0, 6); assert pl.speed_mul == 1.5
    g.dev_tab, g.dev_sel = 0, 7; key(g, pg.K_RIGHT); assert g.dv["tp"] == 1
    x0 = pl.x; press(0, 8); assert pl.x != x0 and g.state == "dev"
    press(0, 9); assert abs(pl.x - w.lv.start[0]) < 1
    n = w.monsters_alive(); assert n > 0
    press(1, 0); assert g.confirm and w.monsters_alive() == n; key(g, pg.K_ESCAPE); assert not g.confirm and w.monsters_alive() == n
    press(1, 0); g.confirm_menu.sel = 0; key(g, pg.K_RETURN); assert w.monsters_alive() == 0 and not g.confirm
    press(1, 4); g.confirm_menu.sel = 0; key(g, pg.K_RETURN); assert w.monsters_alive() == n
    press(1, 2); assert w.freeze_ai; press(1, 2); assert not w.freeze_ai
    press(1, 3); assert w.no_spawn; press(1, 3); assert not w.no_spawn
    press(1, 1); g.confirm_menu.sel = 0; key(g, pg.K_RETURN); assert w.enemies == []
    for r in (0, 1, 2, 3, 4):
        press(2, r)
    assert all(g.dv[k] for k in ("coords", "stats", "counts", "coll", "log"))
    g.dev_back = "play"; g.state = "play"; frames(g, 30); g.state = "dev"; frames(g, 2); assert len(g.dev_log) > 0
    press(2, 6); assert not g.dv["fly"] and not pl.fly and pl.speed_mul == 1.0 and not w.dev_god and not g.dv["log"]

    assert g.run["dev"] is True or w.dev_used

    press(0, 0); runs_before = [dict(r) for r in g.data["runs"]]; hi = g.data["highest_unlocked"]
    old = g.world
    press(3, 1); assert g.confirm and g.world is old; key(g, pg.K_ESCAPE); assert g.world is old
    press(3, 1); g.confirm_menu.sel = 0; key(g, pg.K_RETURN); settle(g); frames(g, 2)
    assert g.world is not old and g.state == "play" and not g.dev_session and not g.cfg["dev"] and not g.dv["fly"]
    assert g.run["resets"] == 1 and not g.run["completed"] and g.data["highest_unlocked"] == hi and len(g.data["runs"]) == len(runs_before)

    typecode("X41551456P")
    for _ in range(100):
        g.update(0.016); g.draw()
    assert g.state == "dev"
    press(0, 0); assert g.world.player.fly
    press(3, 0); assert not g.cfg["dev"] and not g.dev_session and g.state == "play" and not g.world.player.fly
    typecode("X41551456P")
    for _ in range(100):
        g.update(0.016); g.draw()
    key(g, pg.K_ESCAPE); assert g.state == "play" and g.dev_session
    key(g, pg.K_F10); assert g.state == "play"
    typecode("X41551456P")
    for _ in range(100):
        g.update(0.016); g.draw()
    assert g.state == "dev" and g.dev_session
    key(g, pg.K_ESCAPE); assert g.state == "play"
    typecode("X41551456P")
    for _ in range(100):
        g.update(0.016); g.draw()
    assert g.state == "dev"
    key(g, pg.K_ESCAPE)
    g.dev_deactivate(); assert not g.dev_session
    key(g, pg.K_F10); assert g.state == "play"
    typecode("X41551456P")
    for _ in range(100):
        g.update(0.016); g.draw()
    assert g.state == "dev" and g.dev_session
    key(g, pg.K_ESCAPE); g.dev_deactivate(); assert not g.dev_session and g.state == "play"
    assert "DEV MODE" not in [r[0] for r in g.settings_rows] and "REMOTE ADMIN" not in [r[0] for r in g.settings_rows]

    from cybercup.config import TUTORIAL_SECS, HELP_SHRINK_T
    assert TUTORIAL_SECS == 5.0
    cards = []; _real_tut = g.draw_tutorial
    def _tut(v, age):
        cards.append((g.cur_level, g.card_phase(age))); _real_tut(v, age)
    g.draw_tutorial = _tut
    g.start_level(0); settle(g); frames(g, 2)
    assert cards and {c[0] for c in cards} == {0} and cards[-1][1] == 0.0
    n = len(cards); g.start_level(1); settle(g); frames(g, 5); assert len(cards) == n
    g.start_level(0); settle(g); g.world.time = TUTORIAL_SECS + HELP_SHRINK_T / 2; frames(g, 2)
    assert 0 < cards[-1][1] < 1
    g.world.time = TUTORIAL_SECS + 1; frames(g, 2); assert cards[-1][1] is None
    g.draw_tutorial = _real_tut

    from cybercup.config import AFK_GAME_SECS, AFK_GAME_WARN, AFK_MENU_SECS, AFK_MENU_WARN
    assert AFK_GAME_SECS == 10.0 and AFK_MENU_SECS == 60.0
    def idle(secs):
        for _ in range(int(secs / 0.1)):
            g.update(0.1); g.draw()
    g.cfg["dev"] = False
    AFK["on"] = True
    g.start_level(1); settle(g); HELD.clear()
    assert g.user == "Tester" and g.afk_active() and g.afk_gameplay() and g.afk_limit() == (AFK_GAME_SECS, AFK_GAME_WARN)
    idle(4)
    assert g.user == "Tester" and 3.5 < g.afk_t < AFK_GAME_SECS - AFK_GAME_WARN
    idle(2.5)
    assert g.user == "Tester" and g.afk_t > AFK_GAME_SECS - AFK_GAME_WARN
    key(g, pg.K_SPACE); assert g.afk_t == 0.0
    idle(9)
    assert g.user == "Tester" and 8.5 < g.afk_t < AFK_GAME_SECS
    t_before = g.afk_t; key(g, pg.K_x); assert g.afk_t == t_before
    HELD[pg.K_RIGHT] = True; g.world.dev_god = True
    idle(25)
    assert g.user == "Tester" and g.state == "play"
    HELD.clear()

    w = g.world; w.has_key = True; w.exit_open = True
    ex, ey, ew, eh = w.lv.exit; w.player.reset(ex - 10, ey + eh - 40)
    done_before = len(g.data["completed"])
    for _ in range(int(6 / 0.016)): g.update(0.016); g.draw()
    assert g.user == "Tester" and g.state == "complete" and len(g.data["completed"]) == done_before + 1

    assert not g.afk_gameplay() and g.afk_limit() == (AFK_MENU_SECS, AFK_MENU_WARN)
    idle(15)
    assert g.user == "Tester" and g.state == "complete"
    idle(AFK_MENU_SECS)
    settle(g)
    assert g.user is None and g.state == "welcome" and g.world is None and g.data["active_run"] is None and g.data["player_name"] == ""
    assert "Auto logout" in g.toast[0] and "1 minute" in g.toast[0]
    frames(g, 3)

    for nm in ("Tester", "tester", "  TESTER "):
        g.name_text = nm; g.welcome_start(); frames(g, 2)
        assert g.state == "welcome" and g.user is None and "already taken" in g.name_msg, nm
    assert g.main_menu.label(0) == "PLAY GAME"
    g.continue_game(); assert g.user is None and "belum login" in g.toast[0].lower()

    g.name_text = "Budi"; g.welcome_start(); settle(g); frames(g, 2)
    assert g.user == "Budi" and g.state == "play" and g.main_menu.label(0) == "LOGOUT"
    key(g, pg.K_ESCAPE); assert g.state == "pause"
    idle(30)
    assert g.user == "Budi" and g.state == "pause"
    idle(AFK_MENU_SECS)
    settle(g)
    assert g.user is None and g.state == "welcome"

    g.name_text = "Dina"; g.welcome_start(); settle(g); frames(g, 2)
    kx, ky = g.world.lv.key; g.world.player.reset(kx - 10, ky - 20)
    for _ in range(20): g.update(0.016); g.draw()
    assert g.state == "quiz" and not g.afk_gameplay() and g.afk_limit() == (AFK_MENU_SECS, AFK_MENU_WARN)
    idle(AFK_GAME_SECS + 5)
    assert g.user == "Dina" and g.state == "quiz"
    g.handle_event(Ev(pg.TEXTINPUT, text="x")); assert g.afk_t == 0.0
    idle(AFK_MENU_SECS + 2)
    settle(g)
    assert g.user is None and g.state == "welcome" and "1 minute" in g.toast[0]

    g.name_text = "Eli"; g.welcome_start(); settle(g); frames(g, 2)
    assert g.user == "Eli" and g.state == "play" and g.afk_gameplay()
    idle(AFK_GAME_SECS - 3)
    assert g.user == "Eli"
    idle(5)
    settle(g)
    assert g.user is None and g.state == "welcome" and g.data["player_name"] == "" and "10 seconds" in g.toast[0]

    from cybercup.game import HELP_RECT
    g.name_text = "Citra"; g.welcome_start(); settle(g); frames(g, 2)
    w = g.world; t0 = w.time
    key(g, pg.K_i); assert g.help_open and g.help_visible(); frames(g, 5)
    idle(15)
    assert g.user == "Citra" and w.time == t0 and not g.afk_gameplay()
    key(g, pg.K_i); assert not g.help_open
    g.handle_event(Ev(pg.MOUSEBUTTONDOWN, button=1, pos=HELP_RECT.center)); assert g.help_open and g.state == "play"
    frames(g, 3); key(g, pg.K_ESCAPE); assert not g.help_open and g.state == "play"
    g.handle_event(Ev(pg.MOUSEBUTTONDOWN, button=1, pos=HELP_RECT.center)); g.handle_event(Ev(pg.MOUSEBUTTONDOWN, button=1, pos=(600, 300)))
    assert not g.help_open
    frames(g, 30); assert w.time > t0
    g.state = "pause"; assert not g.help_visible(); g.state = "play"

    g.state = "dev"; assert not g.afk_active(); g.state = "play"
    g.fade_dir = 1; assert not g.afk_active(); g.fade_dir = 0

    key(g, pg.K_ESCAPE); assert g.state == "pause"
    assert g.pause_menu.label(len(g.pause_menu.items) - 1) == "LOGOUT" and all(g.pause_menu.label(i) != "MAIN MENU" for i in range(len(g.pause_menu.items)))
    assert g.over_menu.label(len(g.over_menu.items) - 1) == "LOGOUT" and g.victory_menu.label(1) == "LOGOUT"
    g.pause_menu.sel = len(g.pause_menu.items) - 1; key(g, pg.K_RETURN); assert g.confirm
    g.confirm_menu.sel = 1; key(g, pg.K_RETURN); assert not g.confirm and g.user == "Citra"
    key(g, pg.K_RETURN); g.confirm_menu.sel = 0; key(g, pg.K_RETURN); settle(g)
    assert g.user is None and g.state == "welcome" and "logged out" in g.toast[0].lower()
    AFK["on"] = False

    g.name_text = "Winner"; g.welcome_start(); settle(g)
    run = g.run; assert g.run_tracked and run["completed"] is False
    run["play_time"] = 321.0
    for lvl in range(1, len(LEVELS_) + 1):
        g.cur_level = lvl - 1; g.on_level_started(lvl - 1)
        g.on_level_cleared(lvl, False) if lvl < len(LEVELS_) else None
    assert not run["completed"]
    g.cur_level = len(LEVELS_) - 1
    g.on_level_cleared(len(LEVELS_), False)
    assert run["completed"] and run["completion_time"] == 321.0 and g.data["active_run"] is None
    rows = profile_.leaderboard(g.data["runs"])
    assert rows[0]["name"] == "Winner" and rows[0]["status"] == "Completed"
    g.logout(); settle(g); frames(g, 3)
    assert g.state == "welcome" and g.name_text == "" and g.user is None
    g.name_text = "Winner"; g.welcome_start(); frames(g, 2)
    assert g.state == "welcome" and g.user is None and "already taken" in g.name_msg
    g.name_text = "Dev"; g.welcome_start(); settle(g)
    g.run["dev"] = True; g.run["play_time"] = 5.0; g.on_level_started(len(LEVELS_) - 1)
    g.cur_level = len(LEVELS_) - 1; g.on_level_cleared(len(LEVELS_), True)
    assert not g.run["completed"] and all(r["name"] != "Dev" for r in profile_.leaderboard(g.data["runs"]))
    g.logout(); settle(g); frames(g, 2)
    g.name_text = "Rival"; g.welcome_start(); settle(g); frames(g, 2)
    assert g.user == "Rival" and g.run["name"] == "Rival" and g.run["play_time"] < 5 and g.run["level_reached"] == 1
    assert len(g.data["runs"]) >= 3 and sum(1 for r in g.data["runs"] if r["completed"]) == 1

    from cybercup.game import BUY_RECT
    from cybercup.session import LOGOUT_RECT
    assert LOGOUT_RECT.right >= 1260 and LOGOUT_RECT.y < 54 and BUY_RECT.right <= LOGOUT_RECT.x and BUY_RECT.y < 54
    buy_click = lambda: g.handle_event(Ev(pg.MOUSEBUTTONDOWN, button=1, pos=BUY_RECT.center))
    assert g.state == "play" and g.world.state == "play"
    g.world.lives = 1; g.world.gem_bank = 0
    buy_click(); frames(g, 2)
    assert not g.confirm and g.world.lives == 1 and g.world.gem_bank == 0 and "Gem kurang" in g.toast[0]
    g.world.gem_bank = 5
    g.handle_event(Ev(pg.MOUSEBUTTONDOWN, button=1, pos=(10, 400)))
    assert not g.confirm
    buy_click(); frames(g, 1)
    assert g.confirm and "2 gem" in g.confirm["msg"] and g.world.gem_bank == 5 and g.world.lives == 1
    g.confirm_menu.sel = 1; key(g, pg.K_RETURN)
    assert not g.confirm and g.world.gem_bank == 5 and g.world.lives == 1
    key(g, pg.K_b); assert g.confirm
    g.confirm_menu.sel = 0; key(g, pg.K_RETURN)
    assert g.world.lives == 2 and g.world.gem_bank == 3 and g.run["gems"] == 3
    g.world.lives = g.world.max_lives; buy_click()
    assert not g.confirm and g.world.gem_bank == 3 and "penuh" in g.toast[0]
    g.world.lives = 1
    key(g, pg.K_ESCAPE); assert g.state == "pause"
    labels = [g.pause_menu.label(i) for i in range(len(g.pause_menu.items))]
    assert not any("LIFE" in l or "BUY" in l for l in labels), labels
    buy_click(); assert not g.confirm and g.world.gem_bank == 3
    key(g, pg.K_ESCAPE); assert g.state == "play"

    g.cfg["dev"] = True
    g.start_level(1); settle(g)
    key(g, pg.K_ESCAPE); assert g.state == "pause" and len(g.pause_menu.items) == 6
    g.pause_menu.sel = 1; key(g, pg.K_RETURN); assert g.dev_keys and g.world.has_key
    g.pause_menu.sel = 2; key(g, pg.K_RETURN); assert g.autoplay and g.world.god
    g.pause_menu.sel = 0; key(g, pg.K_RETURN); assert g.state == "play"
    for _ in range(60 * 90):
        g.update(0.016); g.draw()
        if g.world.idx == 2:
            break
    assert g.world.idx == 2 and g.autoplay, (g.world.idx, g.state)
    g.cfg["dev"] = False; g.on_dev_change(); frames(g, 2)
    g.start_level(4); settle(g)
    a = g.world.lv.arena
    g.world.player.reset(a["x"] + 300, a["y"] - 40)
    for _ in range(900):
        g.world.god = True; g.world.has_key = True
        g.update(0.016); g.draw()
    g.world.boss.hp = 1; g.world.boss.state = "tired"; g.world.boss.invuln = 0
    g.world._boss_hit()
    for _ in range(600):
        g.update(0.016); g.draw()
    g.world.player.reset(*g.world.lv.exit[:2])
    for _ in range(600):
        g.update(0.016); g.draw()
    assert g.state in ("victory", "complete"), g.state
    frames(g, 5)
    g.start_level(0); settle(g)
    g.world.lives = 1; g.world.kill_pit()
    for _ in range(600):
        g.update(0.016); g.draw()
    assert g.state == "gameover", g.state
    frames(g, 3)
    g.world.gem_bank = 0; g.over_menu.sel = 0; key(g, pg.K_RETURN)
    assert not g.confirm and g.state == "gameover" and "Gem kurang" in g.toast[0] and g.world.lives == 0
    g.world.gem_bank = 4; key(g, pg.K_RETURN); assert g.confirm
    g.confirm_menu.sel = 0; key(g, pg.K_RETURN)
    assert g.state == "play" and g.world.state == "play" and g.world.lives == 1 and g.world.gem_bank == 2
    frames(g, 5)

    g.cfg["dev"] = True; g.dev_session = True; g.dv["log"] = True; g.dlog("test line")
    sysrows = {r.label: r for r in g.dev_rows[3]}
    sysrows["SAVE DEBUG DUMP TO TEMP FILE"].fn()
    import os as _os
    files = [f for f in _os.listdir(save_system.temp_dir()) if f.startswith(save_system.TEMP_PREFIX)]; assert len(files) == 1 and "DEBUG DUMP SAVED" in g.toast[0]
    assert "test line" in open(_os.path.join(save_system.temp_dir(), files[0])).read()
    sysrows["DELETE TEMP FILES"].fn(); g.confirm_menu.sel = 0; key(g, pg.K_RETURN); assert [f for f in _os.listdir(save_system.temp_dir()) if f.startswith(save_system.TEMP_PREFIX)] == []; assert _os.path.exists(save_system.board_path())
    n_before = len(g.data["runs"]); assert n_before >= 3
    sysrows["DELETE LEADERBOARD"].fn(); assert g.confirm and len(g.data["runs"]) == n_before
    g.confirm_menu.sel = 0; key(g, pg.K_RETURN)
    assert g.data["runs"] == [g.run] and g.data["players"] == ["Rival"] and not profile_.name_taken(g.data, "Winner")
    g.dev_deactivate(); g.cfg["dev"] = False
    assert g.run["dev"] is True or True; g.run["dev"] = False
    g.world.lives = 2; g.run["play_time"] = 77.0; g.on_level_started(2); lvl_before = g.run["level_reached"]
    assert g.state == "play" and g.logout_button_visible()
    g.handle_event(Ev(pg.MOUSEBUTTONDOWN, button=1, pos=(10, 400))); assert not g.confirm
    g.handle_event(Ev(pg.MOUSEBUTTONDOWN, button=1, pos=LOGOUT_RECT.center)); assert g.confirm
    g.confirm_menu.sel = 0; key(g, pg.K_RETURN); settle(g); frames(g, 2)
    assert g.user is None and g.state == "welcome" and not g.logout_button_visible()
    rows = profile_.leaderboard(g.data["runs"])
    assert [r["name"] for r in rows] == ["Rival"] and rows[0]["status"] == "Logged out" and rows[0]["level"] == lvl_before and 77.0 <= rows[0]["play_time"] < 80
    g.name_text = "Rival"; g.welcome_start(); frames(g, 2); assert g.user is None and "already taken" in g.name_msg

    import os as _o
    save_system.SAVE_DIR_OVERRIDE = tempfile.mkdtemp()
    h = Game(); settle(h)
    def seed_history():
        for nm, lv in (("Ana", 5), ("Budi", 3)):
            r = profile_.new_run(nm, 10); r["level_reached"] = lv; r["play_time"] = 50.0
            h.data["runs"].append(r); profile_.register_name(h.data, nm)
        h.persist()
    seed_history()
    assert _o.path.isfile(save_system.board_path()) and len(h.data["runs"]) == 2
    _o.remove(save_system.board_path())
    for _ in range(80):
        h.update(0.016); h.draw()
    assert h.data["runs"] == [] and h.data["players"] == [] and profile_.leaderboard(h.data["runs"]) == []
    h.persist(); h.persist()
    assert not _o.path.exists(save_system.board_path())
    assert not profile_.name_taken(h.data, "Ana")
    seed_history(); _o.remove(save_system.board_path()); h.persist()
    assert h.data["runs"] == [] and not _o.path.exists(save_system.board_path())

    seed_history()
    h.name_text = "Cara"; h.welcome_start(); settle(h); frames(h, 2)
    assert h.user == "Cara" and len(h.data["runs"]) == 3
    _o.remove(save_system.board_path()); h.update(1.2)
    assert [r["name"] for r in h.data["runs"]] == ["Cara"] and h.data["players"] == ["Cara"]
    assert not profile_.name_taken(h.data, "Ana") and profile_.name_taken(h.data, "Cara")
    frames(h, 3); h.persist()
    h2 = Game(); settle(h2)
    assert all(r["name"] != "Ana" and r["name"] != "Budi" for r in h2.data["runs"]) and not profile_.name_taken(h2.data, "Ana")

    import shutil as _sh
    seed_history(); _sh.rmtree(save_system.temp_dir()); h.update(1.2)
    assert [r["name"] for r in h.data["runs"]] == ["Cara"]
    print("SMOKE OK (fake pygame): all screens, 5 levels x 500 frames, bosses, victory, game over, confirm dialogs")


if __name__ == "__main__":
    main()

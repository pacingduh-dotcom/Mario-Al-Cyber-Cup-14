import os, sys, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["CYBERCUP_NO_BUG"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pygame
from cybercup import save_system
save_system.SAVE_DIR_OVERRIDE = tempfile.mkdtemp()
from cybercup.game import Game

g = Game()
def frames(n):
    for _ in range(n):
        g.update(1 / 60); g.draw()
frames(30)
assert g.state == "menu"
assert g.cfg["fullscreen"] is True and [g.main_menu.label(i) for i in range(len(g.main_menu.items))] == ["PLAY GAME", "CARA BERMAIN", "CREDITS", "EXIT GAME"]
for _ in range(2):
    g.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, unicode=""))
    frames(3)
assert g.cfg["fullscreen"] is True
g.main_menu.items[0][1](); frames(40)
assert g.state == "welcome"
ev = lambda t, **k: pygame.event.Event(t, **k)
g.handle_event(ev(pygame.TEXTINPUT, text="Radit")); g.handle_event(ev(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
frames(90)
assert g.state == "play" and g.data["player_name"] == "Radit" and g.run_tracked

for ch in "X41551456P":
    g.handle_event(ev(pygame.KEYDOWN, key=ord(ch.lower()), unicode=ch))
assert g.dev_trans is not None
blank_seen = False
for _ in range(200):
    g.update(1 / 60); g.draw()
    if g.dev_trans and g.dev_trans["t"] > 0.4:
        px = [g.view.get_at((x, y))[:3] for x in range(0, 1280, 160) for y in range(0, 720, 120)]
        assert all(c == (0, 0, 0) for c in px), "transition frame is not blank"
        blank_seen = True
assert blank_seen and g.state == "dev" and g.dev_session
g.dev_deactivate(); frames(10)
assert g.state == "play" and not g.dev_session
for st in ("levels", "settings", "howto", "credits", "menu"):
    g.go(st); frames(40)
for lvl in range(10):
    g.data["highest_unlocked"] = 10
    g.pick_level(lvl); frames(40)
    g.edge["jump"] = True
    frames(240)
g.state = "pause"; frames(5)


import time as _t
g2 = Game()
assert callable(g2.main_loop) and isinstance(g2.run, dict)
_t0 = _t.time()
_orig = g2.update
def _upd(dt):
    _orig(dt)
    if _t.time() - _t0 > 1.0:
        g2.running = False
g2.update = _upd
g2.main_loop()
print("MAIN LOOP OK")
print("REAL PYGAME SMOKE OK, audio enabled:", g.audio.ok)

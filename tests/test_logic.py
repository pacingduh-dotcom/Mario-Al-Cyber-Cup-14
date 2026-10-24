import sys, os, json, tempfile
os.environ["CYBERCUP_NO_BUG"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cybercup.world import World
from cybercup.levels import LEVELS, build_level
from cybercup import save_system as ss
from cybercup.physics import MAX_JUMP_DISTANCE, MAX_JUMP_HEIGHT, Player, Solid

DT = 1 / 120


from cybercup.autoplay import AutoPilot


def run_bot(idx, limit=240.0):
    w = World(idx, "Normal", god=True)
    w.has_key = True
    pilot = AutoPilot()
    while w.t < limit:
        w.update(DT, pilot.step(w, DT))
        if w.state == "complete":
            return True, w
        if w.arena_locked:
            return True, w
        if w.state == "gameover":
            break
    return False, w


def test_gaps_within_jump_limits():
    for i in range(5):
        L = build_level(i)
        ground = sorted([s for s in L.solids if s.kind in ("normal", "ice", "conveyor") and s.h > 100], key=lambda s: s.x)
        for a, b in zip(ground, ground[1:]):
            gap = b.x - (a.x + a.w)
            bridged = any(s.kind in ("moving", "collapsing", "vanishing") and a.x + a.w - 1 <= s.x + s.w and s.x <= b.x + 1
                          for s in L.solids)
            if gap > MAX_JUMP_DISTANCE * 0.7:
                assert bridged, (i, gap)
            assert a.y - b.y <= 96 <= MAX_JUMP_HEIGHT * 0.75 + 96, (i, a.y - b.y)


def test_every_level_reachable_by_bot():
    for i in range(5):
        ok, w = run_bot(i)
        assert ok, f"level {i+1}: bot stalled at x={w.player.x:.0f} of {w.lv.width}"


def test_exit_reached_non_boss_levels():
    for i in (0, 1, 2):
        ok, w = run_bot(i)
        assert w.state == "complete", f"level {i+1} exit not reached (x={w.player.x:.0f})"
        assert w.summary["score"] > 0


def test_boss_can_be_defeated_and_exit_opens():
    for i in (3, 4):
        w = World(i, "Normal", god=True)
        w.has_key = True
        a = w.lv.arena
        w.player.reset(a["x"] + 200, a["y"] - 40)
        for _ in range(30):
            w.update(DT, {})
        assert w.boss is not None and w.arena_locked
        n = 0
        while w.boss.alive and n < 120 * 400:
            b = w.boss
            if b.vulnerable:
                w._boss_hit()
            w.update(DT, {})
            n += 1
        assert not w.boss.alive, f"level {i+1} boss never died"
        for _ in range(120 * 3):
            w.update(DT, {})
        assert w.exit_open


def test_quiz_answers_and_subjects():
    from cybercup import quiz
    assert len(quiz.QUIZ) == 5
    for a, b in zip(quiz.QUIZ, quiz.QUIZ[1:]):
        assert a[0] != b[0], (a[0], b[0])
    good = ["38 cm", "Jantung", "Produksi", "Antagonis", "Musyawarah"]
    for i, g in enumerate(good):
        assert quiz.check(i, g), (i, g)
        assert not quiz.check(i, "xyz") and not quiz.check(i, "")
    assert not quiz.check(1, "38") and quiz.hint(0).startswith("Petunjuk") and quiz.tip(0).startswith("Tips:")


def test_key_gates_the_exit():
    for i in range(5):
        w = World(i, "Normal", god=True)
        assert not w.has_key and not w.exit_open
        kx, ky = w.lv.key
        floor = w.lv.key_plat
        stone2 = [s for s in w.solids if s.kind == "normal" and s.h < 100 and abs(s.y - (floor[1] - 180)) < 1 and s.x <= kx <= s.x + s.w]
        stone1 = [s for s in w.solids if s.kind == "normal" and s.h < 100 and abs(s.y - (floor[1] - 90)) < 1]
        assert stone2 and stone1, i
        assert ky < floor[1] - 200
        assert (stone2[0].x - (stone1[0].x + stone1[0].w)) < 154 and 90 <= 96
    w = World(0, "Normal", god=True)
    ex = w.lv.exit
    w.player.reset(ex[0], ex[1])
    for _ in range(60):
        w.update(DT, {})
    assert w.state == "play" and not w.exit_open
    kx, ky = w.lv.key
    w.player.reset(kx - 10, ky - 20)
    w.update(DT, {})
    assert w.quiz_request and not w.has_key
    w.has_key = True
    w.player.reset(ex[0], ex[1])
    for _ in range(30):
        w.update(DT, {})
    assert w.state == "complete"
    b = World(4, "Normal", god=True)
    a = b.lv.arena
    b.player.reset(a["x"] + 300, a["y"] - 40)
    for _ in range(60):
        b.update(DT, {})
    assert b.boss is None and not b.arena_locked
    b.has_key = True
    for _ in range(60):
        b.update(DT, {})
    assert b.arena_locked


def test_autopilot_beats_boss_levels():
    for i in (3, 4):
        w = World(i, "Normal", god=True)
        pilot = AutoPilot()
        while w.t < 400 and w.state != "complete":
            w.update(DT, pilot.step(w, DT))
        assert w.state == "complete", f"autopilot failed level {i+1} (x={w.player.x:.0f}, boss={w.boss and w.boss.hp})"


def _free_world(idx=0, **kw):
    w = World(idx, "Normal", **kw)
    for _ in range(60):
        w.update(DT, {})
    return w


def test_fly_and_noclip():
    w = _free_world()
    p = w.player
    p.fly = True
    y0 = p.y
    for _ in range(60):
        w.update(DT, dict(jump_held=True))
    assert p.y < y0 - 100
    y1 = p.y
    for _ in range(120):
        w.update(DT, {})
    y2 = p.y
    for _ in range(120):
        w.update(DT, {})
    assert p.y == y2 and y2 < y1 + 1
    for _ in range(300):
        w.update(DT, dict(down=True))
    assert p.on_ground
    p.noclip = True
    for _ in range(200):
        w.update(DT, dict(down=True))
    assert p.y > y0 + 40 and w.state == "play"
    p.fly = p.noclip = False


def test_noclip_passes_through_walls():
    w = _free_world()
    p = w.player
    w.solids.append(Solid(1000, 150, 40, 400, "normal"))
    p.fly = True
    p.x, p.y, p.vx, p.vy = 900.0, 300.0, 0.0, 0.0
    for _ in range(240):
        w.update(DT, dict(right=True))
    assert p.x + p.W <= 1000.5
    p.noclip = True
    for _ in range(240):
        w.update(DT, dict(right=True))
    assert p.x > 1040


def test_god_infinite_health_super_jump_speed():
    w = _free_world()
    w.dev_god = True
    h = w.hearts
    w.player.inv_t = 0
    w.damage(1)
    assert w.hearts == h and w.state == "play"
    w.kill_pit()
    assert w.state == "play" and w.lives == 3
    w.dev_god, w.inf_health = False, True
    w.player.inv_t = 0
    w.damage(1)
    w.update(DT, {})
    assert w.hearts == w.max_hearts and w.state == "play" and w.player.hurt_t > 0
    w.inf_health = False

    def apex(mul):
        q = _free_world()
        q.player.jump_mul = mul
        top = q.player.y
        q.update(DT, dict(jump_pressed=True, jump_held=True))
        for _ in range(240):
            q.update(DT, dict(jump_held=True))
            top = min(top, q.player.y)
        return top
    base = _free_world().player.y
    assert base - apex(2.0) > 2.5 * (base - apex(1.0))

    def dist(mul):
        q = _free_world()
        q.player.speed_mul = mul
        x0 = q.player.x
        for _ in range(60):
            q.update(DT, dict(right=True))
        return q.player.x - x0
    assert dist(2.0) > 1.6 * dist(1.0)


def test_monster_tools():
    w = _free_world(1)
    n = w.monsters_alive()
    assert n > 0
    w.freeze_ai = True
    before = [(e.x, e.y) for e in w.enemies]
    for _ in range(120):
        w.update(DT, {})
    assert [(e.x, e.y) for e in w.enemies] == before
    w.freeze_ai = False
    for _ in range(120):
        w.update(DT, {})
    assert [(e.x, e.y) for e in w.enemies] != before
    killed, boss, evs = w.kill_all_monsters()
    assert killed == n and not boss and w.monsters_alive() == 0
    for _ in range(120):
        w.update(DT, {})
    assert w.enemies == []
    w.reset_monsters()
    assert w.monsters_alive() == n
    assert w.clear_monsters() == n and w.enemies == []
    w.no_spawn = True
    w.reset_monsters()
    assert w.enemies == [] and w.spawn_skipped
    w.no_spawn = False
    w.reset_monsters()
    assert w.monsters_alive() == n and not w.spawn_skipped
    assert World(1, "Normal", no_spawn=True).enemies == []


def test_boss_spawn_disable_kill_and_reset():
    w = World(4, "Normal")
    a = w.lv.arena
    w.has_key = True
    w.no_spawn = True
    w.player.reset(a["x"] + 300, a["y"] - 40)
    for _ in range(300):
        w.update(DT, {})
    assert w.boss is None and not w.arena_locked
    w.no_spawn = False
    for _ in range(300):
        w.update(DT, {})
    assert w.boss is not None and w.arena_locked
    w.dev_god = True
    w.boss.hp = 3
    w.reset_monsters()
    assert w.boss.hp == w.boss.max_hp and w.boss.phase == 0
    w.set_freeze(True)
    x0 = w.boss.x
    for _ in range(120):
        w.update(DT, {})
    assert w.boss.x == x0 and not w.shots
    w.set_freeze(False)
    killed, boss, evs = w.kill_all_monsters()
    assert boss and "boss_die" in evs and not w.boss.alive
    for _ in range(400):
        w.update(DT, {})
    assert w.exit_open


def test_teleport_targets_are_safe_on_every_level():
    for i in range(5):
        w = _free_world(i)
        w.dev_god = True
        names = []
        for name, x, y in w.teleport_targets():
            names.append(name)
            assert w.teleport(x, y), (i, name)
            assert w._free_at(w.player.x, w.player.y), (i, name, "inside a solid")
            for _ in range(240):
                w.update(DT, {})
            assert w.state == "play" and w.player.y < w.lv.pit_y - 40, (i, name, "fell")
        assert names[0] == "LEVEL START" and "EXIT GATE" in names and "KEY PLATFORM" in names
        w.state = "dead"
        assert not w.teleport(100, 100)
    w = _free_world()
    p = w.safe_position(300, w.solids[0].y + 5)
    assert w._free_at(*p)


def test_dev_code_detection_and_save_gating():
    from cybercup import devcode
    assert devcode.check_code("X41551456P")
    for bad in ("", "x41551456p", "X41551456", "X41551456P ", " X41551456P", "X41551456PP", "0000"):
        assert not devcode.check_code(bad), bad
    assert "X41551456P" not in open(devcode.__file__).read()
    D = devcode.CodeDetector
    d = D()
    assert [d.feed(c, i * 0.2) for i, c in enumerate("x41551456p")].count(True) == 1
    assert d.buf == ""
    d = D()
    assert not any(d.feed(c, i * 0.2) for i, c in enumerate("X41551456Q"))
    d = D()
    assert not any(d.feed(c, (0 if i < 5 else 10) + i * 0.2) for i, c in enumerate("X41551456P"))
    d = D()
    assert not d.feed("", 0) and not d.feed("ab", 0) and not d.feed(None, 0) and not d.feed("-", 0)
    d = D()
    assert [d.feed(c, i * 0.1) for i, c in enumerate("ZZX41551456P")].count(True) == 1
    with tempfile.TemporaryDirectory() as dd:
        ss.SAVE_DIR_OVERRIDE = dd
        try:
            with open(ss.save_path(), "w") as f:
                json.dump({"settings": {"dev": True, "dev_unlocked": True}}, f)
            st = ss.load()["settings"]
            assert st["dev"] is False and st["dev_unlocked"] is False
            with open(os.path.join(dd, "remote.json"), "w") as f:
                f.write("{}")
            ss.load()
            assert not os.path.exists(os.path.join(dd, "remote.json"))
            data = ss.default_save()
            ss.record_level(data, 2, 999, 10.0, 5, progress_only=True)
            assert 2 in data["completed"] and data["highest_unlocked"] == 3 and not data["best_score"] and data["total_coins"] == 0
        finally:
            ss.SAVE_DIR_OVERRIDE = None


def test_names_and_profile_persistence():
    from cybercup import profile
    assert profile.valid_name("  Ana Maria  ") == (True, "Ana Maria")
    assert profile.valid_name("A") == (True, "A") and profile.valid_name("x" * 16)[0]
    for bad in ("", "   ", "x" * 17, "a\x00b", "\t\n"):
        assert not profile.valid_name(bad)[0], bad
    with tempfile.TemporaryDirectory() as dd:
        ss.SAVE_DIR_OVERRIDE = dd
        try:
            data = ss.default_save()
            assert data["player_name"] == "" and data["runs"] == [] and data["active_run"] is None
            data["player_name"] = "Rina"
            r = profile.new_run("Rina", 10); r["play_time"] = 12.5; r["level_reached"] = 4
            data["runs"].append(r); data["active_run"] = r["id"]
            ss.save(data)
            back = ss.load()
            assert back["player_name"] == "Rina" and back["runs"][0]["level_reached"] == 4 and back["active_run"] == r["id"]
            forged = {"runs": [5, {"name": ""}, {"name": "ok", "id": "a", "completed": True,
                      "completion_time": 5, "level_reached": 3, "total": 10}], "players": ["ok", 7, ""]}
            with open(ss.board_path(), "w") as f:
                json.dump(forged, f)
            with open(ss.save_path(), "w") as f:
                json.dump({"player_name": "x" * 40, "active_run": "zz"}, f)
            d2 = ss.load()
            assert d2["player_name"] == "" and len(d2["runs"]) == 1 and d2["runs"][0]["completed"] is False
            assert d2["active_run"] is None
            os.remove(ss.board_path())
            with open(ss.save_path(), "w") as f:
                json.dump({"player_name": "x" * 40, "runs": forged["runs"], "players": ["ok"]}, f)
            d3 = ss.load()
            assert d3["runs"] == [] and d3["players"] == []
            with open(ss.save_path(), "w") as f:
                f.write("{not json")
            assert ss.load()["player_name"] == ""
        finally:
            ss.SAVE_DIR_OVERRIDE = None


def test_unique_names_registry():
    from cybercup import profile
    with tempfile.TemporaryDirectory() as dd:
        ss.SAVE_DIR_OVERRIDE = dd
        try:
            data = ss.default_save()
            assert data["players"] == [] and not profile.name_taken(data, "Rina")
            profile.register_name(data, "Rina")
            for same in ("Rina", "rina", "RINA", "  rina "):
                assert profile.name_taken(data, same), same
            assert not profile.name_taken(data, "Rina2")
            r = profile.new_run("Budi", 10); data["runs"].append(r)
            assert profile.name_taken(data, "budi")
            ss.save(data)
            back = ss.load()
            assert profile.name_taken(back, "RINA") and profile.name_taken(back, "Budi")
            os.remove(ss.board_path())
            with open(ss.save_path(), "w") as f:
                json.dump({"player_name": "Lama", "runs": [{"name": "Ok", "id": "a", "total": 10}], "players": ["Lama"]}, f)
            old = ss.load()
            assert not profile.name_taken(old, "lama") and not profile.name_taken(old, "ok") and not profile.name_taken(old, "rina")
        finally:
            ss.SAVE_DIR_OVERRIDE = None


def _run(name, level, play, done=False, dev=False, ct=None, total=10):
    from cybercup import profile
    r = profile.new_run(name, total)
    r.update(level_reached=level, play_time=play, completed=done, completion_time=ct, dev=dev)
    return r


def test_leaderboard_ranking_rules():
    from cybercup import profile
    runs = [_run("slow", 10, 900, True, ct=900), _run("fast", 10, 300, True, ct=300), _run("mid", 10, 600, True, ct=600),
            _run("L7", 7, 400), _run("L7b", 7, 200), _run("L3", 3, 50), _run("cheat", 10, 10, True, dev=True, ct=10),
            _run("idle", 5, 0.0), _run("L7b", 6, 100)]
    rows = profile.leaderboard(runs, 10)
    assert [r["name"] for r in rows] == ["fast", "mid", "slow", "L7b", "L7", "idle", "L3"]
    ended = _run("gone", 4, 30.0); ended["ended"] = "logout"
    assert [r for r in profile.leaderboard([ended]) if r["name"] == "gone"][0]["status"] == "Logged out"
    assert rows[3]["level"] == 7 and [r["rank"] for r in rows] == [1, 2, 3, 4, 5, 6, 7]
    assert rows[0]["status"] == "Completed" and rows[3]["status"] == "In progress" and rows[0]["completion_time"] == 300
    assert rows[3]["completion_time"] is None
    assert profile.leaderboard([], 10) == []
    runs2 = [_run("a", 5, 100), _run("b", 5, 100)]
    assert [r["name"] for r in profile.leaderboard(runs2)] == ["a", "b"]
    assert profile.fmt_time(522) == "08m 42s" and profile.fmt_time(632) == "10m 32s"
    assert profile.latest_run(runs, "L7B")["level_reached"] == 6


def test_boss_arena_gate_needs_key():
    for idx in (3, 4):
        w = World(idx, "Normal", god=True)
        a = w.lv.arena
        assert a is not None and w.lv.gate_wall in w.solids
        pilot, best = AutoPilot(), 0.0
        while w.t < 120 and w.state != "gameover":
            inp = pilot.step(w, DT)
            w.has_key = False
            w.update(DT, inp)
            best = max(best, w.player.x + w.player.W)
            assert not w.arena_locked and w.boss is None, idx
        assert best <= a["x"] + 1 and best > a["x"] - 400, (idx, best, a["x"])
        assert w.lv.gate_wall.active
        ok, w2 = run_bot(idx)
        assert ok and not w2.lv.gate_wall.active, idx
    w = World(0, "Normal")
    assert not hasattr(w.lv, "gate_wall") or w.lv.arena is None


def test_dev_temp_files_not_hardcoded():
    with tempfile.TemporaryDirectory() as dd, tempfile.TemporaryDirectory() as other:
        ss.SAVE_DIR_OVERRIDE = dd
        try:
            assert ss.temp_dir() == os.path.join(dd, "temp")
            p1 = ss.write_temp("a"); p2 = ss.write_temp("b")
            assert p1 and p2 and p1 != p2 and open(p1).read() == "a" and os.path.dirname(p1) == ss.temp_dir()
            os.environ["CYBERCUP_TEMP_DIR"] = other
            assert ss.temp_dir() == other
            mine = ss.write_temp("c"); stranger = os.path.join(other, "important.txt"); open(stranger, "w").write("keep")
            assert ss.clear_temp() == 1 and not os.path.exists(mine) and os.path.exists(stranger)
            del os.environ["CYBERCUP_TEMP_DIR"]
            assert ss.clear_temp() == 2
        finally:
            os.environ.pop("CYBERCUP_TEMP_DIR", None)
            ss.SAVE_DIR_OVERRIDE = None


def test_gem_currency_lives_and_revive():
    from cybercup.config import GEM_COST_LIFE, GEM_COST_REVIVE
    w = World(0, "Normal")
    assert w.max_lives == 3
    w.gem_bank = 5
    ok, msg = w.buy_life(GEM_COST_LIFE)
    assert not ok and w.lives == 3 and w.gem_bank == 5 and "penuh" in msg
    w.lives = 1
    ok, _ = w.buy_life(GEM_COST_LIFE)
    assert ok and w.lives == 2 and w.gem_bank == 5 - GEM_COST_LIFE
    w.gem_bank = GEM_COST_LIFE - 1
    ok, msg = w.buy_life(GEM_COST_LIFE)
    assert not ok and w.lives == 2 and w.gem_bank == GEM_COST_LIFE - 1 and "Gem kurang" in msg
    w.gem_bank = 1000
    for _ in range(10):
        w.buy_life(GEM_COST_LIFE)
    assert w.lives == w.max_lives and w.gem_bank >= 1000 - GEM_COST_LIFE * 2
    assert not w.revive(GEM_COST_REVIVE)[0]
    w.lives = 1; w.kill_pit()
    for _ in range(300):
        w.update(DT, {})
    assert w.state == "gameover"
    w.gem_bank = GEM_COST_REVIVE - 1
    ok, _ = w.revive(GEM_COST_REVIVE)
    assert not ok and w.state == "gameover" and w.gem_bank == GEM_COST_REVIVE - 1
    w.gem_bank = GEM_COST_REVIVE
    ok, _ = w.revive(GEM_COST_REVIVE)
    assert ok and w.state == "play" and w.lives == 1 and w.gem_bank == 0 and w.hearts == w.max_hearts
    assert not w.revive(GEM_COST_REVIVE)[0] and w.gem_bank == 0
    assert not w.spend_gems(1) and not w.spend_gems(0) and not w.spend_gems(-3)

    w2 = World(0, "Normal")
    gx, gy, _, key = w2.gems[0]
    w2.player.reset(gx - 13, gy - 20)
    w2.update(DT, {})
    assert w2.gem_bank == 1 and key in w2.gem_claimed
    w3 = World(0, "Normal", gem_bank=w2.gem_bank, gem_claimed=w2.gem_claimed)
    assert not w3.gems[0][2] and w3.gem_bank == 1 and w3.gem_count == 1


def test_exit_door_sequence_single_transition():
    w = World(0, "Normal", god=True)
    w.has_key = True
    ex, ey, ew, eh = w.lv.exit
    w.player.reset(ex - 10, ey + eh - 40)
    w.exit_open = True
    finished, openmax = 0, 0.0
    for _ in range(int(2.2 / DT)):
        was = w.state
        w.update(DT, dict(left=True, jump_pressed=True))
        finished += (was == "play" and w.state == "complete")
        openmax = max(openmax, w.door_open)
    assert w.state == "complete" and finished == 1 and openmax > 0.99
    assert abs(w.player.x + w.player.W / 2 - (ex + ew / 2)) < 2
    s1 = dict(w.summary)
    for _ in range(100):
        w.update(DT, {})
    assert w.summary == s1


def test_leaderboard_lives_in_temp_folder_next_to_the_game():
    import shutil
    from cybercup import profile

    ss.SAVE_DIR_OVERRIDE = None
    os.environ.pop("CYBERCUP_TEMP_DIR", None)
    assert ss.temp_dir() == os.path.join(ss.app_dir(), "temp") or ss.temp_dir().endswith(os.path.join("MarioAlCyberCup14", "temp"))
    assert os.path.isfile(os.path.join(ss.app_dir(), "main.py"))
    shutil.rmtree(os.path.join(ss.app_dir(), "temp"), ignore_errors=True)
    with tempfile.TemporaryDirectory() as dd:
        ss.SAVE_DIR_OVERRIDE = dd
        try:
            data = ss.default_save()
            r = profile.new_run("Rina", 10); r["play_time"] = 30.0; r["level_reached"] = 3
            data["runs"].append(r); profile.register_name(data, "Rina"); data["highest_unlocked"] = 4
            assert ss.save(data)
            assert os.path.isfile(ss.board_path()) and os.path.dirname(ss.board_path()) == ss.temp_dir()
            raw = json.load(open(ss.save_path()))
            assert "runs" not in raw and "players" not in raw and raw["highest_unlocked"] == 4
            back = ss.load()
            assert [x["name"] for x in back["runs"]] == ["Rina"] and back["players"] == ["Rina"]
            shutil.rmtree(ss.temp_dir())
            gone = ss.load()
            assert gone["runs"] == [] and gone["players"] == [] and gone["highest_unlocked"] == 4 and gone["active_run"] is None

            with open(ss.save_path(), "w") as f:
                json.dump({"highest_unlocked": 2, "runs": [r], "players": ["Rina"]}, f)
            old = ss.load()
            assert old["runs"] == [] and old["players"] == [] and old["highest_unlocked"] == 2
            ss.save(old)
            assert "runs" not in json.load(open(ss.save_path())) and not os.path.exists(ss.board_path())
            assert ss.load()["runs"] == []

            data2 = ss.default_save(); data2["runs"].append(r); profile.register_name(data2, "Rina"); ss.save(data2)
            assert ss.load()["runs"] and os.path.isfile(ss.board_path())
            os.remove(ss.board_path())
            assert ss.load()["runs"] == [] and ss.load()["players"] == []

            os.environ["CYBERCUP_TEMP_DIR"] = os.path.join(dd, "elsewhere")
            assert ss.temp_dir() == os.path.join(dd, "elsewhere")
        finally:
            os.environ.pop("CYBERCUP_TEMP_DIR", None)
            ss.SAVE_DIR_OVERRIDE = None
    assert not os.path.exists(os.path.join(ss.app_dir(), "temp"))


def test_afk_limits_game_10s_menu_1min():
    from cybercup.config import AFK_GAME_SECS, AFK_GAME_WARN, AFK_MENU_SECS, AFK_MENU_WARN
    from cybercup import session
    assert AFK_GAME_SECS == 10.0 and AFK_MENU_SECS == 60.0
    assert 0 < AFK_GAME_WARN < AFK_GAME_SECS and 0 < AFK_MENU_WARN < AFK_MENU_SECS
    assert session.afk_label(10) == "10 seconds" and session.afk_label(60) == "1 minute" and session.afk_label(120) == "2 minutes"


def test_boss_hit_window_is_hazard_free_and_wait_is_short():
    from cybercup import entities
    from cybercup.entities import Boss
    from cybercup.levels import LEVELS
    from cybercup.physics import Player
    for lvl in (3, 4):
        b = Boss(LEVELS[lvl]["boss"], dict(x=0, y=500, w=1100), 500, lvl, 1.0)
        p, shots = Player(300, 400), []
        t, prev, left, starts, waits, fired = 0.0, b.state, None, 0, [], 0
        for _ in range(int(60 / DT)):
            b.update(DT, p, shots)
            for s in shots:
                s.update(DT)
            shots[:] = [s for s in shots if s.life > 0]
            fired = max(fired, len(shots))
            if b.state == "tired":
                assert not any(getattr(s, "boss", False) for s in shots) and b.columns == [], (lvl, t)
            if b.state == "tired" and prev != "tired":
                starts += 1
                if left is not None:
                    waits.append(t - left)
            if prev == "tired" and b.state != "tired":
                left = t
            prev, t = b.state, t + DT
        assert starts >= 6 and fired > 0
        assert max(waits) <= 2.4, (lvl, max(waits))
        assert entities.BOSS_ATTACK_T >= entities.BOSS_COL_WARN + entities.BOSS_COL_ACTIVE
        assert entities.BOSS_SHOT_LIFE <= entities.BOSS_ATTACK_T


def test_boss_contact_is_harmless_while_core_glows():
    w = World(4, "Normal")
    w.has_key = True
    a = w.lv.arena
    w.player.reset(a["x"] + 200, a["y"] - 40)
    for _ in range(30):
        w.update(DT, {})
    b = w.boss
    n = 0
    while b.state != "tired" and n < 120 * 20:
        w.player.reset(a["x"] + 200, a["y"] - 40)
        w.player.inv_t = 99
        w.update(DT, {})
        n += 1
    assert b.state == "tired" and not any(getattr(s, "boss", False) for s in w.shots)
    w.player.reset(b.x + 4, b.y + b.h - w.player.H)
    w.player.inv_t, hearts = 0.0, w.hearts
    for _ in range(30):
        w.update(DT, {})
    assert w.hearts == hearts and w.state == "play"
    while b.state == "tired":
        w.player.reset(a["x"] + 200, a["y"] - 40); w.player.inv_t = 99
        w.update(DT, {})
    w.player.reset(b.x + 4, b.y + b.h - w.player.H); w.player.inv_t = 0.0
    for _ in range(10):
        w.update(DT, {})
    assert w.hearts < hearts or w.state != "play" or w.player.inv_t > 0


def test_damage_death_respawn_and_gameover():
    w = World(0, "Hard")
    w.respawn = (500, 500)
    for _ in range(2):
        w.player.inv_t = 0
        w.damage(1)
    assert w.state == "dead"
    for _ in range(300):
        w.update(DT, {})
    assert w.state == "play" and w.hearts == w.max_hearts and w.lives == 1
    w.kill_pit()
    for _ in range(300):
        w.update(DT, {})
    assert w.state == "gameover"


def test_no_damage_while_invulnerable_and_pit_kills():
    w = World(0)
    w.damage(1)
    h = w.hearts
    w.damage(1)
    assert w.hearts == h
    w.player.y = w.lv.pit_y + 10
    w.update(DT, {})
    assert w.state == "dead"


def test_jump_buffer_coyote_and_variable_height():
    solids = [Solid(0, 500, 400, 300)]
    p = Player(100, 460)
    for _ in range(10):
        p.update(DT, {}, solids)
    assert p.on_ground
    peak = 460
    p.update(DT, dict(jump_pressed=True, jump_held=True), solids)
    for _ in range(240):
        p.update(DT, dict(jump_held=True), solids)
        peak = min(peak, p.y)
    full = 460 - peak
    p = Player(100, 460)
    for _ in range(10):
        p.update(DT, {}, solids)
    peak = 460
    p.update(DT, dict(jump_pressed=True, jump_held=True), solids)
    for _ in range(240):
        p.update(DT, {}, solids)
        peak = min(peak, p.y)
    short = 460 - peak
    assert full > short + 20 and full > 100

    solids = [Solid(0, 500, 200, 300)]
    p = Player(190, 460)
    for _ in range(5):
        p.update(DT, {}, solids)
    p.x = 215
    p.update(DT, {}, solids)
    ev = p.update(DT, dict(jump_pressed=True, jump_held=True), solids)
    assert "jump" in ev


def test_save_system():
    from cybercup import save_system as ss
    with tempfile.TemporaryDirectory() as d:
        ss.SAVE_DIR_OVERRIDE = d
        data = ss.load()
        assert data["highest_unlocked"] == 1
        data["highest_unlocked"] = 4
        data["settings"]["music"] = 30
        ss.save(data)
        again = ss.load()
        assert again["highest_unlocked"] == 4 and again["settings"]["music"] == 30
        with open(ss.save_path(), "w") as f:
            f.write("{ corrupted")
        bad = ss.load()
        assert bad["highest_unlocked"] == 1
        with open(ss.save_path(), "w") as f:
            json.dump({"highest_unlocked": 99, "settings": {"music": "loud", "master": 500}}, f)
        odd = ss.load()
        assert odd["highest_unlocked"] == 5 and odd["settings"]["master"] == 100 and odd["settings"]["music"] == 70
        ss.record_level(odd, 3, 1234, 55.0, 12)
        assert odd["highest_unlocked"] == 5 and 3 in odd["completed"]
        ss.record_level(odd, 3, 10, 99.0, 1)
        assert odd["best_score"]["3"] == 1234
        fresh = ss.default_save()
        fresh["completed"] = []
        ss.record_level(fresh, 1, 500, 40.0, 5)
        assert fresh["highest_unlocked"] == 2


def test_quiz_is_fully_indonesian():
    from cybercup import quiz
    english = ("which", "what ", "what is", "the ", "how many", "is the", "of the")
    for subj, q, ans, acc, rules, tp in quiz.QUIZ:
        assert subj.isupper() and q.endswith("?") and ans and ans in acc or quiz.normalize(ans) in {quiz.normalize(a) for a in acc}
        low = q.lower()
        assert not any(w in low for w in ("which ", "what ", "how many", "the name", "what's")), q
    assert {s for s, *_ in quiz.QUIZ} >= {"MATEMATIKA", "IPA", "IPS", "BAHASA INDONESIA", "PPKN"}


def test_boss_age_drives_help_card():
    from cybercup.entities import Boss
    from cybercup.levels import LEVELS
    from cybercup.physics import Player
    spec = LEVELS[4]["boss"]
    b = Boss(spec, dict(x=0, y=500, w=1100), 500, 4, 1.0)
    assert b.age == 0.0
    p = Player(300, 400)
    for _ in range(120):
        b.update(1 / 120, p, [])
    assert abs(b.age - 1.0) < 1e-6


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("PASS", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)

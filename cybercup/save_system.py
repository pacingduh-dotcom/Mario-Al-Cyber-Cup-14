import json
import os
import sys
import copy

SAVE_DIR_OVERRIDE = None
try:
    from .levels import LEVELS
    NUM_LEVELS = len(LEVELS)
except Exception:
    NUM_LEVELS = 5
from . import profile

DEFAULT_SETTINGS = dict(master=80, music=70, sfx=80, fullscreen=True, vsync=False, fps=120,
                        difficulty="Normal", shake=True, particles=True, dev=False, dev_unlocked=False)
FPS_VALUES = (30, 60, 120, 144, 240, 0)
LIMITS = dict(master=(0, 100), music=(0, 100), sfx=(0, 100))


def save_dir():
    if SAVE_DIR_OVERRIDE:
        return SAVE_DIR_OVERRIDE
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "MarioAlCyberCup14")


TEMP_PREFIX, TEMP_SUFFIX = "cybercup-debug-", ".txt"
BOARD_FILE = "leaderboard.json"


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def temp_dir():
    env = os.environ.get("CYBERCUP_TEMP_DIR")
    if env:
        return env
    if SAVE_DIR_OVERRIDE:
        return os.path.join(SAVE_DIR_OVERRIDE, "temp")
    d = os.path.join(app_dir(), "temp")
    try:
        os.makedirs(d, exist_ok=True)
        if os.access(d, os.W_OK):
            return d
    except OSError:
        pass
    return os.path.join(save_dir(), "temp")


def board_path():
    return os.path.join(temp_dir(), BOARD_FILE)


def board_exists():
    return os.path.isfile(board_path())


def write_temp(content):
    import time
    try:
        os.makedirs(temp_dir(), exist_ok=True)
        path = os.path.join(temp_dir(), time.strftime(TEMP_PREFIX + "%Y%m%d-%H%M%S") + TEMP_SUFFIX)
        n = 1
        while os.path.exists(path):
            n += 1
            path = os.path.join(temp_dir(), time.strftime(TEMP_PREFIX + "%Y%m%d-%H%M%S") + f"-{n}" + TEMP_SUFFIX)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
    except OSError:
        return None


def clear_temp():
    n = 0
    try:
        for name in os.listdir(temp_dir()):
            if name.startswith(TEMP_PREFIX) and name.endswith(TEMP_SUFFIX):
                try:
                    os.remove(os.path.join(temp_dir(), name))
                    n += 1
                except OSError:
                    pass
    except OSError:
        pass
    return n


def save_path():
    return os.path.join(save_dir(), "save.json")


def default_save():
    return dict(version=4, highest_unlocked=1, player_name="", players=[], runs=[], active_run=None, completed=[], best_score={}, best_time={},
                total_coins=0, settings=copy.deepcopy(DEFAULT_SETTINGS))


def sanitize_board(raw_runs, raw_players, extra_names=()):
    runs = [r for r in (profile.sanitize_run(x, NUM_LEVELS) for x in raw_runs) if r] if isinstance(raw_runs, list) else []
    seen, uniq = set(), []
    for r in runs:
        if r["id"] not in seen:
            seen.add(r["id"])
            uniq.append(r)
    names, seen_n = [], set()
    cand = (list(raw_players) if isinstance(raw_players, list) else []) + [r["name"] for r in uniq] + list(extra_names)
    for n in cand:
        ok, v = profile.valid_name(n)
        if ok and profile.name_key(v) not in seen_n:
            seen_n.add(profile.name_key(v))
            names.append(v)
    return uniq, names[:5000]


def _sanitize(raw):
    d = default_save()
    if not isinstance(raw, dict):
        return d
    try:
        d["highest_unlocked"] = max(1, min(NUM_LEVELS, int(raw.get("highest_unlocked", 1))))
        d["completed"] = sorted({int(i) for i in raw.get("completed", []) if 1 <= int(i) <= NUM_LEVELS})
        d["best_score"] = {str(int(k)): int(v) for k, v in dict(raw.get("best_score", {})).items()}
        d["best_time"] = {str(int(k)): float(v) for k, v in dict(raw.get("best_time", {})).items()}
        d["total_coins"] = max(0, int(raw.get("total_coins", 0)))
    except (TypeError, ValueError):
        d = default_save()
    nm = profile.valid_name(raw.get("player_name", ""))
    d["player_name"] = nm[1] if nm[0] else ""
    d["runs"], d["players"] = [], []
    d["active_run"] = None
    st = raw.get("settings", {}) if isinstance(raw.get("settings"), dict) else {}
    try:
        old_version = int(raw.get("version", 1))
    except (TypeError, ValueError):
        old_version = 1
    if old_version < 4:
        d["version"] = 4
    else:
        d["version"] = old_version
    for k, default in DEFAULT_SETTINGS.items():
        v = st.get(k, default)
        if isinstance(default, bool):
            d["settings"][k] = v if isinstance(v, bool) else default
        elif k in LIMITS:
            try:
                lo, hi = LIMITS[k]
                d["settings"][k] = max(lo, min(hi, int(v)))
            except (TypeError, ValueError):
                d["settings"][k] = default
        elif k == "fps":
            d["settings"][k] = v if v in FPS_VALUES else default
        elif k == "difficulty":
            d["settings"][k] = v if v in ("Easy", "Normal", "Hard") else default
    # Difficulty is never persisted: every session starts at Normal (MEDIUM).
    d["settings"]["difficulty"] = DEFAULT_SETTINGS["difficulty"]

    d["settings"]["dev"] = d["settings"]["dev_unlocked"] = False
    if raw.get("version", 1) < 2 and st.get("fps", 60) == 60 and st.get("vsync", True) is True:
        d["settings"]["fps"], d["settings"]["vsync"] = DEFAULT_SETTINGS["fps"], DEFAULT_SETTINGS["vsync"]
    return d


def remove_legacy_remote_file():
    try:
        os.remove(os.path.join(save_dir(), "remote.json"))
    except OSError:
        pass


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def load():
    remove_legacy_remote_file()
    raw = _read_json(save_path())
    d = _sanitize(raw)
    board = _read_json(board_path())
    if isinstance(board, dict):
        d["runs"], d["players"] = sanitize_board(board.get("runs"), board.get("players"), [])
    act = raw.get("active_run") if isinstance(raw, dict) else None
    d["active_run"] = act if any(r["id"] == act and not r["completed"] for r in d["runs"]) else None
    profile.prune(d["runs"], d["active_run"])
    return d


def save(data):
    runs, players = data.get("runs", []), data.get("players", [])
    if runs or players or board_exists():
        _write_json(board_path(), dict(version=1, runs=runs, players=players))
    main = dict(data)
    main.pop("runs", None)
    main.pop("players", None)
    return _write_json(save_path(), main)


def record_level(data, level, score, time_s, coins, progress_only=False):
    if level not in data["completed"]:
        data["completed"] = sorted(data["completed"] + [level])
    if progress_only:
        data["highest_unlocked"] = max(data["highest_unlocked"], min(NUM_LEVELS, level + 1))
        return
    k = str(level)
    data["best_score"][k] = max(score, data["best_score"].get(k, 0))
    data["best_time"][k] = min(time_s, data["best_time"].get(k, 1e9))
    data["total_coins"] += coins
    data["highest_unlocked"] = max(data["highest_unlocked"], min(NUM_LEVELS, level + 1))

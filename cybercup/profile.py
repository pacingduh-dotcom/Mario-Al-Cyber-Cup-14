import time
import uuid

from .config import NAME_MAX, MAX_RUNS


def clean_name(s):
    return "".join(c for c in str(s) if c.isprintable()).strip()


def valid_name(s):
    raw = str(s)
    if any(not c.isprintable() for c in raw):
        return False, "Name contains invalid characters."
    n = raw.strip()
    if not n:
        return False, "Please enter a name."
    if len(n) > NAME_MAX:
        return False, f"Name must be at most {NAME_MAX} characters."
    return True, n


def name_key(s):
    return clean_name(s).casefold()


def name_taken(data, name):
    k = name_key(name)
    if any(name_key(p) == k for p in data.get("players", ())):
        return True
    return any(name_key(r.get("name", "")) == k for r in data.get("runs", ()))


def register_name(data, name):
    data.setdefault("players", []).append(name)


def fmt_time(sec):
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    return f"{m:02d}m {s:02d}s"


def new_run(name, total):
    return dict(id=uuid.uuid4().hex[:12], name=name, date=time.strftime("%Y-%m-%d"), total=int(total), play_time=0.0,
                level_reached=1, current_level=1, completed=False, completion_time=None, dev=False, resets=0,
                gems=0, gem_claimed=[], ended=None, difficulty="Normal")


def practice_run(total):
    r = new_run("", total)
    r["id"] = ""
    return r


def sanitize_run(raw, default_total):
    if not isinstance(raw, dict):
        return None
    try:
        name = clean_name(raw.get("name", ""))[:NAME_MAX]
        rid = str(raw.get("id", ""))[:32]
        if not name or not rid:
            return None
        total = max(1, min(999, int(raw.get("total", default_total))))
        play = float(raw.get("play_time", 0.0))
        play = play if 0.0 <= play < 1e7 else 0.0
        lvl = max(1, min(total, int(raw.get("level_reached", 1))))
        cur = max(1, min(total, int(raw.get("current_level", lvl))))
        ct = raw.get("completion_time")
        ct = float(ct) if ct is not None else None
        done = bool(raw.get("completed")) and ct is not None and 0.0 < ct < 1e7 and lvl >= total
        claimed = [str(x)[:16] for x in raw.get("gem_claimed", [])][:200] if isinstance(raw.get("gem_claimed"), list) else []
        return dict(id=rid, name=name, date=str(raw.get("date", ""))[:10], total=total, play_time=play,
                    level_reached=lvl, current_level=cur, completed=done, completion_time=ct if done else None,
                    dev=bool(raw.get("dev", False)), ended=raw.get("ended") if raw.get("ended") in ("logout", "afk") else None, resets=max(0, int(raw.get("resets", 0))),
                    gems=max(0, min(9999, int(raw.get("gems", 0)))), gem_claimed=[] if done else claimed,
                    difficulty=raw.get("difficulty") if raw.get("difficulty") in ("Easy", "Normal", "Hard") else "Normal")
    except (TypeError, ValueError):
        return None


def prune(runs, active_id=None):
    while len(runs) > MAX_RUNS:
        for i, r in enumerate(runs):
            if not r["completed"] and r["id"] != active_id:
                del runs[i]
                break
        else:
            del runs[0]


def rank_key(r):
    if r["completed"]:
        return (0, r["completion_time"], 0, r["play_time"], r["name"].lower())
    return (1, 0.0, -r["level_reached"], r["play_time"], r["name"].lower())


def leaderboard(runs, limit=10):
    best = {}
    for idx, r in enumerate(runs):
        if r.get("dev"):
            continue
        k = r["name"].lower()
        key = rank_key(r) + (idx,)
        if k not in best or key < best[k][0]:
            best[k] = (key, r)
    rows = [v for v in sorted(best.values(), key=lambda kv: kv[0])][:limit]
    return [dict(rank=i + 1, name=r["name"], status="Completed" if r["completed"] else ("Logged out" if r.get("ended") else "In progress"),
                 level=min(r["level_reached"], r["total"]), total=r["total"], play_time=r["play_time"],
                 completion_time=r["completion_time"], difficulty=r.get("difficulty", "Normal")) for i, (_, r) in enumerate(rows)]


def latest_run(runs, name):
    for r in reversed(runs):
        if r["name"].lower() == name.lower() and r["play_time"] > 0:
            return r
    return None

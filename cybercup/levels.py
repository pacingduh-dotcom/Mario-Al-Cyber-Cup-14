import random
from .physics import Solid, MAX_JUMP_DISTANCE

PIT_Y = 820
GROUND_H = 400
ARENA_W = 1100



LEVELS = [
 dict(name="CYBER GREENFIELDS", diff=1, style="hills", sky=((70,150,255),(190,235,255)),
      ground=(60,150,70), accent=(120,255,170), mood=0, length=4600, gap=(50,100), pw=(300,560),
      dy=32, kinds={}, enemies={"walker":1.0}, density=0.45, espeed=0.8, spikes=0.0, orbit=0.0,
      icicle=0.0, secrets=2, boss=None, tutorial=True, cps=3),
 dict(name="NEON PIPE DISTRICT", diff=2, style="city", sky=((20,10,60),(90,30,120)),
      ground=(50,50,90), accent=(255,60,200), mood=1, length=5000, gap=(70,120), pw=(260,480),
      dy=48, kinds={"moving":0.25}, enemies={"walker":0.7,"drone":0.3}, density=0.5, espeed=0.9,
      spikes=0.1, orbit=0.0, icicle=0.0, secrets=2, boss=None, cps=3),
 dict(name="PIXEL DESERT", diff=3, style="desert", sky=((255,170,90),(255,230,160)),
      ground=(200,160,90), accent=(255,220,90), mood=2, length=5400, gap=(80,130), pw=(220,420),
      dy=48, kinds={"collapsing":0.3,"moving":0.1}, enemies={"walker":0.4,"jumper":0.3,"drone":0.3},
      density=0.55, espeed=1.0, spikes=0.2, orbit=0.0, icicle=0.0, secrets=2, boss=None, cps=4),
 dict(name="CYBER FACTORY", diff=4, style="factory", sky=((30,30,40),(80,70,60)),
      ground=(90,90,100), accent=(255,190,40), mood=4, length=5800, gap=(80,140), pw=(220,400),
      dy=64, kinds={"conveyor":0.4,"moving":0.2}, enemies={"walker":0.2,"armored":0.3,"turret":0.3,"jumper":0.2},
      density=0.6, espeed=1.1, spikes=0.15, orbit=0.25, icicle=0.0, secrets=2,
      boss=dict(name="WARDEN MK-I", hp=5, phases=1, w=70, h=80), cps=4),
 dict(name="CYBER OVERLORD", diff=5, style="arena", sky=((10,0,30),(70,0,90)),
      ground=(35,25,80), accent=(255,40,160), mood=9, length=2600, gap=(110,150), pw=(240,360),
      dy=64, kinds={"moving":0.3,"vanishing":0.2}, enemies={"drone":0.4,"turret":0.3,"jumper":0.3},
      density=0.9, espeed=1.3, spikes=0.15, orbit=0.2, icicle=0.0, secrets=1,
      boss=dict(name="CYBER OVERLORD", hp=15, phases=3, w=100, h=110), cps=2),
]
HINTS = [(120, "GERAK: PANAH atau A/D"), (900, "LOMPAT: SPASI  (tahan = lebih tinggi)"),
         (1700, "SERANG: T  -  atau INJAK musuh dari atas"), (2500, "DASH: SHIFT KIRI"),
         (3200, "Bendera adalah checkpoint. Kumpulkan gem!")]


class Level:
    pass


def _pick(rng, weights):
    tot = sum(weights.values())
    r = rng.random() * tot
    for k, w in weights.items():
        r -= w
        if r <= 0:
            return k
    return next(iter(weights))


def build_level(idx):
    spec = LEVELS[idx]
    rng = random.Random(4242 + idx * 97)
    L = Level()
    L.idx, L.spec = idx, spec
    L.solids, L.gems, L.spikes, L.orbiters = [], [], [], []
    L.icicles, L.enemy_defs, L.checkpoints = [], [], []
    L.hints = HINTS if spec.get("tutorial") else []
    safe_gap = int(MAX_JUMP_DISTANCE * 0.68)
    plats = []
    x, y = 0, 560
    first = Solid(x, y, 520, GROUND_H)
    L.solids.append(first)
    plats.append((x, y, 520, "normal"))
    x += 520
    kinds = spec["kinds"]
    while x < spec["length"]:
        bridge = None
        if kinds and rng.random() < 0.28:
            k = _pick(rng, kinds)
            if k in ("moving", "collapsing", "vanishing"):
                bridge = k
        if bridge == "moving":
            gap = rng.randint(200, 280)
            L.solids.append(Solid(x, y, 110, 24, "moving", ax=x, bx=x + gap - 110,
                                  period=rng.choice([3.6, 4.2, 4.8]), offset=rng.random() * 4))
            ny = y
        elif bridge in ("collapsing", "vanishing"):
            g1 = rng.randint(*spec["gap"]); g2 = rng.randint(*spec["gap"])
            g1, g2 = min(g1, safe_gap), min(g2, safe_gap)
            kw = dict(offset=rng.random() * 2.8) if bridge == "vanishing" else {}
            L.solids.append(Solid(x + g1, y, 96, 24, bridge, **kw))
            gap = g1 + 96 + g2
            ny = y
        else:
            gap = min(rng.randint(*spec["gap"]), safe_gap)
            ny = max(400, min(600, y + (rng.randint(-spec["dy"], spec["dy"]) // 16) * 16))
            ny = max(ny, y - 96)
        x += gap
        w = rng.randint(*spec["pw"]) // 16 * 16
        surface = "normal"
        for k in ("ice", "conveyor"):
            if k in kinds and rng.random() < kinds[k]:
                surface = k
        belt = rng.choice([-110, 110]) if surface == "conveyor" else 0
        L.solids.append(Solid(x, ny, w, GROUND_H, surface, belt=belt))
        plats.append((x, ny, w, surface))
        x += w
        y = ny

    if spec["boss"]:
        gap = 90
        x += gap
        L.arena = dict(x=x, y=y, w=ARENA_W)
        L.solids.append(Solid(x, y, ARENA_W, GROUND_H))
        L.solids.append(Solid(x + ARENA_W, y - 600, 32, 600 + GROUND_H, "wall"))
        L.gate_wall = Solid(x, y - 600, 32, 600, "wall")
        L.solids.append(L.gate_wall)
        L.lock_wall = Solid(x + 40, y - 600, 32, 600, "wall")
        L.lock_wall.active = False
        L.solids.append(L.lock_wall)
        L.exit = (x + ARENA_W - 160, y - 110, 64, 110)
        L.width = x + ARENA_W + 32
        L.spawn_boss = (x + ARENA_W - 300, y)
    else:
        L.arena = None
        gap = 90
        x += gap
        L.solids.append(Solid(x, y, 560, GROUND_H))
        plats.append((x, y, 560, "normal"))
        L.exit = (x + 400, y - 110, 64, 110)
        L.width = x + 560
    L.start = (80, 560 - Player_H())
    L.pit_y = PIT_Y

    n = spec["cps"]
    last_cp = 0
    for i in range(1, n + 1):
        target = spec["length"] * i / (n + 1)
        cand = [p for p in plats[1:] if p[0] >= target and p[2] >= 220 and p[3] == "normal"]
        if cand and cand[0][0] - last_cp > 600:
            p = cand[0]
            L.checkpoints.append((p[0] + 60, p[1]))
            last_cp = p[0]
    cp_x = {c[0] for c in L.checkpoints}

    for pi, (px, py, pw, surf) in enumerate(plats):
        last = pi == len(plats) - 1 and not spec["boss"]
        if pi == 0 or last:
            continue
        rng.randint(3, 6)
        near_cp = any(abs(px + 60 - c) < 200 for c in cp_x)
        hazard = False
        if pw >= 300 and rng.random() < spec["spikes"] and not near_cp and surf == "normal":
            sw = 32 * rng.randint(1, 2)
            L.spikes.append((px + pw / 2 - sw / 2, py - 16, sw, 16))
            hazard = True
        elif pw >= 300 and rng.random() < spec["orbit"] and not near_cp:
            L.orbiters.append(dict(cx=px + pw / 2, cy=py - 75, r=58, period=rng.choice([2.6, 3.2]),
                                   phase=rng.random() * 6.28))
            hazard = True
        elif pw >= 260 and rng.random() < spec["icicle"]:
            L.icicles.append((px + pw / 2, py - 260, py))
        if not near_cp and not hazard and pw >= 160:
            for _ in range(2 if pw >= 380 else 1):
                if rng.random() < spec["density"]:
                    L.enemy_defs.append((_pick(rng, spec["enemies"]), px, py, pw))

    def _hazard(q):
        x0, x1 = q[0] - 20, q[0] + q[2] + 20
        return (any(x0 <= sp[0] <= x1 for sp in L.spikes) or any(x0 <= o["cx"] <= x1 for o in L.orbiters)
                or any(x0 <= ic[0] <= x1 for ic in L.icicles))
    want = spec["length"] * 0.55
    body = plats[1:]
    cand = ([q for q in body if q[3] == "normal" and q[2] >= 300 and not _hazard(q)]
            or [q for q in body if q[3] == "normal" and q[2] >= 240 and not _hazard(q)]
            or [q for q in body if q[3] == "normal" and q[2] >= 240] or body)
    kp = min(cand, key=lambda q: abs(q[0] - want))
    kcx = kp[0] + kp[2] / 2
    L.solids.append(Solid(kcx - 150, kp[1] - 90, 80, 16, "normal"))
    L.solids.append(Solid(kcx + 40, kp[1] - 180, 80, 16, "normal"))
    L.key = (kcx + 80, kp[1] - 180 - 38)
    L.key_plat = kp

    wide = [p for p in plats[1:-1] if p[2] >= 240 and p is not kp]
    rng.shuffle(wide)
    for (px, py, pw, _) in wide[:spec["secrets"]]:
        sx = px + pw / 2 - 48
        L.solids.append(Solid(sx, py - 112, 96, 16, "normal"))
        L.gems += [(sx + 28, py - 150), (sx + 68, py - 150)]
    L.par_time = spec["length"] / 230 + (60 if spec["boss"] else 20)
    return L


def Player_H():
    from .physics import Player
    return Player.H

from .physics import MAX_JUMP_DISTANCE


class AutoPilot:
    def __init__(self):
        self.hold = 0.0

    @staticmethod
    def _real(o):
        return o.active and o.kind != "wall" and not (o.kind == "normal" and o.h < 100)

    def step(self, w, dt):
        p = w.player
        inp = dict(left=False, right=True, jump_pressed=False, jump_held=self.hold > 0, attack=False, dash=False)
        if not w.has_key:
            kx, ky = w.lv.key
            if p.x > kx - 20:
                w.has_key = True
                w.notify("AUTO: KEY OBTAINED", 2.0)
        b = w.boss
        if b is not None and b.alive and w.arena_locked:
            dx = (b.x + b.w / 2) - (p.x + p.W / 2)
            inp["right"], inp["left"] = dx > 40, dx < -40
            if abs(dx) < 90:
                inp["attack"] = True
                if b.vulnerable and p.on_ground:
                    inp["jump_pressed"] = True
                    self.hold = 0.3
        else:
            for e in w.enemies:
                if e.alive and 0 < e.x - (p.x + p.W) < 46 and abs(e.y - p.y) < 40:
                    inp["attack"] = True
        if w.exit_open:
            ex = w.lv.exit
            dx = (ex[0] + ex[2] / 2) - (p.x + p.W / 2)
            if abs(dx) > 10:
                inp["right"], inp["left"] = dx > 0, dx < 0
        if p.on_ground and not (b is not None and b.alive and w.arena_locked):
            ahead = p.x + p.W + 28
            feet = p.y + p.H
            solids = [o for o in w.solids if self._real(o)]

            def covered(px, py):
                return any(o.x <= px <= o.x + o.w and o.y - 6 <= py <= o.y + 40 for o in solids)
            wall = any(o.x < p.x + p.W + 10 < o.x + o.w and o.y < feet - 6 and o.y + o.h > feet - 30 for o in solids)
            ahead = p.x + p.W + 28 if inp["right"] or not inp["left"] else p.x - 28
            if wall or (not covered(ahead, feet + 4) and not inp["left"]):
                nxt = [o for o in solids if o.x >= p.x + p.W - 4 and abs(o.y - feet) < 100]
                dist = min((o.x - (p.x + p.W) for o in nxt if o.kind != "moving"), default=999)
                mv = min((o.x - (p.x + p.W) for o in nxt if o.kind == "moving"), default=999)
                if wall or dist <= MAX_JUMP_DISTANCE * 0.62 or mv <= 40:
                    inp["jump_pressed"] = True
                    self.hold = 0.5
                elif any((o.kind == "moving" or (o.kind == "vanishing" and not o.active)) and 0 < o.x - p.x < 320
                         and abs(o.y - feet) < 10 for o in w.solids):
                    inp["right"] = False
        elif not p.on_ground:
            cx = p.x + p.W / 2
            for o in w.solids:
                if o.kind == "moving" and o.x - 20 <= cx <= o.x + o.w + 20 and p.y + p.H <= o.y + 6 and p.vy > 0:
                    if cx > o.x + o.w * 0.45:
                        inp["right"], inp["left"] = False, True
                    break
        self.hold = max(0.0, self.hold - dt)
        return inp

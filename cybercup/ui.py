import math
import pygame

W, H = 1280, 720
_fonts = {}


def font(size, bold=True):
    k = (size, bold)
    if k not in _fonts:
        try:
            _fonts[k] = pygame.font.SysFont("segoeui,verdana,dejavusans,arial", size, bold=bold)
        except Exception:
            _fonts[k] = pygame.font.Font(None, size + 6)
    return _fonts[k]


def hsv(h, s=0.8, v=1.0):
    c = pygame.Color(0)
    c.hsva = (h % 360, s * 100, v * 100, 100)
    return (c.r, c.g, c.b)


def wrap(s, size, maxw, bold=False):
    f = font(size, bold)
    lines, cur = [], ""
    for word in s.split():
        t = (cur + " " + word).strip()
        if cur and f.size(t)[0] > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = t
    return lines + [cur] if cur else lines


_text_cache = {}


def _render(s, size, bold, color):
    k = (s, size, bold, tuple(color))
    img = _text_cache.get(k)
    if img is None:
        if len(_text_cache) > 700:
            _text_cache.clear()
        img = _text_cache[k] = font(size, bold).render(s, True, color)
    return img


def text(surf, s, size, color, pos, anchor="center", bold=True, glow=None, shadow=True):
    img = _render(s, size, bold, color)
    r = img.get_rect()
    setattr(r, anchor, pos)
    if glow:
        g = _render(s, size, bold, glow)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-3, 3), (3, 3)):
            surf.blit(g, r.move(dx, dy))
    elif shadow:
        surf.blit(_render(s, size, bold, (0, 0, 20)), r.move(2, 2))
    surf.blit(img, r)
    return r


def heart(surf, x, y, s, color):
    pygame.draw.circle(surf, color, (x - s // 4, y), s // 3 + 1)
    pygame.draw.circle(surf, color, (x + s // 4, y), s // 3 + 1)
    pygame.draw.polygon(surf, color, [(x - s // 2 + 1, y + 2), (x + s // 2 - 1, y + 2), (x, y + s // 2 + 4)])


def lock_icon(surf, cx, cy, s, color):
    pygame.draw.rect(surf, color, (cx - s // 2, cy - s // 6, s, s * 2 // 3), border_radius=3)
    pygame.draw.arc(surf, color, (cx - s // 3, cy - s * 2 // 3, s * 2 // 3, s * 3 // 4), 0, math.pi, 4)
    pygame.draw.circle(surf, (30, 20, 50), (cx, cy + s // 8), max(2, s // 10))


class Menu:

    def __init__(self, items, cx=W // 2, y0=250, step=58, w=380, h=46, size=26, horizontal=False):
        self.items, self.sel = items, 0
        self.horizontal = horizontal
        self.cx, self.y0, self.step, self.w, self.h, self.size = cx, y0, step, w, h, size
        self.anim = [0.0] * len(items)

    def rect(self, i):
        if self.horizontal:
            total = (len(self.items) - 1) * self.step + self.w
            return pygame.Rect(self.cx - total // 2 + i * self.step, self.y0, self.w, self.h)
        return pygame.Rect(self.cx - self.w // 2, self.y0 + i * self.step, self.w, self.h)

    def label(self, i):
        l = self.items[i][0]
        return l() if callable(l) else l

    def handle(self, e, audio=None):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT) and (e.key != pygame.K_LEFT or self.horizontal):
                self.sel = (self.sel - 1) % len(self.items)
                audio and audio.play("menu")
            elif e.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT) and (e.key != pygame.K_RIGHT or self.horizontal):
                self.sel = (self.sel + 1) % len(self.items)
                audio and audio.play("menu")
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                audio and audio.play("select")
                self.items[self.sel][1]()
                return True
        elif e.type == pygame.MOUSEMOTION:
            for i in range(len(self.items)):
                if self.rect(i).collidepoint(e.pos) and self.sel != i:
                    self.sel = i
                    audio and audio.play("menu")
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i in range(len(self.items)):
                if self.rect(i).collidepoint(e.pos):
                    self.sel = i
                    audio and audio.play("select")
                    self.items[i][1]()
                    return True
        return False

    def draw(self, surf, t, accent=(0, 240, 255)):
        dt = min(0.1, max(0.0, t - getattr(self, "_lt", t)))
        self._lt = t
        k = 1.0 - math.exp(-17.0 * dt)
        for i in range(len(self.items)):
            r = self.rect(i)
            self.anim[i] += ((1.0 if i == self.sel else 0.0) - self.anim[i]) * k
            a = self.anim[i]
            rr = r.inflate(int(24 * a), int(6 * a))
            pygame.draw.rect(surf, (18 + int(30 * a), 10 + int(10 * a), 50 + int(40 * a)), rr, border_radius=10)
            col = tuple(int(70 + (c - 70) * a) for c in accent)
            pygame.draw.rect(surf, col, rr, 2 + int(2 * a), border_radius=10)
            text(surf, self.label(i), self.size, (255, 255, 255) if i == self.sel else (200, 200, 230),
                 rr.center, shadow=False)

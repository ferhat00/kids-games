"""
Dream Flight — a dreamy sky adventure for young children.
Arrow keys steer a magical airplane through friendly animals for points.
Avoid the evil purple frogs or lose a heart!
"""

from __future__ import annotations

import array
import math
import random

import pygame

from framework.game_framework import GameFramework
from framework.ui_components import THEME, ParticleSystem

# ── Constants ─────────────────────────────────────────────────────────────────

GAME_ID     = "dream_flight"
HUD_H       = 52
LIVES_START = 3

PLANE_MAX_SPEED = 320
PLANE_ACCEL     = 500
PLANE_DRAG      = 4.0
GRAVITY         = 55

OBJ_SPEED_BASE  = 140
OBJ_SPEED_SCALE = 3       # extra px/s added per 10 pts scored

SPAWN_BASE = 2.2
SPAWN_MIN  = 0.7
FROG_CHANCE = 0.25

POINTS_ANIMAL = 10

# Sky palette
SKY_TOP   = (70, 50, 150)
SKY_BOT   = (255, 150, 200)
CLOUD_COL = (255, 240, 255)

# Creature colours
DRAGON_COL   = (80, 200, 140)
WHALE_COL    = (80, 140, 255)
ELEPHANT_COL = (180, 160, 210)
FROG_COL     = (90, 15, 145)
FROG_EYE_COL = (255, 50, 50)
BUTTERFLY_COLS = [(255, 100, 200), (255, 200, 50), (100, 220, 255), (180, 100, 255)]

ANIMAL_TYPES = ["unicorn", "butterfly", "dragon", "whale", "elephant"]


# ── Procedural sound helpers ──────────────────────────────────────────────────

def _sine_buf(freq: float, dur_ms: int, vol: float = 0.4, fade: bool = True):
    if not pygame.mixer.get_init():
        return None
    sr  = 44100
    n   = int(sr * dur_ms / 1000)
    buf = array.array("h")
    for i in range(n):
        t   = i / sr
        v   = math.sin(2 * math.pi * freq * t)
        if fade:
            v *= 1.0 - i / n
        buf.append(int(v * 32767 * vol))
        buf.append(int(v * 32767 * vol))
    return pygame.mixer.Sound(buffer=buf)


def _arpeggio_buf(freqs: list, note_ms: int = 80, vol: float = 0.45):
    if not pygame.mixer.get_init():
        return None
    sr    = 44100
    n_per = int(sr * note_ms / 1000)
    buf   = array.array("h")
    for freq in freqs:
        for i in range(n_per):
            t   = i / sr
            v   = math.sin(2 * math.pi * freq * t) * (1 - i / n_per)
            buf.append(int(v * 32767 * vol))
            buf.append(int(v * 32767 * vol))
    return pygame.mixer.Sound(buffer=buf)


def _engine_buf(dur_ms: int = 1000, vol: float = 0.12):
    if not pygame.mixer.get_init():
        return None
    sr  = 44100
    n   = int(sr * dur_ms / 1000)
    buf = array.array("h")
    for i in range(n):
        t = i / sr
        v = (0.55 * math.sin(2 * math.pi * 85 * t) +
             0.30 * math.sin(2 * math.pi * 170 * t) +
             0.15 * math.sin(2 * math.pi * 255 * t))
        buf.append(int(v * 32767 * vol))
        buf.append(int(v * 32767 * vol))
    return pygame.mixer.Sound(buffer=buf)


def _ambient_buf(dur_ms: int = 4000, vol: float = 0.14):
    """Dreamy C-major-7 chord pad that loops cleanly."""
    if not pygame.mixer.get_init():
        return None
    freqs = [261.63, 329.63, 392.00, 493.88, 659.25]
    sr    = 44100
    n     = int(sr * dur_ms / 1000)
    buf   = array.array("h")
    for i in range(n):
        t   = i / sr
        v   = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
        env = math.sin(math.pi * i / n)
        buf.append(int(v * env * 32767 * vol))
        buf.append(int(v * env * 32767 * vol))
    return pygame.mixer.Sound(buffer=buf)


def _build_sounds() -> dict:
    snd = {}
    try:
        snd["engine"]  = _engine_buf(1000, vol=0.14)
        snd["collect"] = _arpeggio_buf([523, 659, 784, 1047], note_ms=70, vol=0.5)
        snd["frog"]    = _arpeggio_buf([200, 160, 120], note_ms=130, vol=0.5)
        snd["music"]   = _ambient_buf(4000, vol=0.13)
    except Exception:
        pass
    return snd


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _gradient_rect(surf: pygame.Surface, top_col, bot_col, rect: pygame.Rect) -> None:
    x, y, w, h = rect
    for dy in range(h):
        t   = dy / max(h - 1, 1)
        col = tuple(int(top_col[i] + (bot_col[i] - top_col[i]) * t) for i in range(3))
        pygame.draw.line(surf, col, (x, y + dy), (x + w - 1, y + dy))


def _draw_plane(surf: pygame.Surface, w: int, h: int, prop_angle: float) -> None:
    cx, cy = w // 2, h // 2
    # Fuselage
    pygame.draw.ellipse(surf, (230, 240, 255), (cx - w // 3, cy - h // 8, w * 2 // 3, h // 4))
    # Pointed nose cone
    pygame.draw.polygon(surf, (200, 220, 255), [
        (cx + w // 3, cy),
        (cx + w // 2, cy - h // 10),
        (cx + w // 2, cy + h // 10),
    ])
    # Top wing
    pygame.draw.polygon(surf, (100, 160, 255), [
        (cx - w // 12, cy - h // 10),
        (cx + w //  6, cy - h // 10),
        (cx + w //  8, cy - h // 2),
        (cx - w //  5, cy - h // 2 + h // 8),
    ])
    # Bottom wing (mirror)
    pygame.draw.polygon(surf, (100, 160, 255), [
        (cx - w // 12, cy + h // 10),
        (cx + w //  6, cy + h // 10),
        (cx + w //  8, cy + h // 2),
        (cx - w //  5, cy + h // 2 - h // 8),
    ])
    # Tail fin
    pygame.draw.polygon(surf, (255, 80, 80), [
        (cx - w // 3 + 4, cy),
        (cx - w // 3 - w // 8, cy - h // 3),
        (cx - w // 4, cy),
    ])
    # Window
    pygame.draw.ellipse(surf, (200, 230, 255), (cx + w // 12, cy - h // 10, w // 8, h // 5))
    pygame.draw.ellipse(surf, (100, 160, 200), (cx + w // 12, cy - h // 10, w // 8, h // 5), 2)
    # Spinning propeller blades
    for offset in (prop_angle, prop_angle + math.pi / 2):
        ex = cx + w // 2 + int(math.cos(offset) * h // 2)
        ey = cy + int(math.sin(offset) * h // 2)
        pygame.draw.line(surf, (255, 220, 50), (cx + w // 2 - 2, cy), (ex, ey), 4)


def _draw_unicorn(surf: pygame.Surface, w: int, h: int) -> None:
    cx, cy = w // 2, h * 3 // 5
    # Body
    pygame.draw.ellipse(surf, (255, 248, 255), (cx - w // 3, cy - h // 4, w * 2 // 3, h // 2))
    # Neck + head
    pygame.draw.ellipse(surf, (255, 248, 255), (cx + w // 6, cy - h // 2, w // 5, h // 3))
    # Golden horn
    hbx = cx + w // 6 + w // 10
    hby = cy - h // 2
    pygame.draw.polygon(surf, (255, 210, 50), [
        (hbx, hby), (hbx - w // 20, hby + h // 6), (hbx + w // 20, hby + h // 6),
    ])
    # Rainbow mane
    mx = cx + w // 6 + w // 12
    for k, col in enumerate([(255, 80, 80), (255, 160, 50), (255, 220, 50),
                              (80, 200, 80), (50, 150, 255), (160, 80, 255)]):
        pygame.draw.arc(surf, col,
                        (mx - k * 3, cy - h // 2 + k * 3, w // 4 - k * 3, h // 4),
                        math.radians(30), math.radians(180), 3)
    # Legs
    for lx in (cx - w // 6, cx, cx + w // 10, cx + w // 4):
        pygame.draw.line(surf, (230, 220, 245), (lx, cy + h // 4 - 4), (lx, cy + h // 3 + 4), 5)
    # Eye
    pygame.draw.circle(surf, (40, 40, 80), (mx + 6, cy - h // 2 + h // 8), 4)
    pygame.draw.circle(surf, (255, 255, 255), (mx + 5, cy - h // 2 + h // 8 - 2), 1)
    # Fairy wings (semi-transparent)
    for sign in (-1, 1):
        wing_s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(wing_s, (200, 220, 255, 150), [
            (cx, cy - h // 8),
            (cx - sign * w // 2, cy - h // 2),
            (cx - sign * w // 3, cy),
        ])
        surf.blit(wing_s, (0, 0))


def _draw_butterfly(surf: pygame.Surface, w: int, h: int) -> None:
    cx, cy = w // 2, h // 2
    wings = [
        [(cx, cy - 4), (cx - w // 2, cy - h // 2), (cx - w // 3, cy + h // 6)],
        [(cx, cy - 4), (cx + w // 2, cy - h // 2), (cx + w // 3, cy + h // 6)],
        [(cx, cy + 4), (cx - w // 2 + w // 8, cy + h // 2), (cx - w // 6, cy - h // 8)],
        [(cx, cy + 4), (cx + w // 2 - w // 8, cy + h // 2), (cx + w // 6, cy - h // 8)],
    ]
    for i, pts in enumerate(wings):
        pygame.draw.polygon(surf, BUTTERFLY_COLS[i], pts)
        pygame.draw.polygon(surf, (255, 255, 255), pts, 2)
        mx = sum(p[0] for p in pts) // 3
        my = sum(p[1] for p in pts) // 3
        pygame.draw.circle(surf, (255, 255, 255), (mx, my), 6)
        pygame.draw.circle(surf, BUTTERFLY_COLS[(i + 2) % 4], (mx, my), 4)
    pygame.draw.ellipse(surf, (60, 30, 80), (cx - 4, cy - h // 3, 8, h * 2 // 3))
    # Antennae
    for sign in (-1, 1):
        tip = (cx + sign * w // 6, cy - h // 2 - 6)
        pygame.draw.line(surf, (60, 30, 80), (cx, cy - h // 3), tip, 2)
        pygame.draw.circle(surf, BUTTERFLY_COLS[0 if sign < 0 else 1], tip, 4)


def _draw_dragon(surf: pygame.Surface, w: int, h: int) -> None:
    cx, cy = w // 2, h * 3 // 5
    pygame.draw.ellipse(surf, DRAGON_COL, (cx - w // 3, cy - h // 5, w * 2 // 3, h * 2 // 5))
    pygame.draw.ellipse(surf, DRAGON_COL, (cx + w // 6, cy - h // 2, w // 4, h // 3))
    # Back spikes
    for k in range(5):
        sx = cx - w // 3 + k * (w * 2 // 3) // 5
        pygame.draw.polygon(surf, (200, 80, 80), [
            (sx + w // 20, cy - h // 5),
            (sx, cy - h // 3 - k * 3),
            (sx - w // 20, cy - h // 5),
        ])
    # Wings
    for sign in (-1, 1):
        wing_s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(wing_s, (200, 100, 50, 200), [
            (cx - sign * w // 8,                  cy - h // 8),
            (cx - sign * w // 2,                  cy - h // 2),
            (cx - sign * w // 2 + sign * w // 5,  cy - h // 8 + h // 4),
            (cx - sign * w // 6,                  cy - h // 8 + h // 5),
        ])
        surf.blit(wing_s, (0, 0))
    # Eye
    pygame.draw.circle(surf, (255, 220, 0), (cx + w // 4 + 8, cy - h // 2 + h // 8), 5)
    # Flame puff
    pygame.draw.polygon(surf, (255, 160, 0), [
        (cx + w // 2 - 2,      cy - h // 2 + h // 8),
        (cx + w // 2 + w // 8, cy - h // 2),
        (cx + w // 2 + w // 10, cy - h // 2 + h // 6),
    ])


def _draw_whale(surf: pygame.Surface, w: int, h: int) -> None:
    cx, cy = w // 2, h // 2
    # Tail
    pygame.draw.polygon(surf, WHALE_COL, [
        (cx - w * 2 // 5 + 8, cy),
        (cx - w // 2,         cy - h // 3),
        (cx - w // 2 - w // 8, cy - h // 8),
        (cx - w // 2,         cy + h // 3),
        (cx - w // 2 + w // 8, cy + h // 8),
    ])
    pygame.draw.ellipse(surf, WHALE_COL, (cx - w * 2 // 5, cy - h // 4, w * 4 // 5, h // 2))
    # Belly
    pygame.draw.ellipse(surf, (180, 210, 255), (cx - w // 4, cy - h // 8, w // 2, h // 4))
    # Little wing fins
    for sign in (-1, 1):
        pygame.draw.ellipse(surf, (60, 110, 220),
                            (cx, cy + sign * h // 4 - h // 16, w // 4, h // 8))
    # Eye
    pygame.draw.circle(surf, (20, 20, 60), (cx + w // 5, cy - h // 8), 6)
    pygame.draw.circle(surf, (255, 255, 255), (cx + w // 5 + 2, cy - h // 8 - 2), 2)
    # Spout
    for k in range(3):
        pygame.draw.line(surf, (200, 230, 255),
                         (cx + w // 8, cy - h // 4 - k * 8),
                         (cx + w // 8 + (k - 1) * 4, cy - h // 4 - k * 8 - 8), 2)


def _draw_elephant(surf: pygame.Surface, w: int, h: int) -> None:
    cx, cy = w // 2, h // 2
    # Big ears as wings
    for sign in (-1, 1):
        ear = [
            (cx,                   cy - h // 6),
            (cx - sign * w * 2 // 5, cy - h // 3),
            (cx - sign * w // 2,   cy),
            (cx - sign * w * 2 // 5, cy + h // 3),
            (cx,                   cy + h // 6),
        ]
        pygame.draw.polygon(surf, (200, 180, 225), ear)
        inner = [(int(p[0] * 0.7 + cx * 0.3), int(p[1] * 0.7 + cy * 0.3)) for p in ear]
        pygame.draw.polygon(surf, (240, 180, 205), inner)
    # Body
    pygame.draw.ellipse(surf, ELEPHANT_COL, (cx - w // 5, cy - h // 4, w * 2 // 5, h // 2))
    # Head
    pygame.draw.circle(surf, ELEPHANT_COL, (cx + w // 6, cy - h // 6), h // 4)
    # Trunk
    pygame.draw.lines(surf, ELEPHANT_COL, False, [
        (cx + w // 6 + h // 8, cy - h // 6 + h // 8),
        (cx + w // 3 + w // 8, cy + h // 6),
        (cx + w // 4,          cy + h // 4 + 4),
    ], 8)
    # Tusk
    pygame.draw.line(surf, (255, 240, 200),
                     (cx + w // 6 + h // 8, cy - h // 6 + h // 12),
                     (cx + w // 3, cy), 4)
    # Eye
    pygame.draw.circle(surf, (40, 30, 50), (cx + w // 6 + h // 10, cy - h // 6 - 2), 5)
    pygame.draw.circle(surf, (255, 255, 255), (cx + w // 6 + h // 10 + 1, cy - h // 6 - 3), 2)


def _draw_frog(surf: pygame.Surface, w: int, h: int) -> None:
    cx, cy = w // 2, h // 2
    # Evil dark purple body
    pygame.draw.ellipse(surf, FROG_COL, (cx - w // 3, cy - h // 4, w * 2 // 3, h // 2))
    # Warts
    for wx, wy, wr in ((cx - w // 5, cy - h // 8, 5), (cx + w // 8, cy, 4), (cx - w // 10, cy + h // 10, 3)):
        pygame.draw.circle(surf, (70, 5, 110), (wx, wy), wr)
    # Big red eyes
    for sign in (-1, 1):
        ex, ey = cx + sign * w // 5, cy - h // 4 - 4
        pygame.draw.circle(surf, (60, 0, 100), (ex, ey), h // 6)
        pygame.draw.circle(surf, FROG_EYE_COL, (ex, ey), h // 7)
        pygame.draw.circle(surf, (20, 0, 30), (ex + 2, ey + 2), h // 10)
        # Evil eyebrow
        pygame.draw.line(surf, (30, 0, 50), (ex - h // 6, ey - h // 6), (ex + h // 6, ey - h // 8), 3)
    # Mean mouth
    pygame.draw.arc(surf, (200, 0, 100),
                    (cx - w // 5, cy + h // 12, w * 2 // 5, h // 5),
                    math.radians(200), math.radians(340), 4)
    # Outstretched legs
    for sign in (-1, 1):
        pygame.draw.line(surf, FROG_COL,
                         (cx + sign * w // 3, cy),
                         (cx + sign * (w // 2 + w // 8), cy - h // 4), 6)
        pygame.draw.line(surf, FROG_COL,
                         (cx + sign * (w // 2 + w // 8), cy - h // 4),
                         (cx + sign * (w // 2 + w // 4), cy), 6)
        pygame.draw.circle(surf, (80, 10, 120), (cx + sign * (w // 2 + w // 4), cy), 7)
    # Dark aura rays
    for k in range(4):
        ang = k * math.pi / 2 + math.pi / 4
        pygame.draw.line(surf, (140, 0, 200),
                         (cx, cy),
                         (cx + int(math.cos(ang) * w // 2), cy + int(math.sin(ang) * h // 3)), 1)


# ── Heart helper (parametric) ─────────────────────────────────────────────────

def _draw_heart(surf: pygame.Surface, cx: int, cy: int, size: int, col) -> None:
    scale = size / 16.0
    pts = []
    for i in range(60):
        a = math.radians(i * 6)
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + int(x * scale), cy + int(y * scale)))
    if len(pts) >= 3:
        pygame.draw.polygon(surf, col, pts)


# ── Game objects ──────────────────────────────────────────────────────────────

class _FlyingObject:
    W, H = 120, 90

    def __init__(self, kind: str, x: float, y: float, speed: float) -> None:
        self.kind  = kind
        self.x     = x
        self.y     = y
        self.speed = speed
        self.alive = True
        self._bob_t   = random.uniform(0, math.pi * 2)
        self._bob_amp = random.uniform(12, 26)
        self._bob_spd = random.uniform(1.6, 3.2)
        self._surf    = self._build_surf()

    def _build_surf(self) -> pygame.Surface:
        surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        {
            "unicorn":   _draw_unicorn,
            "butterfly": _draw_butterfly,
            "dragon":    _draw_dragon,
            "whale":     _draw_whale,
            "elephant":  _draw_elephant,
            "frog":      _draw_frog,
        }[self.kind](surf, self.W, self.H)
        return surf

    @property
    def _display_y(self) -> float:
        return self.y + math.sin(self._bob_t) * self._bob_amp

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x) - self.W // 2,
            int(self._display_y) - self.H // 2,
            self.W, self.H,
        )

    def update(self, dt: float) -> None:
        self.x     -= self.speed * dt
        self._bob_t += self._bob_spd * dt
        if self.x < -self.W:
            self.alive = False

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._surf,
                  (int(self.x) - self.W // 2, int(self._display_y) - self.H // 2))


class _Plane:
    W, H = 90, 60

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y   = x, y
        self.vx, self.vy = 0.0, 0.0
        self._prop  = 0.0
        self._tilt  = 0.0

    def update(self, dt: float, keys) -> None:
        ax = ay = 0.0
        if keys[pygame.K_RIGHT]: ax += PLANE_ACCEL
        if keys[pygame.K_LEFT]:  ax -= PLANE_ACCEL
        if keys[pygame.K_UP]:    ay -= PLANE_ACCEL
        if keys[pygame.K_DOWN]:  ay += PLANE_ACCEL

        self.vx += ax * dt
        self.vy += ay * dt + GRAVITY * dt
        self.vx *= max(0, 1 - PLANE_DRAG * dt)
        self.vy *= max(0, 1 - PLANE_DRAG * dt)

        spd = math.hypot(self.vx, self.vy)
        if spd > PLANE_MAX_SPEED:
            self.vx = self.vx / spd * PLANE_MAX_SPEED
            self.vy = self.vy / spd * PLANE_MAX_SPEED

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.x = max(self.W // 2,       min(900 - self.W // 2, self.x))
        self.y = max(HUD_H + self.H // 2, min(650 - self.H // 2, self.y))

        target_tilt   = max(-25.0, min(25.0, -self.vy * 0.04))
        self._tilt   += (target_tilt - self._tilt) * min(1.0, dt * 8)
        self._prop   += 12.0 * dt

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x) - self.W // 2 + 12,
            int(self.y) - self.H // 2 + 12,
            self.W - 24, self.H - 24,
        )

    def draw(self, surf: pygame.Surface) -> None:
        ps = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        _draw_plane(ps, self.W, self.H, self._prop)
        rot = pygame.transform.rotate(ps, self._tilt)
        rr  = rot.get_rect(center=(int(self.x), int(self.y)))
        surf.blit(rot, rr.topleft)


class _Cloud:
    def __init__(self, spawn: bool = False) -> None:
        self._init(spawn)

    def _init(self, spawn: bool = False) -> None:
        self.y     = random.randint(HUD_H + 20, 620)
        self.speed = random.uniform(20, 55)
        self.alpha = random.randint(55, 135)
        self.scale = random.uniform(0.6, 1.5)
        self.x     = random.randint(0, 900) if spawn else 950 + random.randint(0, 200)

    def update(self, dt: float) -> None:
        self.x -= self.speed * dt
        if self.x < -200:
            self._init()

    def draw(self, surf: pygame.Surface) -> None:
        s   = int(60 * self.scale)
        cs  = pygame.Surface((s * 3, s * 2), pygame.SRCALPHA)
        col = (*CLOUD_COL, self.alpha)
        pygame.draw.ellipse(cs, col, (0, s // 2, s * 2, s))
        pygame.draw.ellipse(cs, col, (s // 2, 0, s * 2, s))
        pygame.draw.ellipse(cs, col, (s, s // 4, s * 2, s))
        surf.blit(cs, (int(self.x) - s, int(self.y) - s // 2))


class _Star:
    def __init__(self) -> None:
        self.x    = random.randint(0, 900)
        self.y    = random.randint(HUD_H + 5, 645)
        self.t    = random.uniform(0, math.pi * 2)
        self.r    = random.randint(2, 5)
        self.spd  = random.uniform(2, 5)

    def update(self, dt: float) -> None:
        self.t += self.spd * dt

    def draw(self, surf: pygame.Surface) -> None:
        r = max(1, int(self.r * (0.5 + 0.5 * math.sin(self.t))))
        t = math.sin(self.t) * 0.5 + 0.5
        pygame.draw.circle(surf, (int(200 + 55 * t), int(180 + 75 * t), 255),
                           (self.x, self.y), r)


class _SparkleTrail:
    def __init__(self) -> None:
        self._sparks: list = []

    def add(self, x: float, y: float) -> None:
        if random.random() < 0.4:
            life = random.uniform(0.3, 0.7)
            self._sparks.append({
                "x":        x + random.uniform(-8, 8),
                "y":        y + random.uniform(-8, 8),
                "life":     life,
                "max_life": life,
                "r":        random.randint(3, 7),
                "col":      random.choice([
                    (255, 220, 50), (255, 150, 200), (150, 220, 255), (200, 255, 150),
                ]),
            })

    def update(self, dt: float) -> None:
        for s in self._sparks:
            s["life"] -= dt
        self._sparks = [s for s in self._sparks if s["life"] > 0]

    def draw(self, surf: pygame.Surface) -> None:
        for s in self._sparks:
            alpha = int(255 * s["life"] / s["max_life"])
            r     = max(1, int(s["r"] * s["life"] / s["max_life"]))
            tmp   = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(tmp, (*s["col"], alpha), (r, r), r)
            surf.blit(tmp, (int(s["x"]) - r, int(s["y"]) - r))


# ── Main game class ───────────────────────────────────────────────────────────

class DreamFlightGame(GameFramework):

    def setup(self) -> None:
        self._score      = 0
        self._level      = 1
        self._lives      = LIVES_START
        self._completion = 0.0
        self._game_over  = False

        self._flash_t   = 0.0   # red tint on frog hit
        self._collect_t = 0.0   # golden glow on animal collect

        self._plane     = _Plane(180, HUD_H + (650 - HUD_H) // 2)
        self._clouds    = [_Cloud(spawn=True) for _ in range(8)]
        self._stars     = [_Star() for _ in range(35)]
        self._trail     = _SparkleTrail()
        self._particles = ParticleSystem()

        self._objects: list        = []
        self._spawn_timer          = 1.2
        self._spawn_interval       = SPAWN_BASE

        try:
            self._font_lg = pygame.font.SysFont("Comic Sans MS", 34, bold=True)
            self._font_sm = pygame.font.SysFont("Comic Sans MS", 21)
            self._font_go = pygame.font.SysFont("Comic Sans MS", 62, bold=True)
        except Exception:
            self._font_lg = pygame.font.Font(None, 34)
            self._font_sm = pygame.font.Font(None, 21)
            self._font_go = pygame.font.Font(None, 62)

        # Pre-build sky gradient
        self._sky = pygame.Surface((900, 650 - HUD_H))
        _gradient_rect(self._sky, SKY_TOP, SKY_BOT, pygame.Rect(0, 0, 900, 650 - HUD_H))

        self._snd       = _build_sounds()
        self._engine_ch = None
        self._music_ch  = None
        self._start_audio()

    # ── Audio ─────────────────────────────────────────────────────────────────

    def _start_audio(self) -> None:
        try:
            eng = self._snd.get("engine")
            if eng:
                self._engine_ch = eng.play(-1)
                if self._engine_ch:
                    self._engine_ch.set_volume(0.15)
            mus = self._snd.get("music")
            if mus:
                self._music_ch = mus.play(-1)
                if self._music_ch:
                    self._music_ch.set_volume(0.12)
        except Exception:
            pass

    def _stop_audio(self) -> None:
        try:
            if self._engine_ch:
                self._engine_ch.stop()
            if self._music_ch:
                self._music_ch.stop()
        except Exception:
            pass

    def _play(self, name: str) -> None:
        snd = self._snd.get(name)
        if snd:
            try:
                snd.play()
            except Exception:
                pass

    # ── Spawning ──────────────────────────────────────────────────────────────

    def _spawn(self) -> None:
        kind  = "frog" if random.random() < FROG_CHANCE else random.choice(ANIMAL_TYPES)
        speed = OBJ_SPEED_BASE + (self._score // 10) * OBJ_SPEED_SCALE + random.uniform(-20, 20)
        y     = random.randint(HUD_H + 55, 650 - 55)
        self._objects.append(_FlyingObject(kind, 950.0, float(y), speed))

    # ── GameFramework interface ───────────────────────────────────────────────

    def handle_input(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if self._game_over and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._stop_audio()
                self.reset()

    def update(self, dt: float) -> None:
        if self._game_over:
            self._particles.update(dt)
            return

        keys = pygame.key.get_pressed()
        self._plane.update(dt, keys)
        self._trail.add(self._plane.x, self._plane.y)
        self._trail.update(dt)

        for c in self._clouds:
            c.update(dt)
        for s in self._stars:
            s.update(dt)

        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn()
            self._spawn_interval = max(SPAWN_MIN, SPAWN_BASE - self._score * 0.008)
            self._spawn_timer    = self._spawn_interval

        pr = self._plane.rect
        for obj in self._objects:
            obj.update(dt)
            if not obj.alive:
                continue
            if pr.colliderect(obj.rect):
                if obj.kind == "frog":
                    self._lives  -= 1
                    self._flash_t = 0.5
                    self._particles.burst(int(obj.x), int(obj.y), count=20)
                    self._play("frog")
                else:
                    self._score     += POINTS_ANIMAL
                    self._collect_t  = 0.35
                    self._particles.burst(int(obj.x), int(obj.y), count=38)
                    self._play("collect")
                obj.alive = False
                self._level = 1 + self._score // 50

        self._objects = [o for o in self._objects if o.alive]
        self._particles.update(dt)
        self._flash_t   = max(0.0, self._flash_t   - dt)
        self._collect_t = max(0.0, self._collect_t - dt)

        if self._lives <= 0:
            self._lives      = 0
            self._game_over  = True
            self._completion = min(1.0, self._score / 200.0)
            self._stop_audio()
            self._particles.burst(450, 350, count=90)

    def render(self, screen: pygame.Surface) -> None:
        # Sky
        screen.blit(self._sky, (0, HUD_H))

        # Stars
        star_s = pygame.Surface((900, 650 - HUD_H), pygame.SRCALPHA)
        for s in self._stars:
            # local y for star surface
            pygame.draw.circle(
                star_s,
                (int(200 + 55 * (math.sin(s.t) * 0.5 + 0.5)),
                 int(180 + 75 * (math.sin(s.t) * 0.5 + 0.5)), 255),
                (s.x, s.y - HUD_H),
                max(1, int(s.r * (0.5 + 0.5 * math.sin(s.t)))),
            )
        screen.blit(star_s, (0, HUD_H))

        # Clouds, trail, objects, particles, plane (absolute coords)
        for c in self._clouds:
            c.draw(screen)
        self._trail.draw(screen)
        for obj in self._objects:
            obj.draw(screen)
        self._particles.draw(screen)
        self._plane.draw(screen)

        # Collect glow
        if self._collect_t > 0:
            ov = pygame.Surface((900, 650 - HUD_H), pygame.SRCALPHA)
            ov.fill((255, 220, 50, int(55 * self._collect_t / 0.35)))
            screen.blit(ov, (0, HUD_H))

        # Frog hit flash
        if self._flash_t > 0:
            ov = pygame.Surface((900, 650), pygame.SRCALPHA)
            ov.fill((255, 0, 0, int(80 * self._flash_t / 0.5)))
            screen.blit(ov, (0, 0))

        self._draw_hud(screen)

        if self._game_over:
            self._draw_game_over(screen)

    def _draw_hud(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, (25, 15, 55), (0, 0, 900, HUD_H))
        pygame.draw.line(screen, (100, 75, 180), (0, HUD_H), (900, HUD_H), 2)

        sc = self._font_lg.render(f"Score: {self._score}", True, (255, 220, 80))
        screen.blit(sc, (16, (HUD_H - sc.get_height()) // 2))

        lv = self._font_sm.render(f"Level {self._level}", True, (180, 220, 255))
        screen.blit(lv, (450 - lv.get_width() // 2, (HUD_H - lv.get_height()) // 2))

        # Lives as hearts
        hx = 880
        for i in range(LIVES_START):
            hx -= 36
            col = (220, 60, 80) if i < self._lives else (55, 35, 80)
            _draw_heart(screen, hx, HUD_H // 2, 13, col)

        # Arrow key hint (fades after level 2)
        if self._level <= 2:
            hint = self._font_sm.render("Arrow keys to fly!", True, (180, 160, 220))
            screen.blit(hint, (450 - hint.get_width() // 2, HUD_H + 8))

    def _draw_game_over(self, screen: pygame.Surface) -> None:
        ov = pygame.Surface((900, 650), pygame.SRCALPHA)
        ov.fill((18, 8, 48, 210))
        screen.blit(ov, (0, 0))

        go = self._font_go.render("Game Over!", True, (255, 100, 160))
        screen.blit(go, (450 - go.get_width() // 2, 200))

        sc = self._font_lg.render(f"Final Score: {self._score}", True, (255, 220, 80))
        screen.blit(sc, (450 - sc.get_width() // 2, 295))

        tip = self._font_sm.render("Press SPACE or ENTER to play again  •  ESC for menu",
                                   True, (200, 180, 255))
        screen.blit(tip, (450 - tip.get_width() // 2, 375))

        self._particles.draw(screen)

    # ── GameFramework required ────────────────────────────────────────────────

    def get_game_info(self) -> dict:
        return {
            "title":           "Dream Flight",
            "description":     "Fly through magical animals, dodge evil frogs!",
            "thumbnail_color": (110, 70, 190),
            "vehicle_types":   ["airplane", "balloon"],
        }

    def get_game_state(self) -> dict:
        return {
            "score":      self._score,
            "level":      self._level,
            "completion": self._completion,
            "lives":      self._lives,
        }

"""
UIComponents — Reusable widgets for all vehicle-themed kids games.

Widgets
-------
Button          Clickable rect with hover/pressed states
TextLabel       Auto-sizing text with shadow option
Counter         Animated score/turn display
Timer           Elapsed-time tracker with HH:MM:SS / MM:SS rendering
AnimationQueue  Runs a sequence of tween animations on a target dict
CardFlip        Per-card flip animation helper (used by MemoryMatch)
ConfirmDialog   Yes/No overlay panel
ProgressBar     Visual fill bar (e.g. health, level progress)
draw_hud        Standalone function — top HUD bar for any game
"""

from __future__ import annotations

import math
import time
from typing import Callable, Dict, List, Optional, Tuple

import pygame

# ─────────────────────────────────────────────────────────────────────────────
# Theme constants (shared across all games for visual consistency)
# ─────────────────────────────────────────────────────────────────────────────
THEME = {
    "bg":          (255, 248, 231),   # warm cream
    "primary":     (255, 107,  53),   # orange-red  (buttons)
    "primary_hov": (255, 140,  90),   # hover tint
    "primary_prs": (200,  80,  30),   # pressed tint
    "secondary":   ( 78, 205, 196),   # teal        (accents)
    "success":     ( 88, 214, 141),   # green
    "danger":      (255, 100, 100),   # red
    "warning":     (255, 210,  50),   # yellow
    "text_dark":   ( 40,  40,  40),
    "text_light":  (255, 255, 255),
    "card_bg":     (255, 255, 255),
    "card_back":   ( 80, 130, 200),   # card face-down colour
    "shadow":      (  0,   0,   0, 60),
    "hud_bg":      ( 50,  50,  80),
    "overlay":     (  0,   0,   0, 160),
}


# ─────────────────────────────────────────────────────────────────────────────
# Button
# ─────────────────────────────────────────────────────────────────────────────

class Button:
    """A rounded rectangle button with hover, pressed, and disabled states.

    Parameters
    ----------
    rect       : (x, y, width, height)
    label      : text displayed on the button
    font_size  : point size of the label
    colour     : base background colour (defaults to theme primary)
    """

    def __init__(
        self,
        rect: Tuple[int, int, int, int],
        label: str,
        font_size: int = 30,
        colour: Optional[Tuple[int, int, int]] = None,
        text_colour: Optional[Tuple[int, int, int]] = None,
        enabled: bool = True,
        border_radius: int = 14,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font_size = font_size
        self.base_colour = colour or THEME["primary"]
        self.text_colour = text_colour or THEME["text_light"]
        self.enabled = enabled
        self.border_radius = border_radius

        self._hovered = False
        self._pressed = False
        self._font: Optional[pygame.font.Font] = None

        # Callbacks
        self.on_click: Optional[Callable[[], None]] = None

    # ── Internal ────────────────────────────────────────────────────────────

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            try:
                self._font = pygame.font.SysFont("Comic Sans MS", self.font_size, bold=True)
            except Exception:
                self._font = pygame.font.Font(None, self.font_size)
        return self._font

    def _current_colour(self) -> Tuple[int, int, int]:
        if not self.enabled:
            return (180, 180, 180)
        if self._pressed:
            return _darken(self.base_colour, 40)
        if self._hovered:
            return _lighten(self.base_colour, 30)
        return self.base_colour

    # ── Public API ──────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process a pygame event.  Returns True when the button is clicked."""
        if not self.enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                if self.on_click:
                    self.on_click()
                return True
            self._pressed = False
        return False

    def draw(self, screen: pygame.Surface) -> None:
        colour = self._current_colour()
        # Shadow
        shadow_rect = self.rect.move(3, 4)
        _draw_rounded_shadow(screen, shadow_rect, self.border_radius)
        # Body
        pygame.draw.rect(screen, colour, self.rect, border_radius=self.border_radius)
        # Outline
        outline_c = _darken(colour, 50)
        pygame.draw.rect(screen, outline_c, self.rect, 2, border_radius=self.border_radius)
        # Label
        font = self._get_font()
        text_surf = font.render(self.label, True, self.text_colour)
        text_rect = text_surf.get_rect(center=self.rect.center)
        if self._pressed:
            text_rect.move_ip(1, 1)
        screen.blit(text_surf, text_rect)

    def set_label(self, label: str) -> None:
        self.label = label


# ─────────────────────────────────────────────────────────────────────────────
# TextLabel
# ─────────────────────────────────────────────────────────────────────────────

class TextLabel:
    """Static or dynamic text, optionally with a drop shadow."""

    def __init__(
        self,
        text: str,
        pos: Tuple[int, int],
        font_size: int = 28,
        colour: Tuple[int, int, int] = THEME["text_dark"],  # type: ignore[assignment]
        shadow: bool = False,
        bold: bool = False,
        anchor: str = "topleft",   # topleft | center | midtop | etc.
    ) -> None:
        self.text = text
        self.pos = pos
        self.font_size = font_size
        self.colour = colour
        self.shadow = shadow
        self.bold = bold
        self.anchor = anchor
        self._font: Optional[pygame.font.Font] = None

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            try:
                self._font = pygame.font.SysFont(
                    "Comic Sans MS", self.font_size, bold=self.bold
                )
            except Exception:
                self._font = pygame.font.Font(None, self.font_size)
        return self._font

    def draw(self, screen: pygame.Surface) -> None:
        font = self._get_font()
        surf = font.render(self.text, True, self.colour)
        rect = surf.get_rect()
        setattr(rect, self.anchor, self.pos)

        if self.shadow:
            shadow_surf = font.render(self.text, True, (0, 0, 0))
            screen.blit(shadow_surf, rect.move(2, 2))

        screen.blit(surf, rect)

    def set_text(self, text: str) -> None:
        self.text = text


# ─────────────────────────────────────────────────────────────────────────────
# Counter  (animated number display)
# ─────────────────────────────────────────────────────────────────────────────

class Counter:
    """Displays an integer value with a short pop/scale animation on change."""

    def __init__(
        self,
        pos: Tuple[int, int],
        prefix: str = "Score: ",
        font_size: int = 32,
        colour: Tuple[int, int, int] = THEME["text_dark"],  # type: ignore[assignment]
    ) -> None:
        self.pos = pos
        self.prefix = prefix
        self.font_size = font_size
        self.colour = colour
        self._value: int = 0
        self._display_value: int = 0
        self._scale: float = 1.0
        self._anim_timer: float = 0.0
        self._font: Optional[pygame.font.Font] = None

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            try:
                self._font = pygame.font.SysFont("Comic Sans MS", self.font_size, bold=True)
            except Exception:
                self._font = pygame.font.Font(None, self.font_size)
        return self._font

    def set_value(self, value: int) -> None:
        if value != self._value:
            self._value = value
            self._anim_timer = 0.25   # 250 ms pop

    def update(self, dt: float) -> None:
        if self._anim_timer > 0:
            self._anim_timer = max(0, self._anim_timer - dt)
            t = self._anim_timer / 0.25
            self._scale = 1.0 + 0.4 * math.sin(t * math.pi)
        else:
            self._scale = 1.0
        self._display_value = self._value

    def draw(self, screen: pygame.Surface) -> None:
        font = self._get_font()
        text = f"{self.prefix}{self._display_value}"
        surf = font.render(text, True, self.colour)

        if self._scale != 1.0:
            new_w = int(surf.get_width() * self._scale)
            new_h = int(surf.get_height() * self._scale)
            surf = pygame.transform.scale(surf, (new_w, new_h))

        rect = surf.get_rect(center=self.pos)
        screen.blit(surf, rect)


# ─────────────────────────────────────────────────────────────────────────────
# Timer
# ─────────────────────────────────────────────────────────────────────────────

class Timer:
    """Elapsed-time tracker that can count up or count down."""

    def __init__(
        self,
        pos: Tuple[int, int],
        countdown: float = 0.0,   # 0 = count up; >0 = seconds to count down from
        font_size: int = 28,
        colour: Tuple[int, int, int] = THEME["text_dark"],  # type: ignore[assignment]
    ) -> None:
        self.pos = pos
        self.font_size = font_size
        self.colour = colour
        self._countdown = countdown
        self._elapsed: float = 0.0
        self._running: bool = False
        self._font: Optional[pygame.font.Font] = None

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            try:
                self._font = pygame.font.SysFont("Comic Sans MS", self.font_size, bold=True)
            except Exception:
                self._font = pygame.font.Font(None, self.font_size)
        return self._font

    # ── Control ─────────────────────────────────────────────────────────────
    def start(self) -> None:   self._running = True
    def stop(self) -> None:    self._running = False
    def reset(self) -> None:   self._elapsed = 0.0

    def update(self, dt: float) -> None:
        if self._running:
            self._elapsed += dt

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def remaining(self) -> float:
        """Seconds remaining for countdown timers; 0 when expired."""
        if self._countdown > 0:
            return max(0.0, self._countdown - self._elapsed)
        return 0.0

    @property
    def expired(self) -> bool:
        return self._countdown > 0 and self._elapsed >= self._countdown

    def _format(self, seconds: float) -> str:
        s = int(seconds)
        m, s2 = divmod(s, 60)
        return f"{m:02d}:{s2:02d}"

    def draw(self, screen: pygame.Surface, label: str = "Time: ") -> None:
        display = self.remaining if self._countdown > 0 else self._elapsed
        text = f"{label}{self._format(display)}"
        colour = self.colour
        if self._countdown > 0 and self.remaining < 10:
            colour = THEME["danger"]
        font = self._get_font()
        surf = font.render(text, True, colour)
        rect = surf.get_rect(center=self.pos)
        screen.blit(surf, rect)


# ─────────────────────────────────────────────────────────────────────────────
# CardFlip  (memory-match card flip animation)
# ─────────────────────────────────────────────────────────────────────────────

class CardFlip:
    """Manages a 3-D flip animation by scaling the card width.

    Usage
    -----
        flip = CardFlip()
        flip.start(to_front=True)   # begin flipping to face-up
        # each frame:
        flip.update(dt)
        # render:
        scale_x, show_front = flip.render_state()
        # draw either front or back surface, stretched by scale_x
    """

    SPEED = 3.5   # full flips per second

    def __init__(self) -> None:
        self._progress: float = 0.0    # 0.0 = fully back, 1.0 = fully front
        self._animating: bool = False
        self._direction: int = 1        # +1 flip to front, -1 flip to back

    def start(self, to_front: bool = True) -> None:
        self._direction = 1 if to_front else -1
        self._animating = True

    def update(self, dt: float) -> None:
        if not self._animating:
            return
        self._progress += self._direction * self.SPEED * dt
        if self._progress >= 1.0:
            self._progress = 1.0
            self._animating = False
        elif self._progress <= 0.0:
            self._progress = 0.0
            self._animating = False

    @property
    def animating(self) -> bool:
        return self._animating

    @property
    def face_up(self) -> bool:
        return self._progress >= 0.5

    def render_state(self) -> Tuple[float, bool]:
        """Return (scale_x, show_front).

        ``scale_x`` is the horizontal scale factor to apply to the card
        surface; it goes 1 → 0 → 1 during the animation.
        ``show_front`` tells you which face to draw.
        """
        scale_x = abs(math.cos(self._progress * math.pi))
        show_front = self._progress >= 0.5
        return max(0.01, scale_x), show_front


# ─────────────────────────────────────────────────────────────────────────────
# AnimationQueue  (generic property tweener)
# ─────────────────────────────────────────────────────────────────────────────

class Tween:
    """Linear or ease-in-out tween of a single float property."""

    def __init__(
        self,
        target: dict,
        key: str,
        end: float,
        duration: float,
        easing: str = "ease_out",
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.target = target
        self.key = key
        self.start_val: float = target[key]
        self.end_val = end
        self.duration = duration
        self.easing = easing
        self.on_done = on_done
        self._elapsed: float = 0.0
        self.done: bool = False

    def update(self, dt: float) -> None:
        if self.done:
            return
        self._elapsed += dt
        t = min(1.0, self._elapsed / self.duration)
        t_eased = _ease(t, self.easing)
        self.target[self.key] = self.start_val + (self.end_val - self.start_val) * t_eased
        if t >= 1.0:
            self.done = True
            if self.on_done:
                self.on_done()


class AnimationQueue:
    """Runs a list of Tweens sequentially."""

    def __init__(self) -> None:
        self._queue: List[Tween] = []
        self._current: Optional[Tween] = None

    def add(self, tween: Tween) -> "AnimationQueue":
        self._queue.append(tween)
        return self

    def update(self, dt: float) -> None:
        if self._current is None or self._current.done:
            if self._queue:
                self._current = self._queue.pop(0)
        if self._current and not self._current.done:
            self._current.update(dt)

    @property
    def idle(self) -> bool:
        return self._current is None or (self._current.done and not self._queue)


# ─────────────────────────────────────────────────────────────────────────────
# ProgressBar
# ─────────────────────────────────────────────────────────────────────────────

class ProgressBar:
    def __init__(
        self,
        rect: Tuple[int, int, int, int],
        colour: Tuple[int, int, int] = THEME["success"],  # type: ignore[assignment]
        bg_colour: Tuple[int, int, int] = (200, 200, 200),
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.colour = colour
        self.bg_colour = bg_colour
        self._value: float = 0.0    # 0.0 – 1.0

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(1.0, value))

    def draw(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, self.bg_colour, self.rect, border_radius=8)
        if self._value > 0:
            filled = pygame.Rect(
                self.rect.x, self.rect.y,
                int(self.rect.width * self._value), self.rect.height
            )
            pygame.draw.rect(screen, self.colour, filled, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 2, border_radius=8)


# ─────────────────────────────────────────────────────────────────────────────
# ConfirmDialog
# ─────────────────────────────────────────────────────────────────────────────

class ConfirmDialog:
    """A modal Yes/No overlay panel.

    Usage
    -----
        dialog = ConfirmDialog(screen_size, "Quit to menu?")
        # In render: if dialog.visible: dialog.draw(screen)
        # In events: dialog.handle_event(event) → True/False/None
    """

    def __init__(
        self,
        screen_size: Tuple[int, int],
        message: str,
        yes_label: str = "Yes",
        no_label: str = "No",
    ) -> None:
        sw, sh = screen_size
        w, h = 420, 220
        x, y = (sw - w) // 2, (sh - h) // 2
        self.rect = pygame.Rect(x, y, w, h)
        self.message = message
        self.visible: bool = False

        btn_w, btn_h = 140, 50
        self._yes_btn = Button(
            (x + 40, y + 130, btn_w, btn_h), yes_label, 26, THEME["success"]
        )
        self._no_btn = Button(
            (x + w - 40 - btn_w, y + 130, btn_w, btn_h), no_label, 26, THEME["danger"]
        )
        self._font: Optional[pygame.font.Font] = None

    def _get_font(self, size: int = 28) -> pygame.font.Font:
        try:
            return pygame.font.SysFont("Comic Sans MS", size, bold=True)
        except Exception:
            return pygame.font.Font(None, size)

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def handle_event(self, event: pygame.event.Event) -> Optional[bool]:
        """Returns True (yes), False (no), or None (no action)."""
        if not self.visible:
            return None
        if self._yes_btn.handle_event(event):
            self.visible = False
            return True
        if self._no_btn.handle_event(event):
            self.visible = False
            return False
        return None

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        # Dim overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        # Panel
        pygame.draw.rect(screen, THEME["card_bg"], self.rect, border_radius=18)
        pygame.draw.rect(screen, THEME["secondary"], self.rect, 3, border_radius=18)
        # Message
        font = self._get_font(28)
        txt = font.render(self.message, True, THEME["text_dark"])
        screen.blit(txt, txt.get_rect(center=(self.rect.centerx, self.rect.y + 70)))
        # Buttons
        self._yes_btn.draw(screen)
        self._no_btn.draw(screen)


# ─────────────────────────────────────────────────────────────────────────────
# Particle / celebration effect
# ─────────────────────────────────────────────────────────────────────────────

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "colour", "radius", "life", "max_life")

    def __init__(self, x: float, y: float, colour: Tuple[int, int, int]) -> None:
        import random
        angle = random.uniform(0, math.tau)
        speed = random.uniform(60, 280)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - 120
        self.colour = colour
        self.radius = random.randint(5, 10)
        self.max_life = random.uniform(0.6, 1.2)
        self.life = self.max_life

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 400 * dt   # gravity
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, screen: pygame.Surface) -> None:
        alpha = int(255 * (self.life / self.max_life))
        r = max(1, int(self.radius * (self.life / self.max_life)))
        colour = (*self.colour, alpha)
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, colour, (r, r), r)
        screen.blit(surf, (int(self.x) - r, int(self.y) - r))


class ParticleSystem:
    """Celebration burst of coloured particles."""

    COLOURS = [
        (255, 80, 80), (80, 200, 80), (80, 120, 255),
        (255, 220, 30), (255, 100, 200), (80, 220, 220),
    ]

    def __init__(self) -> None:
        self._particles: List[Particle] = []

    def burst(self, x: float, y: float, count: int = 30) -> None:
        import random
        for _ in range(count):
            colour = random.choice(self.COLOURS)
            self._particles.append(Particle(x, y, colour))

    def update(self, dt: float) -> None:
        for p in self._particles:
            p.update(dt)
        self._particles = [p for p in self._particles if p.alive]

    def draw(self, screen: pygame.Surface) -> None:
        for p in self._particles:
            p.draw(screen)

    @property
    def active(self) -> bool:
        return bool(self._particles)


# ─────────────────────────────────────────────────────────────────────────────
# Standalone draw_hud  (called by GameFramework.draw_hud_bar)
# ─────────────────────────────────────────────────────────────────────────────

def draw_hud(
    screen: pygame.Surface,
    score: int,
    level: int,
    extra_text: str,
    screen_width: int,
    height: int = 52,
) -> None:
    """Draw a top HUD bar common to all games."""
    pygame.draw.rect(screen, THEME["hud_bg"], (0, 0, screen_width, height))
    pygame.draw.line(screen, THEME["secondary"], (0, height), (screen_width, height), 2)

    try:
        font = pygame.font.SysFont("Comic Sans MS", 24, bold=True)
    except Exception:
        font = pygame.font.Font(None, 28)

    col = THEME["text_light"]
    score_surf = font.render(f"Score: {score}", True, col)
    screen.blit(score_surf, (14, (height - score_surf.get_height()) // 2))

    level_surf = font.render(f"Level {level}", True, THEME["warning"])
    screen.blit(level_surf, (screen_width // 2 - level_surf.get_width() // 2,
                              (height - level_surf.get_height()) // 2))

    if extra_text:
        ex_surf = font.render(extra_text, True, col)
        screen.blit(ex_surf, (screen_width - ex_surf.get_width() - 14,
                               (height - ex_surf.get_height()) // 2))


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _draw_rounded_shadow(
    surface: pygame.Surface, rect: pygame.Rect, radius: int
) -> None:
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 50), s.get_rect(), border_radius=radius)
    surface.blit(s, rect.topleft)


def _darken(colour: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
    return tuple(max(0, c - amount) for c in colour)  # type: ignore[return-value]


def _lighten(colour: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
    return tuple(min(255, c + amount) for c in colour)  # type: ignore[return-value]


def _ease(t: float, mode: str) -> float:
    if mode == "linear":
        return t
    if mode == "ease_in":
        return t * t
    if mode == "ease_out":
        return 1 - (1 - t) ** 2
    # ease_in_out
    return t * t * (3 - 2 * t)

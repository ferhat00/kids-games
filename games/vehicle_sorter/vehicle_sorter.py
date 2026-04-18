"""
VehicleSorterGame — Sort falling vehicles into the correct category bins.

Gameplay
--------
A vehicle appears at the top of the screen and slowly drifts downward.
Three large category bins sit at the bottom:
    🚗 ROAD (cars, trucks, buses, motorcycles, bicycles, ambulances, firetrucks)
    ✈ AIR  (airplanes, helicopters, rockets, balloons)
    🌊 WATER/RAIL (trains, ships, sailboats, submarines)

The player clicks the correct bin (or presses 1/2/3).
    • Correct  → celebration animation, score +100 (+ speed bonus), next vehicle
    • Wrong    → gentle "oops" shake, no penalty, same vehicle, try again

Difficulty levels
-----------------
    Level 1 : 3 vehicles per category (slow drop speed, generous target area)
    Level 2 : 4 per category, slight speed increase
    Level 3 : all vehicles available, fast drop, visible timer per vehicle
Advances to next level every 10 correct sorts.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

import pygame

from framework.game_framework import GameFramework
from framework.asset_manager import AssetManager
from framework.ui_components import (
    Button, Counter, ParticleSystem, ProgressBar, THEME
)

# ─────────────────────────────────────────────────────────────────────────────
# Category definitions
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES: List[Dict] = [
    {
        "id":       "road",
        "label":    "ROAD",
        "emoji":    "🚗",
        "colour":   (255, 107,  53),   # orange-red
        "vehicles": ["car", "truck", "bus", "motorcycle", "bicycle",
                     "ambulance", "firetruck"],
        "key":      pygame.K_1,
    },
    {
        "id":       "air",
        "label":    "AIR",
        "emoji":    "✈",
        "colour":   ( 78, 160, 230),   # sky blue
        "vehicles": ["airplane", "helicopter", "rocket", "balloon"],
        "key":      pygame.K_2,
    },
    {
        "id":       "water",
        "label":    "WATER",
        "emoji":    "🌊",
        "colour":   ( 40, 180, 140),   # teal-green
        "vehicles": ["train", "ship", "sailboat", "submarine"],
        "key":      pygame.K_3,
    },
]

# Build lookup: vehicle → category id
_VEH_TO_CAT: Dict[str, str] = {}
for _cat in CATEGORIES:
    for _v in _cat["vehicles"]:
        _VEH_TO_CAT[_v] = _cat["id"]

# Level configuration
LEVEL_CFG = {
    1: {"pool": 3,  "speed": 55,  "time_per": 0},
    2: {"pool": 5,  "speed": 90,  "time_per": 0},
    3: {"pool": 7,  "speed": 140, "time_per": 10},
}
CORRECT_PER_LEVEL = 10   # sorts to advance a level

# Layout
HUD_H    = 52
BIN_H    = 140
BIN_PAD  = 16
VEH_SIZE = (160, 140)
VEHICLE_X_RANGE = (0.2, 0.8)   # fraction of screen width

# Colours
SKY_TOP  = (135, 206, 235)
SKY_BOT  = (200, 230, 255)
GROUND_C = ( 90, 160,  70)


# ─────────────────────────────────────────────────────────────────────────────
# FallingVehicle
# ─────────────────────────────────────────────────────────────────────────────

class FallingVehicle:
    """A vehicle that drifts downward until sorted or landed."""

    def __init__(
        self,
        vehicle_type: str,
        surf: pygame.Surface,
        x: float,
        speed: float,
        screen_h: int,
    ) -> None:
        self.vehicle_type = vehicle_type
        self.category = _VEH_TO_CAT.get(vehicle_type, "road")
        self.surf = surf
        self.x = x
        self.y = float(HUD_H + 10)
        self.speed = speed

        # Gentle horizontal sway
        self._sway_freq = random.uniform(0.6, 1.2)
        self._sway_amp  = random.uniform(8, 22)
        self._sway_t    = random.uniform(0, math.tau)
        self._base_x    = x

        # Animation state
        self.sorted_to: Optional[str] = None   # category id when sorted
        self.anim_vx: float = 0.0
        self.anim_vy: float = 0.0
        self.anim_scale: float = 1.0
        self.anim_alpha: int = 255
        self.done: bool = False

        # Shake (wrong answer)
        self._shake_t:  float = 0.0
        self._shaking:  bool  = False

    def update(self, dt: float) -> None:
        if self.sorted_to:
            # Fly toward the correct bin
            self.anim_scale = max(0.1, self.anim_scale - dt * 2.5)
            self.anim_alpha = max(0, int(255 * self.anim_scale))
            self.x += self.anim_vx * dt
            self.y += self.anim_vy * dt
            if self.anim_scale <= 0.1:
                self.done = True
            return

        if self._shaking:
            self._shake_t -= dt
            if self._shake_t <= 0:
                self._shaking = False
        else:
            # Normal fall with sway
            self._sway_t += dt
            self.x = self._base_x + self._sway_amp * math.sin(self._sway_t * self._sway_freq)
            self.y += self.speed * dt

    @property
    def rect(self) -> pygame.Rect:
        w, h = self.surf.get_size()
        return pygame.Rect(int(self.x) - w // 2, int(self.y), w, h)

    def shake(self) -> None:
        self._shaking = True
        self._shake_t = 0.4

    def start_sort_animation(self, target_cx: float, target_cy: float) -> None:
        dx = target_cx - self.x
        dy = target_cy - self.y
        speed = 400.0
        dist = math.hypot(dx, dy) or 1
        self.anim_vx = dx / dist * speed
        self.anim_vy = dy / dist * speed
        self.sorted_to = self.category

    def draw(self, screen: pygame.Surface) -> None:
        surf = self.surf
        if self.anim_scale != 1.0:
            new_w = max(1, int(surf.get_width()  * self.anim_scale))
            new_h = max(1, int(surf.get_height() * self.anim_scale))
            surf = pygame.transform.smoothscale(surf, (new_w, new_h))
        if self.anim_alpha < 255:
            surf = surf.copy()
            surf.set_alpha(self.anim_alpha)

        # Shake offset
        shake_x = 0
        if self._shaking:
            shake_x = int(math.sin(self._shake_t * 50) * 10)

        w, h = surf.get_size()
        screen.blit(surf, (int(self.x) - w // 2 + shake_x, int(self.y)))


# ─────────────────────────────────────────────────────────────────────────────
# Bin
# ─────────────────────────────────────────────────────────────────────────────

class Bin:
    """One of the three category bins at the bottom."""

    def __init__(self, rect: pygame.Rect, category: Dict) -> None:
        self.rect = rect
        self.category = category
        self._hovered = False
        self._flash_t: float = 0.0   # >0 when briefly highlighted (correct sort)
        self._correct_flash = False
        try:
            self._label_font = pygame.font.SysFont("Comic Sans MS", 28, bold=True)
            self._emoji_font = pygame.font.SysFont("Segoe UI Emoji", 36)
        except Exception:
            self._label_font = pygame.font.Font(None, 32)
            self._emoji_font = pygame.font.Font(None, 40)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def flash_correct(self) -> None:
        self._flash_t = 0.5
        self._correct_flash = True

    def flash_wrong(self) -> None:
        self._flash_t = 0.3
        self._correct_flash = False

    def update(self, dt: float) -> None:
        if self._flash_t > 0:
            self._flash_t = max(0, self._flash_t - dt)

    def draw(self, screen: pygame.Surface) -> None:
        base = self.category["colour"]

        if self._flash_t > 0:
            t = self._flash_t / 0.5
            if self._correct_flash:
                colour = _lerp_colour(base, (100, 255, 100), t)
            else:
                colour = _lerp_colour(base, (255, 80, 80), t)
        elif self._hovered:
            colour = tuple(min(255, c + 40) for c in base)
        else:
            colour = base

        # Shadow
        s = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, 50), s.get_rect().move(4, 4), border_radius=16)
        screen.blit(s, self.rect.move(0, 4))

        # Body
        pygame.draw.rect(screen, colour, self.rect, border_radius=16)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, 3, border_radius=16)

        # Emoji
        try:
            emoji_surf = self._emoji_font.render(self.category["emoji"], True, (255, 255, 255))
            screen.blit(emoji_surf, (
                self.rect.centerx - emoji_surf.get_width() // 2,
                self.rect.y + 14,
            ))
        except Exception:
            pass

        # Label
        label_surf = self._label_font.render(self.category["label"], True, (255, 255, 255))
        screen.blit(label_surf, (
            self.rect.centerx - label_surf.get_width() // 2,
            self.rect.y + 62,
        ))

        # Keyboard hint
        try:
            hint_font = pygame.font.SysFont("Comic Sans MS", 16)
        except Exception:
            hint_font = pygame.font.Font(None, 18)
        key_hint = hint_font.render(f"[{self.category['key'] - pygame.K_0}]", True, (220, 220, 220))
        screen.blit(key_hint, (
            self.rect.centerx - key_hint.get_width() // 2,
            self.rect.bottom - 22,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# VehicleSorterGame
# ─────────────────────────────────────────────────────────────────────────────

class VehicleSorterGame(GameFramework):
    """Sort falling vehicles into ROAD / AIR / WATER bins."""

    def get_game_info(self) -> dict:
        return {
            "title":           "Vehicle Sorter",
            "description":     "Sort vehicles into the right bins!",
            "thumbnail_color":  THEME["secondary"],
            "vehicle_types":   ["airplane", "car", "train"],
        }

    # ── Setup ──────────────────────────────────────────────────────────────
    def setup(self) -> None:
        self._score       = 0
        self._level       = 1
        self._correct_streak = 0
        self._correct_this_level = 0
        self._total_sorted = 0

        self._vehicle:   Optional[FallingVehicle] = None
        self._particles = ParticleSystem()

        # Bins
        self._bins = self._build_bins()

        # Pre-cache vehicle surfaces
        self._veh_surfs: Dict[str, pygame.Surface] = {}
        self._pool: List[str] = []
        self._update_pool()

        # Level progress bar
        self._level_bar = ProgressBar(
            (HUD_H, self.height - BIN_H - 30, self.width - HUD_H * 2, 16),
            colour=THEME["warning"],
        )

        # "Oops" / "Great!" feedback text
        self._feedback_text: str = ""
        self._feedback_t: float = 0.0
        self._feedback_correct: bool = True

        # Buttons
        self._back_btn = Button(
            (self.width - 110, 8, 100, 36), "Menu", 20, THEME["secondary"]
        )
        self._back_btn.on_click = self.exit
        self._reset_btn = Button(
            (self.width - 220, 8, 100, 36), "Restart", 20, THEME["primary"]
        )
        self._reset_btn.on_click = self.reset

        # Fonts
        try:
            self._hud_font  = pygame.font.SysFont("Comic Sans MS", 24, bold=True)
            self._fb_font   = pygame.font.SysFont("Comic Sans MS", 44, bold=True)
            self._info_font = pygame.font.SysFont("Comic Sans MS", 20)
        except Exception:
            self._hud_font  = pygame.font.Font(None, 28)
            self._fb_font   = pygame.font.Font(None, 50)
            self._info_font = pygame.font.Font(None, 24)

        # Spawn first vehicle
        self._spawn_vehicle()

    # ── Input ──────────────────────────────────────────────────────────────
    def handle_input(self, event: pygame.event.Event) -> None:
        self._back_btn.handle_event(event)
        self._reset_btn.handle_event(event)

        if self._vehicle is None or self._vehicle.sorted_to:
            return

        # Bin click
        for i, bin_ in enumerate(self._bins):
            if bin_.handle_event(event):
                self._try_sort(i)
                return

        # Keyboard shortcut: 1/2/3
        if event.type == pygame.KEYDOWN:
            for i, cat in enumerate(CATEGORIES):
                if event.key == cat["key"]:
                    self._try_sort(i)
                    return

    # ── Update ─────────────────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        self._particles.update(dt)
        for bin_ in self._bins:
            bin_.update(dt)

        if self._feedback_t > 0:
            self._feedback_t = max(0, self._feedback_t - dt)

        if self._vehicle:
            self._vehicle.update(dt)
            # Vehicle escaped off the bottom (no sort) → gently put it back at top
            if not self._vehicle.sorted_to and self._vehicle.y > self.height - BIN_H - VEH_SIZE[1] - 10:
                self._vehicle.y = float(HUD_H + 10)
            # Done animating sort → spawn next
            if self._vehicle.done:
                self._vehicle = None
                self._spawn_vehicle()

        # Level progress bar
        self._level_bar.set_value(self._correct_this_level / CORRECT_PER_LEVEL)

    # ── Render ─────────────────────────────────────────────────────────────
    def render(self, screen: pygame.Surface) -> None:
        # Sky gradient
        for y in range(self.height):
            t = y / self.height
            r = int(SKY_TOP[0] + (SKY_BOT[0] - SKY_TOP[0]) * t)
            g = int(SKY_TOP[1] + (SKY_BOT[1] - SKY_TOP[1]) * t)
            b = int(SKY_TOP[2] + (SKY_BOT[2] - SKY_TOP[2]) * t)
            pygame.draw.line(screen, (r, g, b), (0, y), (self.width, y))

        # Ground strip above bins
        ground_y = self.height - BIN_H - 20
        pygame.draw.rect(screen, GROUND_C, (0, ground_y, self.width, 20))
        # Grass details
        for gx in range(0, self.width, 30):
            pygame.draw.line(screen, (60, 140, 50), (gx, ground_y), (gx + 8, ground_y - 10), 3)
            pygame.draw.line(screen, (60, 140, 50), (gx + 5, ground_y), (gx + 5, ground_y - 14), 3)

        # Bins
        for bin_ in self._bins:
            bin_.draw(screen)

        # Vehicle
        if self._vehicle:
            self._vehicle.draw(screen)

        # Category label above the vehicle
        if self._vehicle and not self._vehicle.sorted_to:
            self._draw_vehicle_label(screen)

        # Particles
        self._particles.draw(screen)

        # Feedback text
        if self._feedback_t > 0:
            alpha = int(255 * min(1.0, self._feedback_t / 0.3))
            colour = (80, 220, 80) if self._feedback_correct else (220, 80, 80)
            fb_surf = self._fb_font.render(self._feedback_text, True, colour)
            fb_surf.set_alpha(alpha)
            screen.blit(fb_surf, (
                self.width // 2 - fb_surf.get_width() // 2,
                self.height // 2 - 80,
            ))

        # HUD
        self.draw_hud_bar(screen, self._score, self._level,
                          f"Sorted: {self._total_sorted}")

        # Buttons
        self._back_btn.draw(screen)
        self._reset_btn.draw(screen)

        # Level progress bar
        self._level_bar.draw(screen)
        prog_label = self._info_font.render(
            f"Level progress: {self._correct_this_level}/{CORRECT_PER_LEVEL}", True, (60, 60, 80)
        )
        screen.blit(prog_label, (HUD_H, self.height - BIN_H - 52))

        # Hint
        hint = self._info_font.render(
            "Click a bin or press 1 / 2 / 3", True, (80, 80, 100)
        )
        screen.blit(hint, (
            self.width // 2 - hint.get_width() // 2,
            self.height - BIN_H - 52,
        ))

    # ── Internal helpers ───────────────────────────────────────────────────

    def _try_sort(self, bin_index: int) -> None:
        if self._vehicle is None or self._vehicle.sorted_to:
            return

        chosen_cat = CATEGORIES[bin_index]
        correct = chosen_cat["id"] == self._vehicle.category
        bin_ = self._bins[bin_index]

        if correct:
            # Score: base + speed bonus (level * 20)
            bonus = self._level * 20
            self._score += 100 + bonus
            self._correct_streak += 1
            self._correct_this_level += 1
            self._total_sorted += 1
            self._completion = self._total_sorted / 100.0

            bin_.flash_correct()
            self._particles.burst(
                bin_.rect.centerx, bin_.rect.centery, 30
            )
            self._feedback_text = random.choice(["Great! ✓", "Correct! ✓", "Nice! ✓", "Woo! ✓"])
            self._feedback_correct = True
            self._feedback_t = 1.0

            # Start fly-to-bin animation
            self._vehicle.start_sort_animation(bin_.rect.centerx, bin_.rect.centery)

            # Level up
            if self._correct_this_level >= CORRECT_PER_LEVEL:
                self._level = min(self._level + 1, max(LEVEL_CFG.keys()))
                self._correct_this_level = 0
                self._update_pool()
        else:
            self._correct_streak = 0
            bin_.flash_wrong()
            self._vehicle.shake()
            self._feedback_text = random.choice(["Oops! Try again!", "Not quite!", "Try again!"])
            self._feedback_correct = False
            self._feedback_t = 1.0

    def _spawn_vehicle(self) -> None:
        if not self._pool:
            self._update_pool()
        vehicle_type = random.choice(self._pool)

        if vehicle_type not in self._veh_surfs:
            self._veh_surfs[vehicle_type] = self.assets.generate_vehicle(vehicle_type, VEH_SIZE)

        cfg = LEVEL_CFG.get(self._level, LEVEL_CFG[3])
        speed = cfg["speed"] + random.uniform(-10, 10)

        x_frac = random.uniform(*VEHICLE_X_RANGE)
        x = self.width * x_frac

        self._vehicle = FallingVehicle(
            vehicle_type=vehicle_type,
            surf=self._veh_surfs[vehicle_type],
            x=x,
            speed=speed,
            screen_h=self.height,
        )

    def _update_pool(self) -> None:
        cfg = LEVEL_CFG.get(self._level, LEVEL_CFG[3])
        pool_size = cfg["pool"]
        self._pool = []
        for cat in CATEGORIES:
            self._pool.extend(cat["vehicles"][:pool_size])

    def _build_bins(self) -> List[Bin]:
        n = len(CATEGORIES)
        total_pad = BIN_PAD * (n + 1)
        bin_w = (self.width - total_pad) // n
        bin_h = BIN_H
        y = self.height - bin_h - 4
        bins = []
        for i, cat in enumerate(CATEGORIES):
            x = BIN_PAD + i * (bin_w + BIN_PAD)
            rect = pygame.Rect(x, y, bin_w, bin_h)
            bins.append(Bin(rect, cat))
        return bins

    def _draw_vehicle_label(self, screen: pygame.Surface) -> None:
        """Draw the vehicle's name and a subtle category hint above it."""
        veh = self._vehicle
        vw, vh = veh.surf.get_size()
        label_x = int(veh.x)
        label_y = int(veh.y) - 28

        name = veh.vehicle_type.replace("_", " ").title()
        name_surf = self._hud_font.render(name, True, (40, 40, 80))
        # Shadow
        shadow = self._hud_font.render(name, True, (0, 0, 0))
        screen.blit(shadow, (label_x - name_surf.get_width() // 2 + 2, label_y + 2))
        screen.blit(name_surf, (label_x - name_surf.get_width() // 2, label_y))

    def get_game_state(self) -> dict:
        return {
            "score":      self._score,
            "level":      self._level,
            "completion": min(1.0, self._completion),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Colour helper
# ─────────────────────────────────────────────────────────────────────────────

def _lerp_colour(
    a: Tuple[int, int, int],
    b: Tuple[int, int, int],
    t: float,
) -> Tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]

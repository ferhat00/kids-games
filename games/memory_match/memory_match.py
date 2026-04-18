"""
MemoryMatchGame — Classic memory/concentration card game with vehicles.

Grid:     4 × 4 = 16 cards = 8 matched pairs
Controls: Mouse click to flip cards
Scoring:  Fewer turns = higher score;  time bonus applied at completion
Levels:   Level 1 = 8 unique vehicles  (4×4)
          (Level 2/3 could expand to 5×4 or 5×6 with minor setup() changes)
"""

from __future__ import annotations

import math
import random
import time
from typing import List, Optional, Tuple

import pygame

from framework.game_framework import GameFramework
from framework.asset_manager import AssetManager
from framework.ui_components import (
    Button, TextLabel, Counter, Timer,
    ParticleSystem, CardFlip, ConfirmDialog, THEME
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

GAME_ID = "memory_match"

# Vehicle types used for the 8 pairs
VEHICLES_POOL = [
    "car", "truck", "bus", "airplane",
    "helicopter", "rocket", "train", "ship",
    # Extras for larger grids / future levels
    "sailboat", "motorcycle", "bicycle", "balloon",
]

# Grid
GRID_COLS = 4
GRID_ROWS = 4
CARD_W = 130
CARD_H = 110
CARD_PAD = 12
HUD_H   = 52   # height of top HUD bar

# Colours
CARD_BACK_TOP    = ( 70, 120, 210)
CARD_BACK_BOT    = ( 40,  80, 160)
CARD_FRONT_BG    = (255, 255, 255)
CARD_MATCHED_BG  = (200, 255, 200)
CARD_BORDER      = ( 30,  30,  30)
BG_TOP           = (180, 220, 255)
BG_BOT           = (240, 250, 255)

# Timing
MISMATCH_SHOW_SECS = 1.0   # how long to show a mismatched pair before flipping back
VICTORY_DELAY      = 1.5   # seconds before returning to menu after winning


# ─────────────────────────────────────────────────────────────────────────────
# Card  (data + animation)
# ─────────────────────────────────────────────────────────────────────────────

class Card:
    """Represents one card on the grid."""

    def __init__(self, vehicle: str, col: int, row: int, x: int, y: int) -> None:
        self.vehicle = vehicle
        self.col = col
        self.row = row
        self.x = x
        self.y = y

        self.matched = False
        self.flip = CardFlip()     # manages the 3-D flip animation

        # Wobble on match
        self._wobble_t: float = 0.0
        self._wobble_on: bool = False

        # Pre-baked surfaces (set by MemoryMatchGame.setup)
        self.front_surf: Optional[pygame.Surface] = None
        self.back_surf:  Optional[pygame.Surface] = None

    @property
    def face_up(self) -> bool:
        return self.flip.face_up

    def start_flip_up(self) -> None:
        if not self.flip.face_up and not self.flip.animating:
            self.flip.start(to_front=True)

    def start_flip_down(self) -> None:
        if self.flip.face_up and not self.flip.animating:
            self.flip.start(to_front=False)

    def trigger_wobble(self) -> None:
        self._wobble_on = True
        self._wobble_t = 0.0

    def update(self, dt: float) -> None:
        self.flip.update(dt)
        if self._wobble_on:
            self._wobble_t += dt
            if self._wobble_t > 0.5:
                self._wobble_on = False

    def draw(self, screen: pygame.Surface) -> None:
        scale_x, show_front = self.flip.render_state()

        # Wobble rotation
        angle = 0.0
        if self._wobble_on:
            angle = math.sin(self._wobble_t * 25) * 8 * (1 - self._wobble_t / 0.5)

        surf = self.front_surf if show_front else self.back_surf
        if surf is None:
            return

        # Scale width for flip effect
        new_w = max(2, int(CARD_W * scale_x))
        scaled = pygame.transform.scale(surf, (new_w, CARD_H))

        # Rotate for wobble
        if angle:
            scaled = pygame.transform.rotate(scaled, angle)

        # Centre on the card's grid position
        cx = self.x + CARD_W // 2
        cy = self.y + CARD_H // 2
        dest_rect = scaled.get_rect(center=(cx, cy))
        screen.blit(scaled, dest_rect)

    # ── Surface builders (called once in setup) ──────────────────────────────

    def build_back(self) -> pygame.Surface:
        surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        # Gradient background
        for y in range(CARD_H):
            t = y / CARD_H
            r = int(CARD_BACK_TOP[0] + (CARD_BACK_BOT[0] - CARD_BACK_TOP[0]) * t)
            g = int(CARD_BACK_TOP[1] + (CARD_BACK_BOT[1] - CARD_BACK_TOP[1]) * t)
            b = int(CARD_BACK_TOP[2] + (CARD_BACK_BOT[2] - CARD_BACK_TOP[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (CARD_W, y))
        pygame.draw.rect(surf, CARD_BORDER, (0, 0, CARD_W, CARD_H), 2, border_radius=12)
        # Question mark decoration
        try:
            font = pygame.font.SysFont("Comic Sans MS", 52, bold=True)
        except Exception:
            font = pygame.font.Font(None, 60)
        q = font.render("?", True, (255, 255, 255))
        surf.blit(q, (CARD_W // 2 - q.get_width() // 2, CARD_H // 2 - q.get_height() // 2))
        return surf

    def build_front(self, vehicle_surf: pygame.Surface, matched: bool = False) -> pygame.Surface:
        bg = CARD_MATCHED_BG if matched else CARD_FRONT_BG
        surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        pygame.draw.rect(surf, bg, (0, 0, CARD_W, CARD_H), border_radius=12)
        pygame.draw.rect(surf, CARD_BORDER, (0, 0, CARD_W, CARD_H), 2, border_radius=12)
        # Centre vehicle image
        margin = 10
        max_w, max_h = CARD_W - margin * 2, CARD_H - margin * 2 - 18
        veh = pygame.transform.smoothscale(vehicle_surf, (max_w, max_h))
        surf.blit(veh, (margin, margin))
        # Vehicle name label
        try:
            lbl_font = pygame.font.SysFont("Comic Sans MS", 14, bold=True)
        except Exception:
            lbl_font = pygame.font.Font(None, 16)
        name = vehicle_surf.get_size()   # just a placeholder; use card.vehicle
        return surf


# ─────────────────────────────────────────────────────────────────────────────
# MemoryMatchGame
# ─────────────────────────────────────────────────────────────────────────────

class MemoryMatchGame(GameFramework):
    """4×4 vehicle memory card matching game."""

    # ── GameFramework metadata ─────────────────────────────────────────────
    def get_game_info(self) -> dict:
        return {
            "title":          "Memory Match",
            "description":    "Find matching vehicle pairs!",
            "thumbnail_color": THEME["primary"],
            "vehicle_types":  ["car", "airplane", "train"],
        }

    # ── Setup ──────────────────────────────────────────────────────────────
    def setup(self) -> None:
        self._score = 0
        self._level = 1
        self._turns = 0
        self._matches_found = 0
        self._total_pairs = (GRID_COLS * GRID_ROWS) // 2

        self._selected: List[Card] = []    # 0, 1, or 2 flipped-up cards
        self._mismatch_timer: float = 0.0
        self._victory: bool = False
        self._victory_timer: float = 0.0

        self._particles = ParticleSystem()

        # Build card grid
        self._cards: List[Card] = self._build_cards()

        # Load (or generate) vehicle surfaces once
        self._vehicle_surfs = {}
        for v in VEHICLES_POOL[:self._total_pairs]:
            self._vehicle_surfs[v] = self.assets.generate_vehicle(v, (CARD_W - 20, CARD_H - 30))

        # Bake each card's front/back surfaces
        for card in self._cards:
            card.back_surf  = card.build_back()
            front_surf = self._vehicle_surfs[card.vehicle]
            card.front_surf = self._build_front_surface(card.vehicle, front_surf)

        # UI widgets
        cx = self.width // 2
        self._turns_counter = Counter((cx - 140, HUD_H // 2 + 4), "Turns: ", 26)
        self._match_counter = Counter((cx + 140, HUD_H // 2 + 4), "Matched: ", 26)
        self._timer = Timer((cx, HUD_H // 2 + 4), font_size=26)
        self._timer.start()

        self._back_btn = Button(
            (self.width - 110, self.height - 50, 100, 38),
            "Menu", 20, THEME["secondary"]
        )
        self._back_btn.on_click = self.exit

        self._reset_btn = Button(
            (self.width - 222, self.height - 50, 100, 38),
            "Restart", 20, THEME["primary"]
        )
        self._reset_btn.on_click = self.reset

        # Victory message font
        try:
            self._big_font = pygame.font.SysFont("Comic Sans MS", 52, bold=True)
            self._med_font = pygame.font.SysFont("Comic Sans MS", 30)
        except Exception:
            self._big_font = pygame.font.Font(None, 60)
            self._med_font = pygame.font.Font(None, 36)

    # ── Input ──────────────────────────────────────────────────────────────
    def handle_input(self, event: pygame.event.Event) -> None:
        if self._victory:
            # Any click after victory → exit
            if event.type in (pygame.MOUSEBUTTONUP, pygame.KEYDOWN):
                self.exit()
            return

        self._back_btn.handle_event(event)
        self._reset_btn.handle_event(event)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._mismatch_timer > 0:
                return   # waiting to flip mismatched cards back
            self._handle_card_click(event.pos)

    def _handle_card_click(self, pos: Tuple[int, int]) -> None:
        mx, my = pos
        for card in self._cards:
            # Hit test
            if card.x <= mx < card.x + CARD_W and card.y <= my < card.y + CARD_H:
                if card.matched or card.face_up or card.flip.animating:
                    return
                if len(self._selected) >= 2:
                    return

                card.start_flip_up()
                self._selected.append(card)

                if len(self._selected) == 2:
                    self._turns += 1
                    self._turns_counter.set_value(self._turns)
                    self._check_match()
                return

    # ── Update ─────────────────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        for card in self._cards:
            card.update(dt)

        self._turns_counter.update(dt)
        self._match_counter.update(dt)
        self._timer.update(dt)
        self._particles.update(dt)

        # Count-down to flipping mismatched pair back
        if self._mismatch_timer > 0:
            self._mismatch_timer -= dt
            if self._mismatch_timer <= 0:
                for card in self._selected:
                    card.start_flip_down()
                self._selected.clear()

        # Victory delay
        if self._victory:
            self._victory_timer -= dt
            if self._victory_timer <= 0:
                pass   # user clicks to continue

    # ── Render ─────────────────────────────────────────────────────────────
    def render(self, screen: pygame.Surface) -> None:
        # Sky background
        for y in range(self.height):
            t = y / self.height
            r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
            g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
            b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
            pygame.draw.line(screen, (r, g, b), (0, y), (self.width, y))

        # HUD bar
        self.draw_hud_bar(screen, self._score, self._level,
                          f"{self._matches_found}/{self._total_pairs} pairs")

        # Cards
        for card in self._cards:
            card.draw(screen)

        # Particles
        self._particles.draw(screen)

        # Counters
        self._turns_counter.draw(screen)
        self._match_counter.draw(screen)
        self._timer.draw(screen, "")

        # Buttons
        self._back_btn.draw(screen)
        self._reset_btn.draw(screen)

        # Victory overlay
        if self._victory:
            self._draw_victory(screen)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _check_match(self) -> None:
        a, b = self._selected[0], self._selected[1]
        if a.vehicle == b.vehicle:
            # Match!
            a.matched = b.matched = True
            a.trigger_wobble()
            b.trigger_wobble()
            self._matches_found += 1
            self._match_counter.set_value(self._matches_found)
            # Rebuild front surfaces with green background
            for card in (a, b):
                card.front_surf = self._build_front_surface(card.vehicle,
                    self._vehicle_surfs[card.vehicle], matched=True)

            # Score: base 100, bonus for low turn count
            turn_bonus = max(0, 50 - self._turns * 2)
            self._score += 100 + turn_bonus
            self._score = max(0, self._score)

            cx = (a.x + b.x) // 2 + CARD_W // 2
            cy = (a.y + b.y) // 2 + CARD_H // 2
            self._particles.burst(cx, cy, 35)

            self._selected.clear()

            # All pairs matched?
            if self._matches_found == self._total_pairs:
                self._timer.stop()
                time_bonus = max(0, int(300 - self._timer.elapsed * 2))
                self._score += time_bonus
                self._victory = True
                self._victory_timer = VICTORY_DELAY
                self._particles.burst(self.width // 2, self.height // 2, 80)
                self._completion = 1.0
        else:
            # No match — show for a moment then flip back
            self._mismatch_timer = MISMATCH_SHOW_SECS

    def _build_cards(self) -> List[Card]:
        """Create a shuffled 4×4 grid of cards."""
        vehicles = VEHICLES_POOL[:self._total_pairs] * 2
        random.shuffle(vehicles)

        # Calculate grid origin to centre it
        grid_w = GRID_COLS * CARD_W + (GRID_COLS - 1) * CARD_PAD
        grid_h = GRID_ROWS * CARD_H + (GRID_ROWS - 1) * CARD_PAD
        origin_x = (self.width  - grid_w) // 2
        origin_y = HUD_H + 8 + (self.height - HUD_H - 60 - grid_h) // 2

        cards = []
        idx = 0
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                x = origin_x + col * (CARD_W + CARD_PAD)
                y = origin_y + row * (CARD_H + CARD_PAD)
                cards.append(Card(vehicles[idx], col, row, x, y))
                idx += 1
        return cards

    def _build_front_surface(
        self,
        vehicle: str,
        vehicle_surf: pygame.Surface,
        matched: bool = False,
    ) -> pygame.Surface:
        bg = CARD_MATCHED_BG if matched else CARD_FRONT_BG
        surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        pygame.draw.rect(surf, bg, (0, 0, CARD_W, CARD_H), border_radius=12)
        pygame.draw.rect(surf, CARD_BORDER, (0, 0, CARD_W, CARD_H), 2, border_radius=12)

        # Vehicle image (centred, with padding)
        margin = 8
        label_h = 20
        max_w = CARD_W - margin * 2
        max_h = CARD_H - margin * 2 - label_h
        veh = pygame.transform.smoothscale(vehicle_surf, (max_w, max_h))
        surf.blit(veh, (margin, margin))

        # Name label
        try:
            lbl = pygame.font.SysFont("Comic Sans MS", 14, bold=True)
        except Exception:
            lbl = pygame.font.Font(None, 16)
        name_surf = lbl.render(vehicle.replace("_", " ").title(), True, (50, 50, 80))
        surf.blit(name_surf, (CARD_W // 2 - name_surf.get_width() // 2,
                               CARD_H - label_h))
        return surf

    def _draw_victory(self, screen: pygame.Surface) -> None:
        # Dim overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        # Stars
        for i in range(3):
            sx = self.width // 2 + (i - 1) * 80
            sy = self.height // 2 - 60
            _draw_star(screen, sx, sy, 36, (255, 220, 30))

        # Title
        txt = self._big_font.render("Amazing! 🎉", True, (255, 220, 30))
        shadow = self._big_font.render("Amazing! 🎉", True, (0, 0, 0))
        cx = self.width // 2
        screen.blit(shadow, (cx - txt.get_width() // 2 + 3, self.height // 2 - 15))
        screen.blit(txt,    (cx - txt.get_width() // 2,     self.height // 2 - 18))

        # Stats
        t = int(self._timer.elapsed)
        m, s = divmod(t, 60)
        stats = self._med_font.render(
            f"Score: {self._score}  |  Turns: {self._turns}  |  Time: {m:02d}:{s:02d}",
            True, (220, 255, 220)
        )
        screen.blit(stats, (cx - stats.get_width() // 2, self.height // 2 + 40))

        tap = self._med_font.render("Click anywhere to continue", True, (200, 200, 200))
        screen.blit(tap, (cx - tap.get_width() // 2, self.height // 2 + 90))

    def get_game_state(self) -> dict:
        return {
            "score": self._score,
            "level": self._level,
            "completion": self._completion,
            "turns": self._turns,
            "time": self._timer.elapsed,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _draw_star(
    surface: pygame.Surface,
    cx: int, cy: int,
    r: int,
    colour: Tuple[int, int, int],
) -> None:
    """Draw a 5-pointed star."""
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        radius = r if i % 2 == 0 else r * 0.45
        points.append((
            cx + radius * math.cos(angle),
            cy + radius * math.sin(angle),
        ))
    pygame.draw.polygon(surface, colour, points)
    pygame.draw.polygon(surface, (200, 160, 0), points, 2)

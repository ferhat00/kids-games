"""
GameManager — Main-menu launcher, game orchestration, and persistent scoring.

States
------
MENU        : thumbnail grid of available games
PLAYING     : active GameFramework subclass running
TRANSITIONING: fade-to-black between states

Persistent data is stored in ``data/game_state.json``.

Adding a new game
-----------------
Append one dict to AVAILABLE_GAMES (bottom of this file).  No other changes
to the framework are needed.
"""

from __future__ import annotations

import importlib
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional

import pygame

from .asset_manager import AssetManager
from .ui_components import (
    Button, TextLabel, ConfirmDialog, ParticleSystem, THEME, draw_hud
)

# ─────────────────────────────────────────────────────────────────────────────
# Game registry — add new games here only
# ─────────────────────────────────────────────────────────────────────────────

AVAILABLE_GAMES: List[Dict] = [
    {
        "id":           "memory_match",
        "module":       "games.memory_match.memory_match",
        "class":        "MemoryMatchGame",
        "card_colour":  (255, 107, 53),    # orange-red
        "badge_colour": (255, 210, 50),
    },
    {
        "id":           "vehicle_sorter",
        "module":       "games.vehicle_sorter.vehicle_sorter",
        "class":        "VehicleSorterGame",
        "card_colour":  (78, 205, 196),    # teal
        "badge_colour": (88, 214, 141),
    },
    {
        "id":           "dream_flight",
        "module":       "games.dream_flight.dream_flight",
        "class":        "DreamFlightGame",
        "card_colour":  (110, 70, 190),    # dreamy purple
        "badge_colour": (255, 200, 50),
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Screen / window constants
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_W, SCREEN_H = 900, 650
FPS = 60
TITLE = "Kids Vehicle Games!"


# ─────────────────────────────────────────────────────────────────────────────
# GameManager
# ─────────────────────────────────────────────────────────────────────────────

class GameManager:
    """Top-level orchestrator.  Call ``run()`` to start the event loop."""

    # ── States ───────────────────────────────────────────────────────────────
    MENU          = "menu"
    PLAYING       = "playing"
    TRANSITIONING = "transitioning"

    def __init__(self) -> None:
        pygame.init()
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._audio = True
        except pygame.error:
            self._audio = False

        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption(TITLE)

        # Try to set a fun window icon via procedural drawing
        try:
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(icon, (255, 107, 53), (16, 16), 15)
            pygame.display.set_icon(icon)
        except Exception:
            pass

        self._clock = pygame.time.Clock()
        self._assets = AssetManager.instance()
        self._state: str = self.MENU
        self._active_game = None

        # Transition
        self._fade_alpha: int = 0
        self._fade_surface = pygame.Surface((SCREEN_W, SCREEN_H))
        self._fade_surface.fill((0, 0, 0))
        self._fade_target_state: str = self.MENU
        self._fade_game_entry: Optional[Dict] = None

        # Persistent data
        self._data_path = Path(__file__).resolve().parent.parent / "data" / "game_state.json"
        self._save_data: Dict = self._load_save()

        # Menu state
        self._menu_cards: List[_MenuCard] = []
        self._volume: float = self._save_data.get("settings", {}).get("volume", 0.8)
        self._particles = ParticleSystem()
        self._confirm_exit = ConfirmDialog(
            (SCREEN_W, SCREEN_H), "Return to menu?", "Yes", "No"
        )

        # Build menu
        self._build_menu()

        # Fonts
        self._title_font = self._make_font(52, bold=True)
        self._small_font  = self._make_font(22)

    # ── Public entry point ───────────────────────────────────────────────────

    def run(self) -> None:
        """Start the main event loop.  Blocks until the window is closed."""
        running = True
        while running:
            dt = self._clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self._handle_event(event)

            self._update(dt)
            self._render()
            pygame.display.flip()

        self._save()
        pygame.quit()

    # ── Event dispatch ───────────────────────────────────────────────────────

    def _handle_event(self, event: pygame.event.Event) -> None:
        if self._state == self.TRANSITIONING:
            return   # ignore input during fade

        if self._state == self.PLAYING and self._active_game:
            # Give confirm dialog first chance to eat the event
            result = self._confirm_exit.handle_event(event)
            if result is True:
                self._begin_transition(self.MENU)
            elif result is None:
                self._active_game.handle_input(event)
            # Escape to open confirm dialog
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if not self._confirm_exit.visible:
                    self._confirm_exit.show()
            return

        # Menu events
        if self._state == self.MENU:
            for card in self._menu_cards:
                if card.handle_event(event):
                    self._launch_game(card.game_entry)
            # Volume +/-
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_EQUALS:
                    self._volume = min(1.0, self._volume + 0.1)
                elif event.key == pygame.K_MINUS:
                    self._volume = max(0.0, self._volume - 0.1)

    # ── Update ───────────────────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        self._particles.update(dt)

        if self._state == self.TRANSITIONING:
            self._update_transition(dt)
            return

        if self._state == self.PLAYING and self._active_game:
            self._active_game.update(dt)
            if self._active_game.exit_requested:
                state = self._active_game.get_game_state()
                self._record_score(self._active_game_id, state)
                self._begin_transition(self.MENU)
            elif self._active_game.reset_requested:
                self._active_game.setup()

    # ── Render ───────────────────────────────────────────────────────────────

    def _render(self) -> None:
        if self._state == self.MENU:
            self._draw_menu()
        elif self._state == self.PLAYING and self._active_game:
            self._active_game.render(self.screen)
            self._confirm_exit.draw(self.screen)
        elif self._state == self.TRANSITIONING:
            # Draw the outgoing frame under the fade
            if self._fade_game_entry is None:  # fading to menu
                self._draw_menu()
            elif self._active_game:
                self._active_game.render(self.screen)

        self._particles.draw(self.screen)

        # Fade overlay
        if self._fade_alpha > 0:
            self._fade_surface.set_alpha(self._fade_alpha)
            self.screen.blit(self._fade_surface, (0, 0))

    # ── Menu drawing ─────────────────────────────────────────────────────────

    def _draw_menu(self) -> None:
        # Sky-gradient background
        for y in range(SCREEN_H):
            t = y / SCREEN_H
            r = int(135 + (200 - 135) * t)
            g = int(206 + (230 - 206) * t)
            b = int(235 + (255 - 235) * t)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (SCREEN_W, y))

        # Decorative road strip at bottom
        road_y = SCREEN_H - 60
        pygame.draw.rect(self.screen, (80, 80, 80), (0, road_y, SCREEN_W, 60))
        for dash_x in range(0, SCREEN_W, 80):
            pygame.draw.rect(self.screen, (240, 210, 30), (dash_x, road_y + 26, 50, 8))

        # Title
        title_surf = self._title_font.render(TITLE, True, (40, 40, 80))
        shadow_surf = self._title_font.render(TITLE, True, (0, 0, 0))
        tx = SCREEN_W // 2 - title_surf.get_width() // 2
        self.screen.blit(shadow_surf, (tx + 3, 27))
        self.screen.blit(title_surf, (tx, 24))

        # Subtitle
        sub = self._small_font.render("Choose a game to play!", True, (60, 60, 120))
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 88))

        # Game cards
        for card in self._menu_cards:
            card.draw(self.screen)

        # Volume indicator
        vol_text = self._small_font.render(
            f"Volume: {'▮' * int(self._volume * 10)}{'▯' * (10 - int(self._volume * 10))}  [- / +]",
            True, (60, 60, 80)
        )
        self.screen.blit(vol_text, (14, road_y + 18))

        # ESC hint (when in-game)
        esc_text = self._small_font.render("ESC — back to menu during play", True, (80, 80, 100))
        self.screen.blit(esc_text, (SCREEN_W - esc_text.get_width() - 14, road_y + 18))

    # ── Transition ───────────────────────────────────────────────────────────

    _FADE_SPEED = 800   # alpha units per second (0-255)

    def _begin_transition(self, target_state: str, game_entry: Optional[Dict] = None) -> None:
        self._state = self.TRANSITIONING
        self._fade_target_state = target_state
        self._fade_game_entry = game_entry
        self._fade_alpha = 0
        self._fading_in = True   # True = fade TO black

    def _update_transition(self, dt: float) -> None:
        if self._fading_in:
            self._fade_alpha = min(255, self._fade_alpha + int(self._FADE_SPEED * dt))
            if self._fade_alpha >= 255:
                # At peak darkness — switch state
                self._apply_transition()
                self._fading_in = False
        else:
            self._fade_alpha = max(0, self._fade_alpha - int(self._FADE_SPEED * dt))
            if self._fade_alpha <= 0:
                self._state = self._fade_target_state

    def _apply_transition(self) -> None:
        if self._fade_target_state == self.PLAYING and self._fade_game_entry:
            self._instantiate_game(self._fade_game_entry)
        elif self._fade_target_state == self.MENU:
            if self._active_game:
                pygame.mixer.stop()
                self._assets.unload_game_assets(self._active_game_id)
            self._active_game = None
            self._active_game_id = ""

    # ── Game lifecycle ────────────────────────────────────────────────────────

    def _launch_game(self, entry: Dict) -> None:
        self._begin_transition(self.PLAYING, game_entry=entry)
        self._particles.burst(SCREEN_W // 2, SCREEN_H // 2, 20)

    def _instantiate_game(self, entry: Dict) -> None:
        module = importlib.import_module(entry["module"])
        cls = getattr(module, entry["class"])
        self._active_game = cls(self.screen, self._assets)
        self._active_game_id = entry["id"]
        self._active_game.setup()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_save(self) -> Dict:
        try:
            with self._data_path.open() as fh:
                return json.load(fh)
        except Exception:
            return {"scores": {}, "settings": {"volume": 0.8}}

    def _save(self) -> None:
        self._save_data.setdefault("settings", {})["volume"] = self._volume
        try:
            self._data_path.parent.mkdir(parents=True, exist_ok=True)
            with self._data_path.open("w") as fh:
                json.dump(self._save_data, fh, indent=2)
        except Exception:
            pass

    def _record_score(self, game_id: str, state: Dict) -> None:
        scores = self._save_data.setdefault("scores", {})
        prev_best = scores.get(game_id, {}).get("best_score", 0)
        new_score = state.get("score", 0)
        scores[game_id] = {
            "best_score": max(prev_best, new_score),
            "last_score": new_score,
            "level_reached": state.get("level", 1),
        }
        self._save()

    # ── Menu card builder ─────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        n = len(AVAILABLE_GAMES)
        card_w, card_h = 340, 200
        cols = min(n, 2)
        rows = math.ceil(n / cols)
        pad = 30
        total_w = cols * card_w + (cols - 1) * pad
        total_h = rows * card_h + (rows - 1) * pad
        start_x = (SCREEN_W - total_w) // 2
        start_y = 120

        for i, entry in enumerate(AVAILABLE_GAMES):
            col = i % cols
            row = i // cols
            x = start_x + col * (card_w + pad)
            y = start_y + row * (card_h + pad)
            rect = (x, y, card_w, card_h)
            best = self._save_data.get("scores", {}).get(entry["id"], {}).get("best_score", 0)
            card = _MenuCard(rect, entry, self._assets, best)
            self._menu_cards.append(card)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_font(size: int, bold: bool = False) -> pygame.font.Font:
        try:
            return pygame.font.SysFont("Comic Sans MS", size, bold=bold)
        except Exception:
            return pygame.font.Font(None, size)


# ─────────────────────────────────────────────────────────────────────────────
# _MenuCard  (internal menu thumbnail card)
# ─────────────────────────────────────────────────────────────────────────────

class _MenuCard:
    """An interactive thumbnail card on the main menu."""

    CORNER_R = 20

    def __init__(
        self,
        rect: tuple,
        game_entry: Dict,
        assets: AssetManager,
        best_score: int = 0,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.game_entry = game_entry
        self._assets = assets
        self._best_score = best_score
        self._hovered = False
        self._hover_lift = 0.0    # pixels lifted on hover
        self._anim_t = 0.0

        # Load game metadata
        config = assets.get_asset_config(game_entry["id"])
        self._info = config
        self._title = config.get("title", game_entry["id"].replace("_", " ").title())
        self._desc  = config.get("description", "")
        self._vehicles = config.get("thumbnail_vehicles", ["car"])

        # Pre-render vehicle thumbnails
        self._thumb_surfs = [
            assets.generate_vehicle(v, (70, 70)) for v in self._vehicles[:3]
        ]

        # Fonts
        try:
            self._title_font = pygame.font.SysFont("Comic Sans MS", 26, bold=True)
            self._desc_font  = pygame.font.SysFont("Comic Sans MS", 17)
        except Exception:
            self._title_font = pygame.font.Font(None, 30)
            self._desc_font  = pygame.font.Font(None, 20)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        # Hover lift animation
        target_lift = 8.0 if self._hovered else 0.0
        self._hover_lift += (target_lift - self._hover_lift) * 0.25
        lift = int(self._hover_lift)
        draw_rect = self.rect.move(0, -lift)

        colour = self.game_entry["card_colour"]

        # Shadow
        shadow_r = self.rect.inflate(4, 4).move(5, 8 - lift)
        _draw_shadow(screen, shadow_r, self.CORNER_R)

        # Card background gradient (top lighter, bottom darker)
        _draw_gradient_rect(screen, draw_rect, colour, self.CORNER_R)

        # Badge stripe at top
        badge_colour = self.game_entry.get("badge_colour", (255, 210, 50))
        badge_rect = pygame.Rect(draw_rect.x, draw_rect.y, draw_rect.width, 10)
        pygame.draw.rect(screen, badge_colour, badge_rect,
                         border_top_left_radius=self.CORNER_R,
                         border_top_right_radius=self.CORNER_R)

        # Vehicle thumbnails
        thumb_y = draw_rect.y + 20
        total_thumb_w = len(self._thumb_surfs) * 74
        thumb_x = draw_rect.x + (draw_rect.width - total_thumb_w) // 2
        for surf in self._thumb_surfs:
            screen.blit(surf, (thumb_x, thumb_y))
            thumb_x += 74

        # Title
        title_surf = self._title_font.render(self._title, True, (255, 255, 255))
        tx = draw_rect.x + (draw_rect.width - title_surf.get_width()) // 2
        # Shadow
        shadow_t = self._title_font.render(self._title, True, (0, 0, 0))
        screen.blit(shadow_t, (tx + 2, draw_rect.y + 102))
        screen.blit(title_surf, (tx, draw_rect.y + 100))

        # Description
        desc_surf = self._desc_font.render(self._desc, True, (240, 240, 255))
        dx = draw_rect.x + (draw_rect.width - desc_surf.get_width()) // 2
        screen.blit(desc_surf, (dx, draw_rect.y + 138))

        # Best score badge
        if self._best_score > 0:
            score_txt = self._desc_font.render(
                f"Best: {self._best_score}", True, self.game_entry["badge_colour"]
            )
            screen.blit(score_txt, (draw_rect.right - score_txt.get_width() - 10,
                                    draw_rect.bottom - score_txt.get_height() - 8))

        # Outline on hover
        if self._hovered:
            pygame.draw.rect(screen, (255, 255, 255), draw_rect, 3,
                             border_radius=self.CORNER_R)
        else:
            pygame.draw.rect(screen, (0, 0, 0, 80), draw_rect, 1,
                             border_radius=self.CORNER_R)

        # "PLAY!" prompt
        if self._hovered:
            play_surf = self._title_font.render("▶  PLAY!", True, (255, 255, 100))
            px = draw_rect.x + (draw_rect.width - play_surf.get_width()) // 2
            screen.blit(play_surf, (px, draw_rect.y + 162))


# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers (module-level, not part of public API)
# ─────────────────────────────────────────────────────────────────────────────

def _draw_shadow(surface: pygame.Surface, rect: pygame.Rect, radius: int) -> None:
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 60), s.get_rect(), border_radius=radius)
    surface.blit(s, rect.topleft)


def _draw_gradient_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    base_colour: tuple,
    radius: int,
) -> None:
    """Draw a vertical gradient rectangle (lighter top, darker bottom)."""
    clip = surface.get_clip()
    surface.set_clip(rect)
    for i, y in enumerate(range(rect.top, rect.bottom)):
        t = i / rect.height
        r = int(base_colour[0] + (base_colour[0] * 0.6 - base_colour[0]) * t)
        g = int(base_colour[1] + (base_colour[1] * 0.6 - base_colour[1]) * t)
        b = int(base_colour[2] + (base_colour[2] * 0.6 - base_colour[2]) * t)
        r = max(0, min(255, int(base_colour[0] * (1 - 0.3 * t))))
        g = max(0, min(255, int(base_colour[1] * (1 - 0.3 * t))))
        b = max(0, min(255, int(base_colour[2] * (1 - 0.3 * t))))
        pygame.draw.line(surface, (r, g, b), (rect.left, y), (rect.right, y))
    surface.set_clip(clip)
    pygame.draw.rect(surface, (0, 0, 0), rect, 1, border_radius=radius)

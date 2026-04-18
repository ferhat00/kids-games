"""
GameFramework — Abstract base class for all vehicle-themed kids games.

Every game subclass must implement the five abstract methods below.
The GameManager calls these methods on the active game each frame.

Minimal new-game template
--------------------------
    class MyGame(GameFramework):
        def setup(self):         ...   # load assets, init state
        def handle_input(self, event): ...   # respond to mouse / keyboard
        def update(self, dt):    ...   # advance game logic
        def render(self, screen): ...  # draw everything
        def get_game_info(self) -> dict: ...  # title, description, thumbnail_color
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from .asset_manager import AssetManager


class GameFramework(ABC):
    """Abstract base that every game must subclass."""

    # ------------------------------------------------------------------ #
    #  Construction                                                        #
    # ------------------------------------------------------------------ #

    def __init__(self, screen: pygame.Surface, asset_manager: "AssetManager") -> None:
        self.screen = screen
        self.assets = asset_manager
        self.width, self.height = screen.get_size()

        # Flags read by GameManager each frame
        self._exit_requested: bool = False
        self._reset_requested: bool = False

        # State tracking — subclasses may override get_game_state() to expose more
        self._score: int = 0
        self._level: int = 1
        self._completion: float = 0.0  # 0.0–1.0

    # ------------------------------------------------------------------ #
    #  Abstract interface — subclasses MUST implement these               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def setup(self) -> None:
        """Called once when the game is first launched.

        Load assets, build the initial game state, and position UI elements.
        ``self.assets`` is already initialised at this point.
        """

    @abstractmethod
    def handle_input(self, event: pygame.event.Event) -> None:
        """Called for every pygame event while this game is active.

        Only process events relevant to your game; ignore others.
        Call ``self.exit()`` to return to the main menu.
        """

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance game logic by ``dt`` seconds (frame-rate independent).

        Args:
            dt: Elapsed seconds since the last frame (typically 0.016 at 60 fps).
        """

    @abstractmethod
    def render(self, screen: pygame.Surface) -> None:
        """Draw the complete current frame onto *screen*.

        The GameManager calls this after ``update``; do NOT call
        ``pygame.display.flip()`` — the manager does that.
        """

    @abstractmethod
    def get_game_info(self) -> dict:
        """Return static metadata shown on the main-menu card.

        Required keys
        -------------
        title         : str  — display name (e.g. "Memory Match")
        description   : str  — one-line blurb for the menu card
        thumbnail_color: tuple[int,int,int]  — RGB fallback card colour
        vehicle_types : list[str] — vehicles used (for thumbnail drawing)
        """

    # ------------------------------------------------------------------ #
    #  Concrete helpers — subclasses may call or override                 #
    # ------------------------------------------------------------------ #

    def get_game_state(self) -> dict:
        """Return live runtime state (score, level, completion).

        Override in subclasses to expose game-specific metrics.
        GameManager uses this for the persistent high-score system.
        """
        return {
            "score": self._score,
            "level": self._level,
            "completion": self._completion,
        }

    def reset(self) -> None:
        """Request a full game restart (handled by GameManager next frame)."""
        self._exit_requested = False
        self._reset_requested = True

    def exit(self) -> None:
        """Request return to the main menu (handled by GameManager next frame)."""
        self._exit_requested = True

    # ------------------------------------------------------------------ #
    #  Internal — read by GameManager; do not override                    #
    # ------------------------------------------------------------------ #

    @property
    def exit_requested(self) -> bool:
        return self._exit_requested

    @property
    def reset_requested(self) -> bool:
        flag = self._reset_requested
        self._reset_requested = False   # auto-clear after read
        return flag

    # ------------------------------------------------------------------ #
    #  Shared drawing helpers — convenient for subclasses                 #
    # ------------------------------------------------------------------ #

    def draw_background(self, screen: pygame.Surface, color: tuple) -> None:
        """Fill background with a solid colour."""
        screen.fill(color)

    def draw_hud_bar(
        self,
        screen: pygame.Surface,
        score: int,
        level: int,
        extra_text: str = "",
    ) -> None:
        """Draw a simple top HUD bar (score + level).  Override for custom HUD."""
        from .ui_components import draw_hud
        draw_hud(screen, score, level, extra_text, self.width)

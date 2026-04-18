"""
AssetManager — Centralised image/sound loading with disk cache and
procedural vehicle fallback graphics.

Usage
-----
    am = AssetManager.instance()
    surface = am.load_image("memory_match", "car")
    sound   = am.load_sound("memory_match", "flip")
    config  = am.get_asset_config("memory_match")

Procedural vehicles are drawn with pygame primitives, so the games work
out-of-the-box without any downloaded artwork.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame

# ─────────────────────────────────────────────────────────────────────────────
# Colour palette for procedural vehicles
# ─────────────────────────────────────────────────────────────────────────────
VEHICLE_COLOURS: Dict[str, Tuple[int, int, int]] = {
    "car":         (220,  60,  60),   # red
    "truck":       (230, 130,  30),   # orange
    "bus":         (240, 210,  30),   # yellow
    "motorcycle":  (140,  60, 200),   # purple
    "airplane":    ( 60, 140, 220),   # sky blue
    "helicopter":  ( 40, 200, 180),   # teal
    "rocket":      (230,  80, 160),   # pink
    "train":       ( 60, 180,  80),   # green
    "ship":        ( 40,  80, 180),   # navy
    "sailboat":    ( 80, 200, 230),   # light blue
    "ambulance":   (240, 240, 240),   # white (red cross added)
    "firetruck":   (200,  30,  30),   # dark red
    "bicycle":     (180, 120,  40),   # brown
    "submarine":   ( 80, 100, 160),   # steel blue
    "balloon":     (220, 100, 200),   # magenta
    "default":     (160, 160, 160),   # grey fallback
}

WHEEL_DARK  = ( 40,  40,  40)
WHEEL_LIGHT = (160, 160, 160)
WINDOW_CLR  = (173, 216, 230)
OUTLINE_CLR = ( 30,  30,  30)


# ─────────────────────────────────────────────────────────────────────────────
# AssetManager
# ─────────────────────────────────────────────────────────────────────────────

class AssetManager:
    """Singleton — obtain via ``AssetManager.instance()``."""

    _singleton: Optional["AssetManager"] = None

    # ── Singleton ──────────────────────────────────────────────────────────
    @classmethod
    def instance(cls) -> "AssetManager":
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton

    def __init__(self) -> None:
        self._images: Dict[str, pygame.Surface] = {}
        self._sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self._configs: Dict[str, dict] = {}
        self._fonts: Dict[str, pygame.font.Font] = {}

        # Project root = two levels above this file
        self._root = Path(__file__).resolve().parent.parent

    # ── Public API ─────────────────────────────────────────────────────────

    def load_image(
        self,
        game_id: str,
        asset_name: str,
        size: Optional[Tuple[int, int]] = None,
    ) -> pygame.Surface:
        """Return a pygame Surface for *asset_name* belonging to *game_id*.

        Lookup order
        ------------
        1. In-memory cache
        2. ``assets/games/<game_id>/<asset_name>.png`` on disk
        3. URL listed in ``game_config.json`` (downloaded then cached to disk)
        4. Procedurally drawn vehicle surface (guaranteed fallback)
        """
        key = f"{game_id}:{asset_name}:{size}"
        if key in self._images:
            return self._images[key]

        surface = self._load_from_disk(game_id, asset_name)
        if surface is None:
            surface = self._download_image(game_id, asset_name)
        if surface is None:
            surface = self.generate_vehicle(asset_name, size or (100, 100))

        if size and surface.get_size() != size:
            surface = pygame.transform.smoothscale(surface, size)

        self._images[key] = surface
        return surface

    def load_sound(
        self,
        game_id: str,
        sound_name: str,
    ) -> Optional[pygame.mixer.Sound]:
        """Return a pygame Sound or *None* if audio is unavailable."""
        key = f"{game_id}:{sound_name}"
        if key in self._sounds:
            return self._sounds[key]

        sound = None
        path = self._root / "assets" / "games" / game_id / "sounds" / f"{sound_name}.wav"
        if path.exists():
            try:
                sound = pygame.mixer.Sound(str(path))
            except pygame.error:
                pass

        self._sounds[key] = sound
        return sound

    def get_asset_config(self, game_id: str) -> dict:
        """Return the parsed ``game_config.json`` for *game_id* (cached)."""
        if game_id in self._configs:
            return self._configs[game_id]

        config_path = self._root / "games" / game_id / "game_config.json"
        if config_path.exists():
            with config_path.open() as fh:
                config = json.load(fh)
        else:
            config = {}

        self._configs[game_id] = config
        return config

    def get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        """Return a cached pygame Font at the requested size."""
        key = f"{size}:{bold}"
        if key not in self._fonts:
            # Try a friendly rounded font first, fall back to default
            preferred = ["Nunito", "Comic Sans MS", "Arial Rounded MT Bold", "Arial"]
            font = None
            for name in preferred:
                try:
                    font = pygame.font.SysFont(name, size, bold=bold)
                    break
                except Exception:
                    pass
            if font is None:
                font = pygame.font.Font(None, size)
            self._fonts[key] = font
        return self._fonts[key]

    def unload_game_assets(self, game_id: str) -> None:
        """Remove cached surfaces/sounds for *game_id* to free memory."""
        prefix = f"{game_id}:"
        for key in list(self._images.keys()):
            if key.startswith(prefix):
                del self._images[key]
        for key in list(self._sounds.keys()):
            if key.startswith(prefix):
                del self._sounds[key]

    # ── Internal helpers ───────────────────────────────────────────────────

    def _load_from_disk(
        self, game_id: str, asset_name: str
    ) -> Optional[pygame.Surface]:
        for ext in (".png", ".jpg", ".jpeg", ".bmp"):
            path = (
                self._root / "assets" / "games" / game_id / f"{asset_name}{ext}"
            )
            if path.exists():
                try:
                    img = pygame.image.load(str(path)).convert_alpha()
                    return img
                except pygame.error:
                    pass
        return None

    def _download_image(
        self, game_id: str, asset_name: str
    ) -> Optional[pygame.Surface]:
        """Download from URL in config if available; save to disk cache."""
        config = self.get_asset_config(game_id)
        url = config.get("assets", {}).get("images", {}).get(asset_name)
        if not url:
            return None

        try:
            import urllib.request, io
            cache_dir = self._root / "assets" / "games" / game_id
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{asset_name}.png"

            with urllib.request.urlopen(url, timeout=5) as resp:
                data = resp.read()
            with open(cache_path, "wb") as fh:
                fh.write(data)

            return pygame.image.load(str(cache_path)).convert_alpha()
        except Exception:
            return None

    # ── Procedural vehicle renderer ────────────────────────────────────────

    def generate_vehicle(
        self, vehicle_type: str, size: Tuple[int, int]
    ) -> pygame.Surface:
        """Return a pygame Surface with a drawn vehicle of *vehicle_type*.

        The drawing is sized to *size* (width, height) and uses SRCALPHA so
        cards can be drawn on any background.
        """
        w, h = size
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        colour = VEHICLE_COLOURS.get(vehicle_type, VEHICLE_COLOURS["default"])

        drawers = {
            "car":        _draw_car,
            "truck":      _draw_truck,
            "bus":        _draw_bus,
            "motorcycle": _draw_motorcycle,
            "airplane":   _draw_airplane,
            "helicopter": _draw_helicopter,
            "rocket":     _draw_rocket,
            "train":      _draw_train,
            "ship":       _draw_ship,
            "sailboat":   _draw_sailboat,
            "ambulance":  _draw_ambulance,
            "firetruck":  _draw_firetruck,
            "bicycle":    _draw_bicycle,
            "submarine":  _draw_submarine,
            "balloon":    _draw_balloon,
        }
        drawer = drawers.get(vehicle_type, _draw_car)
        drawer(surface, w, h, colour)
        return surface


# ─────────────────────────────────────────────────────────────────────────────
# Procedural drawing functions
# All receive (surface, w, h, colour) and draw in-place.
# Coordinates are proportional so the vehicle scales with any size.
# ─────────────────────────────────────────────────────────────────────────────

def _outline(surface, rect, colour, radius=0, width=2):
    pygame.draw.rect(surface, OUTLINE_CLR, rect, width, border_radius=radius)

def _draw_car(surface, w, h, colour):
    # Body
    bx, by, bw, bh = int(w*0.05), int(h*0.42), int(w*0.90), int(h*0.40)
    pygame.draw.rect(surface, colour, (bx, by, bw, bh), border_radius=8)
    pygame.draw.rect(surface, OUTLINE_CLR, (bx, by, bw, bh), 2, border_radius=8)

    # Roof
    rx, ry, rw, rh = int(w*0.18), int(h*0.18), int(w*0.64), int(h*0.30)
    pygame.draw.rect(surface, colour, (rx, ry, rw, rh), border_radius=10)
    pygame.draw.rect(surface, OUTLINE_CLR, (rx, ry, rw, rh), 2, border_radius=10)

    # Windows
    lw_rect = (int(w*0.21), int(h*0.21), int(w*0.24), int(h*0.20))
    rw_rect = (int(w*0.55), int(h*0.21), int(w*0.24), int(h*0.20))
    for wr in (lw_rect, rw_rect):
        pygame.draw.rect(surface, WINDOW_CLR, wr, border_radius=4)
        pygame.draw.rect(surface, OUTLINE_CLR, wr, 1, border_radius=4)

    # Wheels
    wr = int(h*0.17)
    for cx in (int(w*0.24), int(w*0.76)):
        cy = int(h*0.84)
        pygame.draw.circle(surface, WHEEL_DARK, (cx, cy), wr)
        pygame.draw.circle(surface, WHEEL_LIGHT, (cx, cy), wr//2)
        pygame.draw.circle(surface, OUTLINE_CLR, (cx, cy), wr, 2)

    # Headlight
    pygame.draw.ellipse(surface, (255, 240, 100), (int(w*0.87), int(h*0.52), int(w*0.07), int(h*0.12)))


def _draw_truck(surface, w, h, colour):
    # Trailer
    tx, ty, tw, th = int(w*0.30), int(h*0.28), int(w*0.65), int(h*0.55)
    pygame.draw.rect(surface, colour, (tx, ty, tw, th), border_radius=4)
    pygame.draw.rect(surface, OUTLINE_CLR, (tx, ty, tw, th), 2, border_radius=4)
    # Cab
    cx2, cy2, cw2, ch2 = int(w*0.05), int(h*0.38), int(w*0.28), int(h*0.45)
    pygame.draw.rect(surface, _darken(colour, 20), (cx2, cy2, cw2, ch2), border_radius=6)
    pygame.draw.rect(surface, OUTLINE_CLR, (cx2, cy2, cw2, ch2), 2, border_radius=6)
    # Windshield
    pygame.draw.rect(surface, WINDOW_CLR, (int(w*0.07), int(h*0.40), int(w*0.22), int(h*0.18)), border_radius=3)
    # Wheels (4)
    wr = int(h*0.14)
    for cx3 in (int(w*0.15), int(w*0.45), int(w*0.70)):
        cy3 = int(h*0.86)
        pygame.draw.circle(surface, WHEEL_DARK, (cx3, cy3), wr)
        pygame.draw.circle(surface, WHEEL_LIGHT, (cx3, cy3), wr//2)


def _draw_bus(surface, w, h, colour):
    bx, by, bw, bh = int(w*0.05), int(h*0.25), int(w*0.90), int(h*0.58)
    pygame.draw.rect(surface, colour, (bx, by, bw, bh), border_radius=6)
    pygame.draw.rect(surface, OUTLINE_CLR, (bx, by, bw, bh), 2, border_radius=6)
    # Windows row
    for i in range(4):
        wx = int(w*(0.12 + i*0.20))
        pygame.draw.rect(surface, WINDOW_CLR, (wx, int(h*0.30), int(w*0.15), int(h*0.20)), border_radius=3)
    # Door
    pygame.draw.rect(surface, _darken(colour, 30), (int(w*0.78), int(h*0.46), int(w*0.10), int(h*0.28)), border_radius=2)
    # Wheels
    wr = int(h*0.15)
    for cx in (int(w*0.22), int(w*0.78)):
        cy = int(h*0.87)
        pygame.draw.circle(surface, WHEEL_DARK, (cx, cy), wr)
        pygame.draw.circle(surface, WHEEL_LIGHT, (cx, cy), wr//2)


def _draw_motorcycle(surface, w, h, colour):
    # Frame
    pts = [(int(w*0.25), int(h*0.55)), (int(w*0.50), int(h*0.35)),
           (int(w*0.70), int(h*0.55)), (int(w*0.50), int(h*0.65))]
    pygame.draw.polygon(surface, colour, pts)
    pygame.draw.polygon(surface, OUTLINE_CLR, pts, 2)
    # Wheels
    wr = int(h*0.22)
    for cx in (int(w*0.22), int(w*0.78)):
        cy = int(h*0.72)
        pygame.draw.circle(surface, WHEEL_DARK, (cx, cy), wr)
        pygame.draw.circle(surface, WHEEL_LIGHT, (cx, cy), wr//2)
        pygame.draw.circle(surface, OUTLINE_CLR, (cx, cy), wr, 2)
    # Handlebar
    pygame.draw.line(surface, OUTLINE_CLR, (int(w*0.68), int(h*0.30)), (int(w*0.80), int(h*0.30)), 3)
    # Rider helmet
    pygame.draw.circle(surface, _darken(colour, 40), (int(w*0.52), int(h*0.22)), int(h*0.14))


def _draw_airplane(surface, w, h, colour):
    # Fuselage
    fx, fy, fw, fh = int(w*0.10), int(h*0.38), int(w*0.80), int(h*0.24)
    pygame.draw.ellipse(surface, colour, (fx, fy, fw, fh))
    pygame.draw.ellipse(surface, OUTLINE_CLR, (fx, fy, fw, fh), 2)
    # Nose cone
    pygame.draw.polygon(surface, _lighten(colour, 30),
        [(int(w*0.88), int(h*0.45)), (int(w*0.88), int(h*0.55)), (int(w*0.98), int(h*0.50))])
    # Main wings
    wing_pts = [(int(w*0.35), int(h*0.50)), (int(w*0.55), int(h*0.50)),
                (int(w*0.65), int(h*0.85)), (int(w*0.20), int(h*0.85))]
    pygame.draw.polygon(surface, _darken(colour, 20), wing_pts)
    pygame.draw.polygon(surface, OUTLINE_CLR, wing_pts, 2)
    # Tail wings
    tail_pts = [(int(w*0.12), int(h*0.44)), (int(w*0.22), int(h*0.44)),
                (int(w*0.22), int(h*0.62)), (int(w*0.08), int(h*0.62))]
    pygame.draw.polygon(surface, _darken(colour, 20), tail_pts)
    pygame.draw.polygon(surface, OUTLINE_CLR, tail_pts, 2)
    # Vertical tail
    vtail = [(int(w*0.13), int(h*0.20)), (int(w*0.20), int(h*0.20)),
             (int(w*0.20), int(h*0.44)), (int(w*0.13), int(h*0.44))]
    pygame.draw.polygon(surface, colour, vtail)
    pygame.draw.polygon(surface, OUTLINE_CLR, vtail, 2)
    # Windows
    for i in range(4):
        wx = int(w*(0.40 + i*0.10))
        pygame.draw.circle(surface, WINDOW_CLR, (wx, int(h*0.50)), int(h*0.05))


def _draw_helicopter(surface, w, h, colour):
    # Body
    pygame.draw.ellipse(surface, colour, (int(w*0.25), int(h*0.38), int(w*0.50), int(h*0.36)))
    pygame.draw.ellipse(surface, OUTLINE_CLR, (int(w*0.25), int(h*0.38), int(w*0.50), int(h*0.36)), 2)
    # Tail boom
    pygame.draw.rect(surface, _darken(colour, 20),
                     (int(w*0.05), int(h*0.50), int(w*0.25), int(h*0.12)), border_radius=4)
    # Tail rotor
    pygame.draw.circle(surface, _darken(colour, 40), (int(w*0.06), int(h*0.52)), int(h*0.10), 2)
    pygame.draw.line(surface, OUTLINE_CLR, (int(w*0.06), int(h*0.42)), (int(w*0.06), int(h*0.62)), 3)
    # Main rotor shaft
    pygame.draw.line(surface, OUTLINE_CLR, (int(w*0.50), int(h*0.22)), (int(w*0.50), int(h*0.40)), 3)
    # Main rotor blades
    pygame.draw.rect(surface, _darken(colour, 10),
                     (int(w*0.08), int(h*0.16), int(w*0.84), int(h*0.10)), border_radius=6)
    pygame.draw.rect(surface, OUTLINE_CLR,
                     (int(w*0.08), int(h*0.16), int(w*0.84), int(h*0.10)), 2, border_radius=6)
    # Cockpit window
    pygame.draw.ellipse(surface, WINDOW_CLR,
                        (int(w*0.56), int(h*0.42), int(w*0.16), int(h*0.22)))
    # Skids
    for sy in (int(h*0.74), int(h*0.80)):
        pygame.draw.line(surface, OUTLINE_CLR,
                         (int(w*0.30), sy), (int(w*0.70), sy), 3)
    for sx in (int(w*0.35), int(w*0.65)):
        pygame.draw.line(surface, OUTLINE_CLR, (sx, int(h*0.72)), (sx, int(h*0.80)), 2)


def _draw_rocket(surface, w, h, colour):
    # Body cylinder
    bx, bw = int(w*0.30), int(w*0.40)
    pygame.draw.rect(surface, colour, (bx, int(h*0.28), bw, int(h*0.50)), border_radius=8)
    pygame.draw.rect(surface, OUTLINE_CLR, (bx, int(h*0.28), bw, int(h*0.50)), 2, border_radius=8)
    # Nose cone
    nose = [(int(w*0.30), int(h*0.28)), (int(w*0.70), int(h*0.28)), (int(w*0.50), int(h*0.08))]
    pygame.draw.polygon(surface, _lighten(colour, 40), nose)
    pygame.draw.polygon(surface, OUTLINE_CLR, nose, 2)
    # Fins
    for side in (-1, 1):
        ox = int(w*0.50 + side * w*0.20)
        fin = [(ox, int(h*0.68)), (ox + side*int(w*0.16), int(h*0.85)), (ox, int(h*0.78))]
        pygame.draw.polygon(surface, _darken(colour, 30), fin)
        pygame.draw.polygon(surface, OUTLINE_CLR, fin, 2)
    # Window
    pygame.draw.circle(surface, WINDOW_CLR, (int(w*0.50), int(h*0.44)), int(h*0.09))
    pygame.draw.circle(surface, OUTLINE_CLR, (int(w*0.50), int(h*0.44)), int(h*0.09), 2)
    # Flame
    flame_pts = [(int(w*0.34), int(h*0.78)), (int(w*0.66), int(h*0.78)),
                 (int(w*0.60), int(h*0.94)), (int(w*0.50), int(h*0.88)),
                 (int(w*0.40), int(h*0.94))]
    pygame.draw.polygon(surface, (255, 160,  30), flame_pts)
    inner_pts = [(int(w*0.40), int(h*0.78)), (int(w*0.60), int(h*0.78)),
                 (int(w*0.50), int(h*0.90))]
    pygame.draw.polygon(surface, (255, 240, 80), inner_pts)


def _draw_train(surface, w, h, colour):
    # Locomotive body
    lx, ly, lw, lh = int(w*0.40), int(h*0.28), int(w*0.54), int(h*0.50)
    pygame.draw.rect(surface, colour, (lx, ly, lw, lh), border_radius=6)
    pygame.draw.rect(surface, OUTLINE_CLR, (lx, ly, lw, lh), 2, border_radius=6)
    # Cab
    cx2, cy2 = int(w*0.66), int(h*0.20)
    pygame.draw.rect(surface, _darken(colour, 20),
                     (cx2, cy2, int(w*0.24), int(h*0.28)), border_radius=4)
    pygame.draw.rect(surface, OUTLINE_CLR, (cx2, cy2, int(w*0.24), int(h*0.28)), 2, border_radius=4)
    # Cab window
    pygame.draw.rect(surface, WINDOW_CLR,
                     (int(w*0.69), int(h*0.24), int(w*0.14), int(h*0.14)), border_radius=3)
    # Smokestack
    pygame.draw.rect(surface, OUTLINE_CLR, (int(w*0.46), int(h*0.16), int(w*0.08), int(h*0.14)), border_radius=2)
    pygame.draw.rect(surface, WHEEL_DARK, (int(w*0.46), int(h*0.16), int(w*0.08), int(h*0.14)))
    # Car/tender
    pygame.draw.rect(surface, _lighten(colour, 15),
                     (int(w*0.04), int(h*0.36), int(w*0.34), int(h*0.40)), border_radius=4)
    pygame.draw.rect(surface, OUTLINE_CLR, (int(w*0.04), int(h*0.36), int(w*0.34), int(h*0.40)), 2, border_radius=4)
    # Wheels
    wr = int(h*0.13)
    for cx3 in (int(w*0.14), int(w*0.32), int(w*0.53), int(w*0.72), int(w*0.87)):
        cy3 = int(h*0.80)
        pygame.draw.circle(surface, WHEEL_DARK, (cx3, cy3), wr)
        pygame.draw.circle(surface, WHEEL_LIGHT, (cx3, cy3), wr//2)
        pygame.draw.circle(surface, OUTLINE_CLR, (cx3, cy3), wr, 2)
    # Rail
    pygame.draw.rect(surface, (100, 80, 60), (0, int(h*0.88), w, int(h*0.06)))


def _draw_ship(surface, w, h, colour):
    # Hull
    hull = [(int(w*0.05), int(h*0.52)), (int(w*0.95), int(h*0.52)),
            (int(w*0.85), int(h*0.78)), (int(w*0.15), int(h*0.78))]
    pygame.draw.polygon(surface, colour, hull)
    pygame.draw.polygon(surface, OUTLINE_CLR, hull, 2)
    # Deck / superstructure
    pygame.draw.rect(surface, _darken(colour, 20),
                     (int(w*0.25), int(h*0.30), int(w*0.50), int(h*0.24)), border_radius=4)
    # Bridge windows
    for i in range(3):
        pygame.draw.rect(surface, WINDOW_CLR,
                         (int(w*(0.30 + i*0.14)), int(h*0.34), int(w*0.09), int(h*0.12)), border_radius=2)
    # Funnel / smokestack
    pygame.draw.rect(surface, _darken(colour, 40),
                     (int(w*0.46), int(h*0.14), int(w*0.08), int(h*0.18)))
    # Water line
    pygame.draw.line(surface, (100, 160, 220),
                     (int(w*0.05), int(h*0.72)), (int(w*0.95), int(h*0.72)), 3)


def _draw_sailboat(surface, w, h, colour):
    # Hull
    hull = [(int(w*0.10), int(h*0.55)), (int(w*0.90), int(h*0.55)),
            (int(w*0.75), int(h*0.82)), (int(w*0.25), int(h*0.82))]
    pygame.draw.polygon(surface, colour, hull)
    pygame.draw.polygon(surface, OUTLINE_CLR, hull, 2)
    # Mast
    pygame.draw.line(surface, (80, 60, 40),
                     (int(w*0.50), int(h*0.10)), (int(w*0.50), int(h*0.56)), 3)
    # Main sail
    sail = [(int(w*0.50), int(h*0.12)), (int(w*0.50), int(h*0.54)),
            (int(w*0.80), int(h*0.54))]
    pygame.draw.polygon(surface, (250, 250, 250), sail)
    pygame.draw.polygon(surface, OUTLINE_CLR, sail, 2)
    # Jib sail
    jib = [(int(w*0.50), int(h*0.16)), (int(w*0.50), int(h*0.54)),
           (int(w*0.24), int(h*0.54))]
    pygame.draw.polygon(surface, (230, 230, 255), jib)
    pygame.draw.polygon(surface, OUTLINE_CLR, jib, 2)


def _draw_ambulance(surface, w, h, colour):
    _draw_car(surface, w, h, colour)   # reuse car shape
    # Red cross on body
    bx, by = int(w*0.38), int(h*0.48)
    cross_w = int(w*0.08)
    pygame.draw.rect(surface, (220, 30, 30), (bx, by - cross_w, cross_w*3, cross_w))
    pygame.draw.rect(surface, (220, 30, 30), (bx + cross_w, by - cross_w*2, cross_w, cross_w*3))
    # Stripe
    pygame.draw.rect(surface, (220, 30, 30), (int(w*0.05), int(h*0.56), int(w*0.90), int(h*0.08)))


def _draw_firetruck(surface, w, h, colour):
    _draw_truck(surface, w, h, colour)
    # Yellow stripe
    pygame.draw.rect(surface, (255, 220, 0),
                     (int(w*0.05), int(h*0.60), int(w*0.88), int(h*0.08)))
    # Ladder on top
    for i in range(5):
        lx = int(w*(0.35 + i*0.12))
        pygame.draw.line(surface, (200, 200, 100),
                         (lx, int(h*0.28)), (lx, int(h*0.36)), 2)
    pygame.draw.line(surface, (200, 200, 100),
                     (int(w*0.35), int(h*0.28)), (int(w*0.85), int(h*0.28)), 2)
    pygame.draw.line(surface, (200, 200, 100),
                     (int(w*0.35), int(h*0.36)), (int(w*0.85), int(h*0.36)), 2)


def _draw_bicycle(surface, w, h, colour):
    # Wheels
    wr = int(h*0.28)
    for cx in (int(w*0.25), int(w*0.75)):
        cy = int(h*0.65)
        pygame.draw.circle(surface, WHEEL_DARK, (cx, cy), wr, 3)
        pygame.draw.circle(surface, WHEEL_DARK, (cx, cy), wr//4)
        # Spokes
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            pygame.draw.line(surface, WHEEL_DARK, (cx, cy),
                             (int(cx + wr*0.85*math.cos(rad)), int(cy + wr*0.85*math.sin(rad))), 1)
    # Frame
    frame_pts = [(int(w*0.25), int(h*0.65)), (int(w*0.50), int(h*0.36)),
                 (int(w*0.75), int(h*0.65)), (int(w*0.50), int(h*0.36)),
                 (int(w*0.50), int(h*0.65)), (int(w*0.25), int(h*0.65))]
    pygame.draw.lines(surface, colour, False, frame_pts, 4)
    # Handlebar
    pygame.draw.line(surface, OUTLINE_CLR,
                     (int(w*0.62), int(h*0.32)), (int(w*0.74), int(h*0.32)), 3)
    # Seat
    pygame.draw.line(surface, OUTLINE_CLR,
                     (int(w*0.44), int(h*0.30)), (int(w*0.56), int(h*0.30)), 4)


def _draw_submarine(surface, w, h, colour):
    # Hull
    pygame.draw.ellipse(surface, colour, (int(w*0.08), int(h*0.35), int(w*0.80), int(h*0.40)))
    pygame.draw.ellipse(surface, OUTLINE_CLR, (int(w*0.08), int(h*0.35), int(w*0.80), int(h*0.40)), 2)
    # Conning tower
    pygame.draw.rect(surface, _darken(colour, 20),
                     (int(w*0.42), int(h*0.18), int(w*0.18), int(h*0.20)), border_radius=4)
    pygame.draw.rect(surface, OUTLINE_CLR, (int(w*0.42), int(h*0.18), int(w*0.18), int(h*0.20)), 2, border_radius=4)
    # Periscope
    pygame.draw.line(surface, OUTLINE_CLR, (int(w*0.56), int(h*0.08)), (int(w*0.56), int(h*0.20)), 3)
    pygame.draw.line(surface, OUTLINE_CLR, (int(w*0.50), int(h*0.08)), (int(w*0.60), int(h*0.08)), 3)
    # Propeller
    for angle in (45, 135):
        rad = math.radians(angle)
        cx, cy = int(w*0.10), int(h*0.55)
        pygame.draw.line(surface, _darken(colour, 30),
                         (cx, cy),
                         (int(cx + h*0.12*math.cos(rad)), int(cy + h*0.12*math.sin(rad))), 5)
    # Windows / portholes
    for i in range(3):
        px = int(w*(0.30 + i*0.18))
        pygame.draw.circle(surface, WINDOW_CLR, (px, int(h*0.55)), int(h*0.07))
        pygame.draw.circle(surface, OUTLINE_CLR, (px, int(h*0.55)), int(h*0.07), 2)


def _draw_balloon(surface, w, h, colour):
    # Balloon envelope
    pygame.draw.ellipse(surface, colour, (int(w*0.15), int(h*0.05), int(w*0.70), int(h*0.62)))
    pygame.draw.ellipse(surface, OUTLINE_CLR, (int(w*0.15), int(h*0.05), int(w*0.70), int(h*0.62)), 2)
    # Colour panels
    panel_colours = [_darken(colour, 40), _lighten(colour, 40),
                     _darken(colour, 20), _lighten(colour, 20)]
    cx2, cy2 = int(w*0.50), int(h*0.36)
    for i, pc in enumerate(panel_colours):
        ang = math.radians(i * 90 - 45)
        pygame.draw.line(surface, pc, (cx2, cy2),
                         (int(cx2 + w*0.35*math.cos(ang)), int(cy2 - h*0.32*abs(math.sin(ang)))), 2)
    # Ropes
    bx1, by1 = int(w*0.35), int(h*0.65)
    bx2, by2 = int(w*0.65), int(h*0.65)
    bx3, by3 = int(w*0.38), int(h*0.78)
    bx4, by4 = int(w*0.62), int(h*0.78)
    pygame.draw.line(surface, (100, 80, 40), (bx1, by1), (bx3, by3), 2)
    pygame.draw.line(surface, (100, 80, 40), (bx2, by2), (bx4, by4), 2)
    # Basket
    pygame.draw.rect(surface, (180, 130, 60), (int(w*0.34), int(h*0.78), int(w*0.32), int(h*0.18)), border_radius=4)
    pygame.draw.rect(surface, OUTLINE_CLR, (int(w*0.34), int(h*0.78), int(w*0.32), int(h*0.18)), 2, border_radius=4)


# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers
# ─────────────────────────────────────────────────────────────────────────────

def _darken(colour: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
    return tuple(max(0, c - amount) for c in colour)   # type: ignore[return-value]

def _lighten(colour: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
    return tuple(min(255, c + amount) for c in colour)  # type: ignore[return-value]

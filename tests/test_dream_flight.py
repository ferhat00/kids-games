"""
Pytest suite for DreamFlightGame.

Runs headless (SDL_VIDEODRIVER=dummy, SDL_AUDIODRIVER=dummy) so no window or
sound hardware is required.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import math
import pytest
import pygame

# Make sure the repo root is on the path when running from anywhere.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from games.dream_flight.dream_flight import (
    DreamFlightGame,
    _Plane,
    _FlyingObject,
    _Cloud,
    _Star,
    _SparkleTrail,
    LIVES_START,
    POINTS_ANIMAL,
    HUD_H,
    ANIMAL_TYPES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def pygame_init():
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass
    yield
    pygame.quit()


@pytest.fixture
def screen():
    return pygame.display.set_mode((900, 650))


@pytest.fixture
def game(screen):
    """Return a freshly set-up DreamFlightGame with a minimal AssetManager stub."""

    class _FakeAssets:
        def get_asset_config(self, _id):
            return {}
        def generate_vehicle(self, kind, size):
            return pygame.Surface(size)
        def unload_game_assets(self, _id):
            pass

    g = DreamFlightGame(screen, _FakeAssets())
    g.setup()
    return g


# ── Setup / initialisation ────────────────────────────────────────────────────

def test_setup_initial_score(game):
    assert game._score == 0


def test_setup_initial_lives(game):
    assert game._lives == LIVES_START


def test_setup_initial_level(game):
    assert game._level == 1


def test_setup_not_game_over(game):
    assert game._game_over is False


def test_setup_exit_not_requested(game):
    assert game.exit_requested is False


def test_setup_plane_exists(game):
    assert game._plane is not None


def test_setup_clouds_populated(game):
    assert len(game._clouds) > 0


def test_setup_stars_populated(game):
    assert len(game._stars) > 0


# ── ESC key must NOT cause abrupt exit ───────────────────────────────────────

def test_esc_does_not_set_exit_requested(game):
    """Core regression: ESC in handle_input must NOT call self.exit()."""
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
    game.handle_input(ev)
    assert game.exit_requested is False


def test_esc_during_game_over_does_not_set_exit_requested(game):
    game._game_over = True
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
    game.handle_input(ev)
    assert game.exit_requested is False


# ── Game-over reset via SPACE / ENTER ────────────────────────────────────────

def test_space_during_game_over_requests_reset(game):
    game._game_over = True
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
    game.handle_input(ev)
    assert game.reset_requested is True


def test_enter_during_game_over_requests_reset(game):
    game._game_over = True
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r")
    game.handle_input(ev)
    assert game.reset_requested is True


def test_space_without_game_over_does_not_reset(game):
    game._game_over = False
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
    game.handle_input(ev)
    assert game.reset_requested is False


# ── Collision: frog reduces lives ────────────────────────────────────────────

def _place_frog_on_plane(game):
    """Spawn a frog centred on the plane so rects overlap."""
    frog = _FlyingObject("frog", game._plane.x, game._plane.y, 0.0)
    game._objects.append(frog)
    return frog


def test_frog_collision_reduces_lives(game):
    before = game._lives
    _place_frog_on_plane(game)
    game.update(0.016)
    assert game._lives == before - 1


def test_frog_collision_sets_flash(game):
    _place_frog_on_plane(game)
    game.update(0.016)
    assert game._flash_t > 0


def test_frog_object_removed_after_collision(game):
    _place_frog_on_plane(game)
    game.update(0.016)
    assert all(o.kind != "frog" or o.alive for o in game._objects)


# ── Collision: animal increases score ────────────────────────────────────────

def _place_animal_on_plane(game, kind="unicorn"):
    animal = _FlyingObject(kind, game._plane.x, game._plane.y, 0.0)
    game._objects.append(animal)
    return animal


def test_animal_collision_increases_score(game):
    _place_animal_on_plane(game)
    game.update(0.016)
    assert game._score == POINTS_ANIMAL


def test_animal_collision_sets_collect_glow(game):
    _place_animal_on_plane(game)
    game.update(0.016)
    assert game._collect_t > 0


@pytest.mark.parametrize("kind", ANIMAL_TYPES)
def test_all_animal_types_give_points(game, kind, screen):
    """Every animal type should award points on collision."""
    from framework.game_framework import GameFramework

    class _FakeAssets:
        def get_asset_config(self, _id):
            return {}
        def generate_vehicle(self, k, size):
            return pygame.Surface(size)
        def unload_game_assets(self, _id):
            pass

    g = DreamFlightGame(screen, _FakeAssets())
    g.setup()
    _place_animal_on_plane(g, kind)
    g.update(0.016)
    assert g._score == POINTS_ANIMAL


# ── Game-over trigger ─────────────────────────────────────────────────────────

def test_zero_lives_triggers_game_over(game):
    game._lives = 1
    _place_frog_on_plane(game)
    game.update(0.016)
    assert game._game_over is True


def test_game_over_stops_new_scoring(game):
    game._game_over = True
    game._score = 0
    _place_animal_on_plane(game)
    game.update(0.016)
    assert game._score == 0


# ── Plane boundary clamping ───────────────────────────────────────────────────

class _NoKeys:
    """Stub that returns False for every key constant."""
    def __getitem__(self, _k):
        return False


def test_plane_clamped_to_screen_bounds(game):
    plane = game._plane
    plane.x = -9999
    plane.y = -9999
    plane.vx = 0
    plane.vy = 0
    plane.update(0.016, _NoKeys())
    assert plane.x >= plane.W // 2
    assert plane.y >= HUD_H + plane.H // 2


def test_plane_clamped_upper_right(game):
    plane = game._plane
    plane.x = 99999
    plane.y = 99999
    plane.vx = 0
    plane.vy = 0
    plane.update(0.016, _NoKeys())
    assert plane.x <= 900 - plane.W // 2
    assert plane.y <= 650 - plane.H // 2


# ── Spawning ──────────────────────────────────────────────────────────────────

def test_spawn_adds_object(game):
    before = len(game._objects)
    game._spawn()
    assert len(game._objects) == before + 1


def test_spawned_object_is_valid_kind(game):
    game._spawn()
    obj = game._objects[-1]
    assert obj.kind in ANIMAL_TYPES + ["frog"]


# ── get_game_state ────────────────────────────────────────────────────────────

def test_get_game_state_keys(game):
    state = game.get_game_state()
    assert "score" in state
    assert "level" in state
    assert "lives" in state


def test_get_game_state_reflects_score(game):
    game._score = 42
    assert game.get_game_state()["score"] == 42


# ── Level progression ─────────────────────────────────────────────────────────

def test_level_increases_with_score(game):
    game._score = 50
    _place_animal_on_plane(game)
    game.update(0.016)
    assert game._level > 1


# ── _SparkleTrail ─────────────────────────────────────────────────────────────

def test_sparkle_trail_alpha_never_exceeds_255(screen):
    """Regression: max_life must equal initial life so alpha stays in [0, 255]."""
    trail = _SparkleTrail()
    for _ in range(200):
        trail.add(450.0, 325.0)
    # draw must not raise ValueError for invalid color
    trail.draw(screen)


def test_sparkle_trail_max_life_equals_initial_life(pygame_init):
    trail = _SparkleTrail()
    for _ in range(200):
        trail.add(100.0, 100.0)
    for spark in trail._sparks:
        assert spark["life"] <= spark["max_life"]


# ── _FlyingObject ─────────────────────────────────────────────────────────────

def test_flying_object_moves_left(pygame_init):
    obj = _FlyingObject("unicorn", 500.0, 300.0, 100.0)
    x_before = obj.x
    obj.update(0.1)
    assert obj.x < x_before


def test_flying_object_dies_off_screen(pygame_init):
    obj = _FlyingObject("frog", -200.0, 300.0, 100.0)
    obj.update(0.1)
    assert obj.alive is False

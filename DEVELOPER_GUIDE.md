# Kids Vehicle Games — Developer Guide

A step-by-step reference for extending the framework with new games,
new vehicle types, custom assets, and UI tweaks.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Architecture Overview](#2-architecture-overview)
3. [Adding a New Game in 5 Steps](#3-adding-a-new-game-in-5-steps)
4. [GameFramework API Reference](#4-gameframework-api-reference)
5. [AssetManager Reference](#5-assetmanager-reference)
6. [UI Components Reference](#6-ui-components-reference)
7. [Adding New Vehicle Types](#7-adding-new-vehicle-types)
8. [Configuration (game_config.json)](#8-configuration-game_configjson)
9. [Persistent State](#9-persistent-state)
10. [Visual Theme](#10-visual-theme)

---

## 1. Project Structure

```
kids-games/
├── main.py                        ← Entry point — run this
├── requirements.txt
├── DEVELOPER_GUIDE.md
│
├── framework/                     ← Core (never edit for new games)
│   ├── game_framework.py          ← Abstract base class
│   ├── asset_manager.py           ← Image/sound loading + procedural vehicles
│   ├── ui_components.py           ← Button, Timer, Counter, Particles …
│   └── game_manager.py            ← Menu, game launcher, persistence
│
├── games/                         ← One sub-package per game
│   ├── memory_match/
│   │   ├── memory_match.py        ← MemoryMatchGame implementation
│   │   └── game_config.json
│   ├── vehicle_sorter/
│   │   ├── vehicle_sorter.py      ← VehicleSorterGame implementation
│   │   └── game_config.json
│   └── your_new_game/             ← Add new games here
│       ├── your_new_game.py
│       └── game_config.json
│
├── assets/
│   └── games/
│       ├── memory_match/          ← Optional: drop PNG files here
│       │   └── sounds/            ← Optional: drop WAV files here
│       └── vehicle_sorter/
│
└── data/
    └── game_state.json            ← Auto-created; stores scores/settings
```

---

## 2. Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│                     GameManager                        │
│  (main loop, menu, transitions, persistence)           │
│                        │                               │
│         ┌──────────────┼──────────────┐                │
│         ▼              ▼              ▼                │
│    MemoryMatch   VehicleSorter   YourGame              │
│   (GameFramework subclasses)                           │
│                        │                               │
│         ┌──────────────┼──────────────┐                │
│         ▼              ▼              ▼                │
│   AssetManager    UIComponents   game_config.json      │
└────────────────────────────────────────────────────────┘
```

**Data flow per frame:**

```
GameManager.run()
  ├─ event loop → game.handle_input(event)
  ├─ game.update(dt)
  └─ game.render(screen)
       └─ game.exit() or game.reset() flags → picked up next frame
```

---

## 3. Adding a New Game in 5 Steps

### Step 1 — Create the directory

```
games/
└── bingo/
    ├── __init__.py
    ├── bingo.py
    └── game_config.json
```

### Step 2 — Write `game_config.json`

```json
{
  "id": "bingo",
  "title": "Vehicle Bingo",
  "description": "Spot the vehicles on your card!",
  "thumbnail_vehicles": ["car", "airplane", "train"],
  "assets": {
    "images": {},
    "sounds": {}
  }
}
```

### Step 3 — Implement the game class

```python
# games/bingo/bingo.py
from framework.game_framework import GameFramework
from framework.ui_components import Button, ParticleSystem, THEME

class BingoGame(GameFramework):

    def get_game_info(self) -> dict:
        return {
            "title":           "Vehicle Bingo",
            "description":     "Spot the vehicles on your card!",
            "thumbnail_color":  (180, 80, 200),
            "vehicle_types":   ["car", "airplane", "train"],
        }

    def setup(self) -> None:
        """Called once on launch — build your game state here."""
        self._score = 0
        self._level = 1
        # ... initialise grid, load assets, create buttons ...
        self._back_btn = Button(
            (self.width - 110, self.height - 50, 100, 38),
            "Menu", 20, THEME["secondary"]
        )
        self._back_btn.on_click = self.exit

    def handle_input(self, event) -> None:
        """Process player input."""
        self._back_btn.handle_event(event)
        # ... handle card clicks, keyboard ...

    def update(self, dt: float) -> None:
        """Advance game logic (dt = seconds since last frame)."""
        # ... update animations, check win condition ...

    def render(self, screen) -> None:
        """Draw everything onto screen."""
        screen.fill((220, 240, 255))
        self.draw_hud_bar(screen, self._score, self._level, "")
        # ... draw your game ...
        self._back_btn.draw(screen)
```

### Step 4 — Write `__init__.py`

```python
# games/bingo/__init__.py
from .bingo import BingoGame
__all__ = ["BingoGame"]
```

### Step 5 — Register in GameManager

Open `framework/game_manager.py` and add one dict to `AVAILABLE_GAMES`:

```python
AVAILABLE_GAMES = [
    # ... existing games ...
    {
        "id":           "bingo",
        "module":       "games.bingo.bingo",
        "class":        "BingoGame",
        "card_colour":  (180, 80, 200),    # menu card background
        "badge_colour": (220, 160, 255),   # accent stripe colour
    },
]
```

**That's it.** The menu card, thumbnail, best-score badge, and transitions
are handled automatically. No other framework files need changing.

---

## 4. GameFramework API Reference

```python
class GameFramework(ABC):

    # ── Mandatory overrides ─────────────────────────────────────────────
    def setup(self) -> None: ...
    def handle_input(self, event: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def render(self, screen: pygame.Surface) -> None: ...
    def get_game_info(self) -> dict: ...

    # ── Call from your game ─────────────────────────────────────────────
    def exit(self) -> None
        # Signal GameManager to return to the menu.

    def reset(self) -> None
        # Signal GameManager to call setup() again next frame.

    def draw_hud_bar(self, screen, score, level, extra_text="") -> None
        # Draws the standard top HUD bar.

    # ── Override if you track custom metrics ────────────────────────────
    def get_game_state(self) -> dict
        # Must return at minimum {"score": int, "level": int, "completion": float}
        # GameManager uses this for high-score persistence.

    # ── Attributes available in your subclass ───────────────────────────
    self.screen        # pygame.Surface  (the display)
    self.assets        # AssetManager instance
    self.width         # int
    self.height        # int
    self._score        # int  — set directly or via get_game_state()
    self._level        # int
    self._completion   # float  0.0–1.0
```

---

## 5. AssetManager Reference

```python
am = AssetManager.instance()

# Load an image (disk → URL → procedural fallback)
surf = am.load_image("my_game", "car")
surf = am.load_image("my_game", "car", size=(100, 80))

# Generate a procedural vehicle surface directly
surf = am.generate_vehicle("airplane", (160, 120))

# Load a sound (returns None if unavailable)
snd  = am.load_sound("my_game", "explosion")
if snd:
    snd.play()

# Read game_config.json
cfg  = am.get_asset_config("my_game")

# Get a cached Font
font = am.get_font(size=32, bold=True)

# Free memory when leaving a game
am.unload_game_assets("my_game")
```

**Supported procedural vehicle types:**

| ID            | Description              |
|---------------|--------------------------|
| `car`         | Red saloon car           |
| `truck`       | Orange articulated truck |
| `bus`         | Yellow bus               |
| `motorcycle`  | Purple motorcycle        |
| `airplane`    | Blue commercial jet      |
| `helicopter`  | Teal helicopter          |
| `rocket`      | Pink rocket              |
| `train`       | Green steam locomotive   |
| `ship`        | Navy cargo ship          |
| `sailboat`    | Light blue sailboat      |
| `ambulance`   | White ambulance          |
| `firetruck`   | Dark red fire truck      |
| `bicycle`     | Brown bicycle            |
| `submarine`   | Steel blue submarine     |
| `balloon`     | Magenta hot-air balloon  |

To add a new vehicle type, implement a `_draw_<type>(surface, w, h, colour)`
function in `framework/asset_manager.py` and add it to both
`VEHICLE_COLOURS` and the `drawers` dict inside `generate_vehicle()`.

---

## 6. UI Components Reference

```python
from framework.ui_components import (
    Button, TextLabel, Counter, Timer,
    ProgressBar, CardFlip, AnimationQueue, Tween,
    ParticleSystem, ConfirmDialog, THEME, draw_hud
)

# Button
btn = Button(rect=(x,y,w,h), label="Play!", font_size=30,
             colour=THEME["primary"])
btn.on_click = lambda: print("clicked")
btn.handle_event(event)   # call in handle_input
btn.draw(screen)          # call in render

# TextLabel
lbl = TextLabel("Hello!", pos=(cx, cy), font_size=28,
                colour=THEME["text_dark"], shadow=True, anchor="center")
lbl.set_text("New text")
lbl.draw(screen)

# Counter (animated score display)
ctr = Counter(pos=(cx, cy), prefix="Score: ", font_size=32)
ctr.set_value(new_score)   # triggers pop animation
ctr.update(dt)
ctr.draw(screen)

# Timer
tmr = Timer(pos=(cx, cy), countdown=60.0)  # countdown timer
tmr.start(); tmr.stop(); tmr.reset()
tmr.update(dt)
tmr.draw(screen, label="Time: ")
tmr.elapsed    # float seconds
tmr.remaining  # float seconds (countdown mode)
tmr.expired    # bool

# CardFlip animation
flip = CardFlip()
flip.start(to_front=True)
flip.update(dt)
scale_x, show_front = flip.render_state()
# Apply scale_x to your surface width when blitting

# ParticleSystem (celebration bursts)
particles = ParticleSystem()
particles.burst(cx, cy, count=40)
particles.update(dt)
particles.draw(screen)

# ProgressBar
bar = ProgressBar(rect=(x,y,w,h), colour=THEME["success"])
bar.set_value(0.75)   # 0.0–1.0
bar.draw(screen)

# ConfirmDialog (modal yes/no)
dlg = ConfirmDialog(screen_size=(900,650), message="Quit to menu?")
dlg.show()
result = dlg.handle_event(event)  # True=yes, False=no, None=no action
if dlg.visible:
    dlg.draw(screen)

# AnimationQueue (property tweening)
state = {"x": 0.0}
q = AnimationQueue()
q.add(Tween(state, "x", end=500.0, duration=1.0, easing="ease_out"))
q.update(dt)
draw_at_x(state["x"])

# Theme colours
THEME["primary"]      # (255, 107, 53)  orange-red
THEME["secondary"]    # (78, 205, 196)  teal
THEME["success"]      # (88, 214, 141)  green
THEME["danger"]       # (255, 100, 100) red
THEME["warning"]      # (255, 210, 50)  yellow
THEME["bg"]           # (255, 248, 231) warm cream
THEME["text_dark"]    # (40, 40, 40)
THEME["text_light"]   # (255, 255, 255)
THEME["card_back"]    # (80, 130, 200)  card back colour
THEME["hud_bg"]       # (50, 50, 80)    HUD bar background
```

---

## 7. Adding New Vehicle Types

1. Choose a name (`id`) — lowercase, underscore-separated.
2. Add a colour to `VEHICLE_COLOURS` in `framework/asset_manager.py`.
3. Write a `_draw_<id>(surface, w, h, colour)` function in the same file.
4. Register it in the `drawers` dict inside `AssetManager.generate_vehicle()`.
5. Add it to the relevant category in any game that should use it.

```python
# In asset_manager.py

VEHICLE_COLOURS["hovercraft"] = (160, 220, 160)   # light green

def _draw_hovercraft(surface, w, h, colour):
    # Body — wide flat shape
    pygame.draw.ellipse(surface, colour, (int(w*0.05), int(h*0.40), int(w*0.90), int(h*0.30)))
    # Skirt
    pygame.draw.ellipse(surface, _darken(colour, 30),
                        (0, int(h*0.60), w, int(h*0.30)))
    # Propeller at rear
    pygame.draw.rect(surface, OUTLINE_CLR,
                     (int(w*0.04), int(h*0.30), int(w*0.06), int(h*0.40)))
    pygame.draw.line(surface, OUTLINE_CLR,
                     (int(w*0.07), int(h*0.30)), (int(w*0.07), int(h*0.70)), 3)
    # Cockpit
    pygame.draw.ellipse(surface, WINDOW_CLR,
                        (int(w*0.60), int(h*0.36), int(w*0.22), int(h*0.18)))

# In generate_vehicle():
drawers = {
    ...
    "hovercraft": _draw_hovercraft,
}
```

---

## 8. Configuration (game_config.json)

Each game can have a `game_config.json` at `games/<id>/game_config.json`.

```json
{
  "id":           "my_game",
  "title":        "My Awesome Game",
  "description":  "One-line blurb for the menu card",
  "thumbnail_vehicles": ["car", "airplane"],
  "difficulty_levels": ["easy", "medium", "hard"],

  "assets": {
    "images": {
      "car":      "https://cdn.example.com/car.png",
      "airplane": "https://cdn.example.com/plane.png"
    },
    "sounds": {
      "win":   "sounds/win.wav",
      "oops":  "sounds/oops.wav"
    }
  },

  "scoring": {
    "base_score": 100,
    "leaderboard": true
  }
}
```

- `thumbnail_vehicles` — up to 3 vehicle IDs drawn on the menu card.
- Image URLs are downloaded once and cached to `assets/games/<id>/`.
- Sound paths are relative to `assets/games/<id>/`.

---

## 9. Persistent State

`data/game_state.json` is read on startup and written when the window closes
(and after each game session).

```json
{
  "scores": {
    "memory_match":   { "best_score": 850, "last_score": 720, "level_reached": 1 },
    "vehicle_sorter": { "best_score": 2400, "last_score": 1800, "level_reached": 2 }
  },
  "settings": {
    "volume":     0.8,
    "difficulty": "easy"
  },
  "play_history": []
}
```

Your game's `get_game_state()` dict is merged into `scores["your_id"]`.
The `score` key must be present for the best-score badge on the menu card.

---

## 10. Visual Theme

All games share the colour palette in `framework/ui_components.THEME`.
Override individual game backgrounds in your `render()` method but keep
buttons and fonts consistent via the theme dict and `Button` widget.

**Font hierarchy:**

| Use case          | Size | Widget / call                    |
|-------------------|------|----------------------------------|
| Game title        | 52   | Manual `pygame.font.SysFont`     |
| HUD bar           | 24   | `draw_hud_bar()` built-in        |
| Buttons           | 20–30| `Button(font_size=…)`            |
| Body text         | 18–22| `TextLabel(font_size=…)`         |
| Small labels      | 14–16| Manual render                    |

Preferred font: **"Comic Sans MS"** (friendly, round). Falls back to the
pygame default font if not installed.

---

*Happy coding! 🚗 ✈ 🚂*

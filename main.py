"""
Kids Vehicle Games — Entry Point
=================================
Run this file to launch the game launcher:

    python main.py

Requirements
------------
    pip install pygame

Optional (for downloading web assets):
    pip install Pillow requests

The games run fully without any downloaded assets — all vehicles are
drawn procedurally with pygame primitives.
"""

import sys
import os

# Ensure the project root is on the Python path so `framework` and `games`
# are importable regardless of where the script is invoked from.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import pygame
except ImportError:
    print(
        "\n[ERROR] pygame is not installed.\n"
        "Install it with:  pip install pygame\n"
    )
    sys.exit(1)

from framework.game_manager import GameManager


def main() -> None:
    """Create the GameManager and run the main event loop."""
    manager = GameManager()
    manager.run()


if __name__ == "__main__":
    main()

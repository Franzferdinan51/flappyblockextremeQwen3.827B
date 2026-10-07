"""FlippyBlock Extreme — a self-contained Flappy Bird-style game in pygame.

All visual and audio assets are generated procedurally at runtime; the only
dependency is pygame itself. The package layout:

- :mod:`flappy.constants` — shared tuning numbers (no pygame).
- :mod:`flappy.core`      — pure game logic, deterministic, no pygame.
- :mod:`flappy.assets`    — procedurally drawn sprites/surfaces (pygame).
- :mod:`flappy.sound`     — synthesised sound effects (pygame, guarded).
- :mod:`flappy.render`    — the pygame presentation layer / game loop.
"""

from __future__ import annotations

import os

__all__ = ["__version__", "default_highscore_path"]

__version__ = "1.0.0"

# The project root is the parent directory of this package.
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PACKAGE_DIR)


def default_highscore_path() -> str:
    """Where the game persists its high score.

    Kept inside the project folder so the game never writes outside its own
    directory. Overridable via the ``FLIPPYBLOCK_HIGHSCORE`` environment
    variable.
    """
    override = os.environ.get("FLIPPYBLOCK_HIGHSCORE")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(_PROJECT_ROOT, "highscore.json")

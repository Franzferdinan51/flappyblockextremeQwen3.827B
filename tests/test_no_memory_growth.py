"""Memory-growth guard for the real game loop.

Drives the shipped :class:`flappy.render.Game` (headless, dummy video/audio)
through a long sequence of full play -> death -> restart cycles and asserts:

* the pipe list and the pipe-body surface cache stay bounded,
* no unbounded per-frame accumulation happens (process peak memory stays
  flat across several thousand frames of the full draw path),
* animation clocks remain finite.

This is a regression guard against the "memory leak" failure mode: every
state's draw path (text canvases, buttons, overlays, rotated bird, cached
pipe bodies) is exercised on every frame.
"""

import gc
import math
import os
import resource
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import unittest  # noqa: E402

import pygame  # noqa: E402
pygame.init()

from flappy import core as K      # noqa: E402
from flappy import constants as C  # noqa: E402
from flappy import render as R     # noqa: E402


def _rss_kb() -> int:
    """Process peak RSS in KB (ru_maxrss is bytes on macOS, KB on Linux)."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak // 1024 if sys.platform == "darwin" else peak


class TestMemoryGrowth(unittest.TestCase):
    def _resume(self, game) -> None:
        """Drive the real input dispatch back to a live run if the bot died."""
        if game.core.state == K.State.GAME_OVER:
            game._apply(K.Action.RESTART)   # game over -> ready
            game._apply(K.Action.FLAP)      # ready -> playing, bird launches

    def test_long_run_keeps_memory_and_state_bounded(self):
        game = R.Game(highscore_path=None, smoke=True, rng_seed=7,
                      window_size=(C.WIDTH, C.HEIGHT))

        # Warm-up: let every cache (fonts, surfaces, pipe bodies) fill so the
        # measured window reflects steady state, not first-use allocation.
        game.run(max_frames=400, fps=0)
        for _ in range(3):
            self._resume(game)
            game.run(max_frames=game._frame + 1000, fps=0)

        gc.collect()
        rss0 = _rss_kb()

        max_pipes = 0
        for _ in range(8):
            self._resume(game)
            game.run(max_frames=game._frame + 500, fps=0)
            max_pipes = max(max_pipes, len(game.core.pipes))
            self.assertLessEqual(len(game.assets.pipe._body_cache), 512)

        gc.collect()
        rss1 = _rss_kb()

        # Generous bound (20 MB over ~4400 frames): a real leak would grow
        # far beyond this; steady-state churn should be near zero.
        self.assertLess(rss1 - rss0, 20 * 1024,
                        f"peak RSS grew {rss1 - rss0} KB over the measured window")
        self.assertLessEqual(max_pipes, 6, "pipe list grew without bound")
        self.assertTrue(math.isfinite(game.wing_time))


if __name__ == "__main__":
    unittest.main(verbosity=2)

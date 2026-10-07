"""Tests for the procedural asset generator.

Runs headlessly (dummy SDL video driver) and verifies that every asset is a
properly-sized, non-empty surface built entirely in code.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import unittest  # noqa: E402

import pygame  # noqa: E402
pygame.init()

from flappy import assets as A            # noqa: E402
from flappy import constants as C         # noqa: E402


def _painted_fraction(surf, sample=6) -> float:
    """Fraction of sampled pixels that are NOT a single uniform colour."""
    import collections
    w, h = surf.get_size()
    vals = [surf.get_at((x, y)) for y in range(0, h, sample) for x in range(0, w, sample)]
    cols = collections.Counter((c.r // 16, c.g // 16, c.b // 16) for c in vals)
    top = cols.most_common(1)[0][1] / len(vals)
    return 1.0 - top


class TestBirdSprite(unittest.TestCase):
    def test_frame_count_and_size(self):
        bird = A.BirdSprite(C.BIRD_SIZE)
        self.assertEqual(bird.count, len(bird.frames))
        self.assertGreater(bird.count, 1)
        for f in bird.frames:
            self.assertEqual(f.get_size(), (C.BIRD_SIZE, C.BIRD_SIZE))

    def test_frames_are_painted(self):
        for f in A.BirdSprite(C.BIRD_SIZE).frames:
            self.assertGreater(_painted_fraction(f), 0.15)

    def test_rotates(self):
        f = A.BirdSprite(C.BIRD_SIZE).frames[0]
        rot = pygame.transform.rotate(f, 45)
        self.assertGreater(rot.get_size()[0], 0)

    def test_wing_frames_are_visually_distinct(self):
        # Regression: the per-phase wing lift / body offset must yield frames
        # that actually differ; a broken offset would render four identical
        # poses (a bird that never appears to flap).
        bufs = [pygame.image.tostring(f, "RGBA")
                for f in A.BirdSprite(C.BIRD_SIZE).frames]
        self.assertGreater(len(set(bufs)), 1)


class TestPipeSprite(unittest.TestCase):
    def test_body_scales_to_requested_height(self):
        pipe = A.PipeSprite(C.PIPE_WIDTH)
        for h in (40, 200, 372):
            self.assertEqual(pipe.body(h).get_size(), (C.PIPE_WIDTH, max(2, (h // 2) * 2)))

    def test_cap_size(self):
        pipe = A.PipeSprite(C.PIPE_WIDTH)
        w, h = pipe.cap().get_size()
        self.assertEqual(w, C.PIPE_WIDTH + 2 * pipe.cap_lip)
        self.assertGreater(h, 0)

    def test_body_is_painted(self):
        self.assertGreater(_painted_fraction(A.PipeSprite(C.PIPE_WIDTH).body(200)), 0.2)


class TestGroundAndBackground(unittest.TestCase):
    def test_ground_tile(self):
        g = A.Ground(C.WIDTH)
        self.assertEqual(g.tile.get_size(), (C.WIDTH * 2, C.GROUND_HEIGHT))
        self.assertGreater(_painted_fraction(g.tile), 0.3)

    def test_background_covers_window(self):
        bg = A.Background(C.WIDTH, C.HEIGHT)
        self.assertEqual(bg.surface.get_size(), (C.WIDTH, C.HEIGHT))
        self.assertGreater(_painted_fraction(bg.surface), 0.3)

    def test_cloud_layer(self):
        layer = A.CloudLayer(C.WIDTH, C.HEIGHT)
        self.assertGreater(len(layer.clouds), 0)
        for surf, _, _, _ in layer.clouds:
            self.assertGreater(surf.get_size()[0], 0)


class TestAssetBank(unittest.TestCase):
    def test_bank_builds_everything(self):
        bank = A.AssetBank(C.WIDTH, C.HEIGHT)
        self.assertEqual(bank.bird.count, len(bank.bird.frames))
        self.assertEqual(bank.background.surface.get_size(), (C.WIDTH, C.HEIGHT))
        self.assertEqual(bank.ground.tile.get_size()[0], C.WIDTH * 2)
        self.assertGreater(len(bank.clouds.clouds), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

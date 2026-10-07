"""Tests for the pygame presentation layer.

These run headlessly (dummy video + audio drivers) and exercise the real
:class:`flappy.render.Game`: constructing, rendering every state to a
substantially-painted surface, button hit-testing, key mapping, and the smoke
capture path that the entry point uses.
"""

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import unittest  # noqa: E402

import pygame  # noqa: E402
pygame.init()

from flappy import core as K            # noqa: E402
from flappy import constants as C       # noqa: E402
from flappy import render as R          # noqa: E402


def _painted_fraction(surf, sample=6) -> float:
    import collections
    w, h = surf.get_size()
    vals = [surf.get_at((x, y)) for y in range(0, h, sample) for x in range(0, w, sample)]
    cols = collections.Counter((c.r // 16, c.g // 16, c.b // 16) for c in vals)
    return 1.0 - (cols.most_common(1)[0][1] / len(vals))


def _make_game() -> R.Game:
    with tempfile.TemporaryDirectory() as d:
        pass
    # Use a temp high-score file so the test never touches the user's record.
    path = os.path.join(tempfile.gettempdir(), "flippyblock_test_hs.json")
    if os.path.exists(path):
        os.remove(path)
    return R.Game(highscore_path=path, rng_seed=1)


class TestGameConstruction(unittest.TestCase):
    def test_constructs(self):
        game = _make_game()
        self.assertEqual(game.window_size, (C.WIDTH, C.HEIGHT))
        self.assertEqual(game.core.state, K.State.MENU)

    def test_key_mapping(self):
        game = _make_game()
        self.assertEqual(game._map_key(pygame.K_SPACE), K.Action.FLAP)
        self.assertEqual(game._map_key(pygame.K_RETURN), K.Action.START)
        self.assertEqual(game._map_key(pygame.K_p), K.Action.TOGGLE_PAUSE)
        self.assertEqual(game._map_key(pygame.K_m), "mute")
        self.assertEqual(game._map_key(pygame.K_q), "quit")


class TestStateRendering(unittest.TestCase):
    def setUp(self):
        self.game = _make_game()
        self.core = self.game.core

    def _force(self, state):
        self.core.state = state
        self.game._draw()
        pygame.display.flip()

    def test_every_state_renders_a_substantial_frame(self):
        for state in (K.State.MENU, K.State.READY, K.State.PLAYING,
                      K.State.PAUSED, K.State.GAME_OVER):
            self._force(state)
            frac = _painted_fraction(self.game.screen)
            self.assertGreater(frac, 0.25, f"{state} rendered near-blank")
            self.assertGreater(_brightness(self.game.screen), 0)

    def test_game_over_shows_score_and_buttons(self):
        self.core.score = 3
        self.core.is_new_record = False
        self._force(K.State.GAME_OVER)
        btns = self.game._buttons()
        self.assertIn("play", btns)
        self.assertIn("menu", btns)
        self.assertIn("sound", btns)


def _brightness(surf) -> int:
    return sum(surf.get_at((x, y)).r for x in range(0, surf.get_width(), 24)
               for y in range(0, surf.get_height(), 24))


class TestButtons(unittest.TestCase):
    def test_clicking_play_in_game_over_restarts(self):
        game = _make_game()
        game.core.score = 2
        game.core.state = K.State.GAME_OVER
        rect = game._buttons()["play"]
        game._handle_click(rect.center)
        self.assertEqual(game.core.state, K.State.READY)

    def test_clicking_menu_in_game_over_goes_to_menu(self):
        game = _make_game()
        game.core.state = K.State.GAME_OVER
        rect = game._buttons()["menu"]
        game._handle_click(rect.center)
        self.assertEqual(game.core.state, K.State.MENU)

    def test_click_in_playing_flaps(self):
        game = _make_game()
        game.core.state = K.State.PLAYING
        vy_before = game.core.bird.vy
        game._handle_click((C.WIDTH // 2, C.HEIGHT // 2))
        self.assertEqual(game.core.bird.vy, C.FLAP_VELOCITY)


class TestPresentationFreeze(unittest.TestCase):
    def test_paused_state_freezes_ground_and_wing_clock(self):
        # Regression: the ground scroll and wing-flap animation were advanced
        # in every state; a paused/dead bird must hold its last pose.
        game = _make_game()
        game.core.state = K.State.PLAYING
        game.assets.ground.advance(C.PIPE_SPEED * C.FIXED_DT)
        game._scroll(C.FIXED_DT)
        game._physics(C.FIXED_DT)
        ground_before = game.assets.ground.offset
        clouds_before = game.assets.clouds.offset
        wing_before = game.wing_time

        game.core.state = K.State.PAUSED
        for _ in range(120):
            game._scroll(C.FIXED_DT)
            game._physics(C.FIXED_DT)

        self.assertEqual(game.assets.ground.offset, ground_before)
        self.assertEqual(game.assets.clouds.offset, clouds_before)
        self.assertEqual(game.wing_time, wing_before)

    def test_game_over_freezes_ground(self):
        game = _make_game()
        game.core.state = K.State.PLAYING
        game.assets.ground.advance(C.PIPE_SPEED * C.FIXED_DT)
        game._scroll(C.FIXED_DT)
        before = game.assets.ground.offset
        game.core.state = K.State.GAME_OVER
        for _ in range(60):
            game._scroll(C.FIXED_DT)
        self.assertEqual(game.assets.ground.offset, before)


class _SoundSpy:
    """Records play() calls at the audio-device boundary; delegates the rest
    to the real (headless no-op) SoundBank."""

    def __init__(self, real) -> None:
        self._real = real
        self.calls = []

    def play(self, name: str) -> None:
        self.calls.append(name)
        self._real.play(name)

    def set_mute(self, mute: bool) -> None:
        self._real.set_mute(mute)

    def get_mute(self) -> bool:
        return self._real.get_mute()


def _spy(game) -> _SoundSpy:
    spy = _SoundSpy(game.sounds)
    game.sounds = spy
    return spy


class TestGameSounds(unittest.TestCase):
    def test_flap_action_plays_flap_sound(self):
        game = _make_game()
        spy = _spy(game)
        game._apply(K.Action.FLAP)               # menu -> ready, bird flaps
        self.assertIn("flap", spy.calls)
        game._apply(K.Action.FLAP)               # ready -> playing, flaps again
        self.assertEqual(spy.calls.count("flap"), 2)

    def test_game_over_flap_is_silent(self):
        game = _make_game()
        spy = _spy(game)
        game.core.state = K.State.GAME_OVER
        game._apply(K.Action.FLAP)               # ignored by the core
        self.assertNotIn("flap", spy.calls)

    def test_pipe_passed_plays_score_sound(self):
        game = _make_game()
        spy = _spy(game)
        game.core.state = K.State.PLAYING
        # Pipe just scrolled behind the bird, gap centred on it: one pass,
        # no collision.
        game.core.pipes = [K.PipePair(140.0, C.HEIGHT / 2)]
        game.core.bird.y = C.HEIGHT / 2
        game.core.bird.vy = 0.0
        self.assertEqual(game.core.score, 0)
        game._physics(C.FIXED_DT)
        self.assertEqual(game.core.score, 1)
        self.assertIn("score", spy.calls)

    def test_no_score_sound_without_progress(self):
        game = _make_game()
        spy = _spy(game)
        game.core.state = K.State.PLAYING
        game.core.pipes = [K.PipePair(140.0, C.HEIGHT / 2)]
        game.core.bird.y = C.HEIGHT / 2
        game.core.bird.vy = 0.0
        game._physics(C.FIXED_DT)                # the one pass (plays score)
        first = len(spy.calls)
        game._physics(C.FIXED_DT)                # nothing new
        self.assertEqual(len(spy.calls), first)


class TestSmokeRun(unittest.TestCase):
    def test_smoke_produces_a_full_painted_capture(self):
        path = os.path.join(tempfile.gettempdir(), "flippyblock_smoke_test.png")
        game = R.Game(highscore_path=None, smoke=True, rng_seed=7,
                      window_size=(C.WIDTH, C.HEIGHT))
        game.run(max_frames=140, fps=0)
        game.save_capture(path)
        self.assertTrue(os.path.exists(path))
        img = pygame.image.load(path)
        self.assertEqual(img.get_size(), (C.WIDTH, C.HEIGHT))
        self.assertGreater(_painted_fraction(img), 0.2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

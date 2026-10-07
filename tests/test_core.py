"""Unit tests for the pure game-logic core.

These drive the shipped :mod:`flappy.core` directly (no pygame required) and
cover physics, pipe spawning, collision, scoring, the state machine and
high-score persistence.
"""

import os
import random
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from flappy import core as K          # noqa: E402
from flappy import constants as C     # noqa: E402


class TestBirdPhysics(unittest.TestCase):
    def test_flap_applies_upward_impulse(self):
        b = K.Bird()
        before = b.vy
        b.flap()
        self.assertEqual(b.vy, C.FLAP_VELOCITY)
        self.assertLess(b.vy, before)          # impulse is upward
        self.assertLess(b.vy, 0)

    def test_one_flap_changes_velocity_as_specified(self):
        b = K.Bird()
        b.flap()
        self.assertAlmostEqual(b.vy, C.FLAP_VELOCITY)

    def test_gravity_pulls_the_bird_down(self):
        b = K.Bird(y=300)
        y0 = b.y
        for _ in range(60):
            b.step(C.FIXED_DT)
        self.assertGreater(b.y, y0)            # gravity increases downward motion
        self.assertGreater(b.vy, 0)

    def test_velocity_is_capped_at_terminal(self):
        b = K.Bird(y=300)
        for _ in range(60 * 20):
            b.step(C.FIXED_DT)
        self.assertLessEqual(b.vy, C.MAX_FALL_SPEED + 1e-6)
        self.assertGreaterEqual(b.vy, C.MAX_FALL_SPEED - 1e-6)

    def test_n_steps_without_flap_reaches_ground(self):
        b = K.Bird(y=300)
        hit = False
        for i in range(60 * 20):
            b.step(C.FIXED_DT)
            if b.hit_ground:
                hit = True
                break
        self.assertTrue(hit)

    def test_cannot_climb_above_top_forever(self):
        b = K.Bird(y=10)
        b.flap()
        for _ in range(60 * 20):
            b.step(C.FIXED_DT)
        self.assertGreaterEqual(b.y, -1e-9)


class TestPipeSpawning(unittest.TestCase):
    def test_gap_size_is_constant(self):
        rng = random.Random(1)
        for _ in range(200):
            pipe = K.PipePair(0, K.spawn_gap_center(rng))
            self.assertEqual(pipe.gap_size, C.PIPE_GAP)

    def test_gap_center_stays_within_fair_band(self):
        rng = random.Random(2)
        centers = [K.spawn_gap_center(rng) for _ in range(1000)]
        self.assertGreaterEqual(min(centers), C.GAP_MIN_CENTER - 1e-6)
        self.assertLessEqual(max(centers), C.GAP_MAX_CENTER + 1e-6)

    def test_gap_center_varies(self):
        rng = random.Random(3)
        centers = [K.spawn_gap_center(rng) for _ in range(100)]
        self.assertGreater(len(set(centers)), 1)

    def test_gap_is_always_reachable(self):
        rng = random.Random(4)
        for _ in range(200):
            pipe = K.PipePair(0, K.spawn_gap_center(rng))
            self.assertGreaterEqual(pipe.gap_top, 0)
            self.assertLessEqual(pipe.gap_bottom, C.GROUND_TOP)
            self.assertAlmostEqual(pipe.gap_bottom - pipe.gap_top, C.PIPE_GAP)

    def test_nonpositive_spacing_cannot_flood_pipes(self):
        # Regression: with a non-positive PIPE_SPACING the "far enough in"
        # test would be true on every call, appending a pipe forever.
        orig = C.PIPE_SPACING
        C.PIPE_SPACING = 0
        try:
            core = K.GameCore(rng=random.Random(6))
            core.pipes = []
            counts = set()
            for _ in range(600):
                core._maybe_spawn()
                counts.add(len(core.pipes))
            self.assertEqual(counts, {1})      # one initial pipe, never more
        finally:
            C.PIPE_SPACING = orig

    def test_steady_spacing_between_consecutive_pipes(self):
        # Each new pipe spawns exactly PIPE_SPACING ahead of the previous one,
        # and because they all scroll at the same speed the spacing is preserved.
        core = K.GameCore(rng=random.Random(5))
        core.pipes = []
        core._maybe_spawn()
        verified = 0
        for _ in range(3000):
            for p in core.pipes:
                p.x -= 3.0
            before = len(core.pipes)
            core._maybe_spawn()
            if len(core.pipes) > before and len(core.pipes) >= 2:
                self.assertAlmostEqual(
                    core.pipes[-1].x - core.pipes[-2].x,
                    C.PIPE_SPACING, delta=1e-6)
                verified += 1
                if verified >= 5:
                    break
        self.assertGreaterEqual(verified, 5)


class TestCollision(unittest.TestCase):
    def test_bird_inside_gap_does_not_collide(self):
        bird = K.Bird(x=150, y=300)
        pipe = K.PipePair(x=150, gap_center=300)   # opening centred on the bird
        self.assertFalse(pipe.collides(bird))

    def test_bird_overlapping_pipe_reports_collision(self):
        bird = K.Bird(x=150, y=10)                 # high, against the top pipe
        pipe = K.PipePair(x=150, gap_center=300)
        self.assertTrue(pipe.collides(bird))

    def test_bird_rect_intersecting_pipe_rect(self):
        bird = K.Bird(x=150, y=10)
        pipe = K.PipePair(x=150, gap_center=300)
        # Drive the raw rectangle helper: overlap must be detected.
        self.assertTrue(K.rects_collide(bird.rect, pipe.top_rect))

    def test_bird_far_from_pipe_no_collision(self):
        bird = K.Bird(x=150, y=300)
        pipe = K.PipePair(x=400, gap_center=300)   # horizontally apart
        self.assertFalse(pipe.collides(bird))

    def test_rects_collide_is_strict(self):
        # Touching exactly on an edge is not a collision.
        self.assertFalse(K.rects_collide((0, 0, 10, 10), (10, 0, 10, 10)))
        self.assertTrue(K.rects_collide((0, 0, 10, 10), (9, 0, 10, 10)))

    def test_ground_collision(self):
        bird = K.Bird(x=150, y=C.GROUND_TOP + 5)
        self.assertTrue(bird.hit_ground)


class TestScoring(unittest.TestCase):
    def _core_with_pipe_past_bird(self):
        core = K.GameCore(rng=random.Random(6))
        core.state = K.State.PLAYING
        core.bird = K.Bird(x=150, y=300)
        core.pipes = [K.PipePair(x=140, gap_center=300)]  # already behind bird
        return core

    def test_passing_a_pipe_increments_exactly_once(self):
        core = self._core_with_pipe_past_bird()
        self.assertEqual(core.score, 0)
        core.step(C.FIXED_DT)
        self.assertEqual(core.score, 1)
        core.step(C.FIXED_DT)
        core.step(C.FIXED_DT)
        self.assertEqual(core.score, 1)          # no double counting
        self.assertTrue(core.pipes[0].scored)
        self.assertEqual(core.state, K.State.PLAYING)

    def test_multiple_pipes_each_score_once(self):
        core = K.GameCore(rng=random.Random(7))
        core.state = K.State.PLAYING
        core.bird = K.Bird(x=150, y=300)
        core.pipes = [K.PipePair(x=140, gap_center=300), K.PipePair(x=120, gap_center=300)]
        core.step(C.FIXED_DT)
        self.assertEqual(core.score, 2)
        # Exactly the two already-behind pipes are scored; any newly spawned
        # pipe is still ahead and must not be counted yet.
        self.assertEqual(sum(1 for p in core.pipes if p.scored), 2)


class TestStateMachine(unittest.TestCase):
    def test_menu_start_to_ready(self):
        core = K.GameCore()
        self.assertEqual(core.state, K.State.MENU)
        core.handle_action(K.Action.START)
        self.assertEqual(core.state, K.State.READY)

    def test_ready_flap_to_playing(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        self.assertEqual(core.state, K.State.READY)
        core.handle_action(K.Action.FLAP)
        self.assertEqual(core.state, K.State.PLAYING)

    def test_playing_pause_to_paused_and_back(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        core.handle_action(K.Action.FLAP)
        self.assertEqual(core.state, K.State.PLAYING)
        core.handle_action(K.Action.PAUSE)
        self.assertEqual(core.state, K.State.PAUSED)
        core.handle_action(K.Action.RESUME)
        self.assertEqual(core.state, K.State.PLAYING)

    def test_toggle_pause_flips(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        core.handle_action(K.Action.FLAP)
        self.assertEqual(core.state, K.State.PLAYING)
        core.handle_action(K.Action.TOGGLE_PAUSE)
        self.assertEqual(core.state, K.State.PAUSED)
        core.handle_action(K.Action.TOGGLE_PAUSE)
        self.assertEqual(core.state, K.State.PLAYING)

    def test_start_does_not_reset_an_active_run(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        core.handle_action(K.Action.FLAP)
        self.assertEqual(core.state, K.State.PLAYING)
        core.score = 5
        core.handle_action(K.Action.START)   # ENTER mid-run must NOT reset
        self.assertEqual(core.state, K.State.PLAYING)
        self.assertEqual(core.score, 5)

    def test_collision_ends_run_in_game_over(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        core.handle_action(K.Action.FLAP)
        core.bird.y = C.GROUND_TOP + 10      # slam into the ground
        core.step(C.FIXED_DT)
        self.assertEqual(core.state, K.State.GAME_OVER)

    def test_game_over_restart_to_ready(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        core.handle_action(K.Action.FLAP)
        core.score = 7
        core.bird.y = C.GROUND_TOP + 5     # force the death
        core.step(C.FIXED_DT)
        self.assertEqual(core.state, K.State.GAME_OVER)
        core.handle_action(K.Action.RESTART)
        self.assertEqual(core.state, K.State.READY)
        self.assertEqual(core.score, 0)
        self.assertEqual(len(core.pipes), 0)

    def test_to_menu_from_any_state(self):
        core = K.GameCore()
        core.handle_action(K.Action.TO_MENU)
        self.assertEqual(core.state, K.State.MENU)
        self.assertEqual(core.score, 0)
        self.assertEqual(len(core.pipes), 0)

    def test_full_lifecycle(self):
        core = K.GameCore()
        self.assertEqual(core.state, K.State.MENU)
        core.handle_action(K.Action.FLAP)      # menu -> ready
        self.assertEqual(core.state, K.State.READY)
        core.handle_action(K.Action.FLAP)      # ready -> playing
        self.assertEqual(core.state, K.State.PLAYING)
        core.handle_action(K.Action.PAUSE)
        self.assertEqual(core.state, K.State.PAUSED)
        core.handle_action(K.Action.RESUME)
        self.assertEqual(core.state, K.State.PLAYING)
        core.bird.y = C.GROUND_TOP + 5
        core.step(C.FIXED_DT)
        self.assertEqual(core.state, K.State.GAME_OVER)
        core.handle_action(K.Action.START)     # game over -> ready
        self.assertEqual(core.state, K.State.READY)

    def test_pause_freezes_the_world(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        core.handle_action(K.Action.FLAP)
        for _ in range(30):
            core.step(C.FIXED_DT)
        y_before = core.bird.y
        for p in core.pipes:
            pass
        px_before = [p.x for p in core.pipes]
        core.handle_action(K.Action.PAUSE)
        for _ in range(30):
            core.step(C.FIXED_DT)
        self.assertAlmostEqual(core.bird.y, y_before)
        self.assertEqual([p.x for p in core.pipes], px_before)


class TestHighScore(unittest.TestCase):
    def test_in_memory_submit(self):
        store = K.HighScoreStore(path=None, initial=3)
        self.assertFalse(store.submit(2))
        self.assertEqual(store.value, 3)
        self.assertTrue(store.submit(5))
        self.assertEqual(store.value, 5)

    def test_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hs.json")
            store = K.HighScoreStore(path)
            store.submit(11)
            self.assertEqual(store.value, 11)
            reloaded = K.HighScoreStore(path)
            self.assertEqual(reloaded.value, 11)
            self.assertTrue(os.path.exists(path))

    def test_corrupt_file_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "hs.json")
            with open(path, "w") as fh:
                fh.write("not valid json {")
            store = K.HighScoreStore(path)
            self.assertEqual(store.value, 0)

    def test_highscore_updates_on_death(self):
        core = K.GameCore()
        core.handle_action(K.Action.START)
        core.handle_action(K.Action.FLAP)
        core.score = 9
        core.bird.y = C.GROUND_TOP + 5     # die -> submits the score
        core.step(C.FIXED_DT)
        self.assertEqual(core.state, K.State.GAME_OVER)
        self.assertEqual(core.high_score, 9)


def _bot_action(core: "K.GameCore") -> "K.Action":
    """A simple reactive pilot used to prove the game is actually playable.

    It rises when it drifts below the nearest gap centre and holds (to fall)
    otherwise, with a momentum guard to avoid double-flap overshoot.
    """
    bird = core.bird
    ahead = [p for p in core.pipes if p.x >= bird.x - 15]
    if not ahead:
        return (K.Action.FLAP if bird.y > bird.start_y + 8 and bird.vy > -150
                else K.Action.NONE)
    target = min(ahead, key=lambda p: p.x)
    if bird.y > target.gap_center + 6 and bird.vy > -180:
        return K.Action.FLAP
    return K.Action.NONE


class TestPlayableGame(unittest.TestCase):
    """End-to-end: a deterministic pilot drives the shipped core through a run.

    A fixed seed makes this reproducible; it guards the tuning (gravity, flap,
    gap, spacing) so the game stays a fair, beatable Flappy Bird clone.
    """

    def test_bot_survives_and_scores(self):
        core = K.GameCore(rng=random.Random(1))
        core.handle_action(K.Action.FLAP)   # menu -> ready
        core.handle_action(K.Action.FLAP)   # ready -> playing
        steps = 0
        max_score = 0
        while core.state == K.State.PLAYING and steps < 60 * 300:
            action = _bot_action(core)
            if action != K.Action.NONE:
                core.handle_action(action)
            core.step(C.FIXED_DT)
            max_score = max(max_score, core.score)
            steps += 1
        self.assertGreaterEqual(max_score, 1, "pilot passed no pipes")
        self.assertGreaterEqual(steps, 120, "pilot died almost immediately")
        self.assertEqual(core.state, K.State.GAME_OVER)


if __name__ == "__main__":
    unittest.main(verbosity=2)

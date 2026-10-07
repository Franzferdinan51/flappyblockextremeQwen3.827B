"""Pure game-logic core for FlippyBlock Extreme.

Everything in this module is deterministic and free of any pygame (or other
GUI/audio) import. It owns the simulation: bird physics, pipe spawning and
scrolling, collision, scoring, the game state machine and high-score
persistence. The pygame presentation layer in :mod:`flappy.render` reads this
state to draw and translates user input into :meth:`GameCore.handle_action` /
:meth:`GameCore.step` calls.

Geometry is expressed as plain floats and ``(left, top, width, height)``
rectangles rather than ``pygame.Rect`` so the whole core stays importable and
testable headlessly. The render layer converts to ``pygame.Rect`` only when it
draws.
"""

from __future__ import annotations

import json
import math
import os
import random
from enum import Enum
from typing import List, Optional, Tuple

from . import constants as C

# A rectangle is a plain (left, top, width, height) tuple of floats.
Rect = Tuple[float, float, float, float]


def rects_collide(a: Rect, b: Rect) -> bool:
    """Axis-aligned bounding-box overlap test (strict interior overlap).

    A strict test is used so merely touching an exact edge is not a death.
    """
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


class State(Enum):
    """The game states and the order they flow through."""

    MENU = C.STATE_MENU
    READY = C.STATE_READY
    PLAYING = C.STATE_PLAYING
    PAUSED = C.STATE_PAUSED
    GAME_OVER = C.STATE_GAME_OVER


class Action(Enum):
    """Discrete user intents the UI can feed into the core."""

    NONE = "none"
    FLAP = "flap"
    START = "start"          # menu / game_over -> ready
    PAUSE = "pause"          # playing -> paused
    RESUME = "resume"        # paused -> playing
    RESTART = "restart"      # game_over -> ready
    TO_MENU = "to_menu"      # anything -> menu
    TOGGLE_PAUSE = "toggle_pause"


class Bird:
    """The player's bird. Only the vertical axis is simulated."""

    def __init__(self, x: float = C.BIRD_X, y: float = C.BIRD_START_Y) -> None:
        self.x = float(x)
        self.y = float(y)
        self.vy = 0.0
        self.start_y = y
        # Rotation in degrees for the renderer: nose-up after a flap, then the
        # nose drops toward the fall angle as the bird accelerates downward.
        self.rotation = 0.0

    @property
    def rect(self) -> Rect:
        return (self.x - C.BIRD_W / 2, self.y - C.BIRD_H / 2, C.BIRD_W, C.BIRD_H)

    def flap(self) -> None:
        """Apply the upward impulse. This is the player's only control."""
        self.vy = C.FLAP_VELOCITY
        self.rotation = -35.0  # instant nose-up kick for feedback

    def step(self, dt: float) -> None:
        """Advance one physics step by ``dt`` seconds under gravity."""
        self.vy += C.GRAVITY * dt
        if self.vy > C.MAX_FALL_SPEED:
            self.vy = C.MAX_FALL_SPEED
        self.y += self.vy * dt
        # Do not let the bird fly off the top of the world; clamp it so it
        # settles back down instead of being trapped above the screen.
        if self.y < 0:
            self.y = 0.0
            if self.vy < 0:
                self.vy = 0.0
        # Map velocity to the classic nose-up / nose-down range.
        if self.vy < 0:
            self.rotation = -35.0
        else:
            self.rotation = min(90.0, (self.vy / C.MAX_FALL_SPEED) * 120.0)

    @property
    def hit_ground(self) -> bool:
        return self.y + C.BIRD_H / 2 >= C.GROUND_TOP


class PipePair:
    """A top and bottom pipe with a gap. Scrolls left at a constant speed."""

    def __init__(self, x: float, gap_center: float, gap_size: float = C.PIPE_GAP) -> None:
        self.x = float(x)
        self.gap_center = float(gap_center)
        self.gap_size = float(gap_size)
        self.scored = False

    @property
    def gap_top(self) -> float:
        return self.gap_center - self.gap_size / 2

    @property
    def gap_bottom(self) -> float:
        return self.gap_center + self.gap_size / 2

    def step(self, dt: float) -> None:
        self.x -= C.PIPE_SPEED * dt

    @property
    def top_rect(self) -> Rect:
        return (self.x - C.PIPE_WIDTH / 2, 0.0, C.PIPE_WIDTH, self.gap_top)

    @property
    def bottom_rect(self) -> Rect:
        return (self.x - C.PIPE_WIDTH / 2, self.gap_bottom, C.PIPE_WIDTH, C.GROUND_TOP - self.gap_bottom)

    def collides(self, bird: Bird) -> bool:
        r = bird.rect
        return rects_collide(r, self.top_rect) or rects_collide(r, self.bottom_rect)

    def has_passed(self, bird: Bird) -> bool:
        """True once the pipe centre has scrolled behind the bird centre.

        ``x`` is monotonically decreasing, so this becomes true exactly once.
        """
        return self.x < bird.x

    @property
    def is_offscreen(self) -> bool:
        return self.x + C.PIPE_WIDTH / 2 < 0


def spawn_gap_center(rnd: Optional[random.Random] = None) -> float:
    """Return a random gap centre within the fair band.

    The gap *size* is always the constant ``C.PIPE_GAP``; only the centre is
    randomised, and only within ``[GAP_MIN_CENTER, GAP_MAX_CENTER]`` so the
    opening is always reachable.
    """
    rng = rnd or random
    return rng.uniform(C.GAP_MIN_CENTER, C.GAP_MAX_CENTER)


class HighScoreStore:
    """Persists the high score to a small JSON file.

    When ``path`` is ``None`` the score is kept in memory only (used by the
    tests so they never touch the real user file).
    """

    def __init__(self, path: Optional[str] = None, initial: int = 0) -> None:
        self.path = path
        self.value = int(initial)
        if path is not None:
            self.value = self._load()

    def _load(self) -> int:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return max(0, int(data.get("high_score", 0)))
        except (OSError, ValueError, TypeError):
            return self.value

    def submit(self, score: int) -> bool:
        """Record ``score`` if it beats the stored high score.

        Returns ``True`` if a new high score was set.
        """
        if score > self.value:
            self.value = int(score)
            self._save()
            return True
        return False

    def _save(self) -> None:
        if self.path is None:
            return
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump({"high_score": int(self.value)}, fh)
        except OSError:
            # Persistence must never take the game down.
            pass


class GameCore:
    """Owns the whole simulation state and all of its transitions.

    The presentation layer drives it with two calls per frame:
    ``handle_action(action)`` for discrete inputs and ``step(dt)`` for the
    physics/animation tick. Everything else (collision, scoring, state) is
    derived inside these two methods so the logic is trivially unit-testable.
    """

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        highscore_path: Optional[str] = None,
        high_score: int = 0,
    ) -> None:
        self.rng = rng or random
        self.highscore = HighScoreStore(highscore_path, high_score)
        self.state = State.MENU
        self.bird = Bird()
        self.pipes: List[PipePair] = []
        self.score = 0
        self.best_at_run_start = self.highscore.value
        # Per-run animation clock, used for the idle bob in the ready state.
        self.time = 0.0
        self.is_new_record = False

    # -- convenience accessors used by the UI -------------------------------
    @property
    def high_score(self) -> int:
        return self.highscore.value

    @property
    def run_is_record(self) -> bool:
        return self.score > self.best_at_run_start and self.score > 0

    # -- state transitions ---------------------------------------------------
    def _reset_run(self) -> None:
        self.bird = Bird()
        self.pipes = []
        self.score = 0
        self.time = 0.0
        self.is_new_record = False
        self.best_at_run_start = self.highscore.value

    def handle_action(self, action: Action) -> State:
        """Process a discrete user action and return the resulting state.

        Every action is guarded by the current state so that, for example,
        ENTER (START) can only begin a run from the menu or game-over screen,
        never reset an in-progress run.
        """
        if action == Action.NONE:
            return self.state

        s = self.state

        if action == Action.TOGGLE_PAUSE:
            if s == State.PLAYING:
                self.state = State.PAUSED
            elif s == State.PAUSED:
                self.state = State.PLAYING
            return self.state

        if action == Action.START:
            if s in (State.MENU, State.GAME_OVER):
                self._reset_run()
                self.state = State.READY
            return self.state

        if action == Action.FLAP:
            if s == State.MENU:
                self._reset_run()
                self.state = State.READY
                self.bird.flap()
            elif s == State.READY:
                # First flap launches the bird and starts the run.
                self.state = State.PLAYING
                self.bird.flap()
            elif s == State.PLAYING:
                self.bird.flap()
            return self.state

        if action == Action.PAUSE:
            if s == State.PLAYING:
                self.state = State.PAUSED
            return self.state

        if action == Action.RESUME:
            if s == State.PAUSED:
                self.state = State.PLAYING
            return self.state

        if action == Action.RESTART:
            if s in (State.GAME_OVER, State.PAUSED):
                self._reset_run()
                self.state = State.READY
            return self.state

        if action == Action.TO_MENU:
            self._reset_run()
            self.state = State.MENU
            return self.state

        return self.state

    # -- simulation tick -----------------------------------------------------
    def step(self, dt: float) -> State:
        """Advance the simulation by ``dt`` seconds according to the state."""
        self.time += dt
        s = self.state

        if s == State.PLAYING:
            self._step_playing(dt)
        elif s == State.READY:
            # Idle bob; no gravity and no pipes in the ready screen.
            self.bird.y = self.bird.start_y + 8.0 * (1.0 - math.cos(6.0 * self.time))
            self.bird.rotation = 0.0
        # MENU / PAUSED / GAME_OVER: the world is frozen.
        return self.state

    def _step_playing(self, dt: float) -> None:
        self.bird.step(dt)

        for pipe in self.pipes:
            pipe.step(dt)

        self._maybe_spawn()
        self.pipes = [p for p in self.pipes if not p.is_offscreen]

        for pipe in self.pipes:
            if not pipe.scored and pipe.has_passed(self.bird):
                pipe.scored = True
                self.score += 1
                self.is_new_record = self.highscore.submit(self.score)

        if self.bird.hit_ground or any(p.collides(self.bird) for p in self.pipes):
            self._die()

    def _maybe_spawn(self) -> None:
        """Keep a steady stream: spawn a new pair once the newest is far enough in."""
        if not self.pipes:
            self.pipes.append(PipePair(C.FIRST_PIPE_OFFSET, spawn_gap_center(self.rng)))
        elif C.PIPE_SPACING > 0:
            # A non-positive spacing would make the distance test true every
            # tick and flood the screen with pipes, so never spawn in that case.
            last = self.pipes[-1]
            if last.x < C.WIDTH - C.PIPE_SPACING:
                self.pipes.append(PipePair(last.x + C.PIPE_SPACING, spawn_gap_center(self.rng)))

    def _die(self) -> None:
        self.highscore.submit(self.score)
        self.is_new_record = self.score > self.best_at_run_start and self.score > 0
        self.state = State.GAME_OVER

    # -- geometry convenience for the render layer --------------------------
    def bird_rect(self) -> Rect:
        return self.bird.rect

    def pipe_rects(self) -> List[Rect]:
        out: List[Rect] = []
        for pipe in self.pipes:
            out.append(pipe.top_rect)
            out.append(pipe.bottom_rect)
        return out


# Re-export the geometry constants through this module so the render layer and
# tests can import a single surface.
WIDTH = C.WIDTH
HEIGHT = C.HEIGHT
GROUND_TOP = C.GROUND_TOP

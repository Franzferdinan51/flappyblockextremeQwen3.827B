"""Tuning constants for FlippyBlock Extreme.

This module holds every tunable number in one place so the pure game-logic
core, the procedural asset generator and the pygame presentation layer all
agree on the same geometry and feel. It must stay dependency-free (no pygame)
so it can be imported from the pure logic and from tests.
"""

# --- Logical window --------------------------------------------------------
# The game is designed at a fixed logical resolution and scaled to the window
# on display. Keeping a fixed internal resolution keeps physics resolution
# independent and makes the render code simple.
WIDTH = 512
HEIGHT = 768

# --- Ground ----------------------------------------------------------------
GROUND_HEIGHT = 140
# Top edge of the ground strip (y coordinate). Everything above is air.
GROUND_TOP = HEIGHT - GROUND_HEIGHT  # 628

# --- Bird ------------------------------------------------------------------
# Horizontal position is fixed; only vertical physics is simulated (like the
# classic game). The collision box is deliberately a little smaller than the
# sprite so near-misses feel fair.
BIRD_X = 150
BIRD_SIZE = 52            # sprite size in px
BIRD_W = 44               # collision box width
BIRD_H = 32               # collision box height
BIRD_START_Y = HEIGHT // 2

# --- Physics (units are pixels and seconds) --------------------------------
GRAVITY = 2600.0          # downward acceleration, px/s^2
FLAP_VELOCITY = -680.0    # instantaneous vertical velocity applied on flap, px/s
MAX_FALL_SPEED = 1200.0   # terminal velocity, px/s
# A fixed timestep makes physics deterministic and frame-rate independent.
FIXED_DT = 1.0 / 60.0

# --- Pipes -----------------------------------------------------------------
PIPE_SPEED = 210.0        # horizontal scroll speed, px/s
PIPE_WIDTH = 88
PIPE_GAP = 185            # constant vertical opening the bird must pass through
PIPE_SPACING = 300        # horizontal distance between consecutive pipe pairs
# The random gap-centre is constrained to this band so there is always a fair,
# reachable opening (never too close to the ceiling or the ground).
GAP_MIN_CENTER = PIPE_GAP // 2 + 70
GAP_MAX_CENTER = GROUND_TOP - PIPE_GAP // 2 - 70
# Horizontal offset from the left edge where the *first* pipe of a new run
# appears, leaving the player a moment to settle before the first obstacle.
FIRST_PIPE_OFFSET = WIDTH + 160

# --- Scoring / state -------------------------------------------------------
# A pipe counts as passed (and scores) once its centre column has scrolled
# behind the bird's centre column.
STATE_MENU = "menu"
STATE_READY = "ready"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_GAME_OVER = "game_over"

ALL_STATES = (STATE_MENU, STATE_READY, STATE_PLAYING, STATE_PAUSED, STATE_GAME_OVER)

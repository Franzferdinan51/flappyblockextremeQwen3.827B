"""FlippyBlock Extreme — entry point.

Run the game normally:

    python main.py

Run a headless self-test (the "smoke" hook): the real game loop runs for a
fixed number of frames, drives a scripted sequence through
menu -> ready -> playing, saves one rendered PNG and exits. This is what lets
the launcher be verified without a human at the keyboard.

    python main.py --smoke --frames 360 --out frame.png

Everything is generated in code; the only dependency is pygame.
"""

from __future__ import annotations

import argparse
import os
import sys

import pygame

from flappy import default_highscore_path
from flappy.render import Game, new_game, TARGET_FPS


def _ensure_display() -> None:
    """Make sure a display is available, falling back to the dummy driver."""
    if pygame.display.get_init():
        return
    try:
        pygame.display.init()
    except Exception:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.display.init()


def _ensure_font() -> None:
    if not pygame.font.get_init():
        pygame.font.init()


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="flippyblock",
        description="FlippyBlock Extreme — a self-contained Flappy Bird-style game.",
    )
    p.add_argument("--smoke", action="store_true",
                   help="run the game loop for --frames frames, save one frame, then exit")
    p.add_argument("--frames", type=int, default=360,
                   help="number of frames to run in --smoke mode (default 360)")
    p.add_argument("--capture-frame", type=int, default=90,
                   help="frame at which --smoke saves the rendered frame (default 90)")
    p.add_argument("--out", default="smoke_frame.png",
                   help="output path for the saved frame in --smoke mode")
    p.add_argument("--width", type=int, default=512, help="window width (logical 512)")
    p.add_argument("--height", type=int, default=768, help="window height (logical 768)")
    p.add_argument("--highscore", default=None,
                   help="override the high-score file path")
    p.add_argument("--seed", type=int, default=None, help="random seed (reproducible pipes)")
    p.add_argument("--fps", type=int, default=TARGET_FPS, help="target frame rate")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # Configure audio before the rest of pygame inits.
    try:
        pygame.mixer.pre_init(22050, 1, -2048, 512)
    except Exception:
        pass
    pygame.init()
    _ensure_display()
    _ensure_font()

    highscore = args.highscore or default_highscore_path()
    window_size = (args.width, args.height)

    # In smoke mode, pin a default seed so the captured frame is reproducible.
    seed = args.seed if args.seed is not None else (7 if args.smoke else None)

    game = new_game(
        highscore_path=highscore,
        smoke=args.smoke,
        window_size=window_size,
        rng_seed=seed,
        smoke_capture_frame=args.capture_frame,
    )

    try:
        if args.smoke:
            game.run(max_frames=args.frames, fps=0)
            out = os.path.abspath(args.out)
            game.save_capture(out)
            # Emit machine-readable status for the verifier.
            print(f"SMOKE_OK state={game.core.state.value} score={game.core.score} "
                  f"high={game.core.highscore.value} frame={out} size={window_size}")
        else:
            game.run(fps=args.fps)
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# FlippyBlock Extreme

A highly faithful Flappy Bird clone in Python. Everything — bird, pipes, ground,
clouds, UI and all sound effects — is generated procedurally in code at runtime.
There are no external asset files anywhere; the only dependency is **pygame**.

## Run

```bash
pip install pygame
python main.py
```

## Controls

| Input | Action |
| --- | --- |
| `SPACE` / `UP` / `W` / mouse click | Flap |
| `RETURN` | Start / restart |
| `P` or `ESC` | Pause / resume |
| `M` | Mute / unmute |
| `Q` or close the window | Quit |

## Features

- Fixed-timestep simulation (60 Hz physics) with a classic Flappy gravity/flap feel
- Steady pipe stream with constant gap size and randomized-but-fair gap centers
- Menu → get-ready → playing ↔ paused → game-over → restart flow
- Score, persistent high score (JSON file), new-record flash
- Four-frame flapping animation, bird rotation, scrolling ground, parallax clouds
- Procedurally synthesized sounds (flap, score, hit, thud, UI beeps) + mute
- Game-over panel with Play / Menu / Sound buttons (mouse or keyboard)

## Self-test

```bash
python main.py --smoke --frames 360 --out frame.png
```

Runs the real game loop headlessly for a fixed number of frames, saves one
rendered PNG, prints a `SMOKE_OK` status line, and exits.

## Tests

```bash
python -m unittest discover -s tests -v
```

69 tests cover physics, pipe spawning, collision, scoring, the state machine,
high-score persistence, procedural assets, synthesized sound, the render layer,
and a static scan that no asset file is ever loaded.

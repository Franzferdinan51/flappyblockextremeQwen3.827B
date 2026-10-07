"""Synthesised sound effects for FlippyBlock Extreme.

Every sound is generated in code from raw sample buffers (plain Python math +
the :mod:`array` module) and handed to ``pygame.mixer`` — no audio files are
ever read or written.

The whole :class:`SoundBank` is defensive: if the audio subsystem cannot be
initialised (e.g. a headless / dummy SDL environment), every ``play`` call is a
silent no-op, so the game runs fine without sound. A runtime mute flag is also
respected, driving the on-screen sound toggle.
"""

from __future__ import annotations

import array
import math
import random
from typing import Dict, List, Optional

import pygame


def _exp_envelope(t: float, dur: float, attack: float = 0.004) -> float:
    """A fast attack followed by an exponential decay to zero."""
    if dur <= 0:
        return 0.0
    t = max(0.0, t)
    if t < attack:
        env = t / attack if attack > 0 else 1.0
    else:
        env = math.exp(-7.0 * (t - attack) / max(dur - attack, 1e-6))
    # fully gate the very end so there is no click
    if t >= dur:
        env *= max(0.0, 1.0 - (t - dur) / 0.01)
    return max(0.0, min(1.0, env))


def _tone(freq: float, dur: float, vol: float = 1.0, shape: str = "sine",
          slide: float = 0.0, rate: int = 22050) -> List[float]:
    """Render a single oscillator for ``dur`` seconds as a float list."""
    n = max(1, int(dur * rate))
    out: List[float] = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / rate
        f = freq + slide * t
        phase += 2.0 * math.pi * f / rate
        if shape == "sine":
            v = math.sin(phase)
        elif shape == "square":
            v = 1.0 if math.sin(phase) >= 0 else -1.0
        elif shape == "triangle":
            v = (2.0 / math.pi) * math.asin(math.sin(phase))
        else:
            v = math.sin(phase)
        out[i] = v * vol * _exp_envelope(t, dur)
    return out


def _noise(dur: float, vol: float = 1.0, rate: int = 22050, lowpass: float = 0.35,
           seed: Optional[int] = None) -> List[float]:
    """A short filtered noise burst (the 'whoosh' family)."""
    rng = random.Random(seed)
    n = max(1, int(dur * rate))
    out: List[float] = [0.0] * n
    last = 0.0
    for i in range(n):
        t = i / rate
        v = rng.uniform(-1.0, 1.0)
        last = last + lowpass * (v - last)
        out[i] = last * vol * _exp_envelope(t, dur, attack=0.002)
    return out


def _sum(*parts: List[float]) -> List[float]:
    n = max((len(p) for p in parts), default=0)
    out = [0.0] * n
    for part in parts:
        for i, v in enumerate(part):
            out[i] += v
    return out


def _render(samples: List[float], rate: int) -> bytes:
    """Clamp float samples to [-1, 1] and pack to 16-bit signed little-endian."""
    buf = array.array("h")
    buf.extend(int(round(max(-1.0, min(1.0, v)) * 32767)) for v in samples)
    return buf.tobytes()


class SoundBank:
    """Builds every sound once and plays them, honouring mute and availability."""

    def __init__(self, rate: int = 22050, channels: int = 1, mute: bool = False) -> None:
        self.rate = rate
        self.channels = channels
        self.mute = mute
        self.available = False
        self._sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(rate, channels, -2048, 512)
            self.available = pygame.mixer.get_init() is not None
        except Exception:
            self.available = False

        if self.available:
            self._build()

    def _build(self) -> None:
        r = self.rate
        # flap: a soft, quick wing whoosh
        self._sounds["flap"] = self._make(_noise(0.09, 0.55, r, lowpass=0.5, seed=1))
        # score: a bright two-note "ding"
        self._sounds["score"] = self._make(_sum(_tone(1046.0, 0.06, 0.5, "sine", rate=r),
                                                 _tone(1568.0, 0.12, 0.5, "sine", rate=r)[int(0.05 * r):]))
        # hit: a low thump plus a crash
        self._sounds["hit"] = self._make(_sum(_tone(140.0, 0.16, 0.8, "sine", slide=-60.0, rate=r),
                                              _noise(0.14, 0.5, r, lowpass=0.4, seed=7)))
        # die: a descending whistle
        self._sounds["die"] = self._make(_tone(720.0, 0.5, 0.55, "sine", slide=-640.0, rate=r))
        # swoosh: menu / transition
        self._sounds["swoosh"] = self._make(_noise(0.16, 0.4, r, lowpass=0.25, seed=3))
        # record: a little ascending fanfare
        self._sounds["record"] = self._make(_sum(
            _tone(784.0, 0.10, 0.5, "square", rate=r),
            _tone(1046.0, 0.10, 0.5, "square", rate=r)[int(0.09 * r):],
            _tone(1568.0, 0.18, 0.5, "square", rate=r)[int(0.18 * r):],
        ))

    def _make(self, samples: List[float]) -> Optional[pygame.mixer.Sound]:
        try:
            return pygame.mixer.Sound(buffer=_render(samples, self.rate))
        except Exception:
            return None

    def play(self, name: str) -> None:
        if not self.available or self.mute:
            return
        sound = self._sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except Exception:
            pass

    def set_mute(self, mute: bool) -> None:
        self.mute = bool(mute)

    def get_mute(self) -> bool:
        return self.mute

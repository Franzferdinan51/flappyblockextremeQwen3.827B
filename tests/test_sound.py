"""Tests for the synthesised sound bank.

The raw synthesis helpers are pure (no device needed) and are tested directly
for real, non-silent output. The :class:`SoundBank` is tested for graceful
behaviour: it must construct and play without crashing even when the audio
subsystem is unavailable (dummy driver), and it must honour mute.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import array  # noqa: E402
import unittest  # noqa: E402

import pygame  # noqa: E402
pygame.init()

from flappy import sound as S  # noqa: E402


def _peak(samples) -> int:
    buf = S._render(samples, 22050)
    arr = array.array("h")
    arr.frombytes(buf)
    return max(abs(min(arr)), abs(max(arr)))


class TestSynthesis(unittest.TestCase):
    def test_tone_is_non_silent(self):
        self.assertGreater(_peak(S._tone(880.0, 0.1, 1.0, "sine", rate=22050)), 20000)

    def test_slide_changes_pitch(self):
        # A sliding tone has a different spectral shape than a steady one.
        steady = S._tone(440.0, 0.2, 1.0, "sine", rate=22050)
        slide = S._tone(440.0, 0.2, 1.0, "sine", slide=-400.0, rate=22050)
        self.assertNotEqual(steady[:100], slide[:100])

    def test_noise_is_non_silent(self):
        self.assertGreater(_peak(S._noise(0.1, 1.0, rate=22050, seed=1)), 1000)

    def test_envelope_decays(self):
        samples = S._tone(660.0, 0.2, 1.0, "sine", rate=22050)
        start_rms = sum(abs(v) for v in samples[:22]) / 22
        end_rms = sum(abs(v) for v in samples[-22:]) / 22
        self.assertGreater(start_rms, end_rms)

    def test_render_produces_bytes(self):
        buf = S._render([0.5, -0.5, 0.0], 22050)
        self.assertEqual(len(buf), 6)  # 3 * 2 bytes (16-bit)


class TestSoundBank(unittest.TestCase):
    def test_constructs_without_crash(self):
        bank = S.SoundBank()
        # Whether or not a device is present, the object must be usable.
        self.assertIsInstance(bank.available, bool)
        for name in ("flap", "score", "hit", "die", "swoosh", "record"):
            bank.play(name)  # must not raise
        self.assertFalse(bank.get_mute())

    def test_mute_toggle(self):
        bank = S.SoundBank()
        bank.set_mute(True)
        self.assertTrue(bank.get_mute())
        bank.play("flap")  # silent path must not raise
        bank.set_mute(False)
        self.assertFalse(bank.get_mute())


if __name__ == "__main__":
    unittest.main(verbosity=2)

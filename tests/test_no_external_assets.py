"""Static check: the game loads no external asset files.

Scans every game source file for image/audio/font *load* calls and file-path
literals with media extensions. Any actual asset-file load fails the test.
(Generating and *saving* a PNG for the smoke hook is allowed — that is output,
not an asset load.) Also asserts the in-code generation is actually present.
"""

import os
import re
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

ASSET_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tga", ".webp",
              ".wav", ".mp3", ".ogg", ".mid", ".flac", ".m4a",
              ".ttf", ".otf", ".freetype")

IMAGE_LOAD = re.compile(r"\bimage\.(load|load_basic)\s*\(")
MUSIC = re.compile(r"\bmixer\.music\b|\b\.set_file\s*\(")
# A string literal that ends in a media extension -> an external asset path.
STRING_ASSET = re.compile(r"['\"][^'\"]*(" + "|".join(
    re.escape(e) for e in ASSET_EXTS) + r")['\"]")


def _source_files():
    files = [os.path.join(_ROOT, "main.py")]
    pkg = os.path.join(_ROOT, "flappy")
    for name in sorted(os.listdir(pkg)):
        if name.endswith(".py"):
            files.append(os.path.join(pkg, name))
    return files


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestNoExternalAssets(unittest.TestCase):
    def test_no_image_loads(self):
        for path in _source_files():
            self.assertFalse(IMAGE_LOAD.search(_read(path)), f"image.load in {path}")

    def test_no_mixer_music(self):
        for path in _source_files():
            self.assertFalse(MUSIC.search(_read(path)), f"mixer.music in {path}")

    def test_no_string_asset_paths(self):
        # A media-extension string is only an asset *load* if it is read.
        # Output paths (pygame.image.save / argparse --out) and data files
        # (the high-score .json) are not asset loads, so skip those lines.
        save_markers = ("save", "add_argument", "--out", "highscore", "out=", ".json")
        offenders = []
        for path in _source_files():
            with open(path, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if not STRING_ASSET.search(line):
                        continue
                    low = line.lower()
                    if any(marker in low for marker in save_markers):
                        continue
                    offenders.append(f"{path}:{i}: {line.strip()}")
        self.assertFalse(offenders, "External asset path found:\n" + "\n".join(offenders))

    def test_font_uses_builtin_not_file(self):
        # Every pygame.font.Font call must use None (the bundled font), never a path.
        for path in _source_files():
            src = _read(path)
            for m in re.finditer(r"font\.Font\(([^)]*)\)", src):
                self.assertIn("None", m.group(1), f"font path in {path}: {m.group(0)}")

    def test_sound_uses_buffer_not_file(self):
        sound_path = os.path.join(_ROOT, "flappy", "sound.py")
        src = _read(sound_path)
        self.assertTrue(re.search(r"mixer\.Sound\(\s*buffer=", src),
                        "Sound should be built from a generated buffer")

    def test_generation_present(self):
        self.assertIn("pygame.Surface", _read(os.path.join(_ROOT, "flappy", "assets.py")))
        self.assertIn("pygame.draw", _read(os.path.join(_ROOT, "flappy", "assets.py")))
        self.assertIn("array.array", _read(os.path.join(_ROOT, "flappy", "sound.py")))


if __name__ == "__main__":
    unittest.main(verbosity=2)

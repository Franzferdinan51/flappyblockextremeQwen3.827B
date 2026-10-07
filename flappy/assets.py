"""Procedurally generated visual assets for FlippyBlock Extreme.

Nothing here touches the disk: every sprite is a ``pygame.Surface`` built from
primitives (rectangles, ellipses, polygons, gradients). The :class:`AssetBank`
builds and caches everything once, and exposes getters that the render layer
uses each frame.
"""

from __future__ import annotations

from typing import List, Tuple

import pygame

from . import constants as C

Color = Tuple[int, int, int, int]

# --- palette ---------------------------------------------------------------
SKY_TOP = (96, 165, 224, 255)
SKY_BOTTOM = (186, 226, 245, 255)
SUN = (255, 236, 150, 255)
SUN_CORE = (255, 250, 210, 255)
HILL_FAR = (120, 180, 150, 255)
HILL_NEAR = (90, 156, 120, 255)
CLOUD = (255, 255, 255, 235)

PIPE_BODY = (94, 192, 92, 255)
PIPE_LIGHT = (168, 224, 120, 255)
PIPE_DARK = (48, 120, 64, 255)
PIPE_EDGE = (34, 88, 48, 255)
PIPE_CAP = (120, 200, 110, 255)

GROUND_DIRT = (222, 184, 130, 255)
GROUND_DARK = (196, 150, 96, 255)
GRASS = (124, 200, 86, 255)
GRASS_DARK = (96, 168, 66, 255)
GRASS_LIGHT = (158, 224, 108, 255)

BIRD_BODY = (255, 208, 66, 255)
BIRD_BELLY = (255, 240, 196, 255)
BIRD_WING = (255, 170, 60, 255)
BIRD_WING_DARK = (232, 138, 44, 255)
BIRD_BEAK = (255, 140, 60, 255)
BIRD_BEAK_DARK = (224, 108, 40, 255)
BIRD_OUTLINE = (96, 72, 32, 255)
EYE_WHITE = (255, 255, 255, 255)
EYE_BLACK = (40, 40, 48, 255)

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
SHADOW = (0, 0, 0, 160)
PANEL = (255, 250, 240, 235)
PANEL_EDGE = (96, 82, 60, 255)
ACCENT = (255, 170, 40, 255)
ACCENT_DARK = (214, 128, 26, 255)


def _gradient(size: Tuple[int, int], top: Color, bottom: Color, vertical: bool = True) -> pygame.Surface:
    """A smooth two-stop linear gradient surface."""
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    r0, g0, b0, a0 = top
    r1, g1, b1, a1 = bottom
    steps = h if vertical else w
    if steps <= 1:
        surf.fill((int(r1), int(g1), int(b1), int(a1)))
        return surf
    for i in range(steps):
        t = i / (steps - 1)
        col = (
            int(r0 + (r1 - r0) * t),
            int(g0 + (g1 - g0) * t),
            int(b0 + (b1 - b0) * t),
            int(a0 + (a1 - a0) * t),
        )
        if vertical:
            pygame.draw.rect(surf, col, (0, i, w, 1))
        else:
            pygame.draw.rect(surf, col, (i, 0, 1, h))
    return surf


class BirdSprite:
    """Pre-renders the bird in a few wing phases; the render layer rotates."""

    def __init__(self, size: int = C.BIRD_SIZE) -> None:
        self.size = size
        self.frames: List[pygame.Surface] = [self._frame(i, size) for i in range(4)]
        self.count = len(self.frames)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.size // 2, self.size // 2)

    @staticmethod
    def _frame(phase: int, size: int) -> pygame.Surface:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size / 2
        body_r = size * 0.36
        # body
        pygame.draw.ellipse(s, BIRD_BODY, pygame.Rect(c - body_r, c - body_r, body_r * 2, body_r * 2))
        pygame.draw.ellipse(s, BIRD_OUTLINE, pygame.Rect(c - body_r, c - body_r, body_r * 2, body_r * 2), 2)
        # belly (lower-front)
        belly_r = body_r * 0.62
        pygame.draw.ellipse(s, BIRD_BELLY, pygame.Rect(c - belly_r * 0.55, c - belly_r * 0.15, belly_r * 1.5, belly_r * 1.5))
        # wing with a flap phase: the wing lifts/lowers and tilts
        wing_lift = [-6, -1, 4, -1][phase % 4]
        wing_w = body_r * 1.05
        wing_h = body_r * 0.7
        wing_x = c - body_r * 0.85
        wing_y = c - _body_hoff() - body_r * 0.1
        wing_rect = pygame.Rect(wing_x, wing_y + wing_lift, wing_w, wing_h)
        pygame.draw.ellipse(s, BIRD_WING, wing_rect)
        pygame.draw.ellipse(s, BIRD_WING_DARK, wing_rect, 2)
        # beak (right-facing)
        beak_pts = [
            (c + body_r * 0.55, c - body_r * 0.12),
            (c + body_r * 1.5, c + body_r * 0.02),
            (c + body_r * 0.55, c + body_r * 0.30),
        ]
        pygame.draw.polygon(s, BIRD_BEAK, beak_pts)
        pygame.draw.lines(s, BIRD_BEAK_DARK, False, beak_pts, 2)
        # eye (upper-front)
        eye_r = body_r * 0.42
        eye_c = (c + body_r * 0.35, c - body_r * 0.35)
        pygame.draw.circle(s, EYE_WHITE, (int(eye_c[0]), int(eye_c[1])), int(eye_r))
        pygame.draw.circle(s, EYE_WHITE, (int(eye_c[0]), int(eye_c[1])), int(eye_r), 2)
        pygame.draw.circle(s, EYE_BLACK, (int(eye_c[0] + eye_r * 0.35), int(eye_c[1])), int(eye_r * 0.45))
        # tiny highlight
        pygame.draw.circle(s, (255, 255, 255, 255), (int(eye_c[0] + eye_r * 0.05), int(eye_c[1] - eye_r * 0.3)), max(1, int(eye_r * 0.15)))
        return s


def _body_hoff() -> float:
    return C.BIRD_SIZE * 0.10


class PipeSprite:
    """A pipe column with a highlight; body is a gradient strip scaled to fit."""

    def __init__(self, width: int = C.PIPE_WIDTH, cap_height: int = 26, cap_lip: int = 10) -> None:
        self.width = width
        self.cap_height = cap_height
        self.cap_lip = cap_lip
        # A horizontal gradient strip: dark edge, light centre, dark edge.
        self._body_strip = self._make_body_strip()
        self._cap = self._make_cap()
        self._body_cache: dict[int, pygame.Surface] = {}

    def _make_body_strip(self) -> pygame.Surface:
        h = 24
        w = max(2, self.width)
        strip = pygame.Surface((w, h), pygame.SRCALPHA)
        denom = max(1, w - 1)
        for x in range(w):
            t = x / denom
            # symmetric shading: bright around 1/3 from the left, dark at edges
            edge = abs(t - 0.32) * 2.0
            edge = min(1.0, edge)
            r = int(PIPE_LIGHT[0] + (PIPE_DARK[0] - PIPE_LIGHT[0]) * edge)
            g = int(PIPE_LIGHT[1] + (PIPE_DARK[1] - PIPE_LIGHT[1]) * edge)
            b = int(PIPE_LIGHT[2] + (PIPE_DARK[2] - PIPE_LIGHT[2]) * edge)
            pygame.draw.line(strip, (r, g, b, 255), (x, 0), (x, h - 1))
        # crisp outline
        pygame.draw.rect(strip, PIPE_EDGE, (0, 0, w, h), 2)
        return strip

    def _make_cap(self) -> pygame.Surface:
        w = max(2, self.width + self.cap_lip * 2)
        s = pygame.Surface((w, self.cap_height), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, w, self.cap_height)
        pygame.draw.rect(s, PIPE_CAP, rect, border_radius=4)
        # shading like the body
        denom = max(1, w - 1)
        for x in range(w):
            t = x / denom
            edge = min(1.0, abs(t - 0.32) * 2.0)
            r = int(PIPE_LIGHT[0] + (PIPE_DARK[0] - PIPE_LIGHT[0]) * edge)
            g = int(PIPE_LIGHT[1] + (PIPE_DARK[1] - PIPE_LIGHT[1]) * edge)
            b = int(PIPE_LIGHT[2] + (PIPE_DARK[2] - PIPE_LIGHT[2]) * edge)
            pygame.draw.line(s, (r, g, b, 255), (x, 2), (x, self.cap_height - 3))
        pygame.draw.rect(s, PIPE_EDGE, rect, 2, border_radius=4)
        return s

    def body(self, height: int) -> pygame.Surface:
        height = max(1, int(height))
        key = (height // 2) * 2  # quantize to 2px to bound the cache
        surf = self._body_cache.get(key)
        if surf is None:
            surf = pygame.transform.scale(self._body_strip, (self.width, max(2, key)))
            if len(self._body_cache) > 512:
                self._body_cache.clear()
            self._body_cache[key] = surf
        return surf

    def cap(self) -> pygame.Surface:
        return self._cap

    def cap_offset(self) -> int:
        return self.cap_lip


class Ground:
    """A scrolling ground: grass strip on top of dirt with a moving pattern."""

    def __init__(self, width: int, height: int = C.GROUND_HEIGHT) -> None:
        self.width = width
        self.height = height
        self.offset = 0.0
        self.tile = self._make_tile(width, height)
        self.tile_w = width

    def _make_tile(self, width: int, height: int) -> pygame.Surface:
        surf = pygame.Surface((width * 2, height), pygame.SRCALPHA)
        # dirt body
        surf.fill(GROUND_DIRT)
        # subtle diagonal dirt stripes for a scrolling feel
        stripe = 26
        for x in range(-stripe, width * 2, stripe * 2):
            pts = [
                (x, height),
                (x + stripe, 0),
                (x + stripe * 2, 0),
                (x + stripe, height),
            ]
            pygame.draw.polygon(surf, GROUND_DARK, pts)
        # grass top band
        grass_h = 22
        pygame.draw.rect(surf, GRASS, (0, 0, width * 2, grass_h))
        pygame.draw.rect(surf, GRASS_DARK, (0, grass_h - 6, width * 2, 6))
        # little grass ticks
        for x in range(0, width * 2, stripe):
            pygame.draw.polygon(surf, GRASS_LIGHT, [
                (x, grass_h - 6), (x + stripe // 2, grass_h - 14), (x + stripe, grass_h - 6),
            ])
        return surf

    def advance(self, dx: float) -> None:
        self.offset = (self.offset + dx) % self.tile_w

    def blit_to(self, screen: pygame.Surface, ground_top: int) -> None:
        x0 = -int(self.offset)
        screen.blit(self.tile, (x0, ground_top))
        screen.blit(self.tile, (x0 + self.tile_w, ground_top))


class CloudLayer:
    """A slow parallax layer of procedural clouds that drifts and wraps."""

    def __init__(self, width: int, height: int, count: int = 6) -> None:
        self.width = width
        self.height = height
        self.offset = 0.0
        self.clouds: List[Tuple[pygame.Surface, float, float, float]] = []
        for i in range(count):
            w = int(width * (0.10 + 0.06 * (i % 3)))
            surf = self._make_cloud(w)
            x = (width * 1.2) * (i / max(1, count))
            y = height * (0.08 + 0.16 * ((i * 7) % 5) / 5.0)
            self.clouds.append((surf, x, y, 1.0))

    def _make_cloud(self, w: int) -> pygame.Surface:
        h = int(w * 0.5)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for cx, cy, r in [
            (w * 0.28, h * 0.6, h * 0.34),
            (w * 0.5, h * 0.42, h * 0.46),
            (w * 0.72, h * 0.6, h * 0.34),
        ]:
            pygame.draw.circle(s, CLOUD, (int(cx), int(cy)), int(r))
        return s

    def advance(self, dx: float) -> None:
        self.offset = (self.offset + dx) % (self.width * 1.2)

    def blit_to(self, screen: pygame.Surface) -> None:
        span = self.width * 1.2
        for surf, x, y, _ in self.clouds:
            px = (x - self.offset) % span
            screen.blit(surf, (px, y))


class Background:
    """The static sky layer: gradient, sun and far hills."""

    def __init__(self, width: int, height: int) -> None:
        self.surface = self._make(width, height)

    def _make(self, width: int, height: int) -> pygame.Surface:
        sky = _gradient((width, height), SKY_TOP, SKY_BOTTOM)
        # Sun: a soft radial glow (alpha-blended so it never washes the sky
        # out) plus a bright core, offset toward the top-right.
        center = (int(width * 0.80), int(height * 0.17))
        sun_r = max(18, int(height * 0.055))
        glow_r = sun_r * 3
        glow = pygame.Surface((int(glow_r * 2), int(glow_r * 2)), pygame.SRCALPHA)
        for r in range(int(glow_r), 0, -2):
            a = int(70 * (1 - r / glow_r) ** 2)
            pygame.draw.circle(glow, (255, 244, 190, a), (int(glow_r), int(glow_r)), r)
        glow_rect = glow.get_rect(center=center)
        sky.blit(glow, glow_rect)
        pygame.draw.circle(sky, SUN_CORE, center, sun_r)
        pygame.draw.circle(sky, SUN, center, sun_r, 3)
        # far hills along the horizon
        horizon = int(height * 0.62)
        self._hills(sky, horizon, width, height)
        return sky

    @staticmethod
    def _hills(sky: pygame.Surface, horizon: int, width: int, height: int) -> None:
        # a band of rounded distant hills
        band = pygame.Surface((width, height - horizon), pygame.SRCALPHA)
        for i in range(0, width + 80, 90):
            r = 46 + (i % 3) * 12
            cx = i
            cy = 8 + (i % 4) * 6
            pygame.draw.ellipse(band, HILL_FAR, (cx - r, cy - r * 0.5, r * 2, r * 1.3))
        sky.blit(band, (0, horizon))
        # nearer, darker ridge
        band2 = pygame.Surface((width, height - horizon - 10), pygame.SRCALPHA)
        for i in range(-30, width + 60, 70):
            r = 40 + (i % 2) * 10
            cx = i + 30
            cy = 22 + (i % 3) * 8
            pygame.draw.ellipse(band2, HILL_NEAR, (cx - r, cy - r * 0.5, r * 2, r * 1.4))
        sky.blit(band2, (0, horizon + 14))


class AssetBank:
    """Builds every asset once and hands the render layer ready-made views."""

    def __init__(self, width: int = C.WIDTH, height: int = C.HEIGHT) -> None:
        self.width = width
        self.height = height
        self.bird = BirdSprite(C.BIRD_SIZE)
        self.pipe = PipeSprite(C.PIPE_WIDTH)
        self.ground = Ground(width)
        self.clouds = CloudLayer(width, height)
        self.background = Background(width, height)

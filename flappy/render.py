"""Pygame presentation layer for FlippyBlock Extreme.

This is the only module in the game that imports pygame. It owns the window,
event handling, the fixed-timestep game loop, procedural drawing of every state
(menu / ready / playing / paused / game over), on-screen controls (pause, mute,
buttons) and the sound hooks. All game rules live in :mod:`flappy.core`; here
we only translate input into core actions and paint the resulting state.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import pygame

from . import constants as C
from . import core as K
from . import assets as A
from . import sound as S

TARGET_FPS = 60

# UI palette
UI_WHITE = (255, 255, 255, 255)
UI_DARK = (40, 44, 52, 255)
UI_ACCENT = (255, 176, 44, 255)
UI_RED = (224, 66, 54, 255)
UI_GREEN = (92, 178, 80, 255)
UI_BLUE = (70, 130, 210, 255)
OUTLINE = (0, 0, 0, 190)

MEDAL_BRONZE = (200, 120, 70, 255)
MEDAL_SILVER = (190, 190, 200, 255)
MEDAL_GOLD = (240, 200, 70, 255)
MEDAL_PLAT = (180, 220, 230, 255)


def medal_for(score: int) -> Optional[Tuple[int, int, int, int]]:
    """Return the medal colour for a score, or None for no medal."""
    if score >= 40:
        return MEDAL_PLAT
    if score >= 30:
        return MEDAL_GOLD
    if score >= 20:
        return MEDAL_SILVER
    if score >= 10:
        return MEDAL_BRONZE
    return None


class Game:
    """Wires the pure core to a pygame window and drives the game loop."""

    def __init__(
        self,
        highscore_path: Optional[str] = None,
        smoke: bool = False,
        window_size: Optional[Tuple[int, int]] = None,
        rng_seed: Optional[int] = None,
        smoke_capture_frame: int = 90,
    ) -> None:
        self.smoke = smoke
        self.window_size = window_size or (C.WIDTH, C.HEIGHT)
        self.screen = pygame.display.set_mode(self.window_size)
        pygame.display.set_caption("FlippyBlock Extreme")

        self.clock = pygame.time.Clock()
        self.rng = random.Random(rng_seed)
        self.core = K.GameCore(rng=self.rng, highscore_path=highscore_path)
        self.assets = A.AssetBank(C.WIDTH, C.HEIGHT)
        self.sounds = S.SoundBank()

        self.font = self._make_font()
        self.accumulator = 0.0
        self.wing_time = 0.0
        self.running = True
        self._frame = 0
        self._capture: Optional[pygame.Surface] = None
        self._smoke_capture_frame = smoke_capture_frame

    # -- setup --------------------------------------------------------------
    def _make_font(self) -> Dict[str, pygame.font.Font]:
        # pygame's bundled default font; no external .ttf is read.
        return {
            "title": pygame.font.Font(None, 86),
            "big": pygame.font.Font(None, 68),
            "score": pygame.font.Font(None, 96),
            "normal": pygame.font.Font(None, 40),
            "small": pygame.font.Font(None, 30),
            "tiny": pygame.font.Font(None, 22),
        }

    # -- input --------------------------------------------------------------
    def _map_key(self, key: int) -> Optional[str]:
        if key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
            return K.Action.FLAP
        if key == pygame.K_RETURN:
            return K.Action.START
        if key in (pygame.K_p, pygame.K_ESCAPE):
            return K.Action.TOGGLE_PAUSE
        if key == pygame.K_m:
            return "mute"
        if key == pygame.K_r:
            return K.Action.RESTART
        if key == pygame.K_q:
            return "quit"
        return None

    def _real_actions(self) -> List:
        out: List = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                a = self._map_key(event.key)
                if a == "quit":
                    self.running = False
                elif a:
                    out.append(a)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
        return out

    def _handle_click(self, pos: Tuple[int, int]) -> None:
        # Buttons take priority wherever they are drawn.
        for name, rect in self._buttons().items():
            if rect.collidepoint(pos):
                self._apply_button(name)
                return
        if self.core.state == K.State.PAUSED:
            self._apply(K.Action.RESUME)
            return
        # Otherwise the click is a flap (which also starts from menu/ready).
        self._apply(K.Action.FLAP)

    def _apply_button(self, name: str) -> None:
        state = self.core.state
        if name == "sound":
            self._apply("mute")
        elif name == "menu":
            self._apply(K.Action.TO_MENU)
        elif name == "resume":
            self._apply(K.Action.RESUME)
        elif name == "play":
            self._apply(K.Action.RESTART if state == K.State.GAME_OVER else K.Action.START)
        else:
            self._apply(K.Action.FLAP)

    def _apply(self, action) -> None:
        if action == "mute":
            self.sounds.set_mute(not self.sounds.get_mute())
            return
        if action == "quit":
            self.running = False
            return
        prev = self.core.state
        self.core.handle_action(action)
        self._on_state_change(prev, self.core.state)

    def _on_state_change(self, prev: K.State, now: K.State) -> None:
        if prev == now:
            return
        if now == K.State.GAME_OVER:
            self.sounds.play("hit")
            self.sounds.play("die")
            if self.core.is_new_record:
                self.sounds.play("record")
        elif now == K.State.READY or (now == K.State.PLAYING and prev == K.State.PAUSED):
            self.sounds.play("swoosh")

    # -- button layout (pure, shared by drawing and hit-testing) ------------
    def _button_rect(self, label: str, center: Tuple[int, int], font: str = "normal") -> pygame.Rect:
        tw, th = self.font[font].size(label)
        rect = pygame.Rect(0, 0, tw + 44, th + 22)
        rect.center = center
        return rect

    def _buttons(self) -> Dict[str, pygame.Rect]:
        s = self.core.state
        cx = C.WIDTH // 2
        btns: Dict[str, pygame.Rect] = {}
        if s == K.State.GAME_OVER:
            btns["play"] = self._button_rect("PLAY AGAIN", (cx, C.HEIGHT // 2 + 96))
            btns["menu"] = self._button_rect("MENU", (cx, C.HEIGHT // 2 + 156))
            btns["sound"] = self._button_rect("SOUND" if not self.sounds.get_mute() else "MUTED",
                                              (cx, C.HEIGHT // 2 + 216), "small")
        elif s == K.State.MENU:
            btns["play"] = self._button_rect("PLAY", (cx, 470))
            btns["sound"] = self._button_rect("SOUND" if not self.sounds.get_mute() else "MUTED",
                                              (cx, 534), "small")
        return btns

    # -- per-frame update ---------------------------------------------------
    def _physics(self, dt: float) -> None:
        self.accumulator += dt
        self.accumulator = min(self.accumulator, 0.25)  # no spiral of death
        while self.accumulator >= C.FIXED_DT:
            self.core.step(C.FIXED_DT)
            self.accumulator -= C.FIXED_DT
        # The wing animation is a live-world clock; keep it frozen on pause
        # and death so a dead/paused bird holds its last pose.
        if self.core.state in (K.State.MENU, K.State.READY, K.State.PLAYING):
            self.wing_time += dt

    def _scroll(self, dt: float) -> None:
        state = self.core.state
        # The world (ground + clouds) scrolls in the live states and is frozen
        # once paused or on death, giving a consistent "stopped" feel.
        if state in (K.State.MENU, K.State.READY, K.State.PLAYING):
            self.assets.ground.advance(C.PIPE_SPEED * dt)
            self.assets.clouds.advance(28.0 * dt)

    # -- drawing ------------------------------------------------------------
    def _text(self, surf: pygame.Surface, text: str, font: str, color,
              center: Tuple[int, int],
              outline: Optional[Tuple[int, int, int, int]] = None) -> pygame.Rect:
        f = self.font[font]
        if outline is None:
            main = f.render(text, True, color)
            rect = main.get_rect(center=center)
            surf.blit(main, rect)
            return rect
        ow, oh = f.size(text)
        pad = 4
        canvas = pygame.Surface((ow + pad * 2, oh + pad * 2), pygame.SRCALPHA)
        for dx in (-3, 0, 3):
            for dy in (-3, 0, 3):
                canvas.blit(f.render(text, True, outline), (pad + dx, pad + dy))
        canvas.blit(f.render(text, True, color), (pad, pad))
        rect = canvas.get_rect(center=center)
        surf.blit(canvas, rect)
        return rect

    def _draw_button(self, name: str, rect: pygame.Rect, color, dark) -> None:
        label = "PLAY" if name == "play" else (
            "MENU" if name == "menu" else ("RESUME" if name == "resume"
            else ("SOUND" if not self.sounds.get_mute() else "MUTED")))
        font = "small" if name == "sound" else "normal"
        text = self.font[font].render(label, True, UI_WHITE)
        mouse = pygame.mouse.get_pos()
        if rect.collidepoint(mouse):
            color = (min(255, color[0] + 25), min(255, color[1] + 25), min(255, color[2]), 255)
        btn = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(btn, dark, (0, 0, rect.w, rect.h), border_radius=10)
        pygame.draw.rect(btn, color, (2, 2, rect.w - 4, rect.h - 7), border_radius=8)
        btn.blit(text, text.get_rect(center=(rect.w // 2, (rect.h - 5) // 2)))
        self.screen.blit(btn, rect)

    def _dark_for(self, color) -> Tuple[int, int, int, int]:
        return (color[0] // 3, color[1] // 3, color[2] // 3, 255)

    def _draw(self) -> None:
        self.screen.blit(self.assets.background.surface, (0, 0))
        self.assets.clouds.blit_to(self.screen)
        state = self.core.state
        self._draw_pipes()
        self.assets.ground.blit_to(self.screen, C.GROUND_TOP)
        self._draw_bird()

        if state == K.State.MENU:
            self._draw_menu()
        elif state == K.State.READY:
            self._draw_ready()
        elif state == K.State.PLAYING:
            self._draw_score()
            self._draw_hud()
        elif state == K.State.PAUSED:
            self._draw_score()
            self._draw_pause()
        elif state == K.State.GAME_OVER:
            self._draw_game_over()

    def _draw_pipes(self) -> None:
        cap = self.assets.pipe.cap()
        cap_off = self.assets.pipe.cap_offset()
        cap_h = self.assets.pipe.cap_height
        for pipe in self.core.pipes:
            px = int(pipe.x - C.PIPE_WIDTH / 2)
            top_h = int(pipe.gap_top)
            bot_h = int(C.GROUND_TOP - pipe.gap_bottom)
            self.screen.blit(self.assets.pipe.body(top_h), (px, 0))
            self.screen.blit(cap, (px - cap_off, top_h - cap_h))
            if bot_h > 0:
                self.screen.blit(self.assets.pipe.body(bot_h), (px, int(pipe.gap_bottom)))
                self.screen.blit(cap, (px - cap_off, int(pipe.gap_bottom)))

    def _draw_bird(self) -> None:
        frame = self.assets.bird.frames[int(self.wing_time / 0.12) % self.assets.bird.count]
        # Core uses -35 for nose-up; pygame rotates counter-clockwise for
        # positive angles, so negate to keep the beak pointing the right way.
        rot = pygame.transform.rotate(frame, -self.core.bird.rotation)
        rect = rot.get_rect(center=(int(self.core.bird.x), int(self.core.bird.y)))
        self.screen.blit(rot, rect)

    def _draw_score(self) -> None:
        self._text(self.screen, str(self.core.score), "score", UI_WHITE,
                   (C.WIDTH // 2, 92), outline=OUTLINE)

    def _draw_hud(self) -> None:
        self._text(self.screen, f"BEST {self.core.high_score}", "tiny", UI_WHITE,
                   (30, 18), outline=(0, 0, 0, 150))
        label = "MUTED" if self.sounds.get_mute() else "SOUND"
        self._text(self.screen, f"{label} (M)", "tiny", UI_WHITE,
                   (C.WIDTH - 44, 18), outline=(0, 0, 0, 150))

    def _draw_menu(self) -> None:
        cx = C.WIDTH // 2
        self._text(self.screen, "FLIPPYBLOCK", "title", UI_ACCENT, (cx, 150), outline=(90, 55, 10, 255))
        self._text(self.screen, "EXTREME", "big", UI_RED, (cx, 214), outline=(60, 12, 12, 255))
        self._text(self.screen, f"BEST  {self.core.high_score}", "normal", UI_WHITE, (cx, 300), outline=OUTLINE)
        if int(self.wing_time * 2) % 2 == 0:
            self._text(self.screen, "TAP OR PRESS SPACE TO START", "small", UI_WHITE, (cx, 410), outline=OUTLINE)
        self._draw_button("play", self._buttons()["play"], UI_GREEN, self._dark_for(UI_GREEN))
        self._draw_button("sound", self._buttons()["sound"], UI_BLUE, self._dark_for(UI_BLUE))
        self._text(self.screen, "SPACE/CLICK flap   P pause   M sound   ESC quit", "tiny", UI_WHITE, (cx, 600), outline=(0, 0, 0, 130))

    def _draw_ready(self) -> None:
        cx = C.WIDTH // 2
        self._text(self.screen, "GET READY!", "big", UI_GREEN, (cx, 190), outline=(18, 60, 18, 255))
        self._text(self.screen, "TAP OR PRESS SPACE TO FLAP", "small", UI_WHITE, (cx, 360), outline=OUTLINE)
        self._draw_hud()

    def _draw_pause(self) -> None:
        overlay = pygame.Surface(self.window_size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        cx, cy = C.WIDTH // 2, C.HEIGHT // 2
        self._text(self.screen, "PAUSED", "title", UI_WHITE, (cx, cy - 60), outline=OUTLINE)
        self._text(self.screen, "P / ESC to resume", "normal", UI_WHITE, (cx, cy + 10), outline=OUTLINE)
        self._draw_button("resume", self._button_rect("RESUME", (cx, cy + 70)), UI_GREEN, self._dark_for(UI_GREEN))

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface(self.window_size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        cx = C.WIDTH // 2
        cy = C.HEIGHT // 2

        w, h = 360, 300
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill(A.PANEL)
        pygame.draw.rect(panel, A.PANEL_EDGE, (0, 0, w, h), 3, border_radius=14)
        panel_rect = panel.get_rect(center=(cx, cy))
        self.screen.blit(panel, panel_rect)

        self._text(self.screen, "GAME OVER", "big", UI_RED, (cx, cy - 120), outline=(60, 12, 12, 255))

        medal = medal_for(self.core.score)
        my = cy - 40
        if medal is not None:
            pygame.draw.circle(self.screen, (70, 55, 40, 255), (cx, my), 36)
            pygame.draw.circle(self.screen, medal, (cx, my), 31)
            pygame.draw.circle(self.screen, (255, 255, 255, 200), (cx, my), 31, 2)
            self._text(self.screen, "MEDAL", "tiny", UI_DARK, (cx, my + 52), outline=(255, 255, 255, 200))

        self._text(self.screen, f"SCORE  {self.core.score}", "normal", UI_DARK, (cx - 90, cy + 20), outline=(255, 255, 255, 220))
        self._text(self.screen, f"BEST   {self.core.high_score}", "normal", UI_DARK, (cx + 95, cy + 20), outline=(255, 255, 255, 220))
        if self.core.is_new_record and int(self.wing_time * 3) % 2 == 0:
            self._text(self.screen, "NEW BEST!", "small", (210, 130, 0, 255), (cx, cy + 58), outline=(255, 240, 200, 255))

        for name, rect in self._buttons().items():
            color = UI_GREEN if name == "play" else (UI_ACCENT if name == "menu" else UI_BLUE)
            self._draw_button(name, rect, color, self._dark_for(color))

    # -- main loop ----------------------------------------------------------
    def run(self, max_frames: Optional[int] = None, scripted: Optional[bool] = None,
            fps: int = TARGET_FPS) -> None:
        use_script = self.smoke if scripted is None else scripted
        while self.running and (max_frames is None or self._frame < max_frames):
            raw_dt = self.clock.tick(fps) / 1000.0
            # In smoke mode we advance a fixed amount of game time per frame
            # (and run unthrottled) so a headless run is fast and deterministic.
            dt = C.FIXED_DT if self.smoke else min(raw_dt, 0.25)
            for a in (self._scripted_actions() if use_script else self._real_actions()):
                self._apply(a)
            self._scroll(dt)
            self._physics(dt)
            self._draw()
            pygame.display.flip()
            self._frame += 1
            if self.smoke:
                # Capture a bright, mid-game frame if we reach it; otherwise
                # fall back to the last frame so a capture always exists.
                if max_frames is not None:
                    if self._frame == self._smoke_capture_frame:
                        self._capture = self.screen.copy()
                    elif self._frame >= max_frames:
                        if self._capture is None:
                            self._capture = self.screen.copy()

    def _scripted_actions(self) -> List:
        f = self._frame
        if f == 12:
            return [K.Action.START]
        if f == 30:
            return [K.Action.FLAP]
        if f >= 30 and (f - 30) % 16 == 0 and self.core.state == K.State.PLAYING:
            return [K.Action.FLAP]
        return []

    # -- smoke capture ------------------------------------------------------
    def current_capture(self) -> pygame.Surface:
        return self._capture if self._capture is not None else self.screen

    def save_capture(self, path: str) -> None:
        pygame.image.save(self.current_capture(), path)


def new_game(highscore_path: Optional[str] = None, smoke: bool = False,
             window_size: Optional[Tuple[int, int]] = None,
             rng_seed: Optional[int] = None,
             smoke_capture_frame: int = 90) -> Game:
    """Convenience constructor used by the entry point and the tests."""
    return Game(highscore_path=highscore_path, smoke=smoke,
                window_size=window_size, rng_seed=rng_seed,
                smoke_capture_frame=smoke_capture_frame)

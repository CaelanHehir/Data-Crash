from __future__ import annotations

import pygame

from src.display.map_renderer import MapRenderer
from src.game.world.Map import Map


class Camera:
    def __init__(self, map_renderer: MapRenderer,
                 drag_threshold: int = 5) -> None:
        self.map_renderer = map_renderer
        self.drag_threshold = drag_threshold
        self._left_mouse_down_pos: tuple[int, int] | None = None
        self._left_mouse_dragged = False

    @property
    def zoom(self) -> float:
        return self.map_renderer.zoom

    def reset(self) -> None:
        self.cancel_pan_tracking()

    def zoom_at(self, wheel_delta: int, mouse_pos: tuple[int, int],
                screen: pygame.Surface, game_map: Map) -> None:
        self.map_renderer.zoom_at(wheel_delta, mouse_pos, screen, game_map)

    def handle_left_button_down(self, mouse_pos: tuple[int, int]) -> None:
        self._left_mouse_down_pos = mouse_pos
        self._left_mouse_dragged = False
        self.map_renderer.start_pan(mouse_pos)

    def handle_mouse_motion(self, mouse_pos: tuple[int, int],
                            left_button_down: bool, screen: pygame.Surface,
                            game_map: Map) -> None:
        if not left_button_down:
            return

        if self._left_mouse_down_pos is not None:
            delta_x = abs(mouse_pos[0] - self._left_mouse_down_pos[0])
            delta_y = abs(mouse_pos[1] - self._left_mouse_down_pos[1])
            if (delta_x >= self.drag_threshold
                    or delta_y >= self.drag_threshold):
                self._left_mouse_dragged = True

        self.map_renderer.pan_to(mouse_pos, screen, game_map)

    def handle_left_button_up(self) -> bool:
        self.map_renderer.stop_pan()
        was_click = (self._left_mouse_down_pos is not None
                     and not self._left_mouse_dragged)
        self._left_mouse_down_pos = None
        self._left_mouse_dragged = False
        return was_click

    def cancel_pan_tracking(self) -> None:
        self.map_renderer.stop_pan()
        self._left_mouse_down_pos = None
        self._left_mouse_dragged = False

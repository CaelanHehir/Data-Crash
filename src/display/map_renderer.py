from __future__ import annotations

import math
import pygame
from typing import Optional

from src.game.buildings.Datacenter import Datacenter
from src.game.buildings.Headquarters import Headquarters
from src.game.world.Map import Map


class MapRenderer:
    def __init__(self, tile_size: int = 40, margin: int = 2) -> None:
        self.base_tile_size = tile_size
        self.margin = margin
        self.pan_margin_ratio = 0.3

        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 35.0

        self.pan_x = 0.0
        self.pan_y = 0.0

        self._dragging = False
        self._last_mouse_pos: tuple[int, int] | None = None

    def start_pan(self, mouse_pos: tuple[int, int]) -> None:
        self._dragging = True
        self._last_mouse_pos = mouse_pos

    def stop_pan(self) -> None:
        self._dragging = False
        self._last_mouse_pos = None

    def pan_to(self, mouse_pos: tuple[int, int], screen: pygame.Surface,
               game_map: Map) -> None:
        if not self._dragging or self._last_mouse_pos is None:
            return

        dx = mouse_pos[0] - self._last_mouse_pos[0]
        dy = mouse_pos[1] - self._last_mouse_pos[1]
        self.pan_x += dx
        self.pan_y += dy
        self._clamp_pan(screen, game_map)
        self._last_mouse_pos = mouse_pos

    def zoom_at(self, wheel_delta: int, mouse_pos: tuple[int, int],
                screen: pygame.Surface, game_map: Map) -> None:
        if wheel_delta == 0:
            return

        self._update_zoom_bounds(screen, game_map)

        zoom_step = 1.2 if wheel_delta > 0 else (1 / 1.2)
        old_zoom = self.zoom
        proposed_zoom = self.zoom * (zoom_step ** abs(wheel_delta))
        self.zoom = max(self.min_zoom, min(self.max_zoom, proposed_zoom))

        if self.zoom == old_zoom:
            return

        old_origin_x, old_origin_y = self._origin(screen, game_map, old_zoom)
        mouse_x, mouse_y = mouse_pos

        world_x = (mouse_x - old_origin_x) / old_zoom
        world_y = (mouse_y - old_origin_y) / old_zoom

        centered_new_x, centered_new_y = self._centered_origin(
            screen,
            game_map,
            self.zoom)

        self.pan_x = mouse_x - centered_new_x - (world_x * self.zoom)
        self.pan_y = mouse_y - centered_new_y - (world_y * self.zoom)
        self._clamp_pan(screen, game_map)

    def _update_zoom_bounds(self, screen: pygame.Surface,
                            game_map: Map) -> None:
        map_width_px = game_map.WIDTH * self.base_tile_size
        map_height_px = game_map.HEIGHT * self.base_tile_size

        fit_zoom = min(screen.get_width() / map_width_px,
                       screen.get_height() / map_height_px) - 0.1

        # Fully zoomed out, map takes up most of the screen.
        self.min_zoom = fit_zoom

        # Fully zoomed in, one tile takes up the whole screen.
        largest_screen_dim = max(screen.get_width(), screen.get_height())
        self.max_zoom = largest_screen_dim / self.base_tile_size

        if self.max_zoom <= self.min_zoom:
            self.max_zoom = self.min_zoom + 0.01

    def pick_cell(self, mouse_pos: tuple[int, int], screen: pygame.Surface,
                  game_map: Map) -> Optional[tuple[int, int]]:
        origin_x, origin_y = self._origin(screen, game_map, self.zoom)
        mouse_x, mouse_y = mouse_pos

        local_x = (mouse_x - origin_x) / self.zoom
        local_y = (mouse_y - origin_y) / self.zoom

        if local_x < 0 or local_y < 0:
            return None

        col = int(local_x // self.base_tile_size)
        row = int(local_y // self.base_tile_size)

        if row < 0 or row >= game_map.HEIGHT:
            return None
        if col < 0 or col >= game_map.WIDTH:
            return None

        return row, col

    def cell_center(self, row: int, col: int, screen: pygame.Surface,
                    game_map: Map) -> tuple[int, int]:
        origin_x, origin_y = self._origin(screen, game_map, self.zoom)
        scaled_tile = self.base_tile_size * self.zoom

        center_x = origin_x + (col + 0.5) * scaled_tile
        center_y = origin_y + (row + 0.5) * scaled_tile
        return int(center_x), int(center_y)

    def cell_rect(self, row: int, col: int, screen: pygame.Surface,
                  game_map: Map) -> pygame.Rect:
        origin_x, origin_y = self._origin(screen, game_map, self.zoom)
        scaled_tile = self.base_tile_size * self.zoom
        scaled_margin = max(1, int(self.margin * self.zoom))

        x = origin_x + col * scaled_tile
        y = origin_y + row * scaled_tile
        return pygame.Rect(
            int(x + scaled_margin),
            int(y + scaled_margin),
            int(scaled_tile - 2 * scaled_margin),
            int(scaled_tile - 2 * scaled_margin),
        )

    def _centered_origin(self, screen: pygame.Surface, game_map: Map,
                         zoom: float) -> tuple[float, float]:
        map_width_px = game_map.WIDTH * self.base_tile_size * zoom
        map_height_px = game_map.HEIGHT * self.base_tile_size * zoom
        centered_x = (screen.get_width() - map_width_px) / 2
        centered_y = (screen.get_height() - map_height_px) / 2
        return centered_x, centered_y

    def _origin(self, screen: pygame.Surface, game_map: Map,
                zoom: float) -> tuple[float, float]:
        centered_x, centered_y = self._centered_origin(screen, game_map, zoom)
        return centered_x + self.pan_x, centered_y + self.pan_y

    def _clamp_pan(self, screen: pygame.Surface, game_map: Map) -> None:
        map_width = game_map.WIDTH * self.base_tile_size * self.zoom
        map_height = game_map.HEIGHT * self.base_tile_size * self.zoom

        pan_margin_x = map_width * self.pan_margin_ratio
        pan_margin_y = map_height * self.pan_margin_ratio

        screen_width = screen.get_width()
        screen_height = screen.get_height()

        if map_width <= screen_width:
            min_pan_x = -pan_margin_x
            max_pan_x = pan_margin_x
        else:
            centered_x = (screen_width - map_width) / 2
            min_origin_x = screen_width - map_width
            max_origin_x = 0.0
            min_pan_x = min_origin_x - centered_x - pan_margin_x
            max_pan_x = max_origin_x - centered_x + pan_margin_x

        if map_height <= screen_height:
            min_pan_y = -pan_margin_y
            max_pan_y = pan_margin_y
        else:
            centered_y = (screen_height - map_height) / 2
            min_origin_y = screen_height - map_height
            max_origin_y = 0.0
            min_pan_y = min_origin_y - centered_y - pan_margin_y
            max_pan_y = max_origin_y - centered_y + pan_margin_y

        self.pan_x = max(min_pan_x, min(max_pan_x, self.pan_x))
        self.pan_y = max(min_pan_y, min(max_pan_y, self.pan_y))

    def draw(self, screen: pygame.Surface, game_map: Map,
             selected_cell: Optional[tuple[int, int]] = None,
             rebel_counts: Optional[
                 dict[tuple[int, int], int]
             ] = None) -> None:
        self._update_zoom_bounds(screen, game_map)
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom))
        self._clamp_pan(screen, game_map)

        origin_x, origin_y = self._origin(screen, game_map, self.zoom)
        scaled_tile = self.base_tile_size * self.zoom
        scaled_margin = max(1, int(self.margin * self.zoom))

        # Draw cells
        for row_index, row in enumerate(game_map.grid):
            for col_index, cell in enumerate(row):
                tile_rect = self.cell_rect(
                    row_index,
                    col_index,
                    screen,
                    game_map,
                )

                color = (35, 45, 65)
                if isinstance(cell.building, Headquarters):
                    color = (255, 198, 92)
                elif isinstance(cell.building, Datacenter):
                    color = (107, 178, 255)

                pygame.draw.rect(screen, color, tile_rect, border_radius=3)

                if isinstance(cell.building, Headquarters):
                    self._draw_headquarters_progress(
                        screen,
                        tile_rect,
                        cell.building,
                    )

                displayed_rebels = cell.rebels
                if rebel_counts is not None:
                    displayed_rebels = rebel_counts.get(
                        (row_index, col_index),
                        displayed_rebels,
                    )

                self._draw_unit_counts(
                    screen,
                    tile_rect,
                    rebels=displayed_rebels,
                    robots=cell.robots,
                )

                if selected_cell == (row_index, col_index):
                    pygame.draw.rect(screen, (255, 255, 255),
                                     tile_rect, width=2)

        # Draw sector outlines
        sector_size = game_map.SECTOR_SIZE
        outline_color = (150, 150, 150)
        outline_width = 1

        for sector_row in range(0, game_map.HEIGHT, sector_size):
            for sector_col in range(0, game_map.WIDTH, sector_size):
                sector_x = origin_x + sector_col * scaled_tile + scaled_margin
                sector_y = origin_y + sector_row * scaled_tile + scaled_margin
                side_length = max(1, int(sector_size * scaled_tile -
                                  2 * scaled_margin))
                sector_rect = pygame.Rect(int(sector_x), int(sector_y),
                                          side_length, side_length)
                pygame.draw.rect(screen, outline_color, sector_rect,
                                 width=outline_width)

    def _draw_headquarters_progress(self, screen: pygame.Surface,
                                    tile_rect: pygame.Rect,
                                    headquarters: Headquarters) -> None:
        progress = headquarters.cycle_progress
        if progress <= 0:
            return

        if headquarters.mode == Headquarters.MOBILIZING:
            progress_color = (107, 178, 255, 95)
        else:
            progress_color = (255, 120, 120, 95)

        overlay = pygame.Surface(tile_rect.size, pygame.SRCALPHA)
        local_center = (tile_rect.width // 2, tile_rect.height // 2)

        if progress >= 1.0:
            pygame.draw.rect(overlay, progress_color, overlay.get_rect(),
                             border_radius=3)
        else:
            radius = int(math.hypot(tile_rect.width, tile_rect.height))
            points = [local_center]
            start_angle = -math.pi / 2
            end_angle = start_angle + (progress * math.tau)
            segments = max(12, int(48 * progress))

            for step in range(segments + 1):
                angle = start_angle + (
                    (end_angle - start_angle) * step / segments
                )
                points.append((
                    local_center[0] + int(math.cos(angle) * radius),
                    local_center[1] + int(math.sin(angle) * radius),
                ))

            if len(points) >= 3:
                pygame.draw.polygon(overlay, progress_color, points)

        screen.blit(overlay, tile_rect.topleft)

    def _draw_unit_counts(self, screen: pygame.Surface,
                          tile_rect: pygame.Rect,
                          rebels: int,
                          robots: int) -> None:
        font_size = max(12, min(22, tile_rect.height // 3))
        font = pygame.font.SysFont(None, font_size)

        if rebels > 0:
            self._draw_count_badge(
                screen,
                tile_rect,
                text=str(rebels),
                font=font,
                text_color=(255, 255, 255),
                badge_color=(170, 65, 65),
                anchor="top_left",
            )

        if robots > 0:
            self._draw_count_badge(
                screen,
                tile_rect,
                text=str(robots),
                font=font,
                text_color=(255, 255, 255),
                badge_color=(65, 115, 180),
                anchor="bottom_right",
            )

    def _draw_count_badge(self, screen: pygame.Surface,
                          tile_rect: pygame.Rect,
                          text: str,
                          font: pygame.font.Font,
                          text_color: tuple[int, int, int],
                          badge_color: tuple[int, int, int],
                          anchor: str) -> None:
        text_surface = font.render(text, True, text_color)
        padding_x = 6
        padding_y = 2
        badge_width = text_surface.get_width() + padding_x * 2
        badge_height = text_surface.get_height() + padding_y * 2

        if anchor == "top_left":
            badge_rect = pygame.Rect(
                tile_rect.x + 4,
                tile_rect.y + 4,
                badge_width,
                badge_height,
            )
        else:
            badge_rect = pygame.Rect(
                tile_rect.right - badge_width - 4,
                tile_rect.bottom - badge_height - 4,
                badge_width,
                badge_height,
            )

        pygame.draw.rect(screen, badge_color, badge_rect, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255), badge_rect, width=1,
                         border_radius=8)

        text_rect = text_surface.get_rect(center=badge_rect.center)
        screen.blit(text_surface, text_rect)

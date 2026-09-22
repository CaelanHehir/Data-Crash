from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Callable, Optional

import pygame

from src.game.buildings.Headquarters import Headquarters
from src.game.entities.Commander import Commander
from src.game.world.Cell import Cell


@dataclass
class CommandContext:
    cell_coords: tuple[int, int]
    cell: Cell
    available_rebels: int
    commander: Commander
    toggle_headquarters_mode: Callable[[tuple[int, int]], None]
    start_rebel_move_mode: Callable[[tuple[int, int]], None]


@dataclass
class CommandItem:
    label: str
    callback: Callable[[CommandContext], None]
    is_available: Callable[[CommandContext], bool]
    center: tuple[int, int] = (0, 0)


class Commands:
    def __init__(self) -> None:
        self.active = False
        self.cell_coords: Optional[tuple[int, int]] = None
        self.anchor_pos: tuple[int, int] = (0, 0)
        self.context: Optional[CommandContext] = None
        self.base_command_radius = 14
        self.base_command_distance = 52
        self.command_radius = self.base_command_radius
        self.command_distance = self.base_command_distance

        self.items = [CommandItem("T",
                                  self.toggle_building_mode,
                                  self.can_toggle_building_mode),
                      CommandItem("M",
                                  self.start_rebel_move,
                                  self.can_start_rebel_move),
                      CommandItem("C",
                                  self._placeholder_command_c,
                                  self._always_available),
                      CommandItem("D",
                                  self._placeholder_command_d,
                                  self._always_available)]

    def set_item(self, index: int, label: str,
                 callback: Callable[[CommandContext], None],
                 is_available: Optional[
                     Callable[[CommandContext], bool]
                 ] = None
                 ) -> None:
        self.items[index].label = label
        self.items[index].callback = callback
        if is_available is None:
            self.items[index].is_available = self._always_available
        else:
            self.items[index].is_available = is_available

    def show_at_cell(self, cell_coords: tuple[int, int],
                     cell_center: tuple[int, int], zoom: float,
                     context: CommandContext) -> None:
        self.active = True
        self.cell_coords = cell_coords
        self.context = context
        self.update_transform(cell_center, zoom)

    def update_context(self, context: CommandContext) -> None:
        self.context = context

    def update_transform(self, cell_center: tuple[int, int],
                         zoom: float) -> None:
        self.anchor_pos = cell_center
        scaled_radius = int(self.base_command_radius * zoom)
        scaled_distance = int(self.base_command_distance * zoom)

        self.command_radius = max(10, min(30, scaled_radius))
        self.command_distance = max(28, min(120, scaled_distance))
        self._update_layout()

    def hide(self) -> None:
        self.active = False
        self.cell_coords = None
        self.context = None

    def _update_layout(self) -> None:
        cx, cy = self.anchor_pos
        d = self.command_distance
        angles = [145, 108, 72, 35]
        positions = [(int(cx + cos(radians(angle)) * d),
                      int(cy + sin(radians(angle)) * d))
                     for angle in angles]

        for item, pos in zip(self.items, positions):
            item.center = pos

    def click(self, mouse_pos: tuple[int, int]) -> bool:
        if not self.active or self.context is None:
            return False

        mx, my = mouse_pos
        radius_sq = self.command_radius * self.command_radius
        for item in self.items:
            cx, cy = item.center
            dx = mx - cx
            dy = my - cy
            if (dx * dx) + (dy * dy) <= radius_sq:
                if not item.is_available(self.context):
                    return True

                item.callback(self.context)
                self.hide()
                return True

        # Clicking outside command circles closes the menu
        self.hide()
        return False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.active or self.context is None:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        radius_sq = self.command_radius * self.command_radius

        font_size = max(16, int(self.command_radius * 1.2))
        font = pygame.font.SysFont(None, font_size)
        for item in self.items:
            enabled = item.is_available(self.context)
            dx = mouse_x - item.center[0]
            dy = mouse_y - item.center[1]
            hovered = enabled and (dx * dx) + (dy * dy) <= radius_sq

            fill_color = (150, 150, 150)
            border_color = (255, 255, 255)
            text_color = (10, 10, 20)
            if hovered:
                fill_color = (100, 100, 100)
                border_color = (235, 245, 255)
                text_color = (255, 255, 255)

            alpha = 255 if enabled else 120
            diameter = self.command_radius * 2 + 4
            command_surface = pygame.Surface((diameter, diameter),
                                             pygame.SRCALPHA)
            local_center = (diameter // 2, diameter // 2)
            pygame.draw.circle(command_surface,
                               (*fill_color, alpha),
                               local_center,
                               self.command_radius)
            pygame.draw.circle(command_surface,
                               (*border_color, alpha),
                               local_center,
                               self.command_radius,
                               width=1)
            screen.blit(command_surface,
                        (item.center[0] - local_center[0],
                         item.center[1] - local_center[1]))

            label_surface = font.render(item.label, True, text_color)
            if not enabled:
                label_surface.set_alpha(alpha)
            label_rect = label_surface.get_rect(center=item.center)
            screen.blit(label_surface, label_rect)

    def toggle_building_mode(self, context: CommandContext) -> None:
        if not self.can_toggle_building_mode(context):
            return

        context.toggle_headquarters_mode(context.cell_coords)

    def can_toggle_building_mode(self, context: CommandContext) -> bool:
        return isinstance(context.cell.building, Headquarters)

    def start_rebel_move(self, context: CommandContext) -> None:
        if not self.can_start_rebel_move(context):
            return

        context.start_rebel_move_mode(context.cell_coords)

    def can_start_rebel_move(self, context: CommandContext) -> bool:
        return context.available_rebels > 0

    def _always_available(self, _context: CommandContext) -> bool:
        return True

    def _placeholder_command_c(self, _context: CommandContext) -> None:
        return

    def _placeholder_command_d(self, _context: CommandContext) -> None:
        return

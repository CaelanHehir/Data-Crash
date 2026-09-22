from __future__ import annotations
from dataclasses import dataclass
import pygame
from typing import Optional

from src.display.Commands import CommandContext, Commands
from src.display.Popup import Popup
from src.display.map_renderer import MapRenderer
from src.game.buildings.Headquarters import Headquarters
from src.game.entities.Commander import Commander
from src.game.world.Cell import Cell
from src.game.world.Map import Map
from src.game.states.State import State
from src.overseer.Overseer import Overseer


@dataclass
class MoveSelection:
    source_coords: tuple[int, int]
    hovered_coords: Optional[tuple[int, int]] = None
    preview_path: Optional[list[tuple[int, int]]] = None
    destination_coords: Optional[tuple[int, int]] = None
    path: Optional[list[tuple[int, int]]] = None


@dataclass
class RebelMoveBatch:
    path: list[tuple[int, int]]
    rebels: int
    current_index: int = 0
    time_until_advance: float = 0.0


class PlayingState(State):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.overseer = Overseer()
        self._waiting_for_overseer = False
        self.game_map = Map()
        self.commander = Commander()
        self.map_renderer = MapRenderer()
        self.commands = Commands()
        self.popup = Popup()
        self.selected_cell: Optional[Cell] = None
        self.selected_cell_coords: Optional[tuple[int, int]] = None
        self._left_mouse_down_pos: Optional[tuple[int, int]] = None
        self._left_mouse_dragged = False
        self._drag_threshold = 5
        self._commands_consumed_click = False
        self.move_selection: Optional[MoveSelection] = None
        self.active_rebel_moves: list[RebelMoveBatch] = []

    def enter(self) -> None:
        # Reset/initialize a fresh run here (entities, score, etc.)
        self.game_map = Map()
        self.commander = Commander()
        self.selected_cell = None
        self.selected_cell_coords = None
        self._left_mouse_down_pos = None
        self._left_mouse_dragged = False
        self._commands_consumed_click = False
        self.move_selection = None
        self.active_rebel_moves = []
        self.commands.hide()
        self.popup.hide()

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            self.map_renderer.zoom_at(
                event.y,
                mouse_pos,
                self.game.screen,
                self.game_map,
            )
            if self.move_selection is not None:
                self.update_move_hover(mouse_pos)
            return

        if self.move_selection is not None:
            if event.type == pygame.MOUSEMOTION:
                self.update_move_hover(event.pos)
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.handle_move_selection_click(event.pos)
                elif event.button == 3:
                    self.cancel_rebel_move_mode()
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.cancel_rebel_move_mode()
                return

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.commands.click(event.pos):
                    self._commands_consumed_click = True
                    self._left_mouse_down_pos = None
                    self._left_mouse_dragged = False
                    return

                self._left_mouse_down_pos = event.pos
                self._left_mouse_dragged = False
                self.map_renderer.start_pan(event.pos)
            elif event.button == 3:
                self.select_cell(event.pos, toggle=False)
                self.show_commands(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.map_renderer.stop_pan()
                if self._commands_consumed_click:
                    self._commands_consumed_click = False
                    return

                if (self._left_mouse_down_pos is not None
                        and not self._left_mouse_dragged):
                    self.select_cell(event.pos)
                self._left_mouse_down_pos = None
                self._left_mouse_dragged = False
        elif event.type == pygame.MOUSEMOTION:
            if event.buttons[0]:
                if self._left_mouse_down_pos is not None:
                    delta_x = abs(event.pos[0] - self._left_mouse_down_pos[0])
                    delta_y = abs(event.pos[1] - self._left_mouse_down_pos[1])
                    if (delta_x >= self._drag_threshold
                            or delta_y >= self._drag_threshold):
                        self._left_mouse_dragged = True

                self.map_renderer.pan_to(
                    event.pos,
                    self.game.screen,
                    self.game_map,
                )
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                from src.game.states.MenuState import MenuState
                self.game.change_state(MenuState(self.game))
            elif event.key == pygame.K_SPACE:
                self.start_overseer_request()

    def select_cell(self, mouse_pos: tuple[int, int],
                    toggle: bool = True) -> None:
        selected = self.map_renderer.pick_cell(
            mouse_pos,
            self.game.screen,
            self.game_map,
        )

        if selected is None:
            self.selected_cell = None
            self.selected_cell_coords = None
            self.popup.hide()
            return

        if selected == self.selected_cell_coords and toggle:
            self.selected_cell = None
            self.selected_cell_coords = None
            self.popup.hide()
            return

        row, col = selected
        cell = self.game_map.grid[row][col]
        self.selected_cell = cell
        self.selected_cell_coords = selected

        self.update_popup_for_cell(selected, cell)

    def update_popup_for_cell(self, cell_coords: tuple[int, int],
                              cell: Cell) -> None:
        description_lines = []
        if cell.building is not None:
            description_lines.append(f"Building: {cell.building.name}")
            description_lines.append(
                "Durability: "
                f"{cell.building.current_durability}/"
                f"{cell.building.max_durability}"
            )

            if isinstance(cell.building, Headquarters):
                description_lines.append(f"Mode: {cell.building.mode}")

        description_lines.extend([
            f"Rebels: {self.visible_rebel_count(cell_coords)}",
            f"Robots: {cell.robots}",
        ])
        description = "\n".join(description_lines)
        self.popup.show(
            title=f"{cell.sector}{cell.id:02d}",
            description=description,
        )

    def show_commands(self, mouse_pos: tuple[int, int]) -> None:
        selected = self.map_renderer.pick_cell(
            mouse_pos,
            self.game.screen,
            self.game_map,
        )
        if selected is None:
            self.commands.hide()
            return

        row, col = selected
        center = self.map_renderer.cell_center(
            row,
            col,
            self.game.screen,
            self.game_map,
        )
        context = self.command_context_for_cell(selected)
        self.commands.show_at_cell(
            selected,
            center,
            self.map_renderer.zoom,
            context,
        )

    def command_context_for_cell(
        self,
        cell_coords: tuple[int, int],
    ) -> CommandContext:
        row, col = cell_coords
        cell = self.game_map.grid[row][col]
        return CommandContext(
            cell_coords=cell_coords,
            cell=cell,
            available_rebels=self.visible_rebel_count(cell_coords),
            commander=self.commander,
            toggle_headquarters_mode=self.toggle_headquarters_mode,
            start_rebel_move_mode=self.start_rebel_move_mode,
        )

    def start_rebel_move_mode(self, source_coords: tuple[int, int]) -> None:
        if self.visible_rebel_count(source_coords) <= 0:
            return

        self.move_selection = MoveSelection(source_coords=source_coords)
        self.update_move_hover(pygame.mouse.get_pos())

    def cancel_rebel_move_mode(self) -> None:
        self.move_selection = None

    def rebel_batches_at(self,
                         cell_coords: tuple[int, int]) -> list[RebelMoveBatch]:
        return [
            batch for batch in self.active_rebel_moves
            if batch.path[batch.current_index] == cell_coords
        ]

    def visible_rebel_count(self, cell_coords: tuple[int, int]) -> int:
        row, col = cell_coords
        total_rebels = self.game_map.grid[row][col].rebels
        for batch in self.rebel_batches_at(cell_coords):
            total_rebels += batch.rebels

        return total_rebels

    def visible_rebel_counts(self) -> dict[tuple[int, int], int]:
        rebel_counts = {
            (row_index, col_index): cell.rebels
            for row_index, row in enumerate(self.game_map.grid)
            for col_index, cell in enumerate(row)
        }

        for batch in self.active_rebel_moves:
            coords = batch.path[batch.current_index]
            rebel_counts[coords] = rebel_counts.get(coords, 0) + batch.rebels

        return rebel_counts

    def update_move_hover(self, mouse_pos: tuple[int, int]) -> None:
        if self.move_selection is None:
            return

        hovered_coords = self.map_renderer.pick_cell(
            mouse_pos,
            self.game.screen,
            self.game_map,
        )
        self.move_selection.hovered_coords = hovered_coords

        if hovered_coords is None:
            self.move_selection.preview_path = None
            return

        self.move_selection.preview_path = self.commander.find_rebel_path(
            self.game_map,
            self.move_selection.source_coords,
            hovered_coords,
        )

    def handle_move_selection_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.move_selection is None:
            return

        if self._move_confirmation_hit(mouse_pos):
            self.confirm_rebel_move()
            return

        selected = self.map_renderer.pick_cell(
            mouse_pos,
            self.game.screen,
            self.game_map,
        )
        if selected is None:
            self.cancel_rebel_move_mode()
            return

        self.set_move_destination(selected)

    def set_move_destination(
        self,
        destination_coords: tuple[int, int],
    ) -> None:
        if self.move_selection is None:
            return

        source_coords = self.move_selection.source_coords
        path = self.commander.find_rebel_path(
            self.game_map,
            source_coords,
            destination_coords,
        )
        self.move_selection.destination_coords = destination_coords
        self.move_selection.path = path
        self.move_selection.preview_path = path

    def _move_confirmation_hit(self, mouse_pos: tuple[int, int]) -> bool:
        if self.move_selection is None:
            return False
        if self.move_selection.destination_coords is None:
            return False
        if not self.move_selection.path:
            return False

        row, col = self.move_selection.destination_coords
        center_x, center_y = self.map_renderer.cell_center(
            row,
            col,
            self.game.screen,
            self.game_map,
        )
        radius = self.move_confirmation_radius()
        dx = mouse_pos[0] - center_x
        dy = mouse_pos[1] - center_y
        return (dx * dx) + (dy * dy) <= radius * radius

    def move_confirmation_radius(self) -> int:
        scaled_radius = (
            self.map_renderer.base_tile_size * self.map_renderer.zoom * 0.2
        )
        return max(10, int(scaled_radius))

    def confirm_rebel_move(self) -> None:
        if self.move_selection is None or not self.move_selection.path:
            return

        source_coords = self.move_selection.source_coords
        source_row, source_col = source_coords
        destination_coords = self.move_selection.destination_coords
        source_cell = self.game_map.grid[source_row][source_col]
        rebels_to_move = self.visible_rebel_count(source_coords)
        path_edges = len(self.move_selection.path) - 1
        invalid_move = (
            rebels_to_move <= 0
            or path_edges <= 0
            or destination_coords is None
        )

        if invalid_move:
            self.cancel_rebel_move_mode()
            return

        self.redirect_rebel_moves(source_coords, self.move_selection.path)

        stationed_rebels = source_cell.rebels
        if stationed_rebels > 0:
            source_cell.remove_rebels(stationed_rebels)
            self.create_rebel_batches(
                self.move_selection.path,
                stationed_rebels,
            )

        if self.selected_cell_coords == source_coords:
            self.update_popup_for_cell(source_coords, source_cell)

        self.cancel_rebel_move_mode()

    def create_rebel_batches(self, path: list[tuple[int, int]],
                             rebels_to_move: int) -> None:
        remaining_rebels = rebels_to_move
        batch_index = 0
        while remaining_rebels > 0:
            batch_size = min(
                remaining_rebels,
                self.commander.REBEL_MOVE_BATCH_SIZE,
            )
            remaining_rebels -= batch_size
            self.active_rebel_moves.append(RebelMoveBatch(
                path=list(path),
                rebels=batch_size,
                current_index=0,
                time_until_advance=(batch_index + 1)
                * self.commander.REBEL_MOVE_STEP_TIME,
            ))
            batch_index += 1

    def redirect_rebel_moves(self, source_coords: tuple[int, int],
                             path: list[tuple[int, int]]) -> None:
        for batch in self.rebel_batches_at(source_coords):
            preserved_delay = batch.time_until_advance
            batch.path = list(path)
            batch.current_index = 0
            if preserved_delay > 0:
                batch.time_until_advance = preserved_delay
            else:
                batch.time_until_advance = (
                    self.commander.REBEL_MOVE_STEP_TIME
                )

    def toggle_headquarters_mode(self,
                                 cell_coords: tuple[int, int]) -> None:
        row, col = cell_coords
        cell = self.game_map.grid[row][col]
        if not isinstance(cell.building, Headquarters):
            return

        cell.building.toggle_mode()
        if self.selected_cell_coords == cell_coords:
            self.update_popup_for_cell(cell_coords, cell)

    def start_overseer_request(self) -> None:
        if self._waiting_for_overseer:
            print("Overseer request already running...")
            return

        started = self.overseer.request(self.build_prompt())
        if started:
            self._waiting_for_overseer = True
            print("Calling Overseer...")
        else:
            print("Overseer request already running...")

    def update(self, dt: float) -> None:
        self.update_headquarters(dt)
        self.update_rebel_moves(dt)

        result = self.overseer.poll()
        if result is not None:
            self._waiting_for_overseer = False
            status, payload = result
            if status == "ok":
                self.apply_enemy_action(payload)
            else:
                print(f"LLM call failed: {payload}")

    def update_headquarters(self, dt: float) -> None:
        selected_changed = False
        for row_index, row in enumerate(self.game_map.grid):
            for col_index, cell in enumerate(row):
                if not isinstance(cell.building, Headquarters):
                    continue

                manpower_change, rebels_trained = cell.building.update(
                    dt,
                    self.commander.manpower,
                )
                if manpower_change > 0:
                    self.commander.add_manpower(manpower_change)
                elif manpower_change < 0:
                    self.commander.spend_manpower(-manpower_change)
                if rebels_trained:
                    cell.add_rebels(rebels_trained)

                selection_matches = (
                    self.selected_cell_coords == (row_index, col_index)
                )
                if (manpower_change or rebels_trained) and selection_matches:
                    selected_changed = True

        if selected_changed and self.selected_cell is not None:
            selected_coords = self.selected_cell_coords
            if selected_coords is not None:
                self.update_popup_for_cell(selected_coords, self.selected_cell)

    def update_rebel_moves(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt cannot be negative")

        selected_changed = False
        remaining_moves: list[RebelMoveBatch] = []
        for move in self.active_rebel_moves:
            move.time_until_advance -= dt

            while move.time_until_advance <= 0:
                if move.current_index >= len(move.path) - 1:
                    break

                current_row, current_col = move.path[move.current_index]
                next_row, next_col = move.path[move.current_index + 1]
                move.current_index += 1

                if move.current_index == len(move.path) - 1:
                    destination_cell = self.game_map.grid[next_row][next_col]
                    destination_cell.add_rebels(move.rebels)
                else:
                    move.time_until_advance += (
                        self.commander.REBEL_MOVE_STEP_TIME
                    )

                if self.selected_cell_coords in {
                    (current_row, current_col),
                    (next_row, next_col),
                }:
                    selected_changed = True

            if move.current_index < len(move.path) - 1:
                remaining_moves.append(move)

        self.active_rebel_moves = remaining_moves
        if selected_changed and self.selected_cell is not None:
            selected_coords = self.selected_cell_coords
            if selected_coords is not None:
                self.update_popup_for_cell(selected_coords, self.selected_cell)

    def render(self, screen) -> None:
        screen.fill((10, 12, 20))
        self.map_renderer.draw(
            screen,
            self.game_map,
            selected_cell=self.selected_cell_coords,
            rebel_counts=self.visible_rebel_counts(),
        )

        if self.commands.active and self.commands.cell_coords is not None:
            row, col = self.commands.cell_coords
            self.commands.update_context(
                self.command_context_for_cell((row, col))
            )
            center = self.map_renderer.cell_center(
                row,
                col,
                self.game.screen,
                self.game_map,
            )
            self.commands.update_transform(center, self.map_renderer.zoom)

        self.draw_move_preview(screen)
        self.draw_commander_hud(screen)
        self.commands.draw(screen)
        self.popup.draw(screen)

    def draw_move_preview(self, screen: pygame.Surface) -> None:
        if self.move_selection is None:
            return

        path_to_draw = self.move_selection.path
        if path_to_draw is None:
            path_to_draw = self.move_selection.preview_path

        if path_to_draw is not None:
            for row, col in path_to_draw[1:]:
                cell_rect = self.map_renderer.cell_rect(
                    row,
                    col,
                    self.game.screen,
                    self.game_map,
                )
                overlay = pygame.Surface(cell_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(overlay, (120, 220, 120, 90),
                                 overlay.get_rect(), border_radius=3)
                screen.blit(overlay, cell_rect.topleft)

        highlight_coords = self.move_selection.hovered_coords
        if highlight_coords is not None:
            row, col = highlight_coords
            hover_rect = self.map_renderer.cell_rect(
                row,
                col,
                self.game.screen,
                self.game_map,
            )
            pygame.draw.rect(screen, (200, 220, 255), hover_rect, width=2,
                             border_radius=3)

        destination_coords = self.move_selection.destination_coords
        if destination_coords is not None and self.move_selection.path:
            row, col = destination_coords
            center = self.map_renderer.cell_center(
                row,
                col,
                self.game.screen,
                self.game_map,
            )
            radius = self.move_confirmation_radius()
            pygame.draw.circle(screen, (60, 180, 75), center, radius)
            pygame.draw.circle(screen, (255, 255, 255), center, radius,
                               width=1)
            self._draw_confirmation_tick(screen, center, radius)

    def _draw_confirmation_tick(self, screen: pygame.Surface,
                                center: tuple[int, int],
                                radius: int) -> None:
        left = (center[0] - radius // 2, center[1] + radius // 8)
        middle = (center[0] - radius // 8, center[1] + radius // 2)
        right = (center[0] + radius // 2, center[1] - radius // 3)
        line_width = max(2, radius // 5)
        pygame.draw.line(screen, (255, 255, 255), left, middle, line_width)
        pygame.draw.line(screen, (255, 255, 255), middle, right, line_width)

    def draw_commander_hud(self, screen: pygame.Surface) -> None:
        width = 220
        height = 35
        x = 24
        y = 24

        panel_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (20, 26, 42), panel_rect, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255), panel_rect, width=1,
                         border_radius=8)

        title_font = pygame.font.SysFont(None, 32)

        title_surface = title_font.render("Manpower: "
                                          f"{self.commander.manpower}",
                                          True, (220, 230, 250))

        screen.blit(title_surface, (x + 14, y + 10))

    def build_prompt(self) -> str:
        return ("Choose one tool call for this turn. "
                "Return only one function call with arguments.")

    def apply_enemy_action(self, response) -> None:
        name, args = self.extract_function_call(response)
        if name is None:
            text = getattr(response, "text", None)
            if text:
                print(f"Overseer output: {text}")
            else:
                print("Overseer output: no function call found.")
            return

        print(f"Overseer output: function={name}, args={args}")

    def extract_function_call(self, response):
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue

            parts = getattr(content, "parts", None) or []
            for part in parts:
                function_call = getattr(part, "function_call", None)
                if function_call is None:
                    continue

                name = getattr(function_call, "name", None)
                args = getattr(function_call, "args", None)
                return name, args

        return None, None

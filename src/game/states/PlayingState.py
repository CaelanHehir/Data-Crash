from __future__ import annotations
from dataclasses import dataclass
import pygame
from typing import Optional

from src.display.Commands import CommandContext, Commands
from src.display.Popup import Popup
from src.display.map_renderer import MapRenderer
from src.game.buildings.Datacenter import Datacenter
from src.game.buildings.Headquarters import Headquarters
from src.game.buildings.Outpost import Outpost
from src.game.entities.Camera import Camera
from src.game.entities.Commander import Commander
from src.game.world.Cell import Cell
from src.game.world.Map import Map
from src.game.states.State import State
from src.overseer.Overseer import Overseer
from src.display.text_renderer import get_font


@dataclass
class OutpostConstruction:
    elapsed: float = 0.0


class PlayingState(State):
    BATTLE_INTERVAL_SECONDS = 0.2
    MOVE_PREVIEW_FILL_COLOR = (120, 220, 120, 90)
    MOVE_HOVER_OUTLINE_COLOR = (200, 220, 255)
    MOVE_CONFIRM_FILL_COLOR = (60, 180, 75)
    MOVE_CONFIRM_OUTLINE_COLOR = (255, 255, 255)
    MOVE_CONFIRM_TICK_COLOR = (255, 255, 255)

    HUD_PANEL_WIDTH = 220
    HUD_PANEL_HEIGHT = 35
    HUD_PANEL_X = 24
    HUD_PANEL_Y = 24
    HUD_PANEL_COLOR = (20, 26, 42)
    HUD_PANEL_BORDER_COLOR = (255, 255, 255)
    HUD_TEXT_COLOR = (220, 230, 250)
    HUD_TITLE_FONT_SIZE = 32
    HUD_TEXT_OFFSET_X = 14
    HUD_TEXT_OFFSET_Y = 10

    def __init__(self, game) -> None:
        super().__init__(game)
        self.overseer = Overseer()
        self._waiting_for_overseer = False
        self.game_map = Map()
        self.commander = Commander()
        self.map_renderer = MapRenderer()
        self.camera = Camera(self.map_renderer)
        self.commands = Commands()
        self.popup = Popup()
        self.selected_cell: Optional[Cell] = None
        self.selected_cell_coords: Optional[tuple[int, int]] = None
        self._commands_consumed_click = False
        self.active_outpost_constructions: dict[tuple[int, int],
                                                OutpostConstruction] = {}
        self._battle_elapsed = 0.0

    def enter(self) -> None:
        # Reset/initialize a fresh run here (entities, score, etc.)
        self.game_map = Map()
        self.commander = Commander()
        self.camera.reset()
        self.selected_cell = None
        self.selected_cell_coords = None
        self._commands_consumed_click = False
        self.commander.reset_movement_state()
        self.active_outpost_constructions = {}
        self._battle_elapsed = 0.0
        self.commands.hide()
        self.popup.hide()

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            self.camera.zoom_at(event.y,
                                mouse_pos,
                                self.game.screen,
                                self.game_map)

            if self.commander.move_selection is not None:
                self.update_move_hover(mouse_pos)
            return

        if self.commander.move_selection is not None:
            if event.type == pygame.MOUSEMOTION:
                self.camera.handle_mouse_motion(event.pos,
                                                bool(event.buttons[0]),
                                                self.game.screen,
                                                self.game_map)

                self.update_move_hover(event.pos)
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.camera.handle_left_button_down(event.pos)
                elif event.button == 3:
                    self.camera.cancel_pan_tracking()
                    self.cancel_rebel_move_mode()
                return
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    if self.camera.handle_left_button_up():
                        self.handle_move_selection_click(event.pos)
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.camera.cancel_pan_tracking()
                self.cancel_rebel_move_mode()
                return

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.commands.click(event.pos):
                    self._commands_consumed_click = True
                    self.camera.cancel_pan_tracking()
                    return

                self.camera.handle_left_button_down(event.pos)
            elif event.button == 3:
                self.select_cell(event.pos, toggle=False)
                self.show_commands(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                was_click = self.camera.handle_left_button_up()
                if self._commands_consumed_click:
                    self._commands_consumed_click = False
                    return

                if was_click:
                    self.select_cell(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self.camera.handle_mouse_motion(event.pos,
                                            bool(event.buttons[0]),
                                            self.game.screen,
                                            self.game_map)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                from src.game.states.MenuState import MenuState
                self.game.change_state(MenuState(self.game))
            elif event.key == pygame.K_SPACE:
                self.start_overseer_request()

    def select_cell(self, mouse_pos: tuple[int, int],
                    toggle: bool = True) -> None:
        selected = self.map_renderer.pick_cell(mouse_pos, self.game.screen,
                                               self.game_map)

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
            description_lines.append("Durability: "
                                     f"{cell.building.current_durability}/"
                                     f"{cell.building.max_durability}")

            if isinstance(cell.building, Headquarters):
                description_lines.append(f"Mode: {cell.building.mode}")
        elif cell_coords in self.active_outpost_constructions:
            progress = self.outpost_construction_progress(cell_coords)
            build_rate = self.outpost_build_rate_multiplier(cell_coords)
            description_lines.append("Building: Outpost (under construction)")
            description_lines.append(f"Progress: {progress * 100:.0f}%")
            description_lines.append(f"Build rate: {build_rate:.2f}x")

        description_lines.extend([
            f"Rebels: {self.visible_rebel_count(cell_coords)}",
            f"Robots: {cell.robots}"])

        description = "\n".join(description_lines)
        self.popup.show(title=f"{cell.sector}{cell.id:02d}",
                        description=description)

    def show_commands(self, mouse_pos: tuple[int, int]) -> None:
        selected = self.map_renderer.pick_cell(mouse_pos,
                                               self.game.screen,
                                               self.game_map)

        if selected is None:
            self.commands.hide()
            return

        row, col = selected
        center = self.map_renderer.cell_center(row, col, self.game.screen,
                                               self.game_map)
        context = self.command_context_for_cell(selected)
        self.commands.show_at_cell(selected, center,
                                   self.camera.zoom, context)

    def command_context_for_cell(self, cell_coords: tuple[int, int]
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
            start_outpost_build_mode=self.start_outpost_build_mode,
            can_build_outpost=self.can_build_outpost)

    def start_outpost_build_mode(self, cell_coords: tuple[int, int]) -> None:
        if not self.can_build_outpost(cell_coords):
            return

        self.active_outpost_constructions[cell_coords] = OutpostConstruction()

        if self.selected_cell_coords == cell_coords and self.selected_cell:
            self.update_popup_for_cell(cell_coords, self.selected_cell)

    def can_build_outpost(self, cell_coords: tuple[int, int]) -> bool:
        if cell_coords in self.active_outpost_constructions:
            return False

        row, col = cell_coords
        cell = self.game_map.grid[row][col]

        if cell.building is not None:
            return False

        if self.visible_rebel_count(cell_coords) < Outpost.REBEL_REQUIREMENT:
            return False

        if self.sector_has_allied_structure(cell.sector):
            return False

        if self.sector_has_active_outpost_construction(cell.sector):
            return False

        return True

    def sector_has_allied_structure(self, sector: str) -> bool:
        for row in self.game_map.grid:
            for cell in row:
                if (cell.sector == sector
                        and isinstance(cell.building, Headquarters)):
                    return True

        return False

    def sector_has_active_outpost_construction(self, sector: str) -> bool:
        for row, col in self.active_outpost_constructions:
            if self.game_map.grid[row][col].sector == sector:
                return True

        return False

    def outpost_construction_progress(self,
                                      cell_coords: tuple[int, int]) -> float:
        construction = self.active_outpost_constructions.get(cell_coords)
        if construction is None:
            return 0.0

        return min(1.0, construction.elapsed / Outpost.BUILD_TIME)

    def outpost_build_rate_multiplier(self,
                                      cell_coords: tuple[int, int]) -> float:
        row, col = cell_coords
        cell = self.game_map.grid[row][col]
        return max(0.0, cell.rebels / Outpost.REBEL_REQUIREMENT)

    def outpost_construction_progress_map(
            self) -> dict[tuple[int, int], float]:
        return {cell_coords: self.outpost_construction_progress(cell_coords)
                for cell_coords in self.active_outpost_constructions}

    def start_rebel_move_mode(self, source_coords: tuple[int, int]) -> None:
        started = self.commander.start_rebel_move_mode(self.game_map,
                                                       source_coords)
        if not started:
            return

        self.update_move_hover(pygame.mouse.get_pos())

    def cancel_rebel_move_mode(self) -> None:
        self.commander.cancel_rebel_move_mode()

    def visible_rebel_count(self, cell_coords: tuple[int, int]) -> int:
        return self.commander.visible_rebel_count(self.game_map, cell_coords)

    def visible_rebel_counts(self) -> dict[tuple[int, int], int]:
        return self.commander.visible_rebel_counts(self.game_map)

    def update_move_hover(self, mouse_pos: tuple[int, int]) -> None:
        hovered_coords = self.map_renderer.pick_cell(mouse_pos,
                                                     self.game.screen,
                                                     self.game_map)
        self.commander.update_move_hover(self.game_map, hovered_coords)

    def handle_move_selection_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.commander.move_selection is None:
            return

        if self._move_confirmation_hit(mouse_pos):
            self.confirm_rebel_move()
            return

        selected = self.map_renderer.pick_cell(mouse_pos,
                                               self.game.screen,
                                               self.game_map)
        if selected is None:
            self.cancel_rebel_move_mode()
            return

        self.set_move_destination(selected)

    def set_move_destination(self, dest_coords: tuple[int, int]) -> None:
        self.commander.set_move_destination(self.game_map, dest_coords)

    def _move_confirmation_hit(self, mouse_pos: tuple[int, int]) -> bool:
        move_selection = self.commander.move_selection
        if move_selection is None:
            return False
        if move_selection.destination_coords is None:
            return False
        if not move_selection.path:
            return False

        row, col = move_selection.destination_coords
        center_x, center_y = self.map_renderer.cell_center(row,
                                                           col,
                                                           self.game.screen,
                                                           self.game_map)

        radius = self.move_confirmation_radius()
        dx = mouse_pos[0] - center_x
        dy = mouse_pos[1] - center_y
        return (dx * dx) + (dy * dy) <= radius * radius

    def move_confirmation_radius(self) -> int:
        scaled_radius = (self.map_renderer.base_tile_size *
                         self.camera.zoom * 0.275)
        return max(10, int(scaled_radius))

    def confirm_rebel_move(self) -> None:
        moved, source_coords = self.commander.confirm_rebel_move(self.game_map)
        if not moved or source_coords is None:
            return

        source_row, source_col = source_coords
        source_cell = self.game_map.grid[source_row][source_col]
        if self.selected_cell_coords == source_coords:
            self.update_popup_for_cell(source_coords, source_cell)

    def toggle_headquarters_mode(self, cell_coords: tuple[int, int]) -> None:
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

        started = self.overseer.request(self.build_context())
        if started:
            self._waiting_for_overseer = True
            print("\nCalling Overseer...")
        else:
            print("Overseer request already running...")

    def build_context(self) -> str:
        datacenter_cells: list[str] = []
        headquarters_cell: str = ""
        outpost_cells: list[str] = []
        forces_cells: list[str] = []

        for row_index, row in enumerate(self.game_map.grid):
            for col_index, cell in enumerate(row):
                cell_ref = (f"{cell.sector}{cell.id:02d} "
                            f"({row_index}, {col_index})")

                if isinstance(cell.building, Datacenter):
                    datacenter_cells.append(cell_ref)

                if isinstance(cell.building, (Headquarters)):
                    headquarters_cell = cell_ref

                if isinstance(cell.building, (Outpost)):
                    outpost_cells.append(f"{cell_ref}")

                rebels = self.visible_rebel_count((row_index, col_index))
                robots = cell.robots
                if rebels > 0 or robots > 0:
                    forces_cells.append(
                        f"{cell_ref}: rebels={rebels}, robots={robots}")

        lines = []

        lines.append("Your Datacenters:")
        lines.extend(datacenter_cells or ["none"])

        lines.append("")
        lines.append("Enemy Headquarters:")
        lines.append(headquarters_cell or "none")

        lines.append("")
        lines.append("Enemy Outposts:")
        lines.extend(outpost_cells or ["none"])

        lines.append("")
        lines.append("Cells with rebels or robots:")
        lines.extend(forces_cells or ["none"])

        return "\n".join(lines)

    def update(self, dt: float) -> None:
        self.update_headquarters(dt)
        self.update_outpost_constructions(dt)
        self.update_rebel_moves(dt)
        self.update_battles(dt)

        result = self.overseer.poll()
        if result is not None:
            self._waiting_for_overseer = False
            status, payload = result
            if status == "ok":
                self.apply_enemy_action(payload)
            else:
                print(f"LLM call failed: {payload}")

    def update_battles(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt cannot be negative")

        selected_coords = self.selected_cell_coords
        selected_snapshot: Optional[tuple[int, int, bool]] = None
        if selected_coords is not None:
            row, col = selected_coords
            selected_cell = self.game_map.grid[row][col]
            selected_snapshot = (self.visible_rebel_count(selected_coords),
                                 selected_cell.robots,
                                 selected_cell.battle_occurring)

        self._battle_elapsed += dt
        while self._battle_elapsed >= self.BATTLE_INTERVAL_SECONDS:
            self._battle_elapsed -= self.BATTLE_INTERVAL_SECONDS
            for row in self.game_map.grid:
                for cell in row:
                    cell.battle()

        if selected_coords is None or selected_snapshot is None:
            return
        if self.selected_cell is None:
            return

        row, col = selected_coords
        selected_cell = self.game_map.grid[row][col]
        updated_snapshot = (self.visible_rebel_count(selected_coords),
                            selected_cell.robots,
                            selected_cell.battle_occurring)
        if updated_snapshot != selected_snapshot:
            self.update_popup_for_cell(selected_coords, selected_cell)

    def update_outpost_constructions(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt cannot be negative")

        selected_changed = False
        completed_cells: list[tuple[int, int]] = []
        interrupted_cells: list[tuple[int, int]] = []

        for (cell_coords,
             construction) in self.active_outpost_constructions.items():
            row, col = cell_coords
            cell = self.game_map.grid[row][col]

            if cell.battle_occurring:
                interrupted_cells.append(cell_coords)
            else:
                build_rate = self.outpost_build_rate_multiplier(cell_coords)
                construction.elapsed += dt * build_rate
                if construction.elapsed >= Outpost.BUILD_TIME:
                    completed_cells.append(cell_coords)

            if self.selected_cell_coords == cell_coords:
                selected_changed = True

        for cell_coords in interrupted_cells:
            del self.active_outpost_constructions[cell_coords]

        for row, col in completed_cells:
            del self.active_outpost_constructions[(row, col)]
            cell = self.game_map.grid[row][col]
            outpost_name = f"Outpost {cell.sector}"
            cell.set_building(Outpost(name=outpost_name))

        if selected_changed and self.selected_cell is not None:
            selected_coords = self.selected_cell_coords
            if selected_coords is not None:
                self.update_popup_for_cell(selected_coords, self.selected_cell)

    def update_headquarters(self, dt: float) -> None:
        selected_changed = False
        for row_index, row in enumerate(self.game_map.grid):
            for col_index, cell in enumerate(row):
                if not isinstance(cell.building, Headquarters):
                    continue

                manpower_change, rebels_trained = cell.building.update(
                    dt,
                    self.commander.manpower)

                if manpower_change > 0:
                    self.commander.add_manpower(manpower_change)
                elif manpower_change < 0:
                    self.commander.spend_manpower(-manpower_change)
                if rebels_trained:
                    cell.add_rebels(rebels_trained)

                selection_matches = self.selected_cell_coords == (row_index,
                                                                  col_index)

                if (manpower_change or rebels_trained) and selection_matches:
                    selected_changed = True

        if selected_changed and self.selected_cell is not None:
            selected_coords = self.selected_cell_coords
            if selected_coords is not None:
                self.update_popup_for_cell(selected_coords, self.selected_cell)

    def update_rebel_moves(self, dt: float) -> None:
        changed_cells = self.commander.update_rebel_moves(self.game_map, dt)
        if (self.selected_cell_coords in changed_cells
                and self.selected_cell is not None):
            selected_coords = self.selected_cell_coords
            if selected_coords is not None:
                self.update_popup_for_cell(selected_coords, self.selected_cell)

    def render(self, screen) -> None:
        screen.fill((10, 12, 20))
        self.map_renderer.draw(screen, self.game_map,
                               selected_cell=self.selected_cell_coords,
                               rebel_counts=self.visible_rebel_counts(),
                               outpost_construction_progress=(
                                   self.outpost_construction_progress_map()))

        if self.commands.active and self.commands.cell_coords is not None:
            row, col = self.commands.cell_coords
            self.commands.update_context(self.command_context_for_cell((row,
                                                                        col)))
            center = self.map_renderer.cell_center(row,
                                                   col,
                                                   self.game.screen,
                                                   self.game_map)

            self.commands.update_transform(center, self.camera.zoom)

        self.draw_move_preview(screen)
        self.draw_commander_hud(screen)
        self.commands.draw(screen)
        self.popup.draw(screen)

    def draw_move_preview(self, screen: pygame.Surface) -> None:
        move_selection = self.commander.move_selection
        if move_selection is None:
            return

        path_to_draw = move_selection.path
        if path_to_draw is None:
            path_to_draw = move_selection.preview_path

        if path_to_draw is not None:
            for row, col in path_to_draw[1:]:
                cell_rect = self.map_renderer.cell_rect(row, col,
                                                        self.game.screen,
                                                        self.game_map)

                overlay = pygame.Surface(cell_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(overlay, self.MOVE_PREVIEW_FILL_COLOR,
                                 overlay.get_rect(), border_radius=3)
                screen.blit(overlay, cell_rect.topleft)

        highlight_coords = move_selection.hovered_coords
        if highlight_coords is not None:
            row, col = highlight_coords
            hover_rect = self.map_renderer.cell_rect(row, col,
                                                     self.game.screen,
                                                     self.game_map)

            pygame.draw.rect(screen, self.MOVE_HOVER_OUTLINE_COLOR,
                             hover_rect, width=2,
                             border_radius=3)

        destination_coords = move_selection.destination_coords
        if destination_coords is not None and move_selection.path:
            row, col = destination_coords
            center = self.map_renderer.cell_center(row, col,
                                                   self.game.screen,
                                                   self.game_map)

            radius = self.move_confirmation_radius()
            pygame.draw.circle(screen, self.MOVE_CONFIRM_FILL_COLOR,
                               center, radius)
            pygame.draw.circle(screen, self.MOVE_CONFIRM_OUTLINE_COLOR,
                               center, radius,
                               width=1)
            self._draw_confirmation_tick(screen, center, radius)

    def _draw_confirmation_tick(self, screen: pygame.Surface,
                                center: tuple[int, int],
                                radius: int) -> None:
        left = (center[0] - radius // 2, center[1] + radius // 8)
        middle = (center[0] - radius // 8, center[1] + radius // 2)
        right = (center[0] + radius // 2, center[1] - radius // 3)
        line_width = max(2, radius // 5)
        pygame.draw.line(screen, self.MOVE_CONFIRM_TICK_COLOR, left,
                         middle, line_width)
        pygame.draw.line(screen, self.MOVE_CONFIRM_TICK_COLOR, middle,
                         right, line_width)

    def draw_commander_hud(self, screen: pygame.Surface) -> None:
        panel_rect = pygame.Rect(self.HUD_PANEL_X,
                                 self.HUD_PANEL_Y,
                                 self.HUD_PANEL_WIDTH,
                                 self.HUD_PANEL_HEIGHT)
        pygame.draw.rect(screen,
                         self.HUD_PANEL_COLOR,
                         panel_rect,
                         border_radius=8)
        pygame.draw.rect(screen,
                         self.HUD_PANEL_BORDER_COLOR,
                         panel_rect,
                         width=1,
                         border_radius=8)

        title_font = get_font(self.HUD_TITLE_FONT_SIZE)

        title_surface = title_font.render("Manpower: "
                                          f"{self.commander.manpower}",
                                          True, self.HUD_TEXT_COLOR)

        screen.blit(title_surface,
                    (self.HUD_PANEL_X + self.HUD_TEXT_OFFSET_X,
                     self.HUD_PANEL_Y + self.HUD_TEXT_OFFSET_Y))

    def apply_enemy_action(self, response) -> None:
        name, args = self.overseer.extract_function_call(response)
        if name is None:
            text = getattr(response, "text", None)
            if text:
                print(f"Overseer output: {text}")
            else:
                print("Overseer output: no function call found.")
            return

        print(f"Overseer output: function={name}, args={args}")

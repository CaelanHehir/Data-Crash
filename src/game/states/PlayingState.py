from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from collections.abc import Mapping
from random import random
import pygame
from typing import Optional

from src.game.Commands import CommandContext, Commands
from src.display.Popup import Popup
from src.display.map_renderer import MapRenderer
from src.game.buildings.Datacenter import Datacenter
from src.game.buildings.Headquarters import Headquarters
from src.game.buildings.Outpost import Outpost
from src.game.entities.Camera import Camera
from src.game.entities.Commander import Commander
from src.game.world.Cell import Cell
from src.game.world.Map import Map
from src.game.states.EndState import EndState
from src.game.states.State import State
from src.overseer.Overseer import Overseer
from src.display.text_renderer import get_font


@dataclass
class OutpostConstruction:
    elapsed: float = 0.0


@dataclass
class RobotMoveBatch:
    path: list[tuple[int, int]]
    robots: int
    current_index: int = 0
    time_until_advance: float = 0.0


class GameLogs:
    logs: list[str]

    def __init__(self):
        self.logs = []

    def add_log(self, timestamp: int, event: str) -> None:
        print(f"{timestamp}s - {event}")
        self.logs.append(f"{timestamp}s - {event}")

    def clear(self) -> None:
        self.logs.clear()


class PlayingState(State):
    BATTLE_INTERVAL_SECONDS = 0.2
    BUILDING_DAMAGE_CHANCE_PER_ENEMY = 0.1

    BUILDING_REPAIR_COST = 20
    BUILDING_REPAIR_AMOUNT = 150

    ROBOT_MOVE_TIME = 1.5
    ROBOT_MOVE_BATCH_SIZE = 500
    ROBOT_BUILD_AMOUNT = 100

    OVERSEER_FIRST_CALL_DELAY_SECONDS = 120.0
    OVERSEER_CALL_INTERVAL_SECONDS = 30.0

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
        self.current_timestamp_seconds = 0.0
        self.game_logs = GameLogs()
        self._active_battle_cells: set[tuple[int, int]] = set()
        self._active_building_attacks: dict[tuple[int, int], str] = {}
        self.active_robot_moves: list[RobotMoveBatch] = []
        self._overseer_time_until_call = self.OVERSEER_FIRST_CALL_DELAY_SECONDS
        self._selected_popup_state: Optional[tuple] = None

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
        self.current_timestamp_seconds = 0.0
        self.game_logs.clear()
        self._active_battle_cells = set()
        self._active_building_attacks = {}
        self.active_robot_moves = []
        self._overseer_time_until_call = self.OVERSEER_FIRST_CALL_DELAY_SECONDS
        self._selected_popup_state = None
        self.commands.hide()
        self.popup.hide()

    def _timestamp(self) -> int:
        return int(self.current_timestamp_seconds)

    def _cell_name(self, cell_coords: tuple[int, int]) -> str:
        row, col = cell_coords
        cell = self.game_map.grid[row][col]
        return f"{cell.sector}{cell.id:02d}"

    def _log_event(self, event: str) -> None:
        self.game_logs.add_log(self._timestamp(), event)

    def _building_owner(self, cell: Cell) -> Optional[str]:
        if cell.building is None:
            return None
        if isinstance(cell.building, Datacenter):
            return "robots"
        if isinstance(cell.building, (Headquarters, Outpost)):
            return "rebels"
        return None

    def _building_attacker_state(
            self, cell: Cell) -> Optional[tuple[str, int]]:
        if cell.battle_occurring:
            return None

        owner = self._building_owner(cell)
        if owner == "robots" and cell.rebels > 0 and cell.robots == 0:
            return "rebels", cell.rebels
        if owner == "rebels" and cell.robots > 0 and cell.rebels == 0:
            return "robots", cell.robots
        return None

    def _building_damage_roll(self, enemy_units: int) -> int:
        damage = 0
        for _ in range(enemy_units):
            if random() < self.BUILDING_DAMAGE_CHANCE_PER_ENEMY:
                damage += 1

        return damage

    def _battle_cells(self) -> set[tuple[int, int]]:
        return {(row_index, col_index)
                for row_index, row in enumerate(self.game_map.grid)
                for col_index, cell in enumerate(row)
                if cell.battle_occurring}

    def _log_battle_transitions(self) -> None:
        current_battles = self._battle_cells()
        started = current_battles - self._active_battle_cells
        ended = self._active_battle_cells - current_battles

        for cell_coords in started:
            self._log_event("a battle started on cell "
                            f"{self._cell_name(cell_coords)} ")

        for cell_coords in ended:
            row, col = cell_coords
            cell = self.game_map.grid[row][col]
            self._log_event("the battle on cell "
                            f"{self._cell_name(cell_coords)} "
                            f"has ended (status: {cell.battle_status()})")

        self._active_battle_cells = current_battles

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

    def select_cell(self, mouse_pos: tuple[int, int],
                    toggle: bool = True) -> None:
        selected = self.map_renderer.pick_cell(mouse_pos, self.game.screen,
                                               self.game_map)

        if selected is None:
            self.selected_cell = None
            self.selected_cell_coords = None
            self._selected_popup_state = None
            self.popup.hide()
            return

        if selected == self.selected_cell_coords and toggle:
            self.selected_cell = None
            self.selected_cell_coords = None
            self._selected_popup_state = None
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
            f"Robots: {self.visible_robot_count(cell_coords)}"])

        description = "\n".join(description_lines)
        self.popup.show(title=f"{cell.sector}{cell.id:02d}",
                        description=description)

    def _build_selected_popup_state(self) -> Optional[tuple]:
        if self.selected_cell_coords is None:
            return None

        row, col = self.selected_cell_coords
        cell = self.game_map.grid[row][col]

        if cell.building is None:
            building_state: tuple[object, ...] = (None,)
        else:
            building_state = (cell.building.name,
                              cell.building.current_durability,
                              cell.building.max_durability)

        outpost_progress: float | None = None
        if self.selected_cell_coords in self.active_outpost_constructions:
            outpost_progress = self.outpost_construction_progress(
                self.selected_cell_coords)

        return (self.visible_rebel_count(self.selected_cell_coords),
                self.visible_robot_count(self.selected_cell_coords),
                building_state,
                outpost_progress)

    def refresh_selected_popup_if_needed(self, force: bool = False) -> None:
        if self.selected_cell_coords is None or self.selected_cell is None:
            self._selected_popup_state = None
            return

        current_state = self._build_selected_popup_state()
        if force or current_state != self._selected_popup_state:
            row, col = self.selected_cell_coords
            cell = self.game_map.grid[row][col]
            self.selected_cell = cell
            self.update_popup_for_cell(self.selected_cell_coords, cell)
            self._selected_popup_state = current_state

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
            can_build_outpost=self.can_build_outpost,
            repair_building=self.repair_building,
            can_repair_building=self.can_repair_building)

    def can_repair_building(self, cell_coords: tuple[int, int]) -> bool:
        row, col = cell_coords
        cell = self.game_map.grid[row][col]
        building = cell.building
        if building is None:
            return False

        if self._building_owner(cell) != "rebels":
            return False

        if building.current_durability >= building.max_durability:
            return False

        if self.commander.manpower < self.BUILDING_REPAIR_COST:
            return False

        return True

    def repair_building(self, cell_coords: tuple[int, int]) -> None:
        if not self.can_repair_building(cell_coords):
            return

        row, col = cell_coords
        cell = self.game_map.grid[row][col]
        building = cell.building
        if building is None:
            return

        spent = self.commander.spend_manpower(self.BUILDING_REPAIR_COST)
        if not spent:
            return

        building.repair()

        self._log_event(f"Rebels repaired {building.name} on "
                        f"{self._cell_name(cell_coords)}")

    def start_outpost_build_mode(self, cell_coords: tuple[int, int]) -> None:
        if not self.can_build_outpost(cell_coords):
            return

        self.active_outpost_constructions[cell_coords] = OutpostConstruction()
        self._log_event("Rebels started outpost construction on cell "
                        f"{self._cell_name(cell_coords)}")

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

    def robot_batches_at(self,
                         cell_coords: tuple[int, int]) -> list[RobotMoveBatch]:
        return [batch for batch in self.active_robot_moves
                if batch.path[batch.current_index] == cell_coords]

    def visible_robot_count(self, cell_coords: tuple[int, int]) -> int:
        row, col = cell_coords
        total_robots = self.game_map.grid[row][col].robots
        for batch in self.robot_batches_at(cell_coords):
            total_robots += batch.robots

        return total_robots

    def visible_robot_counts(self) -> dict[tuple[int, int], int]:
        robot_counts = {(row_index, col_index): cell.robots
                        for row_index, row in enumerate(self.game_map.grid)
                        for col_index, cell in enumerate(row)}

        for batch in self.active_robot_moves:
            coords = batch.path[batch.current_index]
            robot_counts[coords] = robot_counts.get(coords, 0) + batch.robots

        return robot_counts

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
        move_selection = self.commander.move_selection
        start_event: Optional[str] = None
        if move_selection is not None and move_selection.destination_coords:
            source_coords = move_selection.source_coords
            destination_coords = move_selection.destination_coords
            rebels_to_move = self.visible_rebel_count(source_coords)
            if rebels_to_move > 0 and move_selection.path:
                start_event = (f"{rebels_to_move} rebels started moving "
                               "from "
                               f"{self._cell_name(source_coords)} "
                               "towards "
                               f"{self._cell_name(destination_coords)}")

        moved, source_coords = self.commander.confirm_rebel_move(self.game_map)
        if not moved or source_coords is None:
            return

        if start_event is not None:
            self._log_event(start_event)

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

        started = self.overseer.request(
            context=self.build_context(),
            game_logs=self.game_logs.logs,
            current_timestamp=self.current_timestamp_seconds)
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
                robots = self.visible_robot_count((row_index, col_index))
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

    def _transition_if_game_over(self) -> bool:
        has_robot_datacenter = False
        has_rebel_hq_or_outpost = False

        for row in self.game_map.grid:
            for cell in row:
                if isinstance(cell.building, Datacenter):
                    has_robot_datacenter = True
                elif isinstance(cell.building, (Headquarters, Outpost)):
                    has_rebel_hq_or_outpost = True

        if not has_rebel_hq_or_outpost:
            self.game.change_state(EndState(self.game, did_win=False))
            return True

        if not has_robot_datacenter:
            self.game.change_state(EndState(self.game, did_win=True))
            return True

        return False

    def update(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt cannot be negative")

        self.current_timestamp_seconds += dt

        self.update_headquarters(dt)
        self.update_outpost_constructions(dt)
        self.update_rebel_moves(dt)
        self.update_robot_moves(dt)
        self.update_battles(dt)
        if self._transition_if_game_over():
            return

        self.update_overseer_timer(dt)
        self.refresh_selected_popup_if_needed()

        result = self.overseer.poll()
        if result is not None:
            self._waiting_for_overseer = False
            status, payload = result
            if status == "ok":
                self.apply_enemy_action(payload)
                if self._transition_if_game_over():
                    return
            else:
                print(f"LLM call failed: {payload}")

    def update_overseer_timer(self, dt: float) -> None:
        self._overseer_time_until_call -= dt
        while self._overseer_time_until_call <= 0:
            self.start_overseer_request()
            self._overseer_time_until_call += (
                self.OVERSEER_CALL_INTERVAL_SECONDS)

    def update_battles(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt cannot be negative")

        selected_coords = self.selected_cell_coords
        selected_snapshot: Optional[tuple[int, int, bool]] = None
        if selected_coords is not None:
            row, col = selected_coords
            selected_cell = self.game_map.grid[row][col]
            selected_snapshot = (self.visible_rebel_count(selected_coords),
                                 self.visible_robot_count(selected_coords),
                                 selected_cell.battle_occurring)

        self._battle_elapsed += dt
        while self._battle_elapsed >= self.BATTLE_INTERVAL_SECONDS:
            self._battle_elapsed -= self.BATTLE_INTERVAL_SECONDS
            for row_index, row in enumerate(self.game_map.grid):
                for col_index, cell in enumerate(row):
                    cell.battle()

            next_active_building_attacks: dict[tuple[int, int], str] = {}
            for row_index, row in enumerate(self.game_map.grid):
                for col_index, cell in enumerate(row):
                    attack_state = self._building_attacker_state(cell)
                    if attack_state is None:
                        continue

                    attacker_faction, attacker_count = attack_state
                    cell_coords = (row_index, col_index)
                    attack_already_logged = (
                        cell_coords in self._active_building_attacks)

                    damage = self._building_damage_roll(attacker_count)
                    if damage > 0 and not attack_already_logged:
                        self._log_event(f"{cell.building.name} "
                                        "is being attacked")

                    if damage > 0:
                        building_name = cell.building.name
                        cell.building.take_damage(damage)
                    else:
                        building_name = cell.building.name

                    if cell.building.current_durability <= 0:
                        self._log_event(f"{building_name} "
                                        "has been destroyed")
                        cell.set_building(None)
                        continue

                    if attack_already_logged or damage > 0:
                        next_active_building_attacks[cell_coords] = (
                            attacker_faction)

            self._active_building_attacks = next_active_building_attacks

        self._log_battle_transitions()

        if selected_coords is None or selected_snapshot is None:
            return
        if self.selected_cell is None:
            return

        row, col = selected_coords
        selected_cell = self.game_map.grid[row][col]
        updated_snapshot = (self.visible_rebel_count(selected_coords),
                            self.visible_robot_count(selected_coords),
                            selected_cell.battle_occurring)
        if updated_snapshot != selected_snapshot:
            self.update_popup_for_cell(selected_coords, selected_cell)
            self._selected_popup_state = self._build_selected_popup_state()

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
            self._log_event("Rebels finished outpost construction on cell "
                            f"{self._cell_name((row, col))}")

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

        self._log_battle_transitions()

    def update_rebel_moves(self, dt: float) -> None:
        moves_before = list(self.commander.active_rebel_moves)
        changed_cells = self.commander.update_rebel_moves(self.game_map, dt)

        active_after_ids = {id(move)
                            for move in self.commander.active_rebel_moves}
        arrivals_by_destination: dict[tuple[int, int], int] = defaultdict(int)
        for move in moves_before:
            if id(move) in active_after_ids:
                continue

            destination = move.path[-1]
            arrivals_by_destination[destination] += move.rebels

        for destination, rebels_arrived in arrivals_by_destination.items():
            self._log_event(f"{rebels_arrived} rebels arrived at "
                            f"{self._cell_name(destination)}")

        self._log_battle_transitions()

        if (self.selected_cell_coords in changed_cells
                and self.selected_cell is not None):
            selected_coords = self.selected_cell_coords
            if selected_coords is not None:
                self.update_popup_for_cell(selected_coords, self.selected_cell)

    def update_robot_moves(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt cannot be negative")

        changed_cells: set[tuple[int, int]] = set()
        arrivals_by_destination: dict[tuple[int, int], int] = defaultdict(int)
        remaining_moves: list[RobotMoveBatch] = []

        for move in self.active_robot_moves:
            move.time_until_advance -= dt

            while move.time_until_advance <= 0:
                if move.current_index >= len(move.path) - 1:
                    break

                current_row, current_col = move.path[move.current_index]
                next_row, next_col = move.path[move.current_index + 1]
                move.current_index += 1
                changed_cells.add((current_row, current_col))
                changed_cells.add((next_row, next_col))

                if move.current_index == len(move.path) - 1:
                    destination_cell = self.game_map.grid[next_row][next_col]
                    destination_cell.add_robots(move.robots)
                    arrivals_by_destination[(next_row,
                                             next_col)] += move.robots
                else:
                    move.time_until_advance += self.ROBOT_MOVE_TIME

            if move.current_index < len(move.path) - 1:
                remaining_moves.append(move)

        self.active_robot_moves = remaining_moves

        for destination, robots_arrived in arrivals_by_destination.items():
            self._log_event(f"{robots_arrived} robots arrived at "
                            f"{self._cell_name(destination)}")

        if (self.selected_cell_coords in changed_cells
                and self.selected_cell is not None):
            selected_coords = self.selected_cell_coords
            if selected_coords is not None:
                self.update_popup_for_cell(selected_coords, self.selected_cell)

    def _create_robot_batches(self, path: list[tuple[int, int]],
                              robots_to_move: int) -> None:
        remaining_robots = robots_to_move
        batch_index = 0
        while remaining_robots > 0:
            batch_size = min(remaining_robots, self.ROBOT_MOVE_BATCH_SIZE)
            remaining_robots -= batch_size
            move_time = self.commander.UNIT_MOVE_TIME
            self.active_robot_moves.append(RobotMoveBatch(
                path=list(path),
                robots=batch_size,
                current_index=0,
                time_until_advance=(batch_index + 1) * move_time,
            ))
            batch_index += 1

    def _redirect_robot_moves(self, source_coords: tuple[int, int],
                              path: list[tuple[int, int]]) -> None:
        for batch in self.robot_batches_at(source_coords):
            preserved_delay = batch.time_until_advance
            batch.path = list(path)
            batch.current_index = 0
            if preserved_delay > 0:
                batch.time_until_advance = preserved_delay
            else:
                batch.time_until_advance = self.commander.UNIT_MOVE_TIME

    def render(self, screen) -> None:
        screen.fill((10, 12, 20))
        self.map_renderer.draw(screen, self.game_map,
                               selected_cell=self.selected_cell_coords,
                               rebel_counts=self.visible_rebel_counts(),
                               robot_counts=self.visible_robot_counts(),
                               outpost_construction_progress=(
                                   self.outpost_construction_progress_map()))
        active_destinations = {batch.path[-1]
                               for batch in self.commander.active_rebel_moves
                               if batch.path and batch.current_index
                               < len(batch.path) - 1}
        self.map_renderer.draw_rebel_move_overlay(
            screen,
            self.game_map,
            self.commander.move_selection,
            active_destinations,
            self.move_confirmation_radius())

        if self.commands.active and self.commands.cell_coords is not None:
            row, col = self.commands.cell_coords
            self.commands.update_context(
                self.command_context_for_cell((row, col)))

            center = self.map_renderer.cell_center(row,
                                                   col,
                                                   self.game.screen,
                                                   self.game_map)

            self.commands.update_transform(center, self.camera.zoom)

        self.draw_commander_hud(screen)
        self.commands.draw(screen)
        self.popup.draw(screen)

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
            return

        if name == "build_robots":
            self._apply_enemy_build_robots(args)
            return

        if name == "rally_robots":
            self._apply_enemy_rally_robots(args)
            return

    def _parse_function_args(self, args) -> dict[str, str]:
        if isinstance(args, Mapping):
            return {str(key): value for key, value in args.items()}
        return {}

    def _normalize_cell_name(self, raw_name: str) -> str:
        token = raw_name.strip()
        if not token:
            return ""

        token = token.split()[0]
        token = token.strip().strip(",")
        token = token.split("(")[0].strip()
        return token.lower()

    def _find_cell_coords_by_name(
            self, cell_name: str) -> Optional[tuple[int, int]]:
        normalized_target = self._normalize_cell_name(cell_name)
        if not normalized_target:
            return None

        for row_index, row in enumerate(self.game_map.grid):
            for col_index, cell in enumerate(row):
                canonical_name = f"{cell.sector}{cell.id:02d}".lower()
                if canonical_name == normalized_target:
                    return row_index, col_index

        return None

    def _apply_enemy_build_robots(self, args) -> None:
        parsed_args = self._parse_function_args(args)
        spawn_point = str(parsed_args.get("spawn_point", "")).strip()
        if not spawn_point:
            print("Overseer action rejected: missing spawn_point")
            return

        spawn_coords = self._find_cell_coords_by_name(spawn_point)
        if spawn_coords is None:
            print("Overseer action rejected: unknown spawn_point "
                  f"'{spawn_point}'")
            return

        row, col = spawn_coords
        spawn_cell = self.game_map.grid[row][col]
        if not isinstance(spawn_cell.building, Datacenter):
            print("Overseer action rejected: spawn_point is not a datacenter "
                  f"('{spawn_point}')")
            return

        spawn_cell.add_robots(self.ROBOT_BUILD_AMOUNT)
        self._log_event(f"Overseer built {self.ROBOT_BUILD_AMOUNT} robots "
                        f"at {self._cell_name(spawn_coords)}")

        if self.selected_cell_coords == spawn_coords and self.selected_cell:
            self.update_popup_for_cell(spawn_coords, spawn_cell)

    def _apply_enemy_rally_robots(self, args) -> None:
        parsed_args = self._parse_function_args(args)
        source_name = str(parsed_args.get("source", "")).strip()
        target_name = str(parsed_args.get("target", "")).strip()

        if not source_name or not target_name:
            print("Overseer action rejected: source and target are required")
            return

        source_coords = self._find_cell_coords_by_name(source_name)
        target_coords = self._find_cell_coords_by_name(target_name)

        if source_coords is None:
            print(f"Overseer action rejected: unknown source '{source_name}'")
            return
        if target_coords is None:
            print(f"Overseer action rejected: unknown target '{target_name}'")
            return
        if source_coords == target_coords:
            print("Overseer action rejected: source and target are identical")
            return

        source_row, source_col = source_coords
        source_cell = self.game_map.grid[source_row][source_col]
        path = self.commander.find_rebel_path(self.game_map,
                                              source_coords,
                                              target_coords)
        if not path:
            print("Overseer action rejected: no path found")
            return

        robots_to_move = self.visible_robot_count(source_coords)
        if robots_to_move <= 0:
            print("Overseer action rejected: no robots available at "
                  f"{self._cell_name(source_coords)}")
            return

        self._redirect_robot_moves(source_coords, path)

        stationed_robots = source_cell.robots
        if stationed_robots > 0:
            source_cell.remove_robots(stationed_robots)
            self._create_robot_batches(path, stationed_robots)

        self._log_event(f"Overseer rallied {robots_to_move} robots from "
                        f"{self._cell_name(source_coords)} to "
                        f"{self._cell_name(target_coords)}")

        if self.selected_cell_coords == source_coords and self.selected_cell:
            self.update_popup_for_cell(source_coords, source_cell)

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Optional

from src.game.buildings.Datacenter import Datacenter
from src.game.world.Map import Map


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


class Commander:
    STARTING_MANPOWER = 100
    REBEL_MOVE_TIME = 2.0
    REBEL_MOVE_BATCH_SIZE = 500

    def __init__(self, manpower: int = STARTING_MANPOWER) -> None:
        if manpower < 0:
            raise ValueError("manpower cannot be negative")

        self.manpower = manpower
        self.move_selection: Optional[MoveSelection] = None
        self.active_rebel_moves: list[RebelMoveBatch] = []

    def reset_movement_state(self) -> None:
        self.move_selection = None
        self.active_rebel_moves = []

    def spend_manpower(self, amount: int) -> bool:
        if amount < 0:
            raise ValueError("manpower spend amount cannot be negative")
        if amount > self.manpower:
            return False

        self.manpower -= amount
        return True

    def add_manpower(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("manpower gain amount cannot be negative")

        self.manpower += amount

    def start_rebel_move_mode(self, game_map: Map,
                              source_coords: tuple[int, int]) -> bool:
        if self.visible_rebel_count(game_map, source_coords) <= 0:
            return False

        self.move_selection = MoveSelection(source_coords=source_coords)
        return True

    def cancel_rebel_move_mode(self) -> None:
        self.move_selection = None

    def rebel_batches_at(self,
                         cell_coords: tuple[int, int]) -> list[RebelMoveBatch]:
        return [batch for batch in self.active_rebel_moves
                if batch.path[batch.current_index] == cell_coords]

    def visible_rebel_count(self, game_map: Map,
                            cell_coords: tuple[int, int]) -> int:
        row, col = cell_coords
        total_rebels = game_map.grid[row][col].rebels
        for batch in self.rebel_batches_at(cell_coords):
            total_rebels += batch.rebels

        return total_rebels

    def visible_rebel_counts(
            self, game_map: Map) -> dict[tuple[int, int], int]:
        rebel_counts = {(row_index, col_index): cell.rebels
                        for row_index, row in enumerate(game_map.grid)
                        for col_index, cell in enumerate(row)}

        for batch in self.active_rebel_moves:
            coords = batch.path[batch.current_index]
            rebel_counts[coords] = rebel_counts.get(coords, 0) + batch.rebels

        return rebel_counts

    def update_move_hover(self, game_map: Map,
                          hovered_coords: Optional[tuple[int, int]]) -> None:
        if self.move_selection is None:
            return

        self.move_selection.hovered_coords = hovered_coords

        if hovered_coords is None:
            self.move_selection.preview_path = None
            return

        self.move_selection.preview_path = self.find_rebel_path(
            game_map,
            self.move_selection.source_coords,
            hovered_coords)

    def set_move_destination(self, game_map: Map,
                             dest_coords: tuple[int, int]) -> None:
        if self.move_selection is None:
            return

        source_coords = self.move_selection.source_coords
        path = self.find_rebel_path(game_map, source_coords, dest_coords)
        self.move_selection.destination_coords = dest_coords
        self.move_selection.path = path
        self.move_selection.preview_path = path

    def confirm_rebel_move(self, game_map: Map
                           ) -> tuple[bool, Optional[tuple[int, int]]]:
        if self.move_selection is None or not self.move_selection.path:
            return False, None

        source_coords = self.move_selection.source_coords
        source_row, source_col = source_coords
        destination_coords = self.move_selection.destination_coords
        source_cell = game_map.grid[source_row][source_col]
        rebels_to_move = self.visible_rebel_count(game_map, source_coords)
        path_edges = len(self.move_selection.path) - 1
        invalid_move = (rebels_to_move <= 0 or path_edges <= 0
                        or destination_coords is None)

        if invalid_move:
            self.cancel_rebel_move_mode()
            return False, None

        self._redirect_rebel_moves(source_coords, self.move_selection.path)

        stationed_rebels = source_cell.rebels
        if stationed_rebels > 0:
            source_cell.remove_rebels(stationed_rebels)
            self._create_rebel_batches(self.move_selection.path,
                                       stationed_rebels)

        self.cancel_rebel_move_mode()
        return True, source_coords

    def update_rebel_moves(self, game_map: Map,
                           dt: float) -> set[tuple[int, int]]:
        if dt < 0:
            raise ValueError("dt cannot be negative")

        changed_cells: set[tuple[int, int]] = set()
        remaining_moves: list[RebelMoveBatch] = []
        for move in self.active_rebel_moves:
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
                    destination_cell = game_map.grid[next_row][next_col]
                    destination_cell.add_rebels(move.rebels)
                else:
                    move.time_until_advance += self.REBEL_MOVE_TIME

            if move.current_index < len(move.path) - 1:
                remaining_moves.append(move)

        self.active_rebel_moves = remaining_moves
        return changed_cells

    def find_rebel_path(self, game_map: Map, start: tuple[int, int],
                        destination: tuple[int, int]
                        ) -> list[tuple[int, int]] | None:
        if start == destination:
            return None

        distances: dict[tuple[int, int],
                        tuple[int, int]] = {start: (0, 0)}

        previous: dict[tuple[int, int], tuple[int, int]] = {}
        queue: list[tuple[int, int, tuple[int, int]]] = [(0, 0, start)]

        while queue:
            cost, steps, current = heapq.heappop(queue)
            best = distances.get(current)
            if best is None or best != (cost, steps):
                continue

            if current == destination:
                return self._reconstruct_path(previous, destination)

            for neighbor in self._neighbors(game_map, current):
                row, col = neighbor
                cell = game_map.grid[row][col]
                next_cost = cost + self._movement_priority(cell)
                next_steps = steps + 1
                current_best = distances.get(neighbor)

                if (current_best is None
                        or (next_cost, next_steps) < current_best):
                    distances[neighbor] = (next_cost, next_steps)
                    previous[neighbor] = current
                    heapq.heappush(queue, (next_cost, next_steps, neighbor))

        return None

    def _neighbors(self, game_map: Map,
                   coords: tuple[int, int]) -> list[tuple[int, int]]:
        row, col = coords
        neighbors: list[tuple[int, int]] = []
        for row_offset, col_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            next_row = row + row_offset
            next_col = col + col_offset
            if (0 <= next_row < game_map.HEIGHT
                    and 0 <= next_col < game_map.WIDTH):
                neighbors.append((next_row, next_col))

        return neighbors

    def _movement_priority(self, cell) -> int:
        has_datacenter = isinstance(cell.building, Datacenter)
        has_robots = cell.robots > 0

        if not has_datacenter and not has_robots:
            return 1
        if has_datacenter and not has_robots:
            return 2
        if not has_datacenter and has_robots:
            return 3
        return 4

    def _reconstruct_path(self,
                          previous: dict[tuple[int, int], tuple[int, int]],
                          destination: tuple[int, int]
                          ) -> list[tuple[int, int]]:
        path = [destination]
        current = destination
        while current in previous:
            current = previous[current]
            path.append(current)

        path.reverse()
        return path

    def _create_rebel_batches(self, path: list[tuple[int, int]],
                              rebels_to_move: int) -> None:
        remaining_rebels = rebels_to_move
        batch_index = 0
        while remaining_rebels > 0:
            batch_size = min(remaining_rebels, self.REBEL_MOVE_BATCH_SIZE)

            remaining_rebels -= batch_size
            self.active_rebel_moves.append(RebelMoveBatch(
                path=list(path),
                rebels=batch_size,
                current_index=0,
                time_until_advance=(batch_index + 1) * self.REBEL_MOVE_TIME,
            ))
            batch_index += 1

    def _redirect_rebel_moves(self, source_coords: tuple[int, int],
                              path: list[tuple[int, int]]) -> None:
        for batch in self.rebel_batches_at(source_coords):
            preserved_delay = batch.time_until_advance
            batch.path = list(path)
            batch.current_index = 0
            if preserved_delay > 0:
                batch.time_until_advance = preserved_delay
            else:
                batch.time_until_advance = self.REBEL_MOVE_TIME

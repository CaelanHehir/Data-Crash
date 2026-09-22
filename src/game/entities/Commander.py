from __future__ import annotations

import heapq

from src.game.buildings.Datacenter import Datacenter
from src.game.world.Map import Map


class Commander:
    STARTING_MANPOWER = 10
    REBEL_MOVE_STEP_TIME = 2.0
    REBEL_MOVE_BATCH_SIZE = 10

    def __init__(self, manpower: int = STARTING_MANPOWER) -> None:
        if manpower < 0:
            raise ValueError("manpower cannot be negative")

        self.manpower = manpower

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

    def find_rebel_path(self, game_map: Map,
                        start: tuple[int, int],
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
                    heapq.heappush(queue,
                                   (next_cost, next_steps, neighbor))

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

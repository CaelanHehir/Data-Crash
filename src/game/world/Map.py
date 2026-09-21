from __future__ import annotations

from random import sample

from src.game.buildings.Datacenter import Datacenter
from src.game.buildings.Headquarters import Headquarters
from src.game.world.Cell import Cell


def generate_cell_ids() -> list[str]:
    rows = ["Alpha", "Bravo", "Charlie", "Delta", "Echo",
            "Foxtrot", "Golf", "Hotel", "India", "Juliett",
            "Kilo", "Lima", "Mike", "November", "Oscar",
            "Papa", "Quebec", "Romeo", "Sierra", "Tango"]

    return [f"{row}{column:02d}"
            for row in rows
            for column in range(1, 21)]


class Map:
    WIDTH = 20
    HEIGHT = 20
    DATACENTER_COUNT = 5

    def __init__(self) -> None:
        cell_ids = generate_cell_ids()

        if len(cell_ids) != self.WIDTH * self.HEIGHT:
            raise ValueError("not enough unique cell names")

        self.grid: list[list[Cell]] = []

        index = 0
        for _ in range(self.HEIGHT):
            row: list[Cell] = []
            for _ in range(self.WIDTH):
                row.append(Cell(name=cell_ids[index], building=None))
                index += 1
            self.grid.append(row)

        self._place_buildings()

    def _place_buildings(self) -> None:
        all_cells = [cell for row in self.grid for cell in row]

        chosen_cells = sample(all_cells, 1 + self.DATACENTER_COUNT)
        headquarters_cell = chosen_cells[0]
        datacenter_cells = chosen_cells[1:]

        headquarters_cell.building = Headquarters(name="Headquarters")

        for index, cell in enumerate(datacenter_cells, start=1):
            cell.building = Datacenter(name=f"Datacenter{index}")

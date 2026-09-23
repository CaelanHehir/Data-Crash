from __future__ import annotations

from random import choice, sample

from src.game.buildings.Datacenter import Datacenter
from src.game.buildings.Headquarters import Headquarters
from src.game.world.Cell import Cell


def sector_names() -> list[str]:
    return ["Alpha", "Bravo", "Charlie", "Delta", "Echo",
            "Foxtrot", "Golf", "Hotel", "India", "Juliett",
            "Kilo", "Lima", "Mike", "November", "Oscar",
            "Papa", "Quebec", "Romeo", "Sierra", "Tango",
            "Uniform", "Victor", "Whiskey", "Xray", "Yankee",
            "Zulu"]


class Map:
    WIDTH = 20
    HEIGHT = 20
    SECTOR_SIZE = 4
    DATACENTER_COUNT = 10

    def __init__(self) -> None:
        if (self.WIDTH % self.SECTOR_SIZE != 0 or
                self.HEIGHT % self.SECTOR_SIZE != 0):
            raise ValueError("map dimensions must be divisible by sector size")

        sectors_per_row = self.WIDTH // self.SECTOR_SIZE
        sectors_per_column = self.HEIGHT // self.SECTOR_SIZE
        sector_count = sectors_per_row * sectors_per_column

        available_sector_names = sector_names()
        if len(available_sector_names) < sector_count:
            raise ValueError("not enough sector names")

        cells_per_sector = self.SECTOR_SIZE * self.SECTOR_SIZE

        self.grid: list[list[Cell]] = []

        for row_index in range(self.HEIGHT):
            row: list[Cell] = []
            for col_index in range(self.WIDTH):
                sector_row = row_index // self.SECTOR_SIZE
                sector_col = col_index // self.SECTOR_SIZE
                sector_index = (sector_row * sectors_per_row) + sector_col

                local_row = row_index % self.SECTOR_SIZE
                local_col = col_index % self.SECTOR_SIZE
                cell_id = local_row * self.SECTOR_SIZE + local_col + 1
                if cell_id < 1 or cell_id > cells_per_sector:
                    raise ValueError("invalid cell id generated for sector")

                row.append(Cell(
                    sector=available_sector_names[sector_index],
                    id=cell_id,
                    building=None,
                ))
            self.grid.append(row)

        self._place_buildings()

    def _place_buildings(self) -> None:
        cells_by_sector: dict[str, list[Cell]] = {}
        for row in self.grid:
            for cell in row:
                cells_by_sector.setdefault(cell.sector, []).append(cell)

        building_count = 1 + self.DATACENTER_COUNT
        if building_count > len(cells_by_sector):
            raise ValueError("more buildings than available sectors")

        chosen_sectors = sample(list(cells_by_sector.keys()), building_count)
        headquarters_cell = choice(cells_by_sector[chosen_sectors[0]])

        datacenter_cells: list[Cell] = []
        for sector in chosen_sectors[1:]:
            datacenter_cells.append(choice(cells_by_sector[sector]))

        headquarters_cell.building = Headquarters(name="Headquarters")

        for index, cell in enumerate(datacenter_cells, start=1):
            cell.building = Datacenter(name=f"Datacenter{index}")

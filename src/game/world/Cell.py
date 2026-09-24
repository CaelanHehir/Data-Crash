from __future__ import annotations
from random import random
from typing import Optional

from src.game.buildings.Building import Building
from src.game.buildings.Datacenter import Datacenter
from src.game.buildings.Headquarters import Headquarters
from src.game.buildings.Outpost import Outpost


class Cell:
    EMPTY_COLOR = (35, 45, 65)
    HEADQUARTERS_COLOR = (247, 186, 20)
    OUTPOST_COLOR = (255, 198, 92)
    DATACENTER_COLOR = (107, 178, 255)
    DEFAULT_OUTLINE_COLOR = (75, 75, 75)
    BATTLE_OUTLINE_COLOR = (220, 65, 65)

    def __init__(self, sector: str, id: int,
                 building: Optional[Building]) -> None:
        self.sector = sector
        self.id = id
        self.building = building
        self.color = self._color_for_building(building)
        self.rebels = 0
        self.robots = 0
        self.battle_occurring = False

    def set_building(self, building: Optional[Building]) -> None:
        self.building = building
        self.color = self._color_for_building(building)

    def _color_for_building(self, building: Optional[Building]
                            ) -> tuple[int, int, int]:
        if isinstance(building, Outpost):
            return self.OUTPOST_COLOR
        if isinstance(building, Headquarters):
            return self.HEADQUARTERS_COLOR
        if isinstance(building, Datacenter):
            return self.DATACENTER_COLOR
        return self.EMPTY_COLOR

    def add_rebels(self, number: int) -> None:
        if number < 1:
            raise ValueError("rebel number cannot be negative")
        self.rebels += number
        self._refresh_battle_state()

    def remove_rebels(self, number: int) -> None:
        if number < 1:
            raise ValueError("rebel number cannot be negative")
        if number > self.rebels:
            raise ValueError("cannot remove more rebels than available")

        self.rebels -= number
        self._refresh_battle_state()

    def add_robots(self, number: int) -> None:
        if number < 1:
            raise ValueError("robot number cannot be negative")
        self.robots += number
        self._refresh_battle_state()

    def battle(self) -> None:
        if not self.battle_occurring:
            return

        for _ in range(self.rebels):
            if not self.robots:
                break
            rebels_hit = random() < 0.01
            if rebels_hit:
                self.robots -= 1

        for _ in range(self.robots):
            if not self.rebels:
                break
            robots_hit = random() < 0.01
            if robots_hit and self.rebels > 0:
                self.rebels -= 1

        self._refresh_battle_state()

    @property
    def outline_color(self) -> tuple[int, int, int]:
        if self.battle_occurring:
            return self.BATTLE_OUTLINE_COLOR

        return self.DEFAULT_OUTLINE_COLOR

    def _refresh_battle_state(self) -> None:
        self.battle_occurring = self.rebels > 0 and self.robots > 0

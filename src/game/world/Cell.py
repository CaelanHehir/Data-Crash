from __future__ import annotations
from random import random
from typing import Optional

from src.game.buildings.Building import Building


class Cell:
    def __init__(self, sector: str, id: int,
                 building: Optional[Building]) -> None:
        self.sector = sector
        self.id = id
        self.building = building
        self.rebels = 0
        self.robots = 0

    def add_rebels(self, number: int) -> None:
        if number < 1:
            raise ValueError("rebel number cannot be negative")
        self.rebels += number

    def remove_rebels(self, number: int) -> None:
        if number < 1:
            raise ValueError("rebel number cannot be negative")
        if number > self.rebels:
            raise ValueError("cannot remove more rebels than available")

        self.rebels -= number

    def add_robots(self, number: int) -> None:
        if number < 1:
            raise ValueError("robot number cannot be negative")
        self.robots += number

    def battle(self) -> None:
        for _ in range(self.rebels):
            if not self.robots:
                break
            rebels_hit = random() < 0.3
            if rebels_hit:
                self.robots -= 1

        for _ in range(self.robots):
            if not self.rebels:
                break
            robots_hit = random() < 0.3
            if robots_hit and self.rebels > 0:
                self.rebels -= 1

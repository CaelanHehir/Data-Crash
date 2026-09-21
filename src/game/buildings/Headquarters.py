from __future__ import annotations

from src.game.buildings.Building import Building


class Headquarters(Building):
    def __init__(self, name: str) -> None:
        super().__init__(name)

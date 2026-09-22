from __future__ import annotations

from src.game.buildings.Headquarters import Headquarters


class Outpost(Headquarters):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.max_durability = 200
        self.current_durability = self.max_durability

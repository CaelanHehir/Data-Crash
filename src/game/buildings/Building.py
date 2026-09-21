from __future__ import annotations

from abc import ABC


class Building(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

        self.max_durability = 1000
        self.current_durability = self.max_durability
        self.repair_amount = 100

    def take_damage(self, value: int) -> None:
        if value < 0:
            raise ValueError("damage value cannot be negative")

        self.current_durability = max(0, self.current_durability - value)

    def repair(self) -> None:
        new_durability = min(self.max_durability,
                             self.current_durability + self.repair_amount)
        self.current_durability = new_durability

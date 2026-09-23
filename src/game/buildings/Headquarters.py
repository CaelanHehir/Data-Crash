from __future__ import annotations

from src.game.buildings.Building import Building


class Headquarters(Building):
    MOBILIZING = "Mobilizing"
    TRAINING = "Training"
    MANPOWER_PER_CYCLE = 5
    MOBILIZING_INTERVAL = 10.0
    REBEL_COST = 1
    REBELS_PER_CYCLE = 1
    TRAINING_INTERVAL = 3.0

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.mode = self.MOBILIZING
        self._mode_elapsed = 0.0

    def toggle_mode(self) -> None:
        if self.mode == self.MOBILIZING:
            self.mode = self.TRAINING
        else:
            self.mode = self.MOBILIZING

        self._mode_elapsed = 0.0

    @property
    def cycle_duration(self) -> float:
        if self.mode == self.MOBILIZING:
            return self.MOBILIZING_INTERVAL
        return self.TRAINING_INTERVAL

    @property
    def cycle_progress(self) -> float:
        duration = self.cycle_duration
        if duration <= 0:
            return 0.0

        return min(1.0, self._mode_elapsed / duration)

    def update(self, dt: float,
               available_manpower: int = 0) -> tuple[int, int]:
        if dt < 0:
            raise ValueError("dt cannot be negative")
        if available_manpower < 0:
            raise ValueError("available manpower cannot be negative")

        self._mode_elapsed += dt

        if self.mode == self.MOBILIZING:
            cycles = int(self._mode_elapsed // self.MOBILIZING_INTERVAL)
            if cycles == 0:
                return 0, 0

            self._mode_elapsed -= cycles * self.MOBILIZING_INTERVAL
            return cycles * self.MANPOWER_PER_CYCLE, 0

        cycles = int(self._mode_elapsed // self.TRAINING_INTERVAL)
        if cycles == 0:
            return 0, 0

        max_affordable_cycles = available_manpower // self.REBEL_COST

        completed_cycles = min(cycles, max_affordable_cycles)
        if completed_cycles == 0:
            return 0, 0

        self._mode_elapsed -= completed_cycles * self.TRAINING_INTERVAL
        manpower_spent = completed_cycles * self.REBEL_COST
        rebels_trained = completed_cycles * self.REBELS_PER_CYCLE
        return -manpower_spent, rebels_trained

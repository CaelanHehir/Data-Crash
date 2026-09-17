from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.Game import Game


class State:
    """Base class every game state inherits from."""

    def __init__(self, game: "Game") -> None:
        self.game = game

    def handle_event(self, event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def render(self, screen) -> None:
        pass

    def enter(self) -> None:
        """Called each time this state becomes active."""
        pass

    def exit(self) -> None:
        """Called when leaving this state."""
        pass

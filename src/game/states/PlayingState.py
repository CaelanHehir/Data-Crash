from __future__ import annotations
import pygame
from src.game.states.State import State


class PlayingState(State):
    def enter(self) -> None:
        # Reset/initialize a fresh run here (entities, score, etc.)
        pass

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            from src.game.states.MenuState import MenuState
            self.game.change_state(MenuState(self.game))

    def update(self, dt: float) -> None:
        pass  # entity/game-logic updates go here

    def render(self, screen) -> None:
        screen.fill((10, 12, 20))
        # TODO: draw entities

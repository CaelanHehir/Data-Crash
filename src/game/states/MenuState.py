from __future__ import annotations
import pygame
from src.game.states.State import State
from src.game.states.PlayingState import PlayingState


class MenuState(State):
    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.game.change_state(PlayingState(self.game))
            elif event.key == pygame.K_ESCAPE:
                self.game.running = False

    def render(self, screen) -> None:
        screen.fill((18, 24, 38))
        # TODO: draw title text / "Press Enter to start" prompt

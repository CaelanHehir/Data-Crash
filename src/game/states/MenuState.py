from __future__ import annotations
import pygame
from src.game.states.State import State
from src.game.states.PlayingState import PlayingState
from src.display.text_renderer import get_font


class MenuState(State):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.selection = 0
        self.options = ["Start Game", "Quit"]

    def handle_event(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.selection = 0
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selection = 1
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.selection == 0:
                self.game.change_state(PlayingState(self.game))
            else:
                self.game.running = False
        elif event.key in (pygame.K_q, pygame.K_ESCAPE):
            self.game.running = False

    def render(self, screen) -> None:
        screen.fill((18, 24, 38))

        font_title = get_font(72)
        font_menu = get_font(48)

        title = font_title.render("Data Crash", True, (255, 255, 255))
        title_x = screen.get_width() // 2 - title.get_width() // 2
        screen.blit(title, (title_x, 80))

        for index, label in enumerate(self.options):
            if index == self.selection:
                color = (107, 178, 255)
            else:
                color = (200, 220, 255)

            text = font_menu.render(label, True, color)
            x = screen.get_width() // 2 - text.get_width() // 2
            y = 220 + index * 80
            screen.blit(text, (x, y))

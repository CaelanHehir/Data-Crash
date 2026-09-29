from __future__ import annotations

import pygame

from src.display.text_renderer import get_font
from src.game.states.State import State


class EndState(State):
    def __init__(self, game, did_win: bool) -> None:
        super().__init__(game)
        self.did_win = did_win

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            self._go_to_menu()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._go_to_menu()

    def _go_to_menu(self) -> None:
        from src.game.states.MenuState import MenuState
        self.game.change_state(MenuState(self.game))

    def render(self, screen) -> None:
        if self.did_win:
            background_color = (14, 40, 24)
            title_text = "Victory"
            title_color = (135, 235, 160)
        else:
            background_color = (48, 18, 18)
            title_text = "Defeat"
            title_color = (255, 140, 140)

        screen.fill(background_color)

        title_font = get_font(96)
        subtitle_font = get_font(42)

        title_surface = title_font.render(title_text, True, title_color)
        subtitle_surface = subtitle_font.render(
            "Press any key to return to main menu",
            True,
            (235, 235, 245))

        title_x = screen.get_width() // 2 - title_surface.get_width() // 2
        title_y = screen.get_height() // 2 - title_surface.get_height() - 20

        subtitle_x = (screen.get_width() // 2
                      - subtitle_surface.get_width() // 2)
        subtitle_y = screen.get_height() // 2 + 20

        screen.blit(title_surface, (title_x, title_y))
        screen.blit(subtitle_surface, (subtitle_x, subtitle_y))

from __future__ import annotations

import pygame


class Popup:
    def __init__(self, title: str = "", description: str = "",
                 active: bool = False) -> None:
        self.title = title
        self.description = description
        self.active = active

    @property
    def decription(self) -> str:
        return self.description

    @decription.setter
    def decription(self, value: str) -> None:
        self.description = value

    def show(self, title: str, description: str) -> None:
        self.title = title
        self.description = description
        self.active = True

    def hide(self) -> None:
        self.active = False

    def draw(self, screen: pygame.Surface) -> None:
        if not self.active:
            return

        lines = self.description.split("\n")
        width = 380
        height = max(160, 76 + len(lines) * 24)
        x = screen.get_width() - width - 24
        y = 24

        bg_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (20, 26, 42), bg_rect, border_radius=8)
        pygame.draw.rect(screen, (107, 178, 255), bg_rect, width=2,
                         border_radius=8)

        title_font = pygame.font.SysFont(None, 34)
        body_font = pygame.font.SysFont(None, 24)

        title_surface = title_font.render(self.title, True, (255, 255, 255))
        screen.blit(title_surface, (x + 16, y + 12))

        for index, line in enumerate(lines):
            text = body_font.render(line, True, (220, 230, 250))
            screen.blit(text, (x + 16, y + 56 + index * 24))

from __future__ import annotations
import pygame


class Window:
    def __init__(self, title: str = "Data Crash", width: int = 1000,
                 height: int = 1000, target_fps: int = 60) -> None:
        pygame.init()
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()
        pygame.display.set_caption(title)

    def set_title(self, title: str) -> None:
        pygame.display.set_caption(title)

    def tick(self) -> float:
        return self.clock.tick(self.target_fps) / 1000.0

    def clear(self, color: tuple[int, int, int]) -> None:
        self.screen.fill(color)

    def flip(self) -> None:
        pygame.display.flip()

    def close(self) -> None:
        pygame.quit()


def run_game_window(title: str = "Data Crash", width: int = 1000,
                    height: int = 1000, target_fps: int = 60) -> None:
    """Create and run a simple game window until closed."""
    window = Window(title=title, width=width, height=height,
                    target_fps=target_fps)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        window.clear((18, 24, 38))
        window.flip()
        window.tick()

    window.close()

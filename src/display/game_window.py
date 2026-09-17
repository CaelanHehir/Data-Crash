from __future__ import annotations
import pygame


def run_game_window(title: str = "Data Crash", width: int = 960,
                    height: int = 540, target_fps: int = 60) -> None:
    """Create and run a simple game window until closed."""
    pygame.init()

    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(title)
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill((18, 24, 38))
        pygame.display.flip()
        clock.tick(target_fps)

    pygame.quit()

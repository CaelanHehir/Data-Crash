from __future__ import annotations
import pygame


class Game:
    def __init__(self, title: str = "Data Crash", width: int = 960,
                 height: int = 540, target_fps: int = 60) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.target_fps = target_fps
        self.running = True
        self.current_state = None

    def change_state(self, new_state) -> None:
        if self.current_state:
            self.current_state.exit()
        self.current_state = new_state
        self.current_state.enter()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.target_fps) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.current_state.handle_event(event)

            self.current_state.update(dt)
            self.current_state.render(self.screen)
            pygame.display.flip()

        pygame.quit()

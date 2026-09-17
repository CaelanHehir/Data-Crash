from __future__ import annotations
import pygame

from src.display.game_window import Window


class Game:
    def __init__(self, title: str = "Data Crash", width: int = 1400,
                 height: int = 800, target_fps: int = 60) -> None:
        self.window = Window(
            title=title,
            width=width,
            height=height,
            target_fps=target_fps,
        )
        self.screen = self.window.screen
        self.running = True
        self.current_state = None

    def change_state(self, new_state) -> None:
        if self.current_state:
            self.current_state.exit()
        self.current_state = new_state
        self.current_state.enter()

    def run(self) -> None:
        while self.running:
            dt = self.window.tick()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.current_state.handle_event(event)

            if self.current_state is not None:
                self.current_state.update(dt)
                self.current_state.render(self.window.screen)

            self.window.flip()

        self.window.close()

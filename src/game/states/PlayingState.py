from __future__ import annotations
import pygame
from src.game.states.State import State
from src.overseer.Overseer import Overseer


class PlayingState(State):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.overseer = Overseer()
        self._waiting_for_overseer = False

    def enter(self) -> None:
        # Reset/initialize a fresh run here (entities, score, etc.)
        pass

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                from src.game.states.MenuState import MenuState
                self.game.change_state(MenuState(self.game))
            elif event.key == pygame.K_SPACE:
                self.start_overseer_request()

    def start_overseer_request(self) -> None:
        if self._waiting_for_overseer:
            print("Overseer request already running...")
            return

        started = self.overseer.request(self.build_prompt())
        if started:
            self._waiting_for_overseer = True
            print("Calling Overseer...")
        else:
            print("Overseer request already running...")

    def update(self, dt: float) -> None:
        result = self.overseer.poll()
        if result is not None:
            self._waiting_for_overseer = False
            status, payload = result
            if status == "ok":
                self.apply_enemy_action(payload)
            else:
                print(f"LLM call failed: {payload}")

    def render(self, screen) -> None:
        screen.fill((10, 12, 20))
        # TODO: draw entities

    def build_prompt(self) -> str:
        return ("Choose one tool call for this turn. "
                "Return only one function call with arguments.")

    def apply_enemy_action(self, response) -> None:
        name, args = self.extract_function_call(response)
        if name is None:
            text = getattr(response, "text", None)
            if text:
                print(f"Overseer output: {text}")
            else:
                print("Overseer output: no function call found.")
            return

        print(f"Overseer output: function={name}, args={args}")

    def extract_function_call(self, response):
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue

            parts = getattr(content, "parts", None) or []
            for part in parts:
                function_call = getattr(part, "function_call", None)
                if function_call is None:
                    continue

                name = getattr(function_call, "name", None)
                args = getattr(function_call, "args", None)
                return name, args

        return None, None

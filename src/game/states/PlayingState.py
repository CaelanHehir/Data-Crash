from __future__ import annotations
import pygame
from typing import Optional

from src.display.Popup import Popup
from src.display.map_renderer import MapRenderer
from src.game.world.Cell import Cell
from src.game.world.Map import Map
from src.game.states.State import State
from src.overseer.Overseer import Overseer


class PlayingState(State):
    def __init__(self, game) -> None:
        super().__init__(game)
        self.overseer = Overseer()
        self._waiting_for_overseer = False
        self.game_map = Map()
        self.map_renderer = MapRenderer()
        self.popup = Popup()
        self.selected_cell: Optional[Cell] = None
        self.selected_cell_coords: Optional[tuple[int, int]] = None

    def enter(self) -> None:
        # Reset/initialize a fresh run here (entities, score, etc.)
        self.game_map = Map()
        self.selected_cell = None
        self.selected_cell_coords = None
        self.popup.hide()

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            self.map_renderer.zoom_at(
                event.y,
                mouse_pos,
                self.game.screen,
                self.game_map,
            )
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.map_renderer.start_pan(event.pos)
            elif event.button == 1:
                self.select_cell(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                self.map_renderer.stop_pan()
        elif event.type == pygame.MOUSEMOTION:
            if event.buttons[2]:
                self.map_renderer.pan_to(
                    event.pos,
                    self.game.screen,
                    self.game_map,
                )
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                from src.game.states.MenuState import MenuState
                self.game.change_state(MenuState(self.game))
            elif event.key == pygame.K_SPACE:
                self.start_overseer_request()

    def select_cell(self, mouse_pos: tuple[int, int]) -> None:
        selected = self.map_renderer.pick_cell(
            mouse_pos,
            self.game.screen,
            self.game_map,
        )

        if selected is None:
            self.selected_cell = None
            self.selected_cell_coords = None
            self.popup.hide()
            return

        if selected == self.selected_cell_coords:
            self.selected_cell = None
            self.selected_cell_coords = None
            self.popup.hide()
            return

        row, col = selected
        cell = self.game_map.grid[row][col]
        self.selected_cell = cell
        self.selected_cell_coords = selected

        building_name = "None"
        if cell.building is not None:
            building_name = cell.building.name

        description = (
            f"Building: {building_name}\n"
            f"Rebels: {cell.rebels}\n"
            f"Robots: {cell.robots}"
        )
        self.popup.show(title=cell.name, description=description)

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
        self.map_renderer.draw(
            screen,
            self.game_map,
            selected_cell=self.selected_cell_coords,
        )
        self.popup.draw(screen)

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

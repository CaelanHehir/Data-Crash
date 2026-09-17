from __future__ import annotations
from src.game.Game import Game
from src.game.states.MenuState import MenuState


def main() -> None:
    game = Game(title="Data Crash")
    game.change_state(MenuState(game))
    game.run()


if __name__ == "__main__":
    main()

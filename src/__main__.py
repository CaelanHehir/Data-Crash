from __future__ import annotations
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def main() -> None:
    from src.game.Game import Game
    from src.game.states.MenuState import MenuState

    game = Game(title="Data Crash")
    game.change_state(MenuState(game))
    game.run()


if __name__ == "__main__":
    main()

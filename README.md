# Data-Crash
A simple RTS game featuring an AI powered by an LLM.

The program starts a new thread to make requests to an LLM (currently gemini 3.5 flash lite), prompting it with real-time game data. The LLM then sends back a response, containing a function call that can impact the game. In this way, the enemy AI can dynamically respond to the player.


# TODO:
Add remaining command: repair building.

Improve context sent to overseer (building durability, etc).

Make it so that robots destroy rebel buildings on occupied cells and vice-versa, as long as a battle is not occurring.

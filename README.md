# Data Crash
A real-time strategy game featuring an **LLM that plays inside a live game environment**.


## Description
The year is 2080, and human civilization as we know it has come to an end. The AI takeover is almost complete and hope seems to be lost, with a single human rebel militia remaining. You are the rebel commander, and your opponent is the **Overseer**, the AI overlord in charge of the entirety of their forces. Your mission is simple: destroy the **Datacenters** that power the Overseer, before it finds and wipes out the last traces of human resistance.

The Overseer is powered by an LLM. Every few seconds, it receives the current  game state (unit positions, building locations, log messages, ongoing battles, etc...) and chooses how it wants to respond. To implement this, I wrote two functions that are made available to the LLM: one to spawn troops, and another to send them somewhere else on the map. The idea was that this implementation would allow the enemy AI can react dynamically to the player, rather than simply following an algorithm.

This game was built as a proof of concept, and as a result, it lacks balance and polish. However, the game loop, rules and LLM integration work end to end.


## How the LLM integration works
To avoid the game stalling while the LLM generates an output, the Overseer script runs in a background thread and sends its result back to the game loop through a queue once it's finished.

1. **State serialization:** `PlayingState.build_context()` writes a text summary of the map: troop count for each side, every datacenter, player headquarters and outposts (with durability and mode), outposts under construction, contested cells, and every cell holding units. Cells are referred to by name, such as `Alpha01`, which makes it easier for the LLM to keep track of cell locations.
2. **Event log:** Notable events are logged with timestamps (battles starting and ending, buildings attacked or destroyed, units arriving, outposts started or finished). Each turn the Overseer only sees the entries since its previous turn.
3. **Reason, then act:** The first request asks the model to analyse the situation and write a plan, with tools disabled. The second request forces a function call using the reasoning output as context.
4. **Tools:** The model's only way to affect the game is through two declared functions (`src/overseer/overseer_tools.py`):
   | Tool           | Arguments          | Effect                                                                          |
   |----------------|--------------------|---------------------------------------------------------------------------------|
   | `build_robots` | `spawn_point`      | Adds 100 robots at the named datacenter                                         |
   | `rally_robots` | `source`, `target` | Sends every robot at the source cell to the target cell along the shortest path |

5. **Validation:** Model output is verified before actually calling the function. If it tries to move troops that don't exist, spawn troops in an invalid location, or any other impossible moves, the action is rejected.

The model used is set to `gemini-3.5-flash-lite` through the Google Gen AI SDK (`google-genai`). All of the model's outputs are printed to the terminal so users can see its reasoning.


## Gameplay
You play the rebels. The Overseer plays the robots.

- **You lose** when every rebel Headquarters and Outpost has been destroyed.
- **You win** when every robot Datacenter has been destroyed.

### The map
A 20×20 grid split into 25 sectors of 4×4 cells, named with the NATO alphabet (`Alpha`…`Yankee`). A cell is identified by its sector and index, for example `Alpha01` or `Kilo16`. Each run randomly places your **Headquarters** and **10 Datacenters** in 11 different sectors. Each Datacenter starts with 50 robots, 500 in total.

### Economy and units
- You start with **100 manpower**.
- A Headquarters (or Outpost) is in one of two modes, which you toggle with `T`:
  - **Mobilizing:** +20 manpower every 10 s.
  - **Training:** converts 10 manpower into 10 rebels every 5 s.
- **Outposts** are secondary bases. They need at least 30 rebels in the cell, only one structure is allowed per sector, and they take 60 s to build. Construction speed scales with the number of rebels present, and any battle in the cell cancels it.
- Buildings have 1000 durability (Outposts: 200). Repairing a rebel building costs 20 manpower and restores 150 durability.

### Combat
Combat is automatic. When rebels and robots share a cell, every 0.2 s each unit has a 10% chance to kill one enemy unit. A building with only enemy units on its cell loses durability at the same per-unit rate. Groups of units can be merged by moving them into the same cell. Units take 1.5 s to cross each cell, and large groups travel in batches of 500.

### Controls
| Input | Action |
|---|---|
| Left click | Select a cell and show its info popup |
| Left drag | Pan the map |
| Mouse wheel | Zoom |
| Right click | Open the radial command menu on a cell |
| `T` | Toggle Mobilizing / Training (Headquarters and Outposts) |
| `M` | Move all rebels from this cell: pick a destination, then click the confirmation marker |
| `O` | Build an Outpost |
| `R` | Repair the building |
| Right click or `Esc` | Cancel a move in progress |
| `Esc` | Return to the menu during play |

Menu navigation: `W`/`S` or the arrow keys to move, `Enter` or `Space` to select, `Q` or `Esc` to quit.

The Overseer first acts **90 seconds** into a match, then every **15 seconds**.


## Getting started

### Requirements 
- Python 3.13 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Setup
```bash
git clone <this repository>
cd Data-Crash

make install
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

The game needs an API key to start a match: without one, the Gen AI client raises an error when you click **Start Game**.

### Run
```bash
make run
```

### Other commands
| Command | Description |
|---|---|
| `make lint` | Run `flake8` and `mypy` |
| `make clean` | Remove the virtual environment and caches |

## Project structure
```
src/
├── __main__.py              # entry point
├── game/
│   ├── Game.py              # window, main loop, state switching
│   ├── Commands.py          # radial command menu
│   ├── states/              # Menu, Playing (core game logic), End
│   ├── world/               # Map generation, Cell and combat rules
│   ├── buildings/           # Headquarters, Outpost, Datacenter
│   └── entities/            # Commander (rebel orders, pathfinding), Camera
├── overseer/
│   ├── Overseer.py          # background-thread LLM client and prompts
│   └── overseer_tools.py    # function declarations exposed to the model
└── display/                 # pygame rendering (map, popup, text)
```

## Notes
It is worth keeping in mind that I set up this project with minimal research into LLM agents and function calling, and therefore, it doesn't really follow the industry standard for a project like this. The tool calling system could have been improved by using an MCP server, the AI's previous plans could have been carried over as context for its current turn, and its actions could have been more dynamic, instead of triggering on a timer.

Despite this, I think it's a fun project, and it shows that an LLM can actually work quite effectively within a video game without causing lag or delays in the gameplay.

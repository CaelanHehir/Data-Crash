# Data Crash

A real-time strategy game featuring an **LLM that plays inside a live game environment**.

You command a human rebellion. Your opponent is the **Overseer**, an AI overlord whose decisions come from a large language model. Every few seconds the game serializes its own state (unit positions, building health, ongoing battles, recent events) into a prompt, sends it to the LLM, and executes whichever action the model chooses. The Overseer reacts to what you actually do rather than following a scripted routine.

This game was built as a proof of concept. The game loop, rules and LLM integration work end to end, but the game is not balanced or polished.

## How the LLM integration works

The game never blocks on the model. The Overseer runs in a background thread and hands its result back to the game loop through a queue.

1. **State serialization.** `PlayingState.build_context()` writes a text summary of the map: totals for each side, every datacenter, enemy headquarters and outposts (with durability and mode), outposts under construction, contested cells, and every cell holding units. Cells are referred to by name, such as `Alpha01`.
2. **Event log.** Notable events are logged with timestamps (battles starting and ending, buildings attacked or destroyed, units arriving, outposts started or finished). Each turn the Overseer only sees the entries since its previous turn.
3. **Reason, then act.** The first request asks the model to analyse the situation and write a plan, with tools disabled. The second request forces a function call.
4. **Tools.** The model's only way to affect the game is through two declared functions (`src/overseer/overseer_tools.py`):

   | Tool | Arguments | Effect |
   |---|---|---|
   | `build_robots` | `spawn_point` | Adds 100 robots at the named datacenter |
   | `rally_robots` | `source`, `target` | Sends every robot at the source cell to the target cell along the shortest path |

5. **Validation.** Model output is treated as untrusted. Cell names are normalised and looked up, and an action is rejected (with a message in the terminal) if the cell doesn't exist, the spawn point isn't a datacenter, no path exists, or there are no robots to move. Function-call arguments are never executed directly.

The model is set to `gemini-3.5-flash-lite` through the Google Gen AI SDK (`google-genai`).

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

make install     # creates .venv and installs dependencies with uv
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

`GOOGLE_API_KEY` also works, and a variable already set in your shell takes precedence over `.env`. The game needs a key to start a match: without one, the Gen AI client raises an error when you click **Start Game**.

### Run

```bash
make run         # same as: uv run python -m src
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

## Known limitations

- **No memory between turns.** Each turn the model gets a fresh snapshot and the log entries since its last turn. Its earlier plans are not carried over.
- **Robot production is free.** The prompt tells the model that building costs resources, but the game doesn't enforce a cost, so the only limit is one action per turn.
- **One action per turn, every 15 s.** The Overseer is deliberately slow and coarse. It moves entire stacks at once and can't split groups.
- **Silent failure on API errors.** If the strategy call fails, the action call is sent an empty prompt and the error is only printed to the terminal. The match continues without the Overseer acting.

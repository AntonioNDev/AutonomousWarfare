# HideSeek

HideSeek is a Python/Pygame autonomous-agent simulation set in a procedurally generated world. Multiple teams of units explore the map, manage survival needs, navigate terrain, and respond to nearby enemies through simple decision-making behaviors.

## How it works

The map is generated as a tile-based environment using Perlin noise for two independent values:

- **Elevation** determines water, shores, grasslands, highlands, and mountains.
- **Moisture** determines forest and grassland biomes.

Additional processing assigns water depth, removes small lakes, places mountains, and adds obstacles such as trees and rocks.

Agents navigate the world using the **A\*** pathfinding algorithm. Each agent evaluates its surroundings and chooses actions such as exploring, fleeing, attacking, drinking, eating, resting, or trading. Unit behavior and statistics are configured in `game.yaml`.

## Run the project

Install the dependencies:

```bash
pip install pygame pyyaml noise
```

Then start the simulation:

```bash
python main.py
```

## Controls

- `D` — Toggle debug mode
- `P` — Pause or resume
- `R` — Generate a new world
- Mouse wheel — Zoom
- Left-click and drag — Move the camera

## Main files

- `main.py` — Simulation loop, rendering, input, and agent spawning
- `agents.py` — Agent behavior, needs, combat, and inventory
- `map_generator.py` — Procedural map generation and terrain management
- `pathFinding.py` — A\* pathfinding implementation
- `game.yaml` — Unit and simulation configuration

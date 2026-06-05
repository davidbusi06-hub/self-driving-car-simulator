# Self-Driving Car Simulator

A Python/Pygame navigation simulator with a car that moves through randomized obstacles and checkpoints in a 2D environment.

## Features
- Manual and autonomous driving modes.
- Raycast-style sensor readings.
- Obstacle avoidance and checkpoint tracking.
- Randomized layouts for repeatable testing.

## Tech Stack
- Python
- Pygame

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install pygame
python3 car_sim_day7_final.py
```

## Controls
- Enter or S: Start the simulation.
- Space: Toggle manual / auto mode.
- Arrow keys: Manual driving.
- R: Restart with a new layout.
- Esc: Return to menu.
- Q: Quit.

## About
This project is a visual simulation for practicing control logic, collision handling, and sensor-based navigation. It is not a production self-driving system, but it demonstrates how a simple autonomous controller can react to obstacles and checkpoints.

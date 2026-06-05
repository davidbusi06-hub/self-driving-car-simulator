# Self-Driving Car Simulator

A Python/Pygame autonomous navigation simulator that models a car driving through a 2D obstacle field while aiming for sequential checkpoints.

## Features
- Manual and autonomous driving modes.
- Raycast-style distance sensors.
- Obstacle avoidance and simple steering logic.
- Randomized obstacle and checkpoint generation.
- HUD for mode, speed, heading, checkpoint progress, and sensor data.

## Tech Stack
- Python
- Pygame

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Controls
- Enter or S: Start simulation
- Space: Toggle manual/auto mode
- Arrow keys: Manual driving
- R: Restart with new layout
- Esc: Return to menu
- Q: Quit

## Architecture
- `Car` class handles movement, steering, collision checks, checkpoint tracking, and auto/manual behavior.
- `gen_obstacles()` and `gen_checkpoints()` create randomized test environments.
- `get_sensor_data()` casts multiple rays in a front-facing arc to estimate obstacle distance.
- `update_auto()` uses front and side sensor distances to set speed and steering decisions.

## Interview-ready explanation
This project is a navigation simulator, not a real autonomous driving stack. The goal was to practice environment generation, collision avoidance, sensor-style raycasting, steering logic, and debugging behavior in a visual simulation.

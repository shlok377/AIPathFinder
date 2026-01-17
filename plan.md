# Warehouse Pathfinding Optimizer - Project Plan

## 1. Project Overview
**Problem Statement:** Design an algorithm for multiple robots to navigate a warehouse environment efficiently without colliding or causing deadlocks.
**Goal:** Build a 3D simulation using Python and Ursina that demonstrates a Multi-Agent Pathfinding (MAPF) solution.

## 2. Technical Architecture

### Tech Stack
- **Language:** Python 3.x
- **Visualization/Simulation:** Ursina Engine (3D rendering)
- **Data Structures:** Grid-based graphs (Arrays/Lists or NumPy)
- **Algorithm:** Cooperative A* (CA*) or Prioritized Planning with A*

### Core Components
1.  **The Environment (Warehouse Grid):**
    - A 2D grid logic mapped to 3D space.
    - **Nodes:** Walkable paths.
    - **Obstacles:** Shelves/Racks, Charging Stations, Walls.
2.  **The Agent (Robot):**
    - Properties: ID, Current Position (x, y), Target Position (x, y), Current Path (list of steps).
3.  **The Brain (Pathfinding Manager):**
    - Centralized controller that assigns paths to prevent collisions *before* movement starts.

## 3. Algorithm Strategy (The "Hard" Part)

Since the team is new, we will start with **Prioritized Planning (Decoupled Approach)**, which is easier to implement than fully optimal solvers like CBS (Conflict-Based Search), but effective enough for hackathons.

### Step-by-Step Logic:
1.  **Assign Priorities:** Give each robot a priority ID (e.g., Robot 1 moves first, then Robot 2).
2.  **Space-Time A*:**
    - Standard A* finds a path in X, Y coordinates.
    - **Space-Time A*** finds a path in X, Y, *Time* coordinates.
    - When planning for Robot 2, mark the grid cells occupied by Robot 1 at specific time steps as "obstacles."
    - *Example:* If Robot 1 is at `(5, 5)` at `t=3`, Robot 2 cannot be at `(5, 5)` at `t=3`.
3.  **Deadlock Prevention:**
    - If a robot cannot find a path because higher-priority robots block it, it can wait (add "wait" moves to its path) until the path clears.

## 4. Feature Checklist (Aligned with Judging Criteria)

### A. Efficiency (Speed & Optimality)
- [ ] **Heuristic Function:** Use Manhattan Distance for the grid.
- [ ] **Path Smoothing:** Don't just move square-by-square; visualize smooth transitions.
- [ ] **Task Allocation:** Simple logic to assign the nearest robot to a pending task.

### B. Collision Avoidance (Safety)
- [ ] **Node Reservation:** Ensure no two robots occupy the same node at the same time tick.
- [ ] **Edge Reservation:** Prevent swapping (Robot A moves 1->2, Robot B moves 2->1 simultaneously).

### C. Scalability (Volume)
- [ ] **Configurable Grid:** Ability to load small (10x10) or large (50x50) maps.
- [ ] **Robot Count:** UI slider or config to spawn 2, 5, or 10 robots.

## 5. Implementation Roadmap

### Phase 1: The Skeleton (Day 1 - Morning)
- Set up Python & Ursina.
- Render a static 3D grid (floor tiles).
- Place static cubes representing obstacles (shelves).
- Create a simple camera controller.

### Phase 2: Single Agent Pathfinding (Day 1 - Afternoon)
- Implement basic A* algorithm in a separate `algorithms.py` file.
- Spawn 1 robot (cube).
- Click a tile -> Robot calculates A* path -> Robot moves along path visually.

### Phase 3: Multi-Agent Logic (Day 1 - Night / Day 2)
- Introduce the "Time" dimension to A*.
- Spawn 2 robots with crossing paths.
- Implement the "Reservation Table" (tracks which `(x, y)` is busy at time `t`).
- Make Robot 2 wait if Robot 1 is crossing.

### Phase 4: Polish & UI (Day 2 - Final Hours)
- Replace cubes with nicer 3D models (optional).
- Add UI overlay: "Tasks Completed", "Collisions Avoided: OK".
- Add a "Randomize" button to generate new tasks.

## 6. Required Libraries
```bash
pip install -r requirements.txt
```
(dependencies are listed in requirements.txt)

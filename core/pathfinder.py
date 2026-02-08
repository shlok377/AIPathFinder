# core/pathfinder.py
import heapq

class PathFinder:
    def __init__(self, grid_manager):
        self.gm = grid_manager

    def heuristic(self, a, b):
        # Manhattan distance
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def get_neighbors(self, pos, goal, avoid=None):
        neighbors = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            x, y = pos[0] + dx, pos[1] + dy
            # Skip if cell is in avoid list (unless it's the goal itself)
            if avoid and (x, y) in avoid and (x, y) != goal:
                continue
            if self.gm.is_walkable(x, y, goal, start_pos=pos):
                neighbors.append((x, y))
        return neighbors

    def find_path(self, start, goal, avoid=None):
        # start and goal are (x, y) grid coordinates
        if start == goal:
            return [goal]
            
        frontier = []
        heapq.heappush(frontier, (0, start))
        came_from = {start: None}
        cost_so_far = {start: 0}
        
        # Penalty for making a turn to favor straight lines
        TURN_PENALTY = 2.0

        while frontier:
            current = heapq.heappop(frontier)[1]

            if current == goal:
                break

            for next_node in self.get_neighbors(current, goal, avoid):
                # Calculate movement cost
                move_cost = 1
                
                # Check if this move is a turn
                if came_from[current] is not None:
                    prev_node = came_from[current]
                    # Current direction: current -> next_node
                    # Previous direction: prev_node -> current
                    if (next_node[0] - current[0] != current[0] - prev_node[0] or 
                        next_node[1] - current[1] != current[1] - prev_node[1]):
                        move_cost += TURN_PENALTY

                new_cost = cost_so_far[current] + move_cost
                
                if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                    cost_so_far[next_node] = new_cost
                    # Using a slight multiplier on heuristic can also help favor straight lines towards goal
                    priority = new_cost + self.heuristic(goal, next_node) * 1.1
                    heapq.heappush(frontier, (priority, next_node))
                    came_from[next_node] = current

        if goal not in came_from:
            return []

        # Reconstruct path
        path = []
        current = goal
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path
# core/pathfinder.py
import heapq
from core.config import AppConfig

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

    def find_path(self, start, goal, avoid=None, robot_positions=None, robot_id=None, start_time=None):
        # start and goal are (x, y) grid coordinates
        if start == goal:
            return [goal]
            
        # Estimate ~0.4s per cell (Cell distance 2 / Speed 5)
        TRAVEL_TIME_PER_CELL = 0.4 
        if hasattr(self.gm, 'scale_x'):
            TRAVEL_TIME_PER_CELL = self.gm.scale_x / 5.0 

        frontier = []
        # Frontier state: (priority, current_node, current_time, wait_count)
        heapq.heappush(frontier, (0, start, start_time if start_time is not None else 0, 0))
        came_from = { (start, 0): None } 
        cost_so_far = { (start, 0): 0 }
        
        # ADVANCED TUNING CONSTANTS
        TURN_PENALTY = 3.0
        CONGESTION_COST = 1.0    # Soft penalty for passing robots
        POLARITY_COST = 2.0      # Lane Bias
        WAIT_PENALTY = 1.1       # Cost of waiting 1 step (low to encourage waiting over detour)
        RESERVATION_PENALTY = 40.0 # Penalty for crossing a reserved cell
        MAX_CONSECUTIVE_WAITS = 12 # Max ~5s wait

        final_node = None
        while frontier:
            _, current, curr_t, wait_count = heapq.heappop(frontier)

            if current == goal:
                final_node = (current, wait_count)
                break

            # 1. Normal Neighbors (Moving)
            for next_node in self.get_neighbors(current, goal, avoid):
                # BASE COST
                move_cost = 5.0 # Use higher base to allow for fractional highway discounts
                
                # CITY TRAFFIC MODEL: Highway Discount
                is_highway = (next_node[1] in AppConfig.HIGHWAY_Z or next_node[0] in AppConfig.HIGHWAY_X)
                if is_highway:
                    move_cost *= AppConfig.HIGHWAY_COST_DISCOUNT

                arrival_t = curr_t + TRAVEL_TIME_PER_CELL
                
                # Check Reservation
                res_cost = 0
                if robot_id is not None and hasattr(self.gm, 'is_cell_reserved'):
                    if self.gm.is_cell_reserved(next_node[0], next_node[1], arrival_t, arrival_t + 1.0, robot_id):
                        res_cost = RESERVATION_PENALTY

                # Turn Penalty
                if came_from[(current, wait_count)] is not None:
                    prev_pos = came_from[(current, wait_count)][0]
                    if prev_pos != current: 
                        if (next_node[0] - current[0] != current[0] - prev_pos[0] or 
                            next_node[1] - current[1] != current[1] - prev_pos[1]):
                            move_cost += TURN_PENALTY

                # Congestion Awareness (Soft Avoidance)
                if robot_positions and next_node in robot_positions:
                    move_cost += CONGESTION_COST

                # Traffic Polarity
                if next_node[0] % 2 == 0: 
                    if next_node[1] < current[1]: move_cost += POLARITY_COST 
                else: 
                    if next_node[1] > current[1]: move_cost += POLARITY_COST 

                new_cost = cost_so_far[(current, wait_count)] + move_cost + res_cost
                state = (next_node, 0) 
                
                if state not in cost_so_far or new_cost < cost_so_far[state]:
                    cost_so_far[state] = new_cost
                    priority = new_cost + self.heuristic(goal, next_node) * 1.5 
                    heapq.heappush(frontier, (priority, next_node, arrival_t, 0))
                    came_from[state] = (current, wait_count)

            # 2. Wait Action (Staying Put)
            if wait_count < MAX_CONSECUTIVE_WAITS:
                new_cost = cost_so_far[(current, wait_count)] + WAIT_PENALTY
                arrival_t = curr_t + TRAVEL_TIME_PER_CELL
                state = (current, wait_count + 1)
                
                if state not in cost_so_far or new_cost < cost_so_far[state]:
                    cost_so_far[state] = new_cost
                    priority = new_cost + self.heuristic(goal, current) * 1.5
                    heapq.heappush(frontier, (priority, current, arrival_t, wait_count + 1))
                    came_from[state] = (current, wait_count)

        if final_node is None:
            return []

        # Reconstruct path
        path = []
        curr = final_node
        while curr is not None:
            path.append(curr[0])
            curr = came_from[curr]
        
        path.reverse()
        if path and path[0] == start: path.pop(0)
        return path

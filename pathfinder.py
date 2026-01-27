# core/pathfinder.py
import heapq

class PathFinder:
    def __init__(self, grid_manager):
        self.gm = grid_manager

    def find_path(self, start, goal):
        # Implementation of Feature 1: A* Algorithm
        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}
        
        while open_set:
            _, current = heapq.heappop(open_set)
            if current == goal: return self.reconstruct(came_from, current)

            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                neighbor = (current[0]+dx, current[1]+dy)
                if self.gm.is_walkable(*neighbor):
                    tentative_g = g_score[current] + 1
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f_score = tentative_g + abs(neighbor[0]-goal[0]) + abs(neighbor[1]-goal[1])
                        heapq.heappush(open_set, (f_score, neighbor))
        return None

    def reconstruct(self, came_from, current):
        path = []
        while current in came_from:
            path.append(current)
            current = came_from[current]
        return path[::-1]
# core/grid_manager.py
from . import config

class GridManager:
    def __init__(self):
        self.grid = self.load_grid()
        self.height = len(self.grid)
        self.width = len(self.grid[0]) if self.height > 0 else 0

    def load_grid(self):
        with open(config.LAYOUT_FILE, 'r') as f:
            return [list(line.strip()) for line in f.readlines() if line.strip()]

    def is_walkable(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x] != config.CHAR_OBSTACLE
        return False
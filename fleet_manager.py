# core/fleet_manager.py
from .grid_manager import GridManager
from .pathfinder import PathFinder
from . import config

class FleetManager:
    def __init__(self):
        self.gm = GridManager()
        self.pf = PathFinder(self.gm)
        self.trucks = self.gm.load_grid() # Simplification: search grid for 'T'
        self.chargers = [] # Find '#' in grid
        # Feature 3: Centralized charging tracking
        self.charger_occupancy = {}
# core/fleet_manager.py
from .grid_manager import GridManager
from .pathfinder import PathFinder
from . import config

class FleetManager:
    def __init__(self):
        self.gm = GridManager()
        self.pf = PathFinder(self.gm)
        # Feature 2 & 3: Identify specific locations from the layout [cite: 1]
        self.truck_starts = self.gm.get_element_positions(config.CHAR_ROBOT)
        self.chargers = self.gm.get_element_positions(config.CHAR_CHARGER)
        self.charger_states = {pos: "FREE" for pos in self.chargers} [cite: 3]

    def get_path_to_target(self, start_pos, target_pos):
        """Feature 1: Returns a list of grid coordinates [cite: 1]"""
        return self.pf.find_path(start_pos, target_pos)

    def find_nearest_charger_path(self, current_grid_pos):
        """Feature 3: Find closest available charger """
        best_path = None
        for charger in self.chargers:
            if self.charger_states[charger] == "FREE":
                path = self.pf.find_path(current_grid_pos, charger)
                if not best_path or (path and len(path) < len(best_path)):
                    best_path = path
        return best_path
    # core/fleet_manager.py
from . import config

class FleetManager:
    def __init__(self):
        self.gm = GridManager()
        self.pf = PathFinder(self.gm)
        # Tracking states for Feature 13 logs 
        self.truck_data = {} 
        self._initialize_fleet()

    def _initialize_fleet(self):
        starts = self.gm.get_element_positions(config.CHAR_ROBOT)
        for i, pos in enumerate(starts):
            self.truck_data[i] = {
                "pos": pos,
                "battery": config.INITIAL_BATTERY,
                "state": "IDLE" # IDLE, DELIVERING, CHARGING 
            }

    def find_best_truck_for_package(self, package_pos, delivery_pos):
        """Feature 5: Nearest truck to PACKAGE rather than delivery location """
        best_truck_id = -1
        min_dist = float('inf')

        for t_id, data in self.truck_data.items():
            # Feature 6: Check if battery is sufficient for the whole trip 
            dist_to_pkg = len(self.pf.find_path(data["pos"], package_pos) or [])
            dist_to_delivery = len(self.pf.find_path(package_pos, delivery_pos) or [])
            
            # Simplified return-to-charger estimate (to the nearest charger)
            total_estimated_dist = dist_to_pkg + dist_to_delivery
            required_battery = total_estimated_dist * config.BATTERY_DRAIN_PER_TILE

            if data["battery"] > required_battery and dist_to_pkg < min_dist:
                min_dist = dist_to_pkg
                best_truck_id = t_id

        if best_truck_id != -1:
            print(f"[Log] Assigned Truck {best_truck_id} to package at {package_pos}. "
                  f"Battery: {self.truck_data[best_truck_id]['battery']}%") [cite: 4]
        return best_truck_id
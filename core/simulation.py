from ursina import Entity, time, color, mouse, destroy, distance
import random
from core.config import AppConfig
from core.pathfinder import PathFinder
from core.telemetry import cloud_logger
from entities.cargo import PickupPoint, DropPoint

class TaskSystem(Entity):
    def __init__(self, robots, docks, **kwargs):
        super().__init__(**kwargs)
        self.robots = robots
        self.docks = docks
        for r in self.robots:
            r.manager = self
            
        self.pending_pickup = None
        self.active_tasks = []
        self.unassigned_tasks = []
        self.scale_x = AppConfig.CELL_SCALE[0]
        self.scale_z = AppConfig.CELL_SCALE[2]
        
        self.grid_data = self.load_grid_data()
        self.pathfinder = PathFinder(self)
        
        self.available_chars = [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in ['t', 'x']]
        self.log_timer = 0

        # Auto-Spawner State
        self.spawner_active = False
        self.spawner_timer = 0
        self.spawner_phase = 'IDLE' # IDLE, WAITING_DROP

    def update(self):
        # GCP Telemetry Sync
        cloud_logger.update_fleet_metrics(self.robots, self.docks)
        
        # Auto-Spawner Logic
        if self.spawner_active:
            self.handle_auto_spawner()

        # Continuously check for available tasks to handle queued work immediately
        self.assign_tasks()

    def handle_auto_spawner(self):
        # 1. Check Capacity Limit
        empty_tiles = []
        occupied_tiles = 0
        for z in range(self.height):
            for x in range(self.width):
                char = self.grid_data[z][x]
                if z >= AppConfig.SPAWNER_RESTRICTED_ROWS:
                    if char == '.':
                        empty_tiles.append((x, z))
                    elif char.isalpha():
                        occupied_tiles += 1

        total_valid_tiles = len(empty_tiles) + occupied_tiles
        fill_ratio = occupied_tiles / total_valid_tiles if total_valid_tiles > 0 else 0
        
        # Periodic Debug Log (Every 2 seconds while active)
        if time.time() % 2 < 0.05:
            print(f"[DEBUG] Spawner: Phase={self.spawner_phase}, Tiles={occupied_tiles}/{total_valid_tiles}, Fill={round(fill_ratio*100)}%, Pool={len(self.available_chars)}")

        if occupied_tiles >= total_valid_tiles * AppConfig.SPAWNER_FILL_PERCENT:
            print(f"\033[93m[SPAWNER]\033[0m Target fill ({int(AppConfig.SPAWNER_FILL_PERCENT*100)}%) reached. Stopping.")
            self.spawner_active = False
            return

        if not self.available_chars and self.spawner_phase == 'IDLE':
            print(f"\033[93m[SPAWNER]\033[0m Character pool exhausted. Stopping.")
            self.spawner_active = False
            return

        # 2. Phase Management
        self.spawner_timer -= time.dt
        if self.spawner_timer <= 0:
            if self.spawner_phase == 'IDLE':
                if not empty_tiles:
                    self.spawner_active = False
                    return
                
                gx, gz = random.choice(empty_tiles)
                pos = (gx * self.scale_x, 0, gz * self.scale_z)
                
                p_char = self.available_chars.pop(0)
                if self.update_file_grid(pos, p_char):
                    task_color = color.random_color()
                    self.pending_pickup = PickupPoint(pos, task_color, p_char)
                    self.pending_pickup.task_char = p_char
                    
                    self.spawner_phase = 'WAITING_DROP'
                    self.spawner_timer = AppConfig.SPAWNER_PICKUP_DELAY
                    print(f"\033[94m[SPAWNER]\033[0m Spawned Pickup '{p_char}'")

            elif self.spawner_phase == 'WAITING_DROP':
                # Refresh empty tiles
                current_empty = []
                for z in range(self.height):
                    for x in range(self.width):
                        if z >= AppConfig.SPAWNER_RESTRICTED_ROWS and self.grid_data[z][x] == '.':
                            current_empty.append((x, z))
                
                if not current_empty:
                    self.spawner_active = False
                    return

                gx, gz = random.choice(current_empty)
                pos = (gx * self.scale_x, 0, gz * self.scale_z)
                
                d_char = self.pending_pickup.task_char.upper()
                if self.update_file_grid(pos, d_char):
                    drop = DropPoint(pos, self.pending_pickup.color, d_char)
                    task_info = {
                        'pickup_char': self.pending_pickup.task_char,
                        'pickup_pos': self.pending_pickup.position,
                        'pickup_ent': self.pending_pickup,
                        'drop_char': d_char,
                        'drop_pos': drop.position,
                        'drop_ent': drop,
                        'color': self.pending_pickup.color
                    }
                    self.unassigned_tasks.append(task_info)
                    self.pending_pickup = None
                    
                    self.spawner_phase = 'IDLE'
                    self.spawner_timer = AppConfig.SPAWNER_PAIR_DELAY
                    print(f"\033[94m[SPAWNER]\033[0m Spawned Drop-off '{d_char}'")

    @property
    def width(self): return len(self.grid_data[0]) if self.grid_data else 0
    @property
    def height(self): return len(self.grid_data)
    
    def is_walkable(self, x, y, goal=None, start_pos=None):
        if 0 <= x < self.width and 0 <= y < self.height:
            char = self.grid_data[y][x]
            if char == AppConfig.OBSTACLE_CHAR:
                return False
            
            # Treat docks as obstacles ALWAYS
            if char == AppConfig.DOCK_CHAR:
                return False
            
            # Parking lane restriction (y < 2)
            if y < 2:
                # Allow if goal is in lane (parking spot at Z=1)
                if goal and goal[1] < 2:
                    return True
                # Allow if already in lane (to move around or leave)
                if start_pos and start_pos[1] < 2:
                    return True
                # Otherwise, don't enter the lane
                return False
            return True
        return False

    def load_grid_data(self):
        try:
            with open(AppConfig.LAYOUT_FILE, 'r') as f:
                return [list(line.strip()) for line in f.readlines() if line.strip()]
        except:
            return []

    def save_grid_to_file(self):
        with open(AppConfig.LAYOUT_FILE, 'w') as f:
            for row in self.grid_data:
                f.write("".join(row) + "\n")

    def update_file_grid(self, world_pos, char):
        grid_x = int(round(world_pos[0] / self.scale_x))
        grid_z = int(round(world_pos[2] / self.scale_z))
        if 0 <= grid_z < len(self.grid_data) and 0 <= grid_x < len(self.grid_data[0]):
            self.grid_data[grid_z][grid_x] = char
            self.save_grid_to_file()
            return True
        return False

    def input(self, key):
        if key == 'r':
            cloud_logger.generate_final_report()

        if key == AppConfig.SPAWNER_KEY:
            self.spawner_active = not self.spawner_active
            status = "STARTED" if self.spawner_active else "STOPPED"
            print(f"\033[95m[CONTROL]\033[0m Auto-Spawner {status}")
            if self.spawner_active:
                self.spawner_phase = 'IDLE'
                self.spawner_timer = 0

        if key == 'left mouse down' and mouse.hovered_entity:
            if mouse.hovered_entity.name == 'warehouse_floor':
                snap_x = round(mouse.world_point.x / self.scale_x) * self.scale_x
                snap_z = round(mouse.world_point.z / self.scale_z) * self.scale_z
                pos = (snap_x, 0, snap_z)

                if not self.available_chars and not self.pending_pickup:
                    print("Maximum concurrent tasks (24) reached!")
                    return

                if not self.pending_pickup:
                    p_char = self.available_chars.pop(0)
                    if self.update_file_grid(pos, p_char):
                        task_color = color.random_color()
                        self.pending_pickup = PickupPoint(pos, task_color, p_char)
                        self.pending_pickup.task_char = p_char
                        print(f"PICKUP '{p_char}' added at {pos}")
                else:
                    d_char = self.pending_pickup.task_char.upper()
                    if self.update_file_grid(pos, d_char):
                        drop = DropPoint(pos, self.pending_pickup.color, d_char)
                        task_info = {
                            'pickup_char': self.pending_pickup.task_char,
                            'pickup_pos': self.pending_pickup.position,
                            'pickup_ent': self.pending_pickup,
                            'drop_char': d_char,
                            'drop_pos': drop.position,
                            'drop_ent': drop,
                            'color': self.pending_pickup.color
                        }
                        self.unassigned_tasks.append(task_info)
                        self.assign_tasks()
                        self.pending_pickup = None

    def complete_task(self, task):
        # ANOMALY DETECTION: Check if task took too long
        actual_duration = time.time() - task.get('start_time', time.time())
        est = task.get('est_duration', 999)
        if actual_duration > est * 2:
            grid_pos = (int(round(task['drop_pos'][0] / self.scale_x)), 
                        int(round(task['drop_pos'][2] / self.scale_z)))
            cloud_logger.publish_event("FLEET", "ANOMALY", {"location": grid_pos, "delay": actual_duration})

        # Find the robot that had this task to destroy its cargo visual
        for r in self.robots:
            if r.current_task == task and r.cargo:
                destroy(r.cargo, delay=0.7)
                r.cargo = None
                break
                
        if 'pickup_ent' in task: destroy(task['pickup_ent'])
        if 'drop_ent' in task: destroy(task['drop_ent'])
        px, pz = int(round(task['pickup_pos'][0] / self.scale_x)), int(round(task['pickup_pos'][2] / self.scale_z))
        dx, dz = int(round(task['drop_pos'][0] / self.scale_x)), int(round(task['drop_pos'][2] / self.scale_z))
        if 0 <= pz < len(self.grid_data) and 0 <= px < len(self.grid_data[0]): self.grid_data[pz][px] = '.'
        if 0 <= dz < len(self.grid_data) and 0 <= dx < len(self.grid_data[0]): self.grid_data[dz][dx] = '.'
        self.save_grid_to_file()
        if task in self.active_tasks: self.active_tasks.remove(task)
        
        # Log to GCP Telemetry
        cloud_logger.publish_event("FLEET", "TASK_COMPLETE", {"task_id": task['pickup_char'], "task_id": task['pickup_char']})

        # Return character to the pool for reuse
        self.available_chars.append(task['pickup_char'])
        self.available_chars.sort()

    def assign_tasks(self):
        # Assign available tasks to robots using predictive battery feasibility
        for task in list(self.unassigned_tasks):
            pickup_grid = (int(round(task['pickup_pos'][0] / self.scale_x)), 
                           int(round(task['pickup_pos'][2] / self.scale_z)))
            drop_grid = (int(round(task['drop_pos'][0] / self.scale_x)), 
                         int(round(task['drop_pos'][2] / self.scale_z)))
            
            best_robot = None
            min_dist = float('inf')
            
            for robot in self.robots:
                if robot.state not in ['IDLE', 'RETURNING']:
                    continue
                
                # Check battery
                if robot.battery < AppConfig.BATTERY_LOW_THRESHOLD or robot.is_charging_session:
                    continue
                
                robot_grid = (int(round(robot.x / self.scale_x)), int(round(robot.z / self.scale_z)))
                
                # PREDICTIVE FEASIBILITY: robot -> pickup -> drop -> nearest dock
                path_to_pickup = self.pathfinder.find_path(robot_grid, pickup_grid)
                if not path_to_pickup: continue
                
                path_to_drop = self.pathfinder.find_path(pickup_grid, drop_grid)
                if not path_to_drop: continue
                
                # Find nearest dock from drop-off to ensure return is possible
                # Pass the robot to ensure its current dock is considered potentially available
                nearest_dock = self.get_nearest_unoccupied_dock(task['drop_pos'], requesting_robot=robot)
                if not nearest_dock: continue
                
                path_to_dock = self.pathfinder.find_path(drop_grid, nearest_dock)
                
                total_trip_dist = len(path_to_pickup) + len(path_to_drop) + len(path_to_dock)
                
                # Estimated battery cost (1% per grid cell move is a safe estimate)
                est_cost = total_trip_dist * (AppConfig.BATTERY_DRAIN_MOVE / AppConfig.ROBOT_MOVE_SPEED) * 2.0 # with safety buffer
                
                if robot.battery > est_cost:
                    dist = len(path_to_pickup)
                    if dist < min_dist:
                        min_dist = dist
                        best_robot = robot
            
            if best_robot:
                self.unassigned_tasks.remove(task)
                self.active_tasks.append(task)
                self.assign_task_to_robot(best_robot, task)

    def find_nearest_available_robot(self, task):
        pickup_grid = (int(round(task['pickup_pos'][0] / self.scale_x)), 
                       int(round(task['pickup_pos'][2] / self.scale_z)))
        best_robot = None
        min_dist = float('inf')
        
        # Consider IDLE robots or robots that are RETURNING (can be redirected)
        for robot in self.robots:
            # CHECK BATTERY: Refuse if below low threshold
            if robot.battery < AppConfig.BATTERY_LOW_THRESHOLD or robot.is_charging_session:
                continue

            if robot.state in ['IDLE', 'RETURNING']:
                robot_grid = (int(round(robot.x / self.scale_x)), int(round(robot.z / self.scale_z)))
                path = self.pathfinder.find_path(robot_grid, pickup_grid)
                if path and len(path) < min_dist:
                    min_dist = len(path)
                    best_robot = robot
                    
        return best_robot

    def assign_task_to_robot(self, robot, task):
        print(f"ASSIGNED Task {task['pickup_char']} to Robot {robot.robot_id}")
        cloud_logger.publish_event(robot.robot_id, "TASK_ASSIGN", {"task_id": task['pickup_char']})
        
        # Start timer for Anomaly Detection
        task['start_time'] = time.time()
        # Estimate: distance / speed * buffer
        task['est_duration'] = (len(robot.current_path) + 10) / AppConfig.ROBOT_MOVE_SPEED * 2.5
        
        robot.state = 'TO_PICKUP'
        robot.current_task = task
        robot.current_path = self.pathfinder.find_path(
            (int(round(robot.x / self.scale_x)), int(round(robot.z / self.scale_z))),
            (int(round(task['pickup_pos'][0] / self.scale_x)), int(round(task['pickup_pos'][2] / self.scale_z)))
        )

    def get_nearest_unoccupied_dock(self, source, requesting_robot=None):
        best_dock = None
        min_dist = float('inf')
        
        # Robust handling of source (can be Robot or Vec3)
        pos = source.position if hasattr(source, 'position') else source
        
        # If requesting_robot is not explicitly provided, check if source is a Robot
        if requesting_robot is None and hasattr(source, 'robot_id'):
            requesting_robot = source
            
        # Grid positions of spots already claimed or occupied
        occupied_target_spots = []
        for r in self.robots:
            if requesting_robot and r == requesting_robot: continue # Don't block yourself
            
            # Claimed by someone returning
            if r.state == 'RETURNING' and r.home_pos:
                if requesting_robot is None:
                    occupied_target_spots.append(r.home_pos)
                else:
                    # Stability Tie-breaker
                    if r.priority > requesting_robot.priority or (r.priority == requesting_robot.priority and r.robot_id < requesting_robot.robot_id):
                        occupied_target_spots.append(r.home_pos)
            
            # Occupied by someone already there (in the parking lane)
            elif r.state in ['IDLE', 'WAITING_PICKUP', 'WAITING_DROP']:
                r_grid = (int(round(r.x / self.scale_x)), int(round(r.z / self.scale_z)))
                if r_grid[1] == AppConfig.PARKING_LANE_Z:
                    occupied_target_spots.append(r_grid)

        # Stickiness: If we are a robot and our current spot is still valid, keep it
        if requesting_robot and requesting_robot.home_pos and requesting_robot.home_pos not in occupied_target_spots:
            if requesting_robot.home_pos[1] == AppConfig.PARKING_LANE_Z:
                return requesting_robot.home_pos

        for dock in self.docks:
            # Parking spot is directly in front of the dock
            parking_grid = (int(round(dock.x / self.scale_x)), AppConfig.PARKING_LANE_Z)
            
            if parking_grid not in occupied_target_spots:
                dist = distance(pos, dock.position)
                if dist < min_dist:
                    min_dist = dist
                    best_dock = parking_grid
                    
        return best_dock

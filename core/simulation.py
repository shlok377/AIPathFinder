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
        
        # DYNAMIC HIGHWAY CALCULATION
        self.flying_highways = self._calculate_flying_highways()
        self.normal_highways = self._calculate_normal_highways()
        
        # Path Reservations: (x, y) -> list of {'start': t, 'end': t, 'robot_id': id}
        self.reservations = {}
        
        self.available_chars = [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in ['t', 'x']]
        self.log_timer = 0

        # Auto-Spawner State
        self.spawner_active = False
        self.spawner_timer = 0
        self.spawner_phase = 'IDLE' 

    def _calculate_flying_highways(self):
        # Extreme Left (0,1), Extreme Right (W-1, W-2), Extreme Top (H-1, H-2)
        h = []
        # Extreme Left (2 blocks wide)
        for x in [0, 1]:
            for y in range(self.height): h.append((x, y))
        # Extreme Right (2 blocks wide)
        for x in [self.width-1, self.width-2]:
            for y in range(self.height): h.append((x, y))
        # Extreme End Row (2 blocks wide, opposite to chargers at y=0)
        for y in [self.height-1, self.height-2]:
            for x in range(self.width): h.append((x, y))
        return list(set(h))

    def _calculate_normal_highways(self):
        # Absolute middle column(s) - 2 blocks wide
        h = []
        mid = self.width // 2
        if self.width % 2 != 0:
            cols = [mid, mid + 1]
        else:
            cols = [mid - 1, mid]
        
        for x in cols:
            for y in range(self.height): h.append((x, y))
            
        # Also include joints between shelves (optional but requested "the other joints between shelves should be used")
        # For now, let's focus on the main highways.
        return h

    def is_highway(self, x, y):
        return (x, y) in self.flying_highways or (x, y) in self.normal_highways

    def is_flying_highway(self, x, y):
        return (x, y) in self.flying_highways

    def update(self):
        cloud_logger.update_fleet_metrics(self)
        if self.spawner_active:
            self.handle_auto_spawner()
        self.assign_tasks()

    def handle_auto_spawner(self):
        empty_tiles = []
        occupied_tiles = 0
        for z in range(self.height):
            for x in range(self.width):
                char = self.grid_data[z][x]
                if z >= AppConfig.SPAWNER_RESTRICTED_ROWS:
                    # BLOCK HIGHWAY SPAWNING
                    if self.is_highway(x, z):
                        continue
                    if char == '.':
                        empty_tiles.append((x, z))
                    elif char.isalpha():
                        occupied_tiles += 1

        total_valid_tiles = len(empty_tiles) + occupied_tiles
        if occupied_tiles >= total_valid_tiles * AppConfig.SPAWNER_FILL_PERCENT:
            self.spawner_active = False
            return
        if not self.available_chars and self.spawner_phase == 'IDLE':
            self.spawner_active = False
            return

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
            elif self.spawner_phase == 'WAITING_DROP':
                current_empty = []
                for z in range(self.height):
                    for x in range(self.width):
                        if z >= AppConfig.SPAWNER_RESTRICTED_ROWS and self.grid_data[z][x] == '.' and not self.is_highway(x, z):
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

    @property
    def width(self): return len(self.grid_data[0]) if self.grid_data else 0
    @property
    def height(self): return len(self.grid_data)
    
    def is_walkable(self, x, y, goal=None, start_pos=None):
        if 0 <= x < self.width and 0 <= y < self.height:
            char = self.grid_data[y][x]
            if char == AppConfig.OBSTACLE_CHAR: return False
            if char == AppConfig.DOCK_CHAR: return False
            if y < 2:
                if goal and goal[1] < 2: return True
                if start_pos and start_pos[1] < 2: return True
                return False
            return True
        return False

    def load_grid_data(self):
        try:
            with open(AppConfig.LAYOUT_FILE, 'r') as f:
                return [list(line.strip()) for line in f.readlines() if line.strip()]
        except: return []

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
        if key == 'r': cloud_logger.generate_final_report()
        if key == AppConfig.SPAWNER_KEY:
            self.spawner_active = not self.spawner_active
            if self.spawner_active:
                self.spawner_phase = 'IDLE'
                self.spawner_timer = 0
        if key == 'left mouse down' and mouse.hovered_entity:
            if mouse.hovered_entity.name == 'warehouse_floor':
                snap_x = round(mouse.world_point.x / self.scale_x) * self.scale_x
                snap_z = round(mouse.world_point.z / self.scale_z) * self.scale_z
                gx, gz = int(round(snap_x/self.scale_x)), int(round(snap_z/self.scale_z))
                if self.is_highway(gx, gz):
                    print("Cannot place tasks on Highways!")
                    return
                pos = (snap_x, 0, snap_z)
                if not self.available_chars and not self.pending_pickup: return
                if not self.pending_pickup:
                    p_char = self.available_chars.pop(0)
                    if self.update_file_grid(pos, p_char):
                        task_color = color.random_color()
                        self.pending_pickup = PickupPoint(pos, task_color, p_char)
                        self.pending_pickup.task_char = p_char
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
        actual_duration = time.time() - task.get('start_time', time.time())
        est = task.get('est_duration', 999)
        if actual_duration > est * 2:
            grid_pos = (int(round(task['drop_pos'][0] / self.scale_x)), int(round(task['drop_pos'][2] / self.scale_z)))
            cloud_logger.publish_event("FLEET", "ANOMALY", {"location": grid_pos, "delay": actual_duration})
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
        latency = time.time() - task.get('start_time', time.time())
        cloud_logger.publish_event("FLEET", "TASK_COMPLETE", {"task_id": task['pickup_char'], "latency": latency})
        self.available_chars.append(task['pickup_char'])
        self.available_chars.sort()

    def assign_tasks(self):
        robot_positions = [(int(round(r.x / self.scale_x)), int(round(r.z / self.scale_z))) for r in self.robots]
        for task in list(self.unassigned_tasks):
            pickup_grid = (int(round(task['pickup_pos'][0] / self.scale_x)), int(round(task['pickup_pos'][2] / self.scale_z)))
            drop_grid = (int(round(task['drop_pos'][0] / self.scale_x)), int(round(task['drop_pos'][2] / self.scale_z)))
            best_robot = None
            min_dist = float('inf')
            for robot in self.robots:
                if robot.state not in ['IDLE', 'RETURNING']: continue
                if robot.battery < AppConfig.BATTERY_LOW_THRESHOLD or robot.is_charging_session: continue
                robot_grid = (int(round(robot.x / self.scale_x)), int(round(robot.z / self.scale_z)))
                path_to_pickup = self.pathfinder.find_path(robot_grid, pickup_grid, robot_positions=robot_positions, robot_id=robot.robot_id, start_time=time.time())
                if not path_to_pickup: continue
                pickup_time = time.time() + len(path_to_pickup) * (self.scale_x / AppConfig.ROBOT_MOVE_SPEED)
                path_to_drop = self.pathfinder.find_path(pickup_grid, drop_grid, robot_positions=robot_positions, robot_id=robot.robot_id, start_time=pickup_time)
                if not path_to_drop: continue
                nearest_dock = self.get_nearest_unoccupied_dock(task['drop_pos'], requesting_robot=robot)
                if not nearest_dock: continue
                drop_time = pickup_time + len(path_to_drop) * (self.scale_x / AppConfig.ROBOT_MOVE_SPEED)
                path_to_dock = self.pathfinder.find_path(drop_grid, nearest_dock, robot_positions=robot_positions, robot_id=robot.robot_id, start_time=drop_time)
                total_trip_dist = len(path_to_pickup) + len(path_to_drop) + len(path_to_dock)
                est_cost = total_trip_dist * (AppConfig.BATTERY_DRAIN_MOVE / AppConfig.ROBOT_MOVE_SPEED) * 1.3 
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
        robot_positions = [(int(round(r.x / self.scale_x)), int(round(r.z / self.scale_z))) for r in self.robots]
        pickup_grid = (int(round(task['pickup_pos'][0] / self.scale_x)), int(round(task['pickup_pos'][2] / self.scale_z)))
        best_robot = None
        min_dist = float('inf')
        for robot in self.robots:
            if robot.battery < AppConfig.BATTERY_LOW_THRESHOLD or robot.is_charging_session: continue
            if robot.state in ['IDLE', 'RETURNING']:
                robot_grid = (int(round(robot.x / self.scale_x)), int(round(robot.z / self.scale_z)))
                path = self.pathfinder.find_path(robot_grid, pickup_grid, robot_positions=robot_positions, robot_id=robot.robot_id, start_time=time.time())
                if path and len(path) < min_dist:
                    min_dist = len(path)
                    best_robot = robot
        return best_robot

    def assign_task_to_robot(self, robot, task):
        robot_positions = []
        extra_avoid = []
        my_grid = (int(round(robot.x / self.scale_x)), int(round(robot.z / self.scale_z)))
        
        # HARMONY SECURITY: Pre-avoid neighbors before starting journey to pickup
        for other in self.robots:
            other_grid = (int(round(other.x / self.scale_x)), int(round(other.z / self.scale_z)))
            robot_positions.append(other_grid)
            if other == robot: continue
            
            grid_dist = abs(other_grid[0] - my_grid[0]) + abs(other_grid[1] - my_grid[1])
            if grid_dist <= 2:
                if other.state in ['WAITING_PICKUP', 'WAITING_DROP', 'IDLE']:
                    extra_avoid.append(other_grid)

        task['start_time'] = time.time()
        robot.state = 'TO_PICKUP'
        robot.current_task = task
        robot.current_path = self.pathfinder.find_path(
            my_grid,
            (int(round(task['pickup_pos'][0] / self.scale_x)), int(round(task['pickup_pos'][2] / self.scale_z))),
            avoid=extra_avoid,
            robot_positions=robot_positions, 
            robot_id=robot.robot_id, 
            start_time=time.time(), 
            is_discharged=robot.is_charging_session
        )
        if robot.current_path: self.reserve_path(robot.robot_id, robot.current_path, time.time())
        task['est_duration'] = (len(robot.current_path) + 10) / AppConfig.ROBOT_MOVE_SPEED * 2.5

    def get_nearest_unoccupied_dock(self, source, requesting_robot=None):
        best_dock = None
        min_dist = float('inf')
        pos = source.position if hasattr(source, 'position') else source
        if requesting_robot is None and hasattr(source, 'robot_id'): requesting_robot = source
        occupied_target_spots = []
        for r in self.robots:
            if requesting_robot and r == requesting_robot: continue
            if r.state == 'RETURNING' and r.home_pos:
                if requesting_robot is None: occupied_target_spots.append(r.home_pos)
                else:
                    if r.priority > requesting_robot.priority or (r.priority == requesting_robot.priority and r.robot_id < requesting_robot.robot_id):
                        occupied_target_spots.append(r.home_pos)
            elif r.state in ['IDLE', 'WAITING_PICKUP', 'WAITING_DROP']:
                r_grid = (int(round(r.x / self.scale_x)), int(round(r.z / self.scale_z)))
                if r_grid[1] == AppConfig.PARKING_LANE_Z: occupied_target_spots.append(r_grid)
        if requesting_robot and requesting_robot.home_pos and requesting_robot.home_pos not in occupied_target_spots:
            if requesting_robot.home_pos[1] == AppConfig.PARKING_LANE_Z: return requesting_robot.home_pos
        for dock in self.docks:
            parking_grid = (int(round(dock.x / self.scale_x)), AppConfig.PARKING_LANE_Z)
            if parking_grid not in occupied_target_spots:
                dist = distance(pos, dock.position)
                if dist < min_dist:
                    min_dist = dist
                    best_dock = parking_grid
        return best_dock

    def is_cell_reserved(self, x, y, t_start, t_end, robot_id):
        if (x, y) not in self.reservations: return False
        for res in self.reservations[(x, y)]:
            if res['robot_id'] == robot_id: continue
            if t_start < res['end'] and t_end > res['start']: return True
        return False

    def reserve_path(self, robot_id, path, start_time):
        self.clear_robot_reservations(robot_id)
        TRAVEL_TIME_PER_CELL = AppConfig.CELL_SCALE[0] / AppConfig.ROBOT_MOVE_SPEED
        curr_t = start_time
        for i, (x, y) in enumerate(path):
            t_start, t_end = curr_t, curr_t + TRAVEL_TIME_PER_CELL
            if (x, y) not in self.reservations: self.reservations[(x, y)] = []
            self.reservations[(x, y)].append({'start': t_start, 'end': t_end, 'robot_id': robot_id})
            curr_t = t_end

    def clear_robot_reservations(self, robot_id):
        for cell in self.reservations:
            self.reservations[cell] = [r for r in self.reservations[cell] if r['robot_id'] != robot_id]
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import os
import shutil
from core.pathfinder import PathFinder
from math import atan2, pi

# ==========================================
# CONFIGURATION SECTION
# ==========================================
class AppConfig:
    # Files
    LAYOUT_FILE = 'warehouse_layout.txt'
    DEFAULT_LAYOUT_FILE = 'default_layout.txt'
    ROBOT_MODEL_FILE = 'models/truckF.obj'
    ROBOT_TEXTURE_FILE = 'textures/truck.png'
    PACKAGE_MODEL_FILE = 'models/package.fbx'
    DOCK_MODEL_FILE = 'models/dock.glb'
    SHELF_MODEL_FILE = ['models/shelf1.fbx', 'models/shelf3.fbx']
    SHELF_TEXTURE_FILE = 'textures/shelf.png'
    FLOOR_TEXTURE_FILE = 'white_cube'
    
    # Grid Settings
    DEFAULT_WIDTH = 40
    DEFAULT_HEIGHT = 25
    CELL_SCALE = (2, 2, 2)
    
    # Floor Settings
    FLOOR_Y_POS = -1
    FLOOR_COLOR_A = color.white
    
    # Map Characters
    OBSTACLE_CHAR = 'X'
    DOCK_CHAR = '#'
    ROBOT_CHAR = 'T'
    PICKUP_CHAR = '$'
    DROP_CHAR = '@'
    
    # Obstacle Settings
    OBSTACLE_COLOR = color.white 
    OBSTACLE_Y_POS = 0 
    OBSTACLE_SCALE = (0.007, 0.007, 0.007) 
    
    # Robot Settings
    ROBOT_SCALE = (0.7, 0.7, 0.7) 
    ROBOT_COLOR = color.white 
    ROBOT_MOVE_SPEED = 5
    ROBOT_ROTATION_SPEED = 10
    ROBOT_WAIT_TIME = 3

    # Charging Dock Settings
    DOCK_COLOR = color.white
    DOCK_SCALE = (0.05, 0.05, 0.05) 
    
    # Optimization
    CULLING_DISTANCE = 40 

    # UI Settings
    HUD_SCALE = 0.8

    # Player Settings
    PLAYER_START_HEIGHT = 10
    PLAYER_START_OFFSET_Z = -20 
    MOUSE_VISIBLE = False

    # Top-Down Camera Settings
    TOP_DOWN_SPEED = 40
    TOP_DOWN_HEIGHT = 50
    TOP_DOWN_LIFT_SPEED = 30

    # Battery Settings
    BATTERY_DRAIN_MOVE = 1.0     # % per second while moving
    BATTERY_DRAIN_PASSIVE = 0.2  # % per second while idling
    BATTERY_CHARGE_RATE = 3.0    # % per second while charging
    BATTERY_LOG_INTERVAL = 2.0   # seconds between logs
    BATTERY_LOW_THRESHOLD = 25.0 # Refuse new tasks below this
    BATTERY_RECHARGE_TARGET = 80.0 # Stay at dock until this level
    BATTERY_CRITICAL_THRESHOLD = 13.0 # Forced return below this
    CHARGING_DISTANCE = 3.5      # Distance to dock to allow charging (increased for front-parking)
    HARD_COLLISION_DISTANCE = 1.4 # Minimum physical distance allowed between robot centers
    ROBOT_BRAKING_SENSITIVITY = 3.5 # Multiplier for distance to start slowing down
    ROBOT_MIN_SPEED_FACTOR = 0.02 # Minimum speed factor while slowing down (0.02 = 2%)

    # Dock/Parking Area Settings
    DOCK_ZONE_THRESHOLD = 3      # Distance (in grid cells) to consider as "docking area"
    PARKING_LANE_Z = 1           # Grid Z coordinate for parking spots (in front of docks at Z=0)

    # Staging Points (for idle high-battery trucks)
    STAGING_POINTS = [(6, 6), (18, 6), (6, 18), (18, 18)]

    # Cargo Settings
    CARGO_FLOOR_SCALE = (0.5, 0.5, 0.5)
    CARGO_TRUCK_SCALE = (1.5, 1.5, 1.5)
    CARGO_TRUCK_X_OFFSET = 0.0
    CARGO_TRUCK_Z_OFFSET = -0.5
    CARGO_TRUCK_Y_POS = 1.6
    CARGO_ANIM_DURATION = 1.3
    CARGO_ANIM_CURVE = curve.out_back # Bouncy Bezier-like curve

# ==========================================
# CLASSES
# ==========================================

class ChargingDock(Entity):
    def __init__(self, index, world_x, world_z, assigned_robot_id, pair_color, **kwargs):
        world_y = 1.05
        tinted_color = lerp(color.white, pair_color, 0.1)
        
        super().__init__(
            model=AppConfig.DOCK_MODEL_FILE, 
            position=(world_x, world_y, world_z),
            rotation_y=180,
            scale=AppConfig.DOCK_SCALE,
            color=tinted_color, 
            **kwargs
        )
        self.dock_id = index
        self.assigned_robot_id = assigned_robot_id
        self.name = f"Dock_{index}"
        
        if not self.model:
            self.model = 'cube'
            self.scale = (1.8, 0.1, 1.8)
            self.color = color.green

class Robot(Entity):
    def __init__(self, index, world_x, world_z, pair_color, home_pos, **kwargs):
        world_y = 0
        tinted_color = lerp(color.white, pair_color, 0.1)
        
        super().__init__(
            model=AppConfig.ROBOT_MODEL_FILE, 
            position=(world_x, world_y, world_z),
            rotation_y=0,
            scale=AppConfig.ROBOT_SCALE,
            color=tinted_color,
            texture=AppConfig.ROBOT_TEXTURE_FILE,
            **kwargs
        )
        self.robot_id = index
        self.name = f"Robot_{index}"
        self.home_pos = home_pos
        
        # This will hold the actual entity picked up from the floor
        self.cargo = None
        
        # State Management
        self.state = 'IDLE' # IDLE, TO_PICKUP, WAITING_PICKUP, TO_DROP, WAITING_DROP, RETURNING
        self.current_path = []
        self.alt_path = [] # PLAN B: Pre-calculated alternative route
        self.current_task = None
        self.wait_timer = 0
        self.battery = 100.0
        self.is_charging_session = False
        self.stuck_timer = 0
        self.backoff_timer = 0
        self.dock_wait_timer = 0
        self.zero_speed_timer = 0
        self.deadlock_zone = []
        self.braking_timer = 0
        self.waiting_timer = 0
        self.total_wait_timer = 0
        self.last_pos = self.position

        if not self.model:
            self.model = 'cube'
            self.color = color.blue
            self.scale = (1, 1, 1)

    @property
    def priority(self):
        # 3: Emergency Return (battery < 10%)
        if self.battery < AppConfig.BATTERY_CRITICAL_THRESHOLD:
            return 3
        # 2: Carrying Package
        if self.cargo:
            return 2
        # 1: On Task (to pickup)
        if self.state == 'TO_PICKUP':
            return 1
        # 0: Idle/Returning/Staging
        return 0

    def repath_around_obstacles(self, extra_avoid=None):
        if not self.current_path:
            return None

        # Determine current goal based on state
        goal = None
        if self.state == 'TO_PICKUP' and self.current_task:
            goal = (int(round(self.current_task['pickup_pos'][0] / AppConfig.CELL_SCALE[0])), 
                    int(round(self.current_task['pickup_pos'][2] / AppConfig.CELL_SCALE[2])))
        elif self.state == 'TO_DROP' and self.current_task:
            goal = (int(round(self.current_task['drop_pos'][0] / AppConfig.CELL_SCALE[0])), 
                    int(round(self.current_task['drop_pos'][2] / AppConfig.CELL_SCALE[2])))
        elif self.state == 'RETURNING':
            goal = self.home_pos
            
        if not goal:
            return None

        my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        
        # Build avoid list: current positions of all other robots
        avoid_grids = []
        for r in self.manager.robots:
            if r == self: continue
            r_grid = (int(round(r.x / AppConfig.CELL_SCALE[0])), int(round(r.z / AppConfig.CELL_SCALE[2])))
            avoid_grids.append(r_grid)
            
            # If the robot is parked or idle, it's a static obstacle we MUST avoid
            if r.state == 'IDLE' or not r.current_path:
                # Add surrounding cells as well for extra safety if needed, but the cell itself is key
                pass

        # ALSO avoid the immediate future paths of robots with higher priority
        for other in self.manager.robots:
            if other != self and other.current_path:
                if other.priority > self.priority or (other.priority == self.priority and other.robot_id < self.robot_id):
                    # Avoid their next few intended steps to prevent cutting them off
                    avoid_grids.extend(other.current_path[:3])
        
        if extra_avoid:
            avoid_grids.extend(extra_avoid)
        
        # Remove duplicates
        avoid_grids = list(set(avoid_grids))
        
        new_path = self.manager.pathfinder.find_path(my_grid, goal, avoid=avoid_grids)
        if new_path:
            return new_path
        return None

    def handle_dock_area_traffic(self):
        # ADVANCED Separate Algorithm for Charging/Parking Zones
        my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        
        # Buffer zone activation
        if my_grid[1] > AppConfig.DOCK_ZONE_THRESHOLD + 1:
            return False, None
            
        # CONGESTION DETECTION: Special wait for docking/parking region
        # ONLY check for blockage if there is a stationary/slow robot in FRONT (next 2 blocks)
        should_check_blockage = False
        if self.current_path:
            # Check next 2 blocks in path
            for i in range(min(len(self.current_path), 2)):
                check_grid = self.current_path[i]
                for other in self.manager.robots:
                    if other == self: continue
                    other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), 
                                  int(round(other.z / AppConfig.CELL_SCALE[2])))
                    if other_grid == check_grid:
                        # Found a robot in front. Is it slow or stopped?
                        other_speed = distance(other.position, other.last_pos) / time.dt if time.dt > 0 else 0
                        if other_speed < AppConfig.ROBOT_MOVE_SPEED * 0.5 or other.state in ['WAITING_PICKUP', 'WAITING_DROP', 'IDLE']:
                            should_check_blockage = True
                            break
                if should_check_blockage: break

        if should_check_blockage:
            blocked_sides = 0
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                is_side_blocked = True
                for dist in range(1, 3): # Check distance 1 and 2
                    nx, ny = my_grid[0] + dx * dist, my_grid[1] + dy * dist
                    
                    cell_physically_blocked = False
                    if not (0 <= nx < self.manager.width and 0 <= ny < self.manager.height):
                        cell_physically_blocked = True # Out of bounds
                    elif self.manager.grid_data[ny][nx] in [AppConfig.OBSTACLE_CHAR, AppConfig.DOCK_CHAR]:
                        cell_physically_blocked = True # Physical Obstacle
                    else:
                        # Check if any robot is at this specific cell
                        for other in self.manager.robots:
                            if other == self: continue
                            other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), 
                                          int(round(other.z / AppConfig.CELL_SCALE[2])))
                            if other_grid == (nx, ny):
                                cell_physically_blocked = True
                                break
                    
                    if not cell_physically_blocked:
                        is_side_blocked = False
                        break
                
                if is_side_blocked:
                    blocked_sides += 1
            
            # Only trigger wait if we are actually blocked on 2-3 sides
            if 2 <= blocked_sides <= 3:
                if self.dock_wait_timer <= 0:
                    print(f"Robot {self.robot_id} DOCK AREA CONGESTION ({blocked_sides} sides blocked). Robot in front slow/stopped. Waiting 1.5s.")
                    self.dock_wait_timer = 1.5
                    return True, None

        if not self.current_path:
            return False, None
        
        next_grid = self.current_path[0]

        for other in self.manager.robots:
            if other == self: continue
            other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2])))
            
            # 1. COLUMN EXCLUSIVITY (Entrance Control)
            # If I am trying to enter a dock column (Z decreasing)
            if my_grid[0] == other_grid[0] and next_grid[1] < my_grid[1]:
                # If someone is already in the parking/exit corridor (Z <= 2)
                if other_grid[1] <= 2:
                    # If they are NOT already parked (they are either arriving or leaving)
                    # or if they are in the spot I want
                    if other.state != 'IDLE' or self.home_pos == other_grid:
                        return True, other

            # 2. EXIT PRIORITY (Dynamic)
            # Trucks moving AWAY from docks (Z increasing) have absolute right-of-way
            if other_grid[0] == my_grid[0] and other.current_path:
                other_next = other.current_path[0]
                if other_next[1] > other_grid[1]: # Other is moving OUT
                    if my_grid[1] > other_grid[1]: # I am in their way (OUTSIDE them)
                        return True, other

            # 3. INTERLOCKING PREVENTION (Head-on in lanes Z=2, Z=3)
            if my_grid[1] == other_grid[1] and abs(my_grid[0] - other_grid[0]) <= 2:
                # If we are moving towards each other in the same lane
                if other.current_path and self.current_path:
                    if next_grid == other_grid or next_grid == other.current_path[0]:
                        # Tie-breaker: ID
                        if other.robot_id < self.robot_id:
                            return True, other

        return False, None

    def update(self):
        # DOCK WAIT LOGIC: Special congestion pause
        if self.dock_wait_timer > 0:
            self.dock_wait_timer -= time.dt
            return

        # BACK-OFF LOGIC: If stuck for too long, move backwards to clear the deadlock
        if self.backoff_timer > 0:
            self.backoff_timer -= time.dt
            # Calculate potential reverse position
            move_step = self.forward * (AppConfig.ROBOT_MOVE_SPEED * 0.5) * time.dt
            next_pos = self.position - move_step
            
            # Collision check for reverse: check grid-based obstacles and other robots
            curr_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
            rev_grid = (int(round(next_pos.x / AppConfig.CELL_SCALE[0])), int(round(next_pos.z / AppConfig.CELL_SCALE[2])))
            
            # 1. Grid Check (Shelves, Docks, Lane Restrictions)
            can_reverse = self.manager.is_walkable(rev_grid[0], rev_grid[1], start_pos=curr_grid)
            
            # 2. Robot Check (Aggressive bubble)
            if can_reverse:
                for other in self.manager.robots:
                    if other == self: continue
                    if distance(next_pos, other.position) < AppConfig.HARD_COLLISION_DISTANCE:
                        can_reverse = False
                        break
            
            if can_reverse:
                self.position = next_pos
            else:
                # If path is blocked behind us, stop reversing and trigger repath immediately
                self.backoff_timer = 0
            
            # When back-off ends (or is cut short), force a repath that avoids the deadlock area
            if self.backoff_timer <= 0:
                print(f"Robot {self.robot_id} smart repath after back-off maneuver.")
                new_path = self.repath_around_obstacles(extra_avoid=self.deadlock_zone)
                if new_path:
                    self.current_path = new_path
                self.deadlock_zone = [] # Clear zone after use
            return

        # STUCK DETECTION
        if len(self.current_path) > 0 and self.state not in ['WAITING_PICKUP', 'WAITING_DROP']:
            if distance(self.position, self.last_pos) < 0.01:
                self.stuck_timer += time.dt
                if self.stuck_timer > 3.0: # If stuck for 3 seconds
                    print(f"Robot {self.robot_id} DEADLOCK detected! Initiating back-off.")
                    self.backoff_timer = 1.5 # Back off for 1.5 seconds
                    self.stuck_timer = 0
            else:
                self.stuck_timer = 0
        else:
            self.stuck_timer = 0
        
        self.last_pos = self.position

        # Battery Logic
        is_moving = len(self.current_path) > 0 and self.state not in ['WAITING_PICKUP', 'WAITING_DROP']
        
        at_dock = False
        for dock in self.manager.docks:
            dist_xz = sqrt((self.x - dock.x)**2 + (self.z - dock.z)**2)
            if dist_xz < AppConfig.CHARGING_DISTANCE:
                at_dock = True
                break

        if is_moving:
            self.battery -= AppConfig.BATTERY_DRAIN_MOVE * time.dt
        else:
            if at_dock:
                self.battery += AppConfig.BATTERY_CHARGE_RATE * time.dt
                # End charging session if target reached
                if self.battery >= AppConfig.BATTERY_RECHARGE_TARGET:
                    if self.is_charging_session:
                        print(f"Robot {self.robot_id} recharged to {int(self.battery)}%. Ready for work.")
                    self.is_charging_session = False
            else:
                self.battery -= AppConfig.BATTERY_DRAIN_PASSIVE * time.dt
        
        self.battery = clamp(self.battery, 0, 100)

        # EMERGENCY RETURN: If battery is critically low, drop task and go to dock
        if self.battery < AppConfig.BATTERY_CRITICAL_THRESHOLD and self.state not in ['IDLE', 'RETURNING']:
            print(f"CRITICAL BATTERY on Robot {self.robot_id}! Dropping package and emergency return.")
            self.is_charging_session = True
            if self.current_task:
                task = self.current_task
                if self.package_visual.enabled:
                    task['pickup_pos'] = self.position
                    if 'pickup_ent' in task:
                        task['pickup_ent'].position = (self.x, 0.1, self.z)
                        task['pickup_ent'].visible = True
                    self.manager.update_file_grid(self.position, task['pickup_char'])
                else:
                    if 'pickup_ent' in task: task['pickup_ent'].visible = True
                
                if task in self.manager.active_tasks: self.manager.active_tasks.remove(task)
                self.manager.unassigned_tasks.append(task)
                self.current_task = None
                self.package_visual.enabled = False
            self.start_return_home_phase()

        # LOW BATTERY AUTO-RETURN: If below threshold and idle (not at dock), go charge
        if self.battery < AppConfig.BATTERY_LOW_THRESHOLD and self.state == 'IDLE' and not at_dock:
            self.is_charging_session = True
            self.start_return_home_phase()

        # DOCK RESERVATION VERIFICATION: If returning, make sure our dock is still available/assigned to us
        if self.state == 'RETURNING' and self.home_pos:
            # Check if someone higher priority has claimed our dock
            best_dock = self.manager.get_nearest_unoccupied_dock(self)
            if best_dock != self.home_pos:
                if best_dock:
                    print(f"Robot {self.robot_id} REDIRECTING to better dock at {best_dock}")
                    self.home_pos = best_dock
                    start = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
                    self.current_path = self.manager.pathfinder.find_path(start, self.home_pos)
                else:
                    # No docks available anymore!
                    print(f"Robot {self.robot_id} lost dock reservation and none available!")
                    self.state = 'IDLE'
                    self.current_path = []

        if self.state in ['WAITING_PICKUP', 'WAITING_DROP']:
            self.wait_timer -= time.dt
            if self.wait_timer <= 0:
                if self.state == 'WAITING_PICKUP':
                    self.start_drop_off_phase()
                else:
                    self.start_return_home_phase()
            return

        if not self.current_path:
            return

        # DOCK AREA SPECIALIZED TRAFFIC MANAGEMENT
        dock_blocked, dock_threat = self.handle_dock_area_traffic()
        if dock_blocked:
            # Yield and wait
            return

        # PREDICTIVE TRAFFIC MANAGEMENT (Standard)
        look_ahead = 5
        my_path_segment = self.current_path[:look_ahead]
        blocked = False
        threat = None
        self.alt_path = [] # Reset Plan B each frame for fresh calculation
        
        my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))

        for other in self.manager.robots:
            if other == self: continue
            
            other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2])))
            other_path_segment = other.current_path[:look_ahead]
            
            # Goal-Aware Prediction: If someone is about to stop at a pickup/drop point in my path
            if other.state in ['TO_PICKUP', 'TO_DROP', 'RETURNING'] and other.current_path:
                dest = other.current_path[-1]
                if dest in my_path_segment:
                    # They will stop at 'dest' soon. Prepare Plan B early.
                    if not self.alt_path:
                        self.alt_path = self.repath_around_obstacles(extra_avoid=[dest])
                        if self.alt_path:
                            print(f"Robot {self.robot_id} Plan B READY (Goal Conflict with Robot {other.robot_id} at {dest})")

            # 1. Is there a higher priority robot approaching MY current cell?
            if my_grid in other_path_segment[:3]:
                if other.priority > self.priority or (other.priority == self.priority and other.robot_id < self.robot_id):
                    blocked = True
                    threat = other
                    break

            # 2. Is there a robot in MY path segment?
            collision_cell = None
            if other_grid in my_path_segment:
                collision_cell = other_grid
            else:
                # 3. Do our future paths intersect at the same time/step?
                for i, cell in enumerate(my_path_segment):
                    if i < len(other_path_segment) and cell == other_path_segment[i]:
                        collision_cell = cell
                        break
            
            if collision_cell:
                if other.priority > self.priority or (other.priority == self.priority and other.robot_id < self.robot_id):
                    blocked = True
                    threat = other
                    break

        if blocked:
            # Quick Action: Use Plan B if ready, otherwise re-route now
            new_path = self.alt_path if self.alt_path else self.repath_around_obstacles()
            if new_path:
                print(f"Robot {self.robot_id} QUICK ACTION: Switching to alternative route.")
                self.current_path = new_path
            else:
                # Yielding Logic with Gap Maintenance (ensure 1-block gap)
                other_pos = (int(round(threat.x / AppConfig.CELL_SCALE[0])), int(round(threat.z / AppConfig.CELL_SCALE[2])))
                other_next = threat.current_path[0] if threat.current_path else None
                
                if self.current_path[0] == other_pos or self.current_path[0] == other_next:
                    return

                if len(self.current_path) > 1 and self.current_path[1] == other_pos:
                    return

        # Movement target
        next_grid_pos = self.current_path[0]
        world_target = Vec3(next_grid_pos[0] * AppConfig.CELL_SCALE[0], 0, next_grid_pos[1] * AppConfig.CELL_SCALE[2])
        
        # HARD PROXIMITY RADAR (Bullet-Proof Collision Avoidance)
        hard_stop = False
        threat = None
        for other in self.manager.robots:
            if other == self: continue
            dist = distance(self.position, other.position)
            # Use an aggressive bubble to ensure they NEVER touch
            if dist < AppConfig.HARD_COLLISION_DISTANCE:
                hard_stop = True
                threat = other
                break
        
        # BRAKE-CHECK & RECOVERY LOGIC
        target_speed = AppConfig.ROBOT_MOVE_SPEED
        
        if hard_stop:
            target_speed = 0
            self.zero_speed_timer += time.dt
            
            # DEADLOCK RESOLUTION: Hierarchy-based back-off
            # Only the lower priority truck (or higher ID if same priority) backs off
            is_lower_priority = (self.priority < threat.priority or 
                                (self.priority == threat.priority and self.robot_id > threat.robot_id))
            
            if is_lower_priority and self.zero_speed_timer > 1.0:
                print(f"Robot {self.robot_id} yielding to Robot {threat.robot_id}. Initiating Smart Back-off.")
                self.backoff_timer = 1.5
                self.zero_speed_timer = 0
                
                # Mark deadlock zone (3x3 grid around current position) to avoid during repath
                gx, gz = int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2]))
                deadlock_avoid = []
                for dx in range(-1, 2):
                    for dz in range(-1, 2):
                        deadlock_avoid.append((gx + dx, gz + dz))
                
                self.deadlock_zone = deadlock_avoid 
            
            elif not is_lower_priority and self.zero_speed_timer > 0.7:
                # NEW RULE: Even high priority re-paths after 0.7s instead of waiting
                print(f"Robot {self.robot_id} (Priority) blocked for 0.7s. Force-Repathing.")
                new_path = self.repath_around_obstacles()
                if new_path: self.current_path = new_path
                self.zero_speed_timer = 0
        else:
            self.zero_speed_timer = 0
            # Dynamic Speed Adjustment (Standard)
            look_ahead_speed = 3
            obstacle_in_path = False
            for i in range(min(len(self.current_path), look_ahead_speed)):
                check_cell = self.current_path[i]
                for other in self.manager.robots:
                    if other == self: continue
                    other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2])))
                    if other_grid == check_cell:
                        dist_to_other = distance(self.position, other.position)
                        safety_dist = AppConfig.CELL_SCALE[0] * AppConfig.ROBOT_BRAKING_SENSITIVITY
                        if dist_to_other < safety_dist:
                            obstacle_in_path = True
                            # PHASED BRAKING LOGIC
                            if self.braking_timer < 0.5:
                                # Stage 1: Slow down (0.5s)
                                self.braking_timer += time.dt
                                speed_factor = clamp(dist_to_other / safety_dist, AppConfig.ROBOT_MIN_SPEED_FACTOR, 1.0)
                                target_speed *= speed_factor
                            elif self.waiting_timer < 0.7:
                                # Stage 2: Wait/Stop (Now up to 0.7s total wait before repath)
                                self.waiting_timer += time.dt
                                target_speed = 0
                                if self.waiting_timer >= 0.7:
                                    print(f"Robot {self.robot_id} wait threshold (0.7s) exceeded. Force-Repathing.")
                                    new_path = self.repath_around_obstacles()
                                    if new_path: self.current_path = new_path
                                    self.waiting_timer = 0
                                    self.braking_timer = 0
                            else:
                                target_speed = 0
                            break
                if obstacle_in_path: break
            
            if not obstacle_in_path:
                self.braking_timer = 0
                self.waiting_timer = 0

        # Smooth Rotation
        target_rot_y = atan2(world_target.x - self.x, world_target.z - self.z) * 180 / pi
        self.rotation_y = lerp_angle(self.rotation_y, target_rot_y, time.dt * AppConfig.ROBOT_ROTATION_SPEED)
        
        # TOTAL WAIT TRACKING (Non-movement time while on path)
        if target_speed == 0 and self.dock_wait_timer <= 0:
            self.total_wait_timer += time.dt
            if self.total_wait_timer > 0.7:
                print(f"Robot {self.robot_id} total wait threshold (0.7s) reached. Forcing dynamic repath.")
                new_path = self.repath_around_obstacles()
                if new_path:
                    self.current_path = new_path
                self.total_wait_timer = 0
                self.braking_timer = 0
                self.waiting_timer = 0
                self.zero_speed_timer = 0
        else:
            self.total_wait_timer = 0

        dist = distance(self.position, world_target)
        if dist > 0.1:
            self.position += self.forward * target_speed * time.dt
        else:
            self.position = world_target
            self.current_path.pop(0)
            
            if not self.current_path:
                self.on_reach_target()

    def on_reach_target(self):
        if self.state == 'TO_PICKUP':
            print(f"Robot {self.robot_id} REACHED PICKUP {self.current_task['pickup_char']}. Loading Cargo...")
            self.state = 'WAITING_PICKUP'
            self.wait_timer = AppConfig.ROBOT_WAIT_TIME
            
            task = self.current_task
            if 'pickup_ent' in task:
                # GRAB THE BOX: Reparent the visible box from the floor to the truck
                self.cargo = task['pickup_ent'].cargo
                self.cargo.parent = self
                # Reset position relative to truck and animate into the bed
                self.cargo.position = (AppConfig.CARGO_TRUCK_X_OFFSET, 0, AppConfig.CARGO_TRUCK_Z_OFFSET - 1.2) # Start behind truck
                
                # Bouncy Loading: Position + Scale
                self.cargo.animate_position((AppConfig.CARGO_TRUCK_X_OFFSET, AppConfig.CARGO_TRUCK_Y_POS, AppConfig.CARGO_TRUCK_Z_OFFSET), 
                                            duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
                self.cargo.animate_scale(AppConfig.CARGO_TRUCK_SCALE, 
                                         duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
                
                # Hide the floor marker and stick
                task['pickup_ent'].marker.enabled = False
            
        elif self.state == 'TO_DROP':
            print(f"Robot {self.robot_id} REACHED DROP {self.current_task['drop_char']}. Unloading Cargo...")
            self.state = 'WAITING_DROP'
            self.wait_timer = AppConfig.ROBOT_WAIT_TIME
            
            if self.cargo:
                # Bouncy Unloading: Position + Scale back to original
                self.cargo.animate_position((AppConfig.CARGO_TRUCK_X_OFFSET, 0, AppConfig.CARGO_TRUCK_Z_OFFSET - 1.5), 
                                            duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
                self.cargo.animate_scale(AppConfig.CARGO_FLOOR_SCALE, 
                                         duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
                
            self.manager.complete_task(self.current_task)
            
        elif self.state == 'RETURNING':
            print(f"Robot {self.robot_id} PARKED at home {self.home_pos}")
            self.state = 'IDLE'
            # If we still have cargo visual somehow, destroy it
            if self.cargo:
                destroy(self.cargo)
                self.cargo = None

    def start_drop_off_phase(self):
        print(f"Robot {self.robot_id} moving to DROP {self.current_task['drop_char']}")
        self.state = 'TO_DROP'
        task_sys = self.manager
        start = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        goal = (int(round(self.current_task['drop_pos'][0] / AppConfig.CELL_SCALE[0])), 
                int(round(self.current_task['drop_pos'][2] / AppConfig.CELL_SCALE[2])))
        self.current_path = task_sys.pathfinder.find_path(start, goal)

    def start_return_home_phase(self):
        # Set charging session flag if battery is low
        if self.battery < AppConfig.BATTERY_LOW_THRESHOLD:
            self.is_charging_session = True

        # First check if there are any unassigned tasks - ONLY if battery is healthy and NOT charging
        if not self.is_charging_session and self.battery >= AppConfig.BATTERY_LOW_THRESHOLD and self.manager.unassigned_tasks:
            # Sort tasks by distance to this robot
            self.manager.unassigned_tasks.sort(key=lambda t: distance(self.position, t['pickup_pos']))
            task = self.manager.unassigned_tasks.pop(0)
            self.manager.active_tasks.append(task)
            self.manager.assign_task_to_robot(self, task)
            return

        # If no tasks or battery low, find the nearest unoccupied dock
        nearest_dock_grid = self.manager.get_nearest_unoccupied_dock(self.position)
        if nearest_dock_grid:
            self.home_pos = nearest_dock_grid
            print(f"Robot {self.robot_id} returning to nearest dock at {self.home_pos}")
            self.state = 'RETURNING'
            start = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
            self.current_path = self.manager.pathfinder.find_path(start, self.home_pos)
            self.current_task = None
        else:
            print(f"Robot {self.robot_id} - No available docks found!")
            self.state = 'IDLE'

class PickupPoint(Entity):
    def __init__(self, pos, pair_color, char, **kwargs):
        super().__init__(position=(pos[0], 0, pos[2]), **kwargs)
        
        # 1. The floor marker (remains on floor)
        self.marker = Entity(
            parent=self,
            model='cube',
            position=(0, 0.1, 0),
            scale=(1.5, 0.05, 1.5),
            color=pair_color,
            alpha=0.5
        )
        # Vertical stick for visibility
        Entity(parent=self.marker, model='cube', position=(0, 4, 0), scale=(0.2, 8, 0.2), color=pair_color, alpha=0.3)
        
        # 2. The Actual Cargo (this is what the robot will grab)
        self.cargo = Entity(
            parent=self,
            model='cube',
            position=(0, 0.5, 0),
            scale=AppConfig.CARGO_FLOOR_SCALE,
            color=pair_color,
            texture='white_cube' # Using a texture makes it look more like a box
        )

class DropPoint(Entity):
    def __init__(self, pos, pair_color, char, **kwargs):
        super().__init__(
            model='cube',
            position=(pos[0], 0.1, pos[2]),
            scale=(1.5, 0.05, 1.5),
            color=pair_color,
            alpha=0.4,
            **kwargs
        )
        Entity(parent=self, model='cube', position=(0, 2, 0), scale=(1, 4, 1), color=pair_color, alpha=0.5)

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

    def update(self):
        # Systematic battery logging
        self.log_timer += time.dt
        if self.log_timer >= AppConfig.BATTERY_LOG_INTERVAL:
            self.log_timer = 0
            log_str = " | ".join([f"Truck {r.robot_id}: {int(r.battery)}%" for r in self.robots])
            print(f"[BATTERY STATUS] {log_str}")
        
        # Continuously check for available tasks to handle queued work immediately
        self.assign_tasks()

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

class TopDownCamera(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.move_speed = AppConfig.TOP_DOWN_SPEED
        self.lift_speed = AppConfig.TOP_DOWN_LIFT_SPEED

    def update(self):
        if not self.enabled:
            return

        # Arrow keys for X and Z axes
        self.x += (held_keys['right arrow'] - held_keys['left arrow']) * self.move_speed * time.dt
        self.z += (held_keys['up arrow'] - held_keys['down arrow']) * self.move_speed * time.dt

        # E and Q for Y axis (vertical)
        self.y += (held_keys['e'] - held_keys['q']) * self.lift_speed * time.dt

class CameraManager(Entity):
    def __init__(self, player, top_down, **kwargs):
        super().__init__(**kwargs)
        self.player = player
        self.top_down = top_down

    def input(self, key):
        if key == 'tab':
            self.player.enabled = not self.player.enabled
            self.top_down.enabled = not self.player.enabled
            
            if self.top_down.enabled:
                self.top_down.position = (self.player.x, self.top_down.y, self.player.z)
                camera.parent = self.top_down
                camera.position = (0, 0, 0)
                camera.rotation = (90, 0, 0)
                mouse.visible = True
                mouse.locked = False
            else:
                camera.parent = self.player.camera_pivot
                camera.position = (0, 0, 0)
                camera.rotation = (0, 0, 0)
                mouse.visible = AppConfig.MOUSE_VISIBLE
                mouse.locked = True

class FleetHUD(Entity):
    def __init__(self, robots, task_system, **kwargs):
        super().__init__(parent=camera.ui, **kwargs)
        self.robots = robots
        self.ts = task_system
        
        # Increased scale for the panel to fit larger text
        self.bg = Panel(scale=(0.5, 0.55), position=(0.75, 0.1), color=color.black66)
        self.title = Text("FLEET STATUS", parent=self.bg, origin=(0,0), y=0.45, scale=3.0, color=color.azure)
        
        self.info_texts = []
        for i in range(len(self.robots)):
            # Adjusted scale and spacing for 7 trucks
            t = Text("", parent=self.bg, origin=(-0.5, 0), x=-0.45, y=0.35 - (i * 0.11), scale=1.3)
            self.info_texts.append(t)
            
        # Increased scale to 2.4 (2x original 1.2)
        self.queue_text = Text("", parent=self.bg, origin=(0,0), y=-0.4, scale=2.4, color=color.yellow)

    def update(self):
        for i, robot in enumerate(self.robots):
            b_color = color.green if robot.battery > 50 else (color.orange if robot.battery > 20 else color.red)
            state_str = robot.state
            if robot.is_charging_session:
                state_str = "CHARGING..."
            
            self.info_texts[i].text = f"Truck {robot.robot_id}: {state_str}\nBattery: <{b_color.brightness + 0.2}>{int(robot.battery)}%</{b_color.brightness + 0.2}>"
            self.info_texts[i].color = b_color

        total_pending = len(self.ts.unassigned_tasks)
        self.queue_text.text = f"Pending Tasks: {total_pending}"

# ==========================================
# MAIN APPLICATION
# ==========================================

def reset_layout_file(filename):
    try:
        if os.path.exists(AppConfig.DEFAULT_LAYOUT_FILE):
            # Close files and ensure target is writable
            shutil.copy2(AppConfig.DEFAULT_LAYOUT_FILE, filename)
            print(f"Layout file '{filename}' reset from '{AppConfig.DEFAULT_LAYOUT_FILE}'.")
        else:
            print(f"Warning: {AppConfig.DEFAULT_LAYOUT_FILE} not found.")
    except Exception as e:
        print(f"Warning: Could not reset layout file: {e}")

def load_grid(filename):
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        return ["." * AppConfig.DEFAULT_WIDTH for _ in range(AppConfig.DEFAULT_HEIGHT)]

def parse_map_and_spawn(grid):
    height, width = len(grid), len(grid[0]) if len(grid) > 0 else 0
    scale_x, scale_z = AppConfig.CELL_SCALE[0], AppConfig.CELL_SCALE[2]
    dock_locations = []
    robot_locations = []
    shelf_parents = {m: Entity(name=f'sh_{i}', enabled=False) for i, m in enumerate(AppConfig.SHELF_MODEL_FILE)}
    
    for z in range(height):
        for x in range(width):
            char = grid[z][x]
            wx, wz = x * scale_x, z * scale_z
            if char == AppConfig.OBSTACLE_CHAR:
                m = AppConfig.SHELF_MODEL_FILE[random.randint(0, len(AppConfig.SHELF_MODEL_FILE)-1)]
                Entity(parent=shelf_parents[m], model=m, texture=AppConfig.SHELF_TEXTURE_FILE, 
                       position=(wx, 0, wz), scale=AppConfig.OBSTACLE_SCALE, rotation_y=90, double_sided=True)
            elif char == AppConfig.DOCK_CHAR: dock_locations.append((wx, wz))
            elif char == AppConfig.ROBOT_CHAR: robot_locations.append((wx, wz))

    floor_parent = Entity(name='floor_parent')
    for m, p in shelf_parents.items():
        if p.children: 
            p.parent = floor_parent
            p.enabled = True
            p.flatten_strong()
            p.double_sided = True # Apply to combined mesh

    Entity(model='cube', parent=floor_parent, name='warehouse_floor',
           position=((width-1)*scale_x/2, AppConfig.FLOOR_Y_POS, (height-1)*scale_z/2),
           scale=(width * scale_x, AppConfig.CELL_SCALE[1], height * scale_z),
           texture=AppConfig.FLOOR_TEXTURE_FILE, texture_scale=(width, height),
           color=AppConfig.FLOOR_COLOR_A, collider='box')
    
    robots, docks = [], []
    pair_colors = [color.red, color.green, color.blue, color.yellow, color.cyan, color.magenta, color.orange, color.azure]
    count = min(len(dock_locations), len(robot_locations))
    for i in range(count):
        d_pos, r_pos = dock_locations[i], robot_locations[i]
        c = pair_colors[i % len(pair_colors)]
        docks.append(ChargingDock(i, d_pos[0], d_pos[1], i, c))
        home_grid = (int(round(r_pos[0]/scale_x)), int(round(r_pos[1]/scale_z)))
        robots.append(Robot(i, r_pos[0], r_pos[1], c, home_grid))

    return width, height, floor_parent, robots, docks

def main():
    app = Ursina()
    reset_layout_file(AppConfig.LAYOUT_FILE)
    grid = load_grid(AppConfig.LAYOUT_FILE)
    width, height, floor_parent, robots, docks = parse_map_and_spawn(grid)
    center_x, center_z = (width / 2) * AppConfig.CELL_SCALE[0], (height / 2) * AppConfig.CELL_SCALE[2]
    player = FirstPersonController()
    player.position = (center_x, AppConfig.PLAYER_START_HEIGHT, center_z + AppConfig.PLAYER_START_OFFSET_Z)
    player.cursor.visible = AppConfig.MOUSE_VISIBLE
    
    top_down_camera = TopDownCamera(position=(center_x, AppConfig.TOP_DOWN_HEIGHT, center_z), enabled=False)
    CameraManager(player, top_down_camera)

    ts = TaskSystem(robots=robots, docks=docks)
    FleetHUD(robots=robots, task_system=ts)
    app.run()

if __name__ == "__main__":
    main()
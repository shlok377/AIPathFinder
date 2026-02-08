from ursina import Entity, lerp, color, curve, time, Vec3, clamp, lerp_angle, distance, destroy
from math import atan2, pi, sqrt
from core.config import AppConfig
from core.telemetry import cloud_logger

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
            
            # If the robot is parked or essentially stationary, it is a hard obstacle
            if r.state in ['IDLE', 'WAITING_PICKUP', 'WAITING_DROP'] or distance(r.position, r.last_pos) < 0.05:
                avoid_grids.append(r_grid)
            
            # If they are in my immediate way (within 2 steps), avoid them regardless of priority
            my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
            if distance(Vec3(r_grid[0], 0, r_grid[1]), Vec3(my_grid[0], 0, my_grid[1])) <= 2:
                avoid_grids.append(r_grid)

        # ALSO avoid the immediate future paths of robots with higher priority
        for other in self.manager.robots:
            if other != self and other.current_path:
                if other.priority > self.priority or (other.priority == self.priority and other.robot_id < self.robot_id):
                    # Avoid their next few intended steps
                    avoid_grids.extend(other.current_path[:2])
        
        if extra_avoid:
            avoid_grids.extend(extra_avoid)
        
        # Remove duplicates
        avoid_grids = list(set(avoid_grids))
        
        new_path = self.manager.pathfinder.find_path(my_grid, goal, avoid=avoid_grids)
        if new_path:
            cloud_logger.publish_event(self.robot_id, "REPATH", {"reason": "dynamic_obstacle", "goal": goal})
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
                    cloud_logger.publish_event(self.robot_id, "YIELD_STP", {"area": "dock_zone", "blocked_sides": blocked_sides})
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
                if self.stuck_timer > 3.0: 
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
            cloud_logger.publish_event(self.robot_id, "CRITICAL_BATTERY", {"battery": round(self.battery, 1)})
            print(f"CRITICAL BATTERY on Robot {self.robot_id}! Dropping package and emergency return.")
            self.is_charging_session = True
            if self.current_task:
                task = self.current_task
                if self.cargo:
                    task['pickup_pos'] = self.position
                    if 'pickup_ent' in task:
                        # Drop cargo back at current position
                        task['pickup_ent'].position = (self.x, 0, self.z)
                        task['pickup_ent'].visible = True
                        task['pickup_ent'].marker.enabled = True
                        
                        # Return cargo to pickup entity
                        self.cargo.parent = task['pickup_ent']
                        self.cargo.position = (0, 0.5, 0)
                        self.cargo.scale = AppConfig.CARGO_FLOOR_SCALE
                        
                    self.manager.update_file_grid(self.position, task['pickup_char'])
                    self.cargo = None
                else:
                    if 'pickup_ent' in task: task['pickup_ent'].visible = True
                
                if task in self.manager.active_tasks: self.manager.active_tasks.remove(task)
                self.manager.unassigned_tasks.append(task)
                self.current_task = None
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
                        # Lower priority/Higher ID robot will proactively re-route around the destination
                        is_lower_priority = (self.priority < other.priority or 
                                            (self.priority == other.priority and self.robot_id > other.robot_id))
                        
                        if is_lower_priority:
                            # Avoid a 3x3 area around their destination to give them room to load/unload
                            dx, dz = dest
                            avoid_zone = []
                            for ox in range(-1, 2):
                                for oz in range(-1, 2):
                                    avoid_zone.append((dx + ox, dz + oz))
                            
                            self.alt_path = self.repath_around_obstacles(extra_avoid=avoid_zone)
                            if self.alt_path:
                                # cloud_logger.publish_event(self.robot_id, "PLAN_B", {"reason": "goal_conflict", "target": dest})
                                pass
                        else:
                            # Higher priority robot just clears current calculation and waits briefly
                            # This prevents the head-on logic fight
                            pass

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
            # Check if I am the higher priority robot in this conflict
            is_higher_priority = (self.priority > threat.priority or 
                                 (self.priority == threat.priority and self.robot_id < threat.robot_id))

            if not is_higher_priority:
                # Lower priority: Use Plan B (3x3 avoidance) if ready, otherwise re-route now
                new_path = self.alt_path if self.alt_path else self.repath_around_obstacles()
                if new_path:
                    self.current_path = new_path
            else:
                # Higher priority: Reset and wait for the area to clear
                # This prevents "fighting" for the same cell
                self.waiting_timer = 0.5 # Wait 0.5s before moving/re-checking
                target_speed = 0
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
            
            # Master-Slave Priority Check
            is_slave = (self.priority < threat.priority or 
                       (self.priority == threat.priority and self.robot_id > threat.robot_id))
            
            # SLAVE DECISION
            if is_slave and self.zero_speed_timer > 1.0:
                print(f"Robot {self.robot_id} (Slave) backing off from Robot {threat.robot_id} (Master).")
                self.backoff_timer = 1.5
                self.zero_speed_timer = 0
                
                # SLAVE MUST AVOID 3x3 Area around Master
                tx, tz = int(round(threat.x / AppConfig.CELL_SCALE[0])), int(round(threat.z / AppConfig.CELL_SCALE[2]))
                avoid_zone = []
                for dx in range(-1, 2):
                    for dz in range(-1, 2):
                        avoid_zone.append((tx + dx, tz + dz))
                self.deadlock_zone = avoid_zone
            
            # MASTER DECISION
            elif not is_slave and self.zero_speed_timer > 0.6:
                # Master just refreshes path locally without 3x3 avoidance
                # and waits for the Slave to execute its back-off/re-route
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
                            my_threshold = 0.6 + (self.robot_id % 4) * 0.2
                            
                            if self.braking_timer < 0.4:
                                # Stage 1: Slow down
                                self.braking_timer += time.dt
                                speed_factor = clamp(dist_to_other / safety_dist, AppConfig.ROBOT_MIN_SPEED_FACTOR, 1.0)
                                target_speed *= speed_factor
                            elif self.waiting_timer < my_threshold:
                                # Stage 2: Wait/Stop
                                self.waiting_timer += time.dt
                                target_speed = 0
                                if self.waiting_timer >= my_threshold:
                                    # Master-Slave Priority Check
                                    is_slave = (self.priority < other.priority or 
                                               (self.priority == other.priority and self.robot_id > other.robot_id))
                                    
                                    if is_slave:
                                        print(f"Robot {self.robot_id} (Slave) re-routing around Robot {other.robot_id} (Master).")
                                        tx, tz = int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2]))
                                        avoid_3x3 = []
                                        for dx in range(-1, 2):
                                            for dz in range(-1, 2):
                                                avoid_3x3.append((tx + dx, tz + dz))
                                        new_path = self.repath_around_obstacles(extra_avoid=avoid_3x3)
                                    else:
                                        # Master just refreshes path
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
            
            # Determine priority in the conflict
            # Find the robot that is currently blocking us
            conflict_threat = None
            if len(self.current_path) > 0:
                next_cell = self.current_path[0]
                for other in self.manager.robots:
                    if other == self: continue
                    other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2])))
                    if other_grid == next_cell:
                        conflict_threat = other
                        break
            
            # If we don't have a specific threat but are stopped, we use general timeout
            # Use ID-based asymmetric threshold to prevent simultaneous action
            my_threshold = 0.6 + (self.robot_id % 4) * 0.2
            
            if self.total_wait_timer > my_threshold:
                if conflict_threat:
                    # ROLE ASSIGNMENT
                    is_slave = (self.priority < conflict_threat.priority or 
                               (self.priority == conflict_threat.priority and self.robot_id > conflict_threat.robot_id))
                    
                    if is_slave:
                        # SLAVE: Re-route instantly avoiding 3x3 area around the Master
                        print(f"Robot {self.robot_id} (Slave) re-routing around Robot {conflict_threat.robot_id} (Master).")
                        tx, tz = int(round(conflict_threat.x / AppConfig.CELL_SCALE[0])), int(round(conflict_threat.z / AppConfig.CELL_SCALE[2]))
                        avoid_3x3 = []
                        for dx in range(-1, 2):
                            for dz in range(-1, 2):
                                avoid_3x3.append((tx + dx, tz + dz))
                        
                        new_path = self.repath_around_obstacles(extra_avoid=avoid_3x3)
                        if new_path:
                            self.current_path = new_path
                    else:
                        # MASTER: Just reset calculations and wait for the slave to move
                        print(f"Robot {self.robot_id} (Master) holding position for Robot {conflict_threat.robot_id} (Slave).")
                        self.current_path = self.repath_around_obstacles() # Refresh normally
                else:
                    # General deadlock (blocked by static peer or something else)
                    new_path = self.repath_around_obstacles()
                    if new_path:
                        self.current_path = new_path
                
                # Reset all timers after intervention
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

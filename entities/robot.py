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
        
        self.cargo = None
        
        self.state = 'IDLE' 
        self.current_path = []
        self.alt_path = [] 
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
        self.current_speed = 0.0
        self.near_miss_cooldown = 0
        self.last_pos = self.position

        if not self.model:
            self.model = 'cube'
            self.color = color.blue
            self.scale = (1, 1, 1)

    @property
    def priority(self):
        if self.battery < AppConfig.BATTERY_CRITICAL_THRESHOLD:
            return 3
        if self.cargo:
            return 2
        if self.state == 'TO_PICKUP':
            return 1
        return 0

    def apply_harmony_security(self):
        # HARMONY SECURITY CHECK: Radius 2 scan for stationary peers
        extra_avoid = []
        my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        
        for other in self.manager.robots:
            if other == self: continue
            other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2])))
            
            # Check L1 distance (Manhattan) for radius 2
            grid_dist = abs(other_grid[0] - my_grid[0]) + abs(other_grid[1] - my_grid[1])
            if grid_dist <= 2:
                # If they are currently waiting/loading, we MUST work in harmony and avoid them
                if other.state in ['WAITING_PICKUP', 'WAITING_DROP', 'IDLE']:
                    extra_avoid.append(other_grid)
        return extra_avoid

    def repath_around_obstacles(self, extra_avoid=None):
        if not self.current_path:
            return None

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
        
        avoid_grids = self.apply_harmony_security() # Inject Harmony
        robot_positions = []
        for r in self.manager.robots:
            rg = (int(round(r.x / AppConfig.CELL_SCALE[0])), int(round(r.z / AppConfig.CELL_SCALE[2])))
            robot_positions.append(rg)
            if r == self: continue
            
            if r.state in ['IDLE', 'WAITING_PICKUP', 'WAITING_DROP'] or distance(r.position, r.last_pos) < 0.05:
                avoid_grids.append(rg)
            
            if distance(Vec3(rg[0], 0, rg[1]), Vec3(my_grid[0], 0, my_grid[1])) <= 2:
                avoid_grids.append(rg)

        for other in self.manager.robots:
            if other != self and other.current_path:
                if other.priority > self.priority or (other.priority == self.priority and other.robot_id < self.robot_id):
                    avoid_grids.extend(other.current_path[:2])
        
        if extra_avoid:
            avoid_grids.extend(extra_avoid)
        
        avoid_grids = list(set(avoid_grids))
        
        new_path = self.manager.pathfinder.find_path(my_grid, goal, avoid=avoid_grids, robot_positions=robot_positions)
        if new_path:
            cloud_logger.publish_event(self.robot_id, "REPATH", {"reason": "dynamic_obstacle", "goal": goal})
            return new_path
        return None

    def handle_dock_area_traffic(self):
        my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        if my_grid[1] > AppConfig.DOCK_ZONE_THRESHOLD + 1:
            return False, None
            
        should_check_blockage = False
        if self.current_path:
            for i in range(min(len(self.current_path), 2)):
                check_grid = self.current_path[i]
                for other in self.manager.robots:
                    if other == self: continue
                    other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), 
                                  int(round(other.z / AppConfig.CELL_SCALE[2])))
                    if other_grid == check_grid:
                        other_speed = distance(other.position, other.last_pos) / time.dt if time.dt > 0 else 0
                        if other_speed < AppConfig.ROBOT_MOVE_SPEED * 0.5 or other.state in ['WAITING_PICKUP', 'WAITING_DROP', 'IDLE']:
                            should_check_blockage = True
                            break
                if should_check_blockage: break

        if should_check_blockage:
            blocked_sides = 0
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                is_side_blocked = True
                for dist in range(1, 3):
                    nx, ny = my_grid[0] + dx * dist, my_grid[1] + dy * dist
                    cell_physically_blocked = False
                    if not (0 <= nx < self.manager.width and 0 <= ny < self.manager.height):
                        cell_physically_blocked = True 
                    elif self.manager.grid_data[ny][nx] in [AppConfig.OBSTACLE_CHAR, AppConfig.DOCK_CHAR]:
                        cell_physically_blocked = True 
                    else:
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
            if my_grid[0] == other_grid[0] and next_grid[1] < my_grid[1]:
                if other_grid[1] <= 2:
                    if other.state != 'IDLE' or self.home_pos == other_grid:
                        return True, other
            if other_grid[0] == my_grid[0] and other.current_path:
                other_next = other.current_path[0]
                if other_next[1] > other_grid[1]: 
                    if my_grid[1] > other_grid[1]: 
                        return True, other
            if my_grid[1] == other_grid[1] and abs(my_grid[0] - other_grid[0]) <= 2:
                if other.current_path and self.current_path:
                    if next_grid == other_grid or next_grid == other.current_path[0]:
                        if other.robot_id < self.robot_id:
                            return True, other
        return False, None

    def update(self):
        if self.dock_wait_timer > 0:
            self.dock_wait_timer -= time.dt
            return

        if self.backoff_timer > 0:
            self.backoff_timer -= time.dt
            move_step = self.forward * (AppConfig.ROBOT_MOVE_SPEED * 0.5) * time.dt
            next_pos = self.position - move_step
            curr_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
            rev_grid = (int(round(next_pos.x / AppConfig.CELL_SCALE[0])), int(round(next_pos.z / AppConfig.CELL_SCALE[2])))
            
            is_junction = False
            valid_neighbors = 0
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                if self.manager.is_walkable(curr_grid[0]+dx, curr_grid[1]+dy):
                    valid_neighbors += 1
            if valid_neighbors >= 3: is_junction = True
            
            can_reverse = self.manager.is_walkable(rev_grid[0], rev_grid[1], start_pos=curr_grid)
            if can_reverse:
                for other in self.manager.robots:
                    if other == self: continue
                    if distance(next_pos, other.position) < AppConfig.HARD_COLLISION_DISTANCE:
                        can_reverse = False
                        break
            
            if can_reverse:
                self.position = next_pos
                if is_junction and self.backoff_timer < 1.0:
                    self.backoff_timer = 0
            else:
                self.backoff_timer = 0
            
            if self.backoff_timer <= 0:
                new_path = self.repath_around_obstacles(extra_avoid=self.deadlock_zone)
                if new_path: self.current_path = new_path
                self.deadlock_zone = [] 
            return

        if len(self.current_path) > 0 and self.state not in ['WAITING_PICKUP', 'WAITING_DROP']:
            if distance(self.position, self.last_pos) < 0.01:
                self.stuck_timer += time.dt
                if self.stuck_timer > 3.0: 
                    self.backoff_timer = 1.5 
                    self.stuck_timer = 0
            else:
                self.stuck_timer = 0
        else:
            self.stuck_timer = 0
        
        self.last_pos = self.position

        is_moving = len(self.current_path) > 0 and self.state not in ['WAITING_PICKUP', 'WAITING_DROP']
        at_dock = False
        for dock in self.manager.docks:
            dist_xz = sqrt((self.x - dock.x)**2 + (self.z - dock.z)**2)
            if dist_xz < AppConfig.CHARGING_DISTANCE:
                at_dock = True
                break
        
        my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        is_flying_highway = self.manager.is_flying_highway(my_grid[0], my_grid[1])
        is_normal_highway = self.manager.is_highway(my_grid[0], my_grid[1]) and not is_flying_highway

        if is_moving:
            drain = AppConfig.HIGHWAY_DRAIN_MOVE if is_flying_highway else AppConfig.BATTERY_DRAIN_MOVE
            self.battery -= drain * time.dt
        else:
            if at_dock:
                self.battery += AppConfig.BATTERY_CHARGE_RATE * time.dt
                if self.battery >= AppConfig.BATTERY_RECHARGE_TARGET:
                    self.is_charging_session = False
            else:
                self.battery -= AppConfig.BATTERY_DRAIN_PASSIVE * time.dt
        self.battery = clamp(self.battery, 0, 100)

        if self.battery < AppConfig.BATTERY_CRITICAL_THRESHOLD and self.state not in ['IDLE', 'RETURNING', 'WAITING_PICKUP', 'WAITING_DROP']:
            cloud_logger.publish_event(self.robot_id, "CRITICAL_BATTERY", {"battery": round(self.battery, 1)})
            self.is_charging_session = True
            if self.current_task:
                task = self.current_task
                if self.cargo:
                    task['pickup_pos'] = self.position
                    if 'pickup_ent' in task and task['pickup_ent'] and not task['pickup_ent'].is_empty():
                        task['pickup_ent'].position = (self.x, 0, self.z)
                        task['pickup_ent'].visible = True
                        task['pickup_ent'].marker.enabled = True
                        self.cargo.parent = task['pickup_ent']
                        self.cargo.position = (0, 0.5, 0)
                        self.cargo.scale = AppConfig.CARGO_FLOOR_SCALE
                    self.manager.update_file_grid(self.position, task['pickup_char'])
                    self.cargo = None
                else:
                    if 'pickup_ent' in task and task['pickup_ent'] and not task['pickup_ent'].is_empty():
                        task['pickup_ent'].visible = True
                if task in self.manager.active_tasks: self.manager.active_tasks.remove(task)
                self.manager.unassigned_tasks.append(task)
                self.current_task = None
            self.start_return_home_phase()

        if self.battery < AppConfig.BATTERY_LOW_THRESHOLD and self.state == 'IDLE' and not at_dock:
            self.is_charging_session = True
            self.start_return_home_phase()

        if self.state == 'RETURNING' and self.home_pos:
            best_dock = self.manager.get_nearest_unoccupied_dock(self)
            if best_dock != self.home_pos:
                if best_dock:
                    self.home_pos = best_dock
                    start = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
                    robot_positions = [(int(round(r.x / AppConfig.CELL_SCALE[0])), int(round(r.z / AppConfig.CELL_SCALE[2]))) for r in self.manager.robots]
                    self.current_path = self.manager.pathfinder.find_path(start, self.home_pos, robot_positions=robot_positions)
                else:
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

        dock_blocked, dock_threat = self.handle_dock_area_traffic()
        if dock_blocked:
            return

        look_ahead = 5
        my_path_segment = self.current_path[:look_ahead]
        blocked = False
        threat = None
        self.alt_path = [] 

        for other in self.manager.robots:
            if other == self: continue
            other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2])))
            other_path_segment = other.current_path[:look_ahead]
            if other.state in ['TO_PICKUP', 'TO_DROP', 'RETURNING'] and other.current_path:
                dest = other.current_path[-1]
                if dest in my_path_segment:
                    if not self.alt_path:
                        is_lower_priority = (self.priority < other.priority or (self.priority == other.priority and self.robot_id > other.robot_id))
                        if is_lower_priority:
                            dx, dz = dest
                            avoid_zone = []
                            for ox in range(-1, 2):
                                for oz in range(-1, 2):
                                    avoid_zone.append((dx + ox, dz + oz))
                            self.alt_path = self.repath_around_obstacles(extra_avoid=avoid_zone)

            if my_grid in other_path_segment[:3]:
                if other.priority > self.priority or (other.priority == self.priority and other.robot_id < self.robot_id):
                    blocked = True
                    threat = other
                    break

            collision_cell = None
            if other_grid in my_path_segment:
                collision_cell = other_grid
            else:
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
            is_higher_priority = (self.priority > threat.priority or (self.priority == threat.priority and self.robot_id < threat.robot_id))
            if not is_higher_priority:
                new_path = self.alt_path if self.alt_path else self.repath_around_obstacles()
                if new_path: self.current_path = new_path
            else:
                self.waiting_timer = 0.5
                return

        next_grid_pos = self.current_path[0]
        if next_grid_pos == my_grid and len(self.current_path) > 1:
            self.current_path.pop(0)
            next_grid_pos = self.current_path[0]
        world_target = Vec3(next_grid_pos[0] * AppConfig.CELL_SCALE[0], 0, next_grid_pos[1] * AppConfig.CELL_SCALE[2])
        
        hard_stop = False
        threat = None
        for other in self.manager.robots:
            if other == self: continue
            dist = distance(self.position, other.position)
            if dist < AppConfig.HARD_COLLISION_DISTANCE * 1.5:
                if self.near_miss_cooldown <= 0:
                    cloud_logger.publish_event(self.robot_id, "NEAR_MISS", {"with": other.robot_id, "dist": round(dist, 2)})
                    self.near_miss_cooldown = 3.0
            if dist < AppConfig.HARD_COLLISION_DISTANCE:
                hard_stop = True
                threat = other
                break
        
        if self.near_miss_cooldown > 0: self.near_miss_cooldown -= time.dt
        
        if is_flying_highway:
            target_speed = AppConfig.HIGHWAY_SPEED
        elif is_normal_highway:
            target_speed = AppConfig.MIDDLE_CORRIDOR_SPEED
        else:
            target_speed = AppConfig.ROBOT_MOVE_SPEED

        if hard_stop:
            target_speed = 0
            self.zero_speed_timer += time.dt
            is_slave = (self.priority < threat.priority or (self.priority == threat.priority and self.robot_id > threat.robot_id))
            if is_slave and self.zero_speed_timer > 1.0:
                self.backoff_timer = 1.5
                self.zero_speed_timer = 0
                tx, tz = int(round(threat.x / AppConfig.CELL_SCALE[0])), int(round(threat.z / AppConfig.CELL_SCALE[2]))
                avoid_zone = []
                for dx in range(-1, 2):
                    for dz in range(-1, 2):
                        avoid_zone.append((tx + dx, tz + dz))
                self.deadlock_zone = avoid_zone
            elif not is_slave and self.zero_speed_timer > 0.6:
                new_path = self.repath_around_obstacles()
                if new_path: self.current_path = new_path
                self.zero_speed_timer = 0
        else:
            self.zero_speed_timer = 0
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
                            if other.state in ['WAITING_PICKUP', 'WAITING_DROP'] and self.current_path:
                                print(f"Robot {self.robot_id} proactive evasion around stationary Robot {other.robot_id}")
                                new_path = self.repath_around_obstacles()
                                if new_path: 
                                    self.current_path = new_path
                                    self.braking_timer = 0
                                    self.waiting_timer = 0
                                    obstacle_in_path = False 
                                    continue
                            heading_match = False
                            if len(other.current_path) > 0 and len(self.current_path) > 0:
                                my_vec = (self.current_path[0][0] - my_grid[0], self.current_path[0][1] - my_grid[1])
                                other_vec = (other.current_path[0][0] - other_grid[0], other.current_path[0][1] - other_grid[1])
                                if my_vec == other_vec: heading_match = True
                            if heading_match and other.current_speed > 0.1:
                                target_speed = min(target_speed, other.current_speed)
                            else:
                                my_threshold = 0.6 + (self.robot_id % 4) * 0.2
                                if self.braking_timer < 0.4:
                                    self.braking_timer += time.dt
                                    speed_factor = clamp(dist_to_other / safety_dist, AppConfig.ROBOT_MIN_SPEED_FACTOR, 1.0)
                                    target_speed *= speed_factor
                                elif self.waiting_timer < my_threshold:
                                    self.waiting_timer += time.dt
                                    target_speed = 0
                                    if self.waiting_timer >= my_threshold:
                                        is_slave = (self.priority < other.priority or (self.priority == other.priority and self.robot_id > other.robot_id))
                                        if is_slave:
                                            tx, tz = int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2]))
                                            avoid_3x3 = []
                                            for dx in range(-1, 2):
                                                for dz in range(-1, 2):
                                                    avoid_3x3.append((tx + dx, tz + dz))
                                            new_path = self.repath_around_obstacles(extra_avoid=avoid_3x3)
                                        else:
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

        dist_to_target = distance(self.position, world_target)
        if dist_to_target > 0.05:
            target_rot_y = atan2(world_target.x - self.x, world_target.z - self.z) * 180 / pi
            angle_diff = abs(self.rotation_y - target_rot_y) % 360
            if angle_diff > 180: angle_diff = 360 - angle_diff
            if angle_diff > 1.0 or dist_to_target > 0.5:
                self.rotation_y = lerp_angle(self.rotation_y, target_rot_y, time.dt * AppConfig.ROBOT_ROTATION_SPEED)
        
        if target_speed == 0 and self.dock_wait_timer <= 0:
            self.total_wait_timer += time.dt
            conflict_threat = None
            if len(self.current_path) > 0:
                next_cell = self.current_path[0]
                for other in self.manager.robots:
                    if other == self: continue
                    other_grid = (int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2])))
                    if other_grid == next_cell:
                        conflict_threat = other
                        break
            if self.total_wait_timer > 4.5:
                if conflict_threat:
                    is_slave = (self.priority < conflict_threat.priority or (self.priority == conflict_threat.priority and self.robot_id > conflict_threat.robot_id))
                    if is_slave:
                        print(f"SECURITY RESET: Robot {self.robot_id} (Slave) performing emergency reroute around {conflict_threat.robot_id}")
                        self.current_path = [] 
                        tx, tz = int(round(conflict_threat.x / AppConfig.CELL_SCALE[0])), int(round(conflict_threat.z / AppConfig.CELL_SCALE[2]))
                        avoid_3x3 = []
                        for dx in range(-1, 2):
                            for dz in range(-1, 2):
                                avoid_3x3.append((tx + dx, tz + dz))
                        new_path = self.repath_around_obstacles(extra_avoid=avoid_3x3)
                        if new_path: self.current_path = new_path
                    else:
                        print(f"SECURITY HOLD: Robot {self.robot_id} (Master) waiting for area to clear...")
                        self.current_path = self.repath_around_obstacles()
                else:
                    new_path = self.repath_around_obstacles()
                    if new_path: self.current_path = new_path
                self.total_wait_timer = 0
                self.braking_timer = 0
                self.waiting_timer = 0
                self.zero_speed_timer = 0
        else:
            self.total_wait_timer = 0

        accel_rate = 4.0
        if self.current_speed < target_speed:
            self.current_speed = min(target_speed, self.current_speed + accel_rate * time.dt)
        else:
            self.current_speed = max(target_speed, self.current_speed - accel_rate * 2.0 * time.dt)

        move_step = self.current_speed * time.dt
        if dist_to_target > move_step and dist_to_target > 0.01:
            self.position += self.forward * move_step
        else:
            old_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
            self.position = world_target
            if self.current_path:
                new_grid = self.current_path.pop(0)
                cloud_logger.register_cell_transition(self.robot_id, old_grid, new_grid)
            if not self.current_path:
                self.on_reach_target()

    def on_reach_target(self):
        if self.state == 'TO_PICKUP':
            print(f"Robot {self.robot_id} REACHED PICKUP {self.current_task['pickup_char']}. Loading Cargo...")
            self.state = 'WAITING_PICKUP'
            self.wait_timer = AppConfig.ROBOT_WAIT_TIME
            task = self.current_task
            if 'pickup_ent' in task:
                self.cargo = task['pickup_ent'].cargo
                self.cargo.parent = self
                self.cargo.position = (AppConfig.CARGO_TRUCK_X_OFFSET, 0, AppConfig.CARGO_TRUCK_Z_OFFSET - 1.2) 
                self.cargo.animate_position((AppConfig.CARGO_TRUCK_X_OFFSET, AppConfig.CARGO_TRUCK_Y_POS, AppConfig.CARGO_TRUCK_Z_OFFSET), 
                                            duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
                self.cargo.animate_scale(AppConfig.CARGO_TRUCK_SCALE, 
                                         duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
                task['pickup_ent'].marker.enabled = False
        elif self.state == 'TO_DROP':
            print(f"Robot {self.robot_id} REACHED DROP {self.current_task['drop_char']}. Unloading Cargo...")
            self.state = 'WAITING_DROP'
            self.wait_timer = AppConfig.ROBOT_WAIT_TIME
            if self.cargo:
                self.cargo.animate_position((AppConfig.CARGO_TRUCK_X_OFFSET, 0, AppConfig.CARGO_TRUCK_Z_OFFSET - 1.5), 
                                            duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
                self.cargo.animate_scale(AppConfig.CARGO_FLOOR_SCALE, 
                                         duration=AppConfig.CARGO_ANIM_DURATION, curve=AppConfig.CARGO_ANIM_CURVE)
            self.manager.complete_task(self.current_task)
        elif self.state == 'RETURNING':
            print(f"Robot {self.robot_id} PARKED at home {self.home_pos}")
            self.state = 'IDLE'
            if self.cargo:
                destroy(self.cargo)
                self.cargo = None

    def start_drop_off_phase(self):
        robot_positions = []
        extra_avoid = self.apply_harmony_security() # Radius 2 Harmony
        my_grid = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        for other in self.manager.robots:
            robot_positions.append((int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2]))))

        print(f"Robot {self.robot_id} moving to DROP {self.current_task['drop_char']} (Harmony Active)")
        self.state = 'TO_DROP'
        start = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
        goal = (int(round(self.current_task['drop_pos'][0] / AppConfig.CELL_SCALE[0])), 
                int(round(self.current_task['drop_pos'][2] / AppConfig.CELL_SCALE[2])))
        self.current_path = self.manager.pathfinder.find_path(start, goal, avoid=extra_avoid, robot_positions=robot_positions)

    def start_return_home_phase(self):
        robot_positions = []
        extra_avoid = self.apply_harmony_security() # Radius 2 Harmony
        for other in self.manager.robots:
            robot_positions.append((int(round(other.x / AppConfig.CELL_SCALE[0])), int(round(other.z / AppConfig.CELL_SCALE[2]))))

        if self.battery < AppConfig.BATTERY_LOW_THRESHOLD:
            self.is_charging_session = True
        if not self.is_charging_session and self.battery >= AppConfig.BATTERY_LOW_THRESHOLD and self.manager.unassigned_tasks:
            self.manager.unassigned_tasks.sort(key=lambda t: distance(self.position, t['pickup_pos']))
            task = self.manager.unassigned_tasks.pop(0)
            self.manager.active_tasks.append(task)
            self.manager.assign_task_to_robot(self, task)
            return
        nearest_dock_grid = self.manager.get_nearest_unoccupied_dock(self.position)
        if nearest_dock_grid:
            self.home_pos = nearest_dock_grid
            print(f"Robot {self.robot_id} returning to nearest dock at {self.home_pos} (Harmony Active)")
            self.state = 'RETURNING'
            start = (int(round(self.x / AppConfig.CELL_SCALE[0])), int(round(self.z / AppConfig.CELL_SCALE[2])))
            self.current_path = self.manager.pathfinder.find_path(start, self.home_pos, avoid=extra_avoid, robot_positions=robot_positions)
            self.current_task = None
        else:
            print(f"Robot {self.robot_id} - No available docks found!")
            self.state = 'IDLE'

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import os
import shutil

from core.config import AppConfig
from entities.dock import ChargingDock
from entities.robot import Robot
from core.simulation import TaskSystem
from core.ui import TopDownCamera, CameraManager, FleetHUD

# ==========================================
# CINEMATIC CAMERA
# ==========================================

class CinematicMode(Entity):
    def __init__(self, player, top_down_camera):
        super().__init__()
        self.player = player
        self.top_down_camera = top_down_camera
        
        self.is_active = False
        self.is_smooth = False
        self.sensitivity = 1.0  # Default sensitivity (speed multiplier)
        
        # Track UI elements we hide so we can show them again
        self.hidden_ui_elements = []
        
        # Values for smooth movement
        self.target_position = None
        self.target_rotation = None
        self.smooth_speed = 2.0
        
        # Black bars for cinematic ratio
        self.bars = Entity(parent=camera.ui, enabled=False)
        self.top_bar = Entity(parent=self.bars, model='quad', color=color.black, scale=(2, 0.3), y=0.45, z=-1)
        self.bot_bar = Entity(parent=self.bars, model='quad', color=color.black, scale=(2, 0.3), y=-0.45, z=-1)

    def input(self, key):
        if key == 'c':
            self.toggle()
        
        if self.is_active:
            # Toggle Cinematic Aspect Ratio (Bars)
            if key == 'v':
                self.bars.enabled = not self.bars.enabled
                print(f"Cinematic Bars: {'ON' if self.bars.enabled else 'OFF'}")

            # Toggle Smoothing
            if key == 'n':
                self.is_smooth = not self.is_smooth
                # Reset targets to current to prevent snapping
                if self.is_smooth:
                    self.target_position = camera.position
                    self.target_rotation = camera.rotation
                print(f"Cinematic Smoothing: {'ON' if self.is_smooth else 'OFF'}")
            
            # Sensitivity Controls (Arrows + Scroll)
            if key == 'up arrow' or key == 'scroll up':
                self.sensitivity += 0.1
                print(f"Cinematic Sensitivity: {self.sensitivity:.1f}x")

            if key == 'down arrow' or key == 'scroll down':
                self.sensitivity = max(0.1, self.sensitivity - 0.1)
                print(f"Cinematic Sensitivity: {self.sensitivity:.1f}x")

    def toggle(self):
        self.is_active = not self.is_active
        
        if self.is_active:
            # Enable Cinematic Mode
            self.player.enabled = False
            self.top_down_camera.enabled = False
            
            # Hide all current UI elements (except our bars)
            self.hidden_ui_elements = []
            for e in camera.ui.children:
                if e != self.bars and e.enabled:
                    self.hidden_ui_elements.append(e)
                    e.enabled = False
            
            self.bars.enabled = True
            
            # Setup initial state
            self.is_smooth = False
            mouse.locked = True
            mouse.visible = False
            
        else:
            # Disable Cinematic Mode
            self.bars.enabled = False
            
            # Restore the UI elements we hid
            for e in self.hidden_ui_elements:
                e.enabled = True
            self.hidden_ui_elements = []
            
            self.player.enabled = True
            
            # Reset mouse state to config
            self.player.cursor.visible = AppConfig.MOUSE_VISIBLE
            # Ensure mouse is locked if player controller needs it (FirstPersonController usually does)
            mouse.locked = True 

    def update(self):
        if not self.is_active:
            return

        # --- Rotation ---
        # Get mouse movement and apply sensitivity
        rot_x = mouse.velocity[1] * 40 * self.sensitivity
        rot_y = mouse.velocity[0] * 40 * self.sensitivity
        
        # --- Movement ---
        # Calculate direction based on camera facing
        direction = Vec3(0,0,0)
        
        # Flatten vectors for XZ plane movement (Safe normalization)
        temp_forward = Vec3(camera.forward.x, 0, camera.forward.z)
        forward_xz = temp_forward.normalized() if temp_forward.length() > 0.001 else Vec3(0,0,0)
        
        temp_right = Vec3(camera.right.x, 0, camera.right.z)
        right_xz = temp_right.normalized() if temp_right.length() > 0.001 else Vec3(0,0,0)
        
        # WASD - Plane movement (XZ only)
        if held_keys['w']: direction += forward_xz
        if held_keys['s']: direction -= forward_xz
        if held_keys['d']: direction += right_xz
        if held_keys['a']: direction -= right_xz
        
        # Space/Shift - Vertical movement (World Up/Down)
        if held_keys['space']: direction += Vec3(0, 1, 0)
        if held_keys['shift']: direction -= Vec3(0, 1, 0)

        # Apply speed and sensitivity
        speed = 15 * time.dt * self.sensitivity

        if self.is_smooth:
            # --- Cinematic Smoothing Logic ---
            # Update target position/rotation
            self.target_position += direction * speed
            self.target_rotation += Vec3(-rot_x, rot_y, 0)
            
            # Lerp camera towards target
            camera.position = lerp(camera.position, self.target_position, time.dt * self.smooth_speed)
            camera.rotation = lerp(camera.rotation, self.target_rotation, time.dt * self.smooth_speed)
        else:
            # --- Direct Control ---
            camera.position += direction * speed
            camera.rotation_x -= rot_x
            camera.rotation_y += rot_y

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
    # We create the HUD, but we don't need to pass it to CinematicMode anymore
    FleetHUD(robots=robots, task_system=ts)

    # Initialize Cinematic Mode
    CinematicMode(player, top_down_camera)

    app.run()

if __name__ == "__main__":
    main()
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
    window.borderless = False
    window.fullscreen = False
    window.size = (window.fullscreen_size.y, window.fullscreen_size.y)
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
    app.run()

if __name__ == "__main__":
    main()

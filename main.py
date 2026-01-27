from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
from core.fleet_manager import FleetManager

# Inside your main() or as a global
fleet = FleetManager()

# ==========================================
# CONFIGURATION SECTION
# Modify these values to change the simulation settings
# ==========================================
class AppConfig:
    # Files
    LAYOUT_FILE = 'warehouse_layout.txt'
    ROBOT_MODEL_FILE = 'models/truckF.obj'
    ROBOT_TEXTURE_FILE = 'textures/truck.png'
    DOCK_MODEL_FILE = 'models/dock.glb'
    SHELF_MODEL_FILE = ['models/shelf1.fbx', 'models/shelf3.fbx']
    SHELF_TEXTURE_FILE = 'textures/shelf.png'
    FLOOR_TEXTURE_FILE = 'white_cube'
    
    # Grid Settings
    DEFAULT_WIDTH = 25
    DEFAULT_HEIGHT = 25
    CELL_SCALE = (2, 2, 2)
    
    # Floor Settings
    FLOOR_Y_POS = -1
    FLOOR_COLOR_A = color.white
    
    # Map Characters
    OBSTACLE_CHAR = 'X'
    DOCK_CHAR = '#'
    ROBOT_CHAR = 'T'
    
    # Obstacle Settings
    OBSTACLE_COLOR = color.white 
    OBSTACLE_Y_POS = 0 
    OBSTACLE_SCALE = (0.007, 0.007, 0.007) 
    
    # Robot Settings
    ROBOT_SCALE = (0.7, 0.7, 0.7) 
    ROBOT_COLOR = color.white 

    # Charging Dock Settings
    DOCK_COLOR = color.white
    DOCK_SCALE = (0.05, 0.05, 0.05) 
    
    # Special Tags / Pairings
    PAIRINGS = [] 
    
    # Optimization
    CULLING_DISTANCE = 40 

    # Player Settings
    PLAYER_START_HEIGHT = 10
    PLAYER_START_OFFSET_Z = -20 
    MOUSE_VISIBLE = False

# ==========================================
# CLASSES
# ==========================================

class CullingSystem(Entity):
    def __init__(self, target, items_parent, distance=50, **kwargs):
        super().__init__(**kwargs)
        self.target = target 
        self.items_parent = items_parent 
        self.distance = distance
        self.distance_sq = distance * distance 
        self.update_interval = 0.1 
        self.timer = 0

    def update(self):
        self.timer += time.dt
        if self.timer < self.update_interval:
            return
        self.timer = 0
        
        target_pos_x = self.target.x
        target_pos_z = self.target.z
        
        for item in self.items_parent.children:
            dx = item.x - target_pos_x
            dz = item.z - target_pos_z
            dist_sq = dx*dx + dz*dz
            
            should_be_enabled = dist_sq < self.distance_sq
            
            if item.enabled != should_be_enabled:
                item.enabled = should_be_enabled

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
        self.tag = f"Pair_Color_{pair_color.name}" if hasattr(pair_color, 'name') else f"Pair_{index}"
        self.name = f"Dock_{index}"
        
        if not self.model:
            print(f"Warning: Model '{AppConfig.DOCK_MODEL_FILE}' not found. Using fallback.")
            self.model = 'cube'
            self.scale = (1.8, 0.1, 1.8)
            self.color = color.green

class Robot(Entity):
    def __init__(self, index, world_x, world_z, pair_color, **kwargs):
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
        self.assigned_dock_id = index 
        self.tag = f"Pair_Color_{pair_color.name}" if hasattr(pair_color, 'name') else f"Pair_{index}"
        self.name = f"Robot_{index}"
        
        if not self.model:
            self.model = 'cube'
            self.color = color.blue
            self.scale = (1, 1, 1)

    def update(self):
        pass

# ==========================================
# MAIN APPLICATION
# ==========================================

def load_grid(filename):
    """Loads the grid layout from a file."""
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print(f"Error: {filename} not found. Using default empty grid.")
        return ["." * AppConfig.DEFAULT_WIDTH for _ in range(AppConfig.DEFAULT_HEIGHT)]

def parse_map_and_spawn(grid):
    """
    Parses the grid to:
    1. Create the visual environment (Floor, Shelves).
    2. Identify spawn points for Robots and Docks.
    3. Spawn and pair Robots and Docks.
    """
    height = len(grid)
    width = len(grid[0]) if height > 0 else 0
    scale_x = AppConfig.CELL_SCALE[0]
    scale_z = AppConfig.CELL_SCALE[2]
    
    floor_parent = Entity(name='floor_parent')
    
    dock_locations = []
    robot_locations = []

    print(f"Parsing map {width}x{height}...")

    for z in range(height):
        for x in range(width):
            char = grid[z][x]
            
            # Calculate World Position
            world_x = x * scale_x
            world_z = z * scale_z
            
            # Spawn Shelves
            if char == AppConfig.OBSTACLE_CHAR:
                Entity(
                    parent=floor_parent,
                    model=AppConfig.SHELF_MODEL_FILE[random.randint(0, len(AppConfig.SHELF_MODEL_FILE)-1)],
                    texture=AppConfig.SHELF_TEXTURE_FILE, 
                    double_sided=True,
                    color=AppConfig.OBSTACLE_COLOR,
                    position=(world_x, AppConfig.OBSTACLE_Y_POS, world_z),
                    scale=AppConfig.OBSTACLE_SCALE,
                    rotation_y=90
                )
            
            # Record Dock Locations
            elif char == AppConfig.DOCK_CHAR:
                dock_locations.append((world_x, world_z))
                
            # Record Robot Locations
            elif char == AppConfig.ROBOT_CHAR:
                robot_locations.append((world_x, world_z))

    # Spawn Giant Floor
    Entity(
        model='cube',
        position=((width-1)*scale_x/2, AppConfig.FLOOR_Y_POS, (height-1)*scale_z/2),
        scale=(width * scale_x, AppConfig.CELL_SCALE[1], height * scale_z),
        texture=AppConfig.FLOOR_TEXTURE_FILE,
        texture_scale=(width, height),
        color=AppConfig.FLOOR_COLOR_A,
        collider='box',
        visible=True
    )
    
    # --- Spawn and Pair Robots & Docks ---
    robots = []
    docks = []
    AppConfig.PAIRINGS = []
    
    pair_colors = [color.red, color.green, color.blue, color.yellow, color.cyan, color.magenta, color.orange, color.azure]

    # We pair them based on the order they were found (reading order: top-left to bottom-right)
    count = min(len(dock_locations), len(robot_locations))
    
    print("\n" + "="*40)
    print(f"FOUND {len(dock_locations)} Docks and {len(robot_locations)} Robots. Spawning {count} pairs.")
    print("="*40)

    for i in range(count):
        dock_pos = dock_locations[i]
        robot_pos = robot_locations[i]
        current_pair_color = pair_colors[i % len(pair_colors)]
        
        # Spawn Dock
        dock = ChargingDock(
            index=i, 
            world_x=dock_pos[0], 
            world_z=dock_pos[1], 
            assigned_robot_id=i, 
            pair_color=current_pair_color
        )
        docks.append(dock)

        # Spawn Robot
        robot = Robot(
            index=i, 
            world_x=robot_pos[0], 
            world_z=robot_pos[1], 
            pair_color=current_pair_color
        )
        robots.append(robot)

        pair_info = {'color': current_pair_color.name, 'robot': robot.name, 'dock': dock.name}
        AppConfig.PAIRINGS.append(pair_info)
        print(f"PAIR {i}: Color={current_pair_color.name} | {robot.name} at {robot.position} <---> {dock.name} at {dock.position}")

    print("="*40 + "\n")

    return width, height, floor_parent

def main():
    app = Ursina()

    grid = load_grid(AppConfig.LAYOUT_FILE)
    
    # New combined function
    width, height, floor_parent = parse_map_and_spawn(grid)

    scale_x, scale_z = AppConfig.CELL_SCALE[0], AppConfig.CELL_SCALE[2]
    center_x, center_z = (width / 2) * scale_x, (height / 2) * scale_z
    
    player = FirstPersonController()
    player.position = (center_x, AppConfig.PLAYER_START_HEIGHT, center_z + AppConfig.PLAYER_START_OFFSET_Z)
    player.cursor.visible = AppConfig.MOUSE_VISIBLE

    CullingSystem(target=player, items_parent=floor_parent, distance=AppConfig.CULLING_DISTANCE)

    app.run()

if __name__ == "__main__":
    main()
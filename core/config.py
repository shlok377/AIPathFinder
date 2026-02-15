from ursina import color, curve

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
    FLOOR_COLOR_A = color.gray
    
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
    ROBOT_MOVE_SPEED = 5.0
    ROBOT_ROTATION_SPEED = 10
    ROBOT_WAIT_TIME = 1.75

    # Highway Physics & Economy
    HIGHWAY_SPEED = 7.0          # 2 higher than normal (5+2)
    MIDDLE_CORRIDOR_SPEED = 6.0  # Medium speed
    HIGHWAY_DRAIN_MOVE = 2.0     # 1 higher than normal drain (1+1)
    
    # Highway Geography
    # Extreme columns (0,1 and width-2, width-1) and extreme end row (height-1, height-2)
    # Middle columns (dependent on width)
    # Absolute middle(if the no of rows are odd) on middle two columns(if the no of rows are even)
    # These highways will be 2 blocks wide, one lane for going up and one lane for going down.
    
    HIGHWAY_MISUSE_PENALTY = 50.0 # Cost added to side highways for short, non-charging trips

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
    BATTERY_LOW_THRESHOLD = 27.0 # Refuse new tasks below this
    BATTERY_RECHARGE_TARGET = 80.0 # Stay at dock until this level
    BATTERY_CRITICAL_THRESHOLD = 13.0 # Forced return below this
    CHARGING_DISTANCE = 3.5      # Distance to dock to allow charging (increased for front-parking)
    HARD_COLLISION_DISTANCE = 1.4 # Minimum physical distance allowed between robot centers
    ROBOT_BRAKING_SENSITIVITY = 3.5 # Multiplier for distance to start slowing down
    ROBOT_MIN_SPEED_FACTOR = 0.02 # Minimum speed factor while slowing down (0.02 = 2%)

    # Dock/Parking Area Settings
    DOCK_ZONE_THRESHOLD = 3      # Distance (in grid cells) to consider as "docking area"
    PARKING_LANE_Z = 1           # Grid Z coordinate for parking spots (in front of docks at Z=0)

    # Highway System (City Traffic Model)
    # These grid coordinates have reduced traversal costs to encourage "Highway" use
    HIGHWAY_Z = [3, 12, 22]      # Main East-West corridors
    HIGHWAY_X = [2, 19, 37]      # Main North-South corridors
    HIGHWAY_COST_DISCOUNT = 0.7  # Multiplier for movement cost on highways (lower is cheaper)
    
    # Lazy Re-planning Settings
    LAZY_REPLAN_THRESHOLD = 10.0 # Wait up to 10 seconds before generating a massive detour

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

    # Auto-Spawner Settings
    SPAWNER_KEY = 'p'
    SPAWNER_FILL_PERCENT = 0.6
    SPAWNER_RESTRICTED_ROWS = 3
    SPAWNER_PICKUP_DELAY = 0.2
    SPAWNER_PAIR_DELAY = 1.0

# Legacy/Shared Constants
LAYOUT_FILE = AppConfig.LAYOUT_FILE
CHAR_EMPTY = '.'
CHAR_OBSTACLE = AppConfig.OBSTACLE_CHAR
CHAR_ROBOT = AppConfig.ROBOT_CHAR
CHAR_CHARGER = AppConfig.DOCK_CHAR
CHAR_TARGET = AppConfig.DROP_CHAR
CHAR_PICKUP = AppConfig.PICKUP_CHAR

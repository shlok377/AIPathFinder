# core/config.py
LAYOUT_FILE = 'warehouse_layout.txt'
CHAR_EMPTY = '.'
CHAR_OBSTACLE = 'X'
CHAR_ROBOT = 'T'
CHAR_CHARGER = '#'
CHAR_TARGET = '@'
CHAR_PICKUP = '$'  # Feature 4
# core/config.py # 
STOP_DURATION = 5  # Seconds to wait at checkpoint
# core/config.py
CHAR_PACKAGE = '$'  # Using $ as the pickup/package location [cite: 1]
CHAR_DELIVERY = '@' # Delivery/Target location [cite: 1]

# Battery Settings
INITIAL_BATTERY = 100.0
BATTERY_DRAIN_PER_TILE = 2.0  # % used per move 
FAST_CHARGE_RATE = 10.0       # % gained per second when near charger 
BATTERY_RESERVE_THRESHOLD = 15.0 # Minimum battery to stay safe
from ursina import *
import random
import datetime

app = Ursina()
window.color = color.black
window.title = "Google Cloud Robotics: Mission Control"

# ==========================================
# 🎨 THEME
# ==========================================
theme = {
    'bg': color.rgba(30, 32, 38, 255),
    'panel_bg': color.rgba(255, 255, 255, 10),
    'accent': color.hex("#4285F4"),
    'success': color.hex("#0F9D58"),
    'warning': color.hex("#F4B400"),
    'danger': color.hex("#DB4437"),
    'text_main': color.white,
    'text_sub': color.gray
}
Text.default_font = 'VeraMono.ttf'

# ==========================================
# 🧱 LAYOUT: RIGHT SIDEBAR
# ==========================================
sidebar = Entity(parent=camera.ui, model='quad', color=theme['bg'], scale=(0.7, 1), position=(0.65, 0), z=5)
Entity(parent=sidebar, model='quad', color=theme['accent'], scale=(0.015, 1), position=(-0.505, 0))

# ==========================================
# 1️⃣ TOP SECTION: WORKFLOW & UTILIZATION
# ==========================================
top_section = Entity(parent=sidebar, model='quad', color=color.clear, scale=(0.9, 0.15), position=(0, 0.42))
Text(text="WORKFLOW EFFICIENCY", parent=top_section, scale=1.2, y=0.4, x=-0.45, color=theme['text_sub'])
val_workflow = Text(text="84%", parent=top_section, scale=4, y=-0.1, x=-0.45, color=theme['success'])
Text(text="FLEET UTILIZATION", parent=top_section, scale=1.2, y=0.4, x=0.1, color=theme['text_sub'])
Entity(parent=top_section, model='quad', color=color.black, scale=(0.4, 0.15), position=(0.3, 0))
bar_util = Entity(parent=top_section, model='quad', color=theme['accent'], scale=(0.3, 0.15), position=(0.25, 0))
Text(text="75%", parent=bar_util, scale=5, origin=(0,0), color=color.white, z=-1)

# ==========================================
# 2️⃣ MIDDLE SECTION: KPI GRID
# ==========================================
kpi_grid = Entity(parent=sidebar, model='quad', color=color.clear, scale=(0.9, 0.25), position=(0, 0.2))
def create_mini_card(parent, title, unit, x, y, col):
    card = Entity(parent=parent, model='quad', color=theme['panel_bg'], scale=(0.48, 0.45), position=(x, y))
    Text(text=title, parent=card, scale=1.5, x=-0.45, y=0.35, color=theme['text_sub'])
    val = Text(text="0", parent=card, scale=4, x=-0.4, y=-0.1, color=col)
    Text(text=unit, parent=card, scale=1.2, x=0.45, y=-0.35, origin=(0.5,0), color=theme['text_sub'])
    return val
val_near_miss = create_mini_card(kpi_grid, "NEAR MISSES", "Events", -0.25, 0.25, theme['warning'])
val_energy = create_mini_card(kpi_grid, "ENERGY USED", "kWh", 0.25, 0.25, theme['text_main'])
val_conflicts = create_mini_card(kpi_grid, "CONFLICTS", "Hotspots", -0.25, -0.25, theme['danger'])
val_efficiency = create_mini_card(kpi_grid, "EFFICIENCY", "kWh/Job", 0.25, -0.25, theme['success'])

# ==========================================
# 3️⃣ HEARTBEAT SECTION: LIVE FLEET TABLE
# ==========================================
table_section = Entity(parent=sidebar, model='quad', color=theme['panel_bg'], scale=(0.92, 0.25), position=(0, -0.08))
headers = ["ID", "STATE", "BATT %", "TASK", "ETA"]
for i, h in enumerate(headers):
    Text(text=h, parent=table_section, scale=1.5, y=0.4, x=-0.46 + (i*0.23), color=theme['accent'])
robot_uis = {}
for i, rid in enumerate(['A', 'B', 'C', 'D']):
    y = 0.2 - (i * 0.22)
    if i % 2 == 0: Entity(parent=table_section, model='quad', color=color.rgba(255,255,255,10), scale=(1, 0.2), position=(0, y))
    Text(text=rid, parent=table_section, scale=2, y=y, x=-0.46, origin=(0,0))
    t_state = Text(text="IDLE", parent=table_section, scale=1.3, y=y, x=-0.23, origin=(0,0))
    Entity(parent=table_section, model='quad', color=color.black, scale=(0.15, 0.1), position=(0, y))
    fill_bat = Entity(parent=table_section, model='quad', color=theme['success'], scale=(0.15, 0.1), position=(0, y))
    t_task = Text(text="-", parent=table_section, scale=1.5, y=y, x=0.23, origin=(0,0))
    t_eta = Text(text="0s", parent=table_section, scale=1.5, y=y, x=0.46, origin=(0,0))
    robot_uis[rid] = {'state': t_state, 'bar': fill_bat, 'task': t_task, 'eta': t_eta}

# ==========================================
# 4️⃣ BOTTOM SECTION: SYSTEM LOAD & ALERTS (UPDATED)
# ==========================================
bottom_section = Entity(parent=sidebar, model='quad', color=color.clear, scale=(0.9, 0.22), position=(0, -0.34))

# --- Left Side: Graph & Latency ---
left_sub = Entity(parent=bottom_section, model='quad', color=color.clear, scale=(0.6, 1), position=(-0.2, 0.1))
Text(text="THROUGHPUT TREND", parent=left_sub, scale=1.2, x=-0.45, y=0.45, color=theme['text_sub'])
graph_bg = Entity(parent=left_sub, model='quad', color=color.black, scale=(0.9, 0.4), position=(0, 0))
graph_bars = []
for i in range(10):
    bar = Entity(parent=graph_bg, model='quad', color=theme['accent'], scale=(0.08, 0.1), position=(-0.45 + (i*0.1), -0.4), origin=(0,-0.5))
    graph_bars.append(bar)
# NEW: Latency Metrics
Text(text="TASK LATENCY (Avg/Max)", parent=left_sub, scale=1.1, x=-0.45, y=-0.3, color=theme['text_sub'])
val_latency = Text(text="24s / 55s", parent=left_sub, scale=2, x=-0.45, y=-0.5, color=theme['text_main'])

# --- Right Side: Queue & Spawner ---
right_sub = Entity(parent=bottom_section, model='quad', color=color.clear, scale=(0.35, 1), position=(0.3, 0.1))
Text(text="QUEUE", parent=right_sub, scale=1.2, x=0, y=0.45, color=theme['text_sub'])
val_queue = Text(text="12", parent=right_sub, scale=4, x=0, y=0.15, origin=(0,0), color=theme['warning'])
# NEW: Spawner Status
Text(text="SPAWNER", parent=right_sub, scale=1.1, x=0, y=-0.2, color=theme['text_sub'])
val_spawner = Text(text="ACTIVE (95%)", parent=right_sub, scale=1.8, x=0, y=-0.4, origin=(0,0), color=theme['success'])

# --- Alert Box at very bottom ---
alert_box = Entity(parent=sidebar, model='quad', color=color.rgba(219,68,55,50), scale=(0.9, 0.05), position=(0, -0.47))
Text(text="🚨 ALERT:", parent=alert_box, scale=1.2, x=-0.48, y=0, origin=(-0.5, 0), color=theme['danger'])
val_alert = Text(text="System Nominal", parent=alert_box, scale=1.2, x=-0.25, y=0, origin=(-0.5, 0), color=theme['text_main'])

# ==========================================
# 🔄 DUMMY DATA GENERATOR
# ==========================================
def update():
    if random.random() < 0.1:
        for bar in graph_bars:
            bar.scale_y = lerp(bar.scale_y, random.uniform(0.1, 0.9), 0.1)
    if random.random() < 0.05:
        val_energy.text = str(round(float(val_energy.text) + 0.15, 2))
        # Simulate Latency changing
        avg = random.randint(20, 30)
        val_latency.text = f"{avg}s / {avg + random.randint(10,30)}s"
        
        if random.random() < 0.1:
            val_near_miss.text = str(int(val_near_miss.text) + 1)
            val_alert.text = f"High Latency detected on Task {random.randint(100,999)}"
            val_alert.color = theme['warning']
            invoke(reset_alert, delay=2)

    for rid, ui in robot_uis.items():
        new_bat = (ui['bar'].scale_x / 0.15) - 0.001
        if new_bat < 0: new_bat = 1.0
        ui['bar'].scale_x = new_bat * 0.15
        if new_bat < 0.2: ui['bar'].color = theme['danger']
        elif new_bat < 0.5: ui['bar'].color = theme['warning']
        else: ui['bar'].color = theme['success']
        if random.random() < 0.02:
            ui['state'].text = random.choice(["PICKUP", "DELIVER", "CHARGE", "IDLE"])
            ui['task'].text = random.choice(['a', 'b', '-', '-'])
            ui['eta'].text = f"{random.randint(5, 120)}s"

def reset_alert():
    val_alert.text = "System Nominal"
    val_alert.color = theme['text_main']

app.run()
from ursina import Entity, Panel, Text, color, camera, held_keys, time, mouse, sin
from core.config import AppConfig
from core.telemetry import cloud_logger

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
        
        # Simple Panel
        self.bg = Panel(scale=(0.4, 0.5), position=(0.78, 0.1), color=color.black66)
        self.title = Text("FLEET STATUS", parent=self.bg, origin=(0,0), y=0.45, scale=2.0, color=color.azure)
        
        self.info_texts = []
        for i in range(len(self.robots)):
            t = Text("", parent=self.bg, origin=(-0.5, 0), x=-0.45, y=0.35 - (i * 0.1), scale=1.2)
            self.info_texts.append(t)
            
        self.queue_text = Text("", parent=self.bg, origin=(0,0), y=-0.4, scale=1.5, color=color.yellow)

    def update(self):
        for i, robot in enumerate(self.robots):
            self.info_texts[i].text = f"Truck {robot.robot_id}: {robot.state} | {int(robot.battery)}%"
            self.info_texts[i].color = color.white if robot.battery > 20 else color.red

        total_pending = len(self.ts.unassigned_tasks)
        self.queue_text.text = f"Pending Tasks: {total_pending}"
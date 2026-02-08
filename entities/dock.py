from ursina import Entity, lerp, color
from core.config import AppConfig

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

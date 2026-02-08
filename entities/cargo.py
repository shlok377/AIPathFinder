from ursina import Entity, color
from core.config import AppConfig

class PickupPoint(Entity):
    def __init__(self, pos, pair_color, char, **kwargs):
        super().__init__(position=(pos[0], 0, pos[2]), **kwargs)
        
        # 1. The floor marker (remains on floor)
        self.marker = Entity(
            parent=self,
            model='cube',
            position=(0, 0.1, 0),
            scale=(1.5, 0.05, 1.5),
            color=pair_color,
            alpha=0.5
        )
        # Vertical stick for visibility
        Entity(parent=self.marker, model='cube', position=(0, 4, 0), scale=(0.2, 8, 0.2), color=pair_color, alpha=0.3)
        
        # 2. The Actual Cargo (this is what the robot will grab)
        self.cargo = Entity(
            parent=self,
            model='cube',
            position=(0, 0.5, 0),
            scale=AppConfig.CARGO_FLOOR_SCALE,
            color=pair_color,
            texture='white_cube' # Using a texture makes it look more like a box
        )
        self.task_char = char

class DropPoint(Entity):
    def __init__(self, pos, pair_color, char, **kwargs):
        super().__init__(
            model='cube',
            position=(pos[0], 0.1, pos[2]),
            scale=(1.5, 0.05, 1.5),
            color=pair_color,
            alpha=0.4,
            **kwargs
        )
        Entity(parent=self, model='cube', position=(0, 2, 0), scale=(1, 4, 1), color=pair_color, alpha=0.5)

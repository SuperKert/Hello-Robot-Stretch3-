import numpy as np

class Floor:
    def __init__(self, floor_id, name):
        self.floor_id = floor_id
        self.name = name
        self.rooms = []
        self.vertices = np.array([])
        self.min_bounds = np.array([np.inf, np.inf, np.inf])
        self.max_bounds = np.array([-np.inf, -np.inf, -np.inf])
        self.floor_zero_level = 0.0
        self.floor_height = 0.0

    def add_room(self, room):
        self.rooms.append(room)
import numpy as np

class Room:
    def __init__(self, room_id, floor_id, name):
        self.room_id = room_id
        self.floor_id = floor_id
        self.name = name
        self.objects = []
        self.vertices = np.array([])
        self.min_bounds = np.array([np.inf, np.inf, np.inf])
        self.max_bounds = np.array([-np.inf, -np.inf, -np.inf])
        self.room_zero_level = 0.0
        self.room_height = 0.0

    def add_object(self, obj):
        self.objects.append(obj)
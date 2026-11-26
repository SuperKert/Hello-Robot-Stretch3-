import numpy as np

class Object:
    def __init__(self, object_id, room_id):
        self.object_id = object_id
        self.room_id = room_id
        self.vertices = np.array([])
        self.embedding = None
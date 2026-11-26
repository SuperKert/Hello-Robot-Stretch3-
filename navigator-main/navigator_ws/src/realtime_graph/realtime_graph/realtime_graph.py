import numpy as np
import json
# Importaciones relativas (funcionan porque están en la misma carpeta)
from .floor import Floor
from .room import Room
from .object import Object

class RealTimeHOVSG:
    def __init__(self):
        # 1. ELIMINADA la dependencia de OVO. Ahora es una caja negra independiente.
        self.floors_dict = {}

    def update_graph(self, numero_mascara, centroide_objeto, numero_room, numero_floor, embedding=None):
        """
        Ahora acepta 'embedding' como argumento opcional.
        """
        punto_xyz = np.array(centroide_objeto)

        # 1. GESTIÓN DE PISO
        if numero_floor not in self.floors_dict:
            self._crear_floor(numero_floor)
        current_floor = self.floors_dict[numero_floor]

        # 2. GESTIÓN DE HABITACIÓN
        target_room_id = f"{numero_floor}_{numero_room}"
        current_room = self._obtener_o_crear_room(current_floor, target_room_id, numero_room, numero_floor)

        # 3. GESTIÓN DE OBJETO
        self._agregar_objeto(current_room, numero_mascara, punto_xyz, embedding)

        # 4. LÓGICA DE CENTROIDES
        self._actualizar_limites_nodo(current_room, punto_xyz)
        self._actualizar_limites_nodo(current_floor, current_room.min_bounds)
        self._actualizar_limites_nodo(current_floor, current_room.max_bounds)

    def get_graph_dict(self):
        """
        Devuelve el grafo entero como diccionario puro (listo para JSON/ROS).
        """
        data = {"floors": []}
        for f in self.floors_dict.values():
            f_data = {
                "id": str(f.floor_id),
                "name": f.name,
                "vertices": f.vertices.tolist() if isinstance(f.vertices, np.ndarray) else [],
                "rooms": []
            }
            for r in f.rooms:
                r_data = {
                    "id": str(r.room_id),
                    "name": r.name,
                    "vertices": r.vertices.tolist() if isinstance(r.vertices, np.ndarray) else [],
                    "objects": []
                }
                for o in r.objects:
                    o_data = {
                        "id": str(o.object_id),
                        "vertices": o.vertices.tolist() if isinstance(o.vertices, np.ndarray) else [],
                        # "embedding": o.embedding.tolist() if o.embedding is not None else []
                    }
                    r_data["objects"].append(o_data)
                f_data["rooms"].append(r_data)
            data["floors"].append(f_data)
        return data

    # --- MÉTODOS INTERNOS (Limpios) ---

    def _actualizar_limites_nodo(self, nodo, punto):
        nodo.min_bounds = np.minimum(nodo.min_bounds, punto)
        nodo.max_bounds = np.maximum(nodo.max_bounds, punto)
        nodo.vertices = np.array([nodo.min_bounds, nodo.max_bounds])

    def _crear_floor(self, floor_id):
        new_floor = Floor(floor_id=str(floor_id), name=f"floor_{floor_id}")
        new_floor.min_bounds = np.array([np.inf, np.inf, np.inf])
        new_floor.max_bounds = np.array([-np.inf, -np.inf, -np.inf])
        self.floors_dict[floor_id] = new_floor

    def _obtener_o_crear_room(self, floor, room_id, room_num, floor_num):
        for r in floor.rooms:
            if r.room_id == room_id: return r
        new_room = Room(room_id=room_id, floor_id=str(floor_num), name=f"room_{room_num}")
        new_room.min_bounds = np.array([np.inf, np.inf, np.inf])
        new_room.max_bounds = np.array([-np.inf, -np.inf, -np.inf])
        floor.add_room(new_room)
        return new_room

    def _agregar_objeto(self, room, mask_id, centroide, embedding):
        target_obj_id = str(mask_id)
        for obj in room.objects:
            if obj.object_id == target_obj_id: return

        new_object = Object(object_id=target_obj_id, room_id=room.room_id)
        if embedding is not None:
            new_object.embedding = np.array(embedding)
        new_object.vertices = np.array([centroide])
        room.add_object(new_object)
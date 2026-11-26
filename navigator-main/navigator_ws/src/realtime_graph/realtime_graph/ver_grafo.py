import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import open3d as o3d
import numpy as np

# --- CONFIGURACIÓN VISUAL ---
EJE_VERTICAL = 1  # 0=X, 1=Y, 2=Z (En Replica Y suele ser arriba)

ALTURA_ENTRE_PISOS = 4.0  # Cuánto subimos visualmente cada planta (Floor 0 -> Floor 1)
OFFSET_ROOM_NODE = 2.5  # Altura del nodo Rojo respecto al suelo de su piso
OFFSET_FLOOR_NODE = 3.5  # Altura del nodo Azul respecto al suelo de su piso


class VisualizadorROS(Node):
    def __init__(self):
        super().__init__('visualizador_3d')
        self.subscription = self.create_subscription(
            String, '/realtime_graph/full_graph', self.listener_callback, 10)
        self.latest_json = None
        self.new_data = False
        self.get_logger().info('Visualizador Jerárquico esperando datos...')

    def listener_callback(self, msg):
        try:
            self.latest_json = json.loads(msg.data)
            self.new_data = True
        except json.JSONDecodeError:
            pass


def get_center_from_vertices(vertices_list):
    """Calcula el centro de la bounding box (media de min y max)"""
    if not vertices_list or len(vertices_list) == 0:
        return np.array([0.0, 0.0, 0.0])
    arr = np.array(vertices_list)
    return np.mean(arr, axis=0)


def main():
    rclpy.init()
    ros_node = VisualizadorROS()

    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name="Grafo Jerárquico Multicapa", width=1000, height=800)
    vis.add_geometry(o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0))

    try:
        while rclpy.ok():
            rclpy.spin_once(ros_node, timeout_sec=0.01)

            if ros_node.new_data and ros_node.latest_json:
                vis.clear_geometries()
                vis.add_geometry(o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0))

                data = ros_node.latest_json

                # --- PROCESAR PISOS ---
                floors = data.get("floors", [])
                for floor in floors:
                    # 1. Calculamos la ALTURA BASE según el ID del piso (0, 1, 2...)
                    try:
                        floor_level = int(floor["id"])
                    except:
                        floor_level = 0

                    # La altura física base de este piso (ej: Piso 1 empieza en Y=4.0m)
                    y_base_piso = floor_level * ALTURA_ENTRE_PISOS

                    # Centroide de la caja del piso
                    c_f = get_center_from_vertices(floor.get("vertices", []))

                    # POSICIÓN NODO PISO (AZUL) - Flotando alto
                    pos_f = c_f.copy()
                    pos_f[EJE_VERTICAL] = y_base_piso + OFFSET_FLOOR_NODE

                    sphere_f = o3d.geometry.TriangleMesh.create_sphere(radius=0.3)
                    sphere_f.translate(pos_f)
                    sphere_f.paint_uniform_color([0, 0, 1])  # Azul
                    vis.add_geometry(sphere_f)

                    # --- PROCESAR HABITACIONES ---
                    rooms = floor.get("rooms", [])
                    for room in rooms:
                        c_r = get_center_from_vertices(room.get("vertices", []))

                        # POSICIÓN NODO ROOM (ROJO) - Flotando medio
                        pos_r = c_r.copy()
                        pos_r[EJE_VERTICAL] = y_base_piso + OFFSET_ROOM_NODE

                        sphere_r = o3d.geometry.TriangleMesh.create_sphere(radius=0.2)
                        sphere_r.translate(pos_r)
                        sphere_r.paint_uniform_color([1, 0, 0])  # Rojo
                        vis.add_geometry(sphere_r)

                        # Línea Piso -> Room
                        l = o3d.geometry.LineSet()
                        l.points = o3d.utility.Vector3dVector([pos_f, pos_r])
                        l.lines = o3d.utility.Vector2iVector([[0, 1]])
                        l.paint_uniform_color([0.7, 0.7, 0.7])
                        vis.add_geometry(l)

                        # --- PROCESAR OBJETOS ---
                        objects = room.get("objects", [])
                        for obj in objects:
                            c_o = get_center_from_vertices(obj.get("vertices", []))

                            # POSICIÓN OBJETO (VERDE)
                            # Truco: Si el simulador manda (0,0,0) para el piso 1, 
                            # aquí le sumamos la altura base para que visualmente esté arriba.
                            pos_o = c_o.copy()
                            pos_o[EJE_VERTICAL] += y_base_piso

                            sphere_o = o3d.geometry.TriangleMesh.create_sphere(radius=0.08)
                            sphere_o.translate(pos_o)
                            sphere_o.paint_uniform_color([0, 1, 0])  # Verde
                            vis.add_geometry(sphere_o)

                            # Línea Room -> Objeto
                            l2 = o3d.geometry.LineSet()
                            l2.points = o3d.utility.Vector3dVector([pos_r, pos_o])
                            l2.lines = o3d.utility.Vector2iVector([[0, 1]])
                            l2.paint_uniform_color([0.8, 0.8, 0.8])
                            vis.add_geometry(l2)

                ros_node.new_data = False

            vis.poll_events()
            vis.update_renderer()

    except KeyboardInterrupt:
        pass
    finally:
        vis.destroy_window()
        ros_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
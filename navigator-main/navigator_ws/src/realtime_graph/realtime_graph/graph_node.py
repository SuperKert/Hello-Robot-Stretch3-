import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import os  # Necesario para crear carpetas
import numpy as np
# Importamos tu clase del archivo de al lado
from .realtime_graph import RealTimeHOVSG


class HovsgNode(Node):
    def __init__(self):
        super().__init__('realtime_graph_node')

        # Inicializar tu lógica
        self.logic = RealTimeHOVSG()

        # Suscriptor: Escucha objetos nuevos (Input)
        self.subscription = self.create_subscription(
            String,
            '/realtime_graph/input_object',
            self.listener_callback,
            10
        )

        # Publicador: Envía el grafo resultante (Output)
        self.publisher_ = self.create_publisher(
            String,
            '/realtime_graph/full_graph',
            10
        )

        self.get_logger().info('Nodo RealTime Graph LISTO. Esperando JSONs...')

    def listener_callback(self, msg):
        try:
            # 1. Leer datos del mensaje ROS
            data = json.loads(msg.data)

            # 2. Actualizar grafo (usando tu lógica)
            self.logic.update_graph(
                numero_mascara=data['id'],
                centroide_objeto=data['xyz'],
                numero_room=data['room'],
                numero_floor=data['floor'],
                embedding=data.get('emb', None)
            )

            # 3. Obtener el grafo actualizado como diccionario (para enviar por ROS)
            grafo_dict = self.logic.get_graph_dict()

            # 4. Publicar resultado
            out_msg = String()
            out_msg.data = json.dumps(grafo_dict)
            self.publisher_.publish(out_msg)

        except Exception as e:
            self.get_logger().error(f'Error procesando objeto: {e}')

    def exportar_estilo_hov(self):
        """
        Genera la estructura de carpetas idéntica a HOV original:
        output_graph/
          ├── floors/
          ├── rooms/
          └── objects/
        """
        output_dir = "output_graph"
        floors_dir = os.path.join(output_dir, "graph", "floors")
        rooms_dir = os.path.join(output_dir, "graph", "rooms")
        objects_dir = os.path.join(output_dir, "graph", "objects")

        self.get_logger().info(f"Generando estructura HOV en: {os.path.abspath(output_dir)} ...")

        # 1. Crear directorios
        os.makedirs(floors_dir, exist_ok=True)
        os.makedirs(rooms_dir, exist_ok=True)
        os.makedirs(objects_dir, exist_ok=True)

        # 2. Recorrer la jerarquía y crear archivos individuales
        for floor in self.logic.floors_dict.values():
            # --- GUARDAR PISO ---
            f_data = {
                "id": str(floor.floor_id),
                "name": floor.name,
                "rooms": [str(r.room_id) for r in floor.rooms],
                "vertices": floor.vertices.tolist() if isinstance(floor.vertices, np.ndarray) else []
            }
            with open(os.path.join(floors_dir, f"{floor.floor_id}.json"), "w") as f:
                json.dump(f_data, f, indent=4)

            for room in floor.rooms:
                # --- GUARDAR HABITACIÓN ---
                r_data = {
                    "id": str(room.room_id),
                    "floor_id": str(floor.floor_id),
                    "name": room.name,
                    "objects": [str(obj.object_id) for obj in room.objects],
                    "vertices": room.vertices.tolist() if isinstance(room.vertices, np.ndarray) else []
                }
                with open(os.path.join(rooms_dir, f"{room.room_id}.json"), "w") as f:
                    json.dump(r_data, f, indent=4)

                for obj in room.objects:
                    # --- GUARDAR OBJETO ---
                    o_data = {
                        "id": str(obj.object_id),
                        "room_id": str(room.room_id),
                        "vertices": obj.vertices.tolist() if isinstance(obj.vertices, np.ndarray) else []
                    }
                    # Si tiene embedding, lo guardamos también
                    if obj.embedding is not None:
                        # Convertimos a lista si es numpy
                        if isinstance(obj.embedding, np.ndarray):
                            o_data["embedding"] = obj.embedding.tolist()
                        else:
                            o_data["embedding"] = obj.embedding

                    with open(os.path.join(objects_dir, f"{obj.object_id}.json"), "w") as f:
                        json.dump(o_data, f, indent=4)

        self.get_logger().info("✅ Exportación completada con éxito.")


def main(args=None):
    rclpy.init(args=args)
    node = HovsgNode()

    try:
        # Bucle principal
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # AL SALIR (Ctrl+C), EJECUTAMOS LA EXPORTACIÓN
        node.exportar_estilo_hov()

        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()